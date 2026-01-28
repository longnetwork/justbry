#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
    DOM с биндингом событий передаваемых на сторону сервера
"""

from collections import deque

from .dommorph import DomMorph, Cmp

from . import ReactEndpoint


class DomReact(DomMorph):
    """
        Поддержка react по средствам ajax (сокеты - для морфинга, ajax - для событий)
    """

    # glock = asyncio.Lock()
                  
    reactendpoint = ReactEndpoint;  # Один маршрут с параметром на все dom

    
    def __init__(self, /, *body_components, static="/", version=None, **kwargs):
        super().__init__(*body_components, static=static, version=version, **kwargs)


        baseroute = self.reactendpoint.reactroute.rsplit('/', 1)[0] or "/evt"
        
        self.reactroute = baseroute + '/' + str(self.dom_id)


        self.head.add(
            Cmp('script', type="text/python", id='react')(     # XXX id это имя модуля доступного через import и не может содержать '-'
                type(self).react(EVENTROUTE=self.reactroute),  # Может быть перегружен в наследника как статический метод
            ),
            
            # eventers := Cmp('script', type="text/python", id='eventers')  # Контейнер для всех скриптов DomReact.eventer()           
        )

        self.html.add(
            eventers := Cmp('script', type="text/python", id='eventers')  # Контейнер для всех скриптов DomReact.eventer()           
        )

        self.eventers = eventers

        self.handlers = {};  # {currentTarget: [ (evtype, handler), ... ]}

        self.evque = deque(maxlen=256)

    async def response(self, request=None):
        self.reactendpoint.doms[self.dom_id] = self
        return await super().response(request)


    @staticmethod
    @DomMorph.brython
    def react(EVENTROUTE="/", EVENT_START_TIMEOUT=3, EVENT_MAX_TIMEOUT=24):
        """ Модуль извлечения информации о событии и отправки на сервер """
        # pylint: disable=E0401,W0611,W0612,W0621,W0601,R0204

        from javascript import JSON
        from browser import document, window, ajax, console, timer, DOMEvent, DOMNode
        from morpher import compress
        

        props_white_list = {  # FIXME Определиться с точным списком без не нужного
            'type', 'currentTarget',  # 'target',
            'timeStamp',
            'bubbles',
            'cancelable',
            'detail',
            'isTrusted',
            'eventPhase',
            'pointerType',

            'button',
            'clientX', 'clientY', 'pageX', 'pageY',
            'screenX', 'screenY',
            'altKey', 'ctrlKey', 'metaKey', 'shiftKey',
            'key', 'code', 'repeat', 'inputType',
            'id', 'tagName', 'name', 'className',  # 'classList',
            'value', 'checked', 'files', 'selectedIndex',
            # 'innerText', 'textContent',

            'offsetLeft', 'offsetTop',
            'offsetWidth', 'offsetHeight',

            'force', 'identifier',
            'radiusX', 'radiusY',
            'rotationAngle',
            'tiltX', 'tiltY', 'pressure',

            # 'action',
            # 'method',
            # 'encoding',
            # 'noValidate',
            
            'multiple', 'selectedOptions',

            'getBoundingClientRect', 'top', 'left', 'width', 'height',
            
            # 'validity', 'valid',
            'touches', 'changedTouches',
            # 'dataset',
            'elements',  # HTMLFormControlsCollection
        }
        
        def _props_to_dict(obj):
            res = {}
            if isinstance(obj, (DOMEvent, DOMNode)):
                for k in props_white_list:
                    v = getattr(obj, k, None)
                    if v:

                        if isinstance(v, (bool, int, float, str, bytes)):
                            res[k] = v
                            
                            continue
                            
                        if isinstance(v, (DOMEvent, DOMNode)):
                            v = _props_to_dict(v)
                            if v: res[k] = v
                            
                            continue

                        if callable(v):
                            try:
                                v = _props_to_dict(v())
                                if v: res[k] = v
                            except:
                                pass

                            continue
                            
                        # Если итерируемый объект
                        try:
                            v = list(v)
                            v = [ r for _ in v if (r := _props_to_dict(_)) ]
                            if v: res[k] = v
                        except:
                            pass

                    
            return res


        def event_to_dict(ev):
            ct = ev.currentTarget
        
            result = {}
            
            result.update(_props_to_dict(ev))

            result.setdefault('currentTarget', {}).update((a.name, a.value) for a in ct.attributes if a.name.startswith('data-'))
            
            return result

        
        def _ajax_event(data):
            """
                XXX Барузеры могут ставить ajax в очередь (например при перезапуске uvicorn с открытыми сессиями)
                    - используем алгоритм пропихивания события на сервер с прогрессирующим таймаутом
                    - используем ev.preventDefault() для предотвращения NS_BINDONG_ABORTED 
            """
            # event_url = f"{window.location.protocol}//{window.location.hostname}:{window.location.port}{EVENTROUTE}"
            event_url = EVENTROUTE

            headers = {
                'Content-Type': "text/plain;charset=UTF-8",
                'Cache-Control': "private, no-cache, no-store, max-age=0, must-revalidate",
                'Pragma': "no-cache",
                'Expires': "0",
                # 'Vary': '*',
                'Priority': "u=0",
            }

            # Могут быть повторные передачи с прогрессирующим таймаутом
            def _oncomplete(req, timeout):
                try:
                    if not req.status:
                        timeout = timeout * 2
                        if timeout <= EVENT_MAX_TIMEOUT:
                            ajax.post( event_url, headers=headers, data=data, timeout = timeout,
                                       oncomplete = lambda r, timeout=timeout: _oncomplete(r, timeout))
                finally:
                    req.abort()

            # ~ if data != "_ping_":
                # ~ # FIXME uvicorn закрывает соединение по --timeout-keep-alive и иногда первый запрос становится в pending.
                # ~ #       Для обхода - первым пихаем пинг, чтобы не ждать EVENT_START_TIMEOUT в этом случае
                # ~ ajax.post( event_url, headers=headers, data="_ping_", timeout=EVENT_START_TIMEOUT )

            ajax.post( event_url, headers=headers, data=data, timeout=EVENT_START_TIMEOUT,
                       oncomplete = lambda r, t=EVENT_START_TIMEOUT: _oncomplete(r, t) )
            
        reactCount = 0;  # Для уникальности хеша события на стороне сервера (есть также timeStamp)

        def send_event(ev):
            global reactCount
            
            # ev.preventDefault()

            # console.time("geteventprops")
            
            reactCount += 1
            
            data = event_to_dict(ev); data['reactCount'] = reactCount

            now = window.Date.new()

            data['timestamp'] = now.getTime() / 1000;         # sec
            data['tzoffset'] = now.getTimezoneOffset() * 60;  # sec
            data['language'] = window.navigator.language
            
            # console.timeEnd("geteventprops")

            console.debug(f"Send Event `{ev.type}` from id {ev.currentTarget.id} to: {EVENTROUTE}")

            # return compress(JSON.stringify(data)).then( _ajax_event );  # Promise
            # compress(JSON.stringify(data)).then( _ajax_event ); return False
            compress(JSON.stringify(data)).then( _ajax_event )

        # На всякий случай начальный пинг для принятия текущих заголовков
        _ajax_event(data="_ping_");  # Символа "_" нету в base64
        

    @staticmethod
    @DomMorph.brython
    def eventer(ID=None, EVENTTYPE='onload'):
        """ Фронт-энд скрипт привязывающийся к компоненту единственное назначение которого - это слать событие на сервер """
        from react import document, send_event;  # pylint: disable=E0401
        if (el := document.getElementById(str(ID))): el.bind(EVENTTYPE, send_event)


    def bind(self, cmp: Cmp, evtype, handler: "server-side"):  # pylint: disable=W0221
        """
            cmp обязан быть в структуре dom и иметь id.
        """

        assert cmp._get_dom() is self

        self.eventers.add(
            type(self).eventer(cmp.id, evtype)
        )
        handlers = self.handlers.setdefault(str(cmp.id), [])

        handlers.append( (evtype, handler) )



