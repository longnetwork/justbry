#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
    DOM с биндингом событий передаваемых на сторону сервера
"""


from .dommorph import DomMorph, Cmp

from . import ReactEndpoint


class DomReact(DomMorph):
    """
        Поддержка react по средствам ajax (сокеты - для морфинга, ajax - для событий)
    """

    # glock = asyncio.Lock()
                  
    reactendpoint = ReactEndpoint;  # Один маршрут с параметром на все dom

    
    def __init__(self, /, *body_components, static="/", version=None):
        super().__init__(*body_components, static=static, version=version)


        baseroute = self.reactendpoint.reactroute.rsplit('/', 1)[0] or "/evt"
        
        self.reactroute = baseroute + '/' + str(self.dom_id)


        self.head.add(
            Cmp('script', type="text/python", id='react')(    # XXX id это имя модуля доступного через import и не может содержать '-'
                type(self).react(),                           # Может быть перегружен в наследника как статический метод
            ),
            
            eventers := Cmp('script', type="text/python", id='eventers')  # Контейнер для всех скриптов DomReact.eventer()           
        )

        self.eventers = eventers

        self.handlers = {};  # {target_id: [handler, ...]}


    async def response(self, request=None):
        self.reactendpoint.doms[self.dom_id] = self
        return await super().response(request)



    @DomMorph.brython
    @staticmethod
    def react():
        """ Модуль извлечения информации о событии и отправки на сервер """
        # pylint: disable=E0401,W0611,W0612
        
        from browser import document, window, ajax;   # noqa
        from morpher import compress

        event_props_black_list = {
            'baseURI',
            'namespaceURI',
            'innerHTML',
            'innerText',
            'outerHTML',
            'outerText',
            'textContent',
            'formAction',
            'valueAsNumber',
        }
        
        def event_to_dict(ev):
            tt = ev.target
            
            result = {}
            
            for k in dir(ev):
                if k in event_props_black_list: continue
                if isinstance(k, str) and k.isupper(): continue
                v = getattr(ev, k, None)
                if not isinstance(v, (str, bool, int, float)): continue
                
                result[k] = v
            
            target = result['target'] = {}
            for k in dir(tt):
                if k in event_props_black_list: continue
                if isinstance(k, str) and k.isupper(): continue
                v = getattr(tt, k, None)
                if not isinstance(v, (str, bool, int, float)): continue
                
                target[k] = v

            return result


        def send_event(EVENTROUTE, ev):
            compress(repr(event_to_dict(ev))).then( lambda data: ajax.put(EVENTROUTE, data=data) )
            

    @DomMorph.brython
    @staticmethod
    def eventer(ID=None, EVENTTYPE='onload', EVENTROUTE="/"):
        """ Фронт-энд скрипт привязывающийся к компоненту единственное назначение которого - это слать событие на сервер """
        from react import document, send_event;  # pylint: disable=E0401
        if (el := document.getElementById(str(ID))): el.addEventListener(EVENTTYPE, lambda ev: send_event(EVENTROUTE, ev))


    def bind(self, cmp: Cmp, evtype, handler: "server-side"):  # pylint: disable=W0221
        """
            cmp обязан быть в структуре dom и иметь id.
        """

        assert cmp._get_dom() is self

        self.eventers.add(
            type(self).eventer(cmp.id, evtype, self.reactroute)
        )
        handlers = self.handlers.setdefault(str(cmp.id), [])
        handlers.append(handler)



