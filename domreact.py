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

        self.handlers = {};  # {target_id: [ (evtype, handler), ... ]}


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

        event_props_black_list = {  # FIXME Определиться с полным списком не нужного
            'baseURI',
            'namespaceURI',
            'innerHTML',
            'innerText',
            'outerHTML',
            'outerText',
            'textContent',
            'formAction',
            'action',
            'valueAsNumber',
            
            'enctype',
            'encoding',
            'method',
        }

        event_props_while_list = {
            'elements',  # HTMLFormControlsCollection
        }

        def _event_props_to_dict(el):
            res = {}
            for k in el.__dict__:
                if k.isupper(): continue
                if k in event_props_black_list: continue
                v = getattr(el, k, None)
                if not isinstance(v, (str, bool, int, float)): continue
                if v:
                    res[k] = v
                    
            return res

        def event_to_dict(ev):
            tt = ev.target
            
            result = {}

            result.update(_event_props_to_dict(ev))

            target = result['target'] = {}

            target.update(_event_props_to_dict(tt))

            for k in event_props_while_list:
                v = getattr(tt, k, None)
                if isinstance(v, (str, bool, int, float)):
                    if v:
                        target[k] = v
                else:
                    try:
                        elements = list(v);  # Список контролов в form с текущими values
                        if elements:
                            target[k] = [ _event_props_to_dict(el) for el in elements]
                    except:
                        pass
                
            return result


        def send_event(EVENTROUTE, ev):
            compress(repr(event_to_dict(ev))).then( lambda data: ajax.post(EVENTROUTE, data=data) )
            

    @DomMorph.brython
    @staticmethod
    def eventer(ID=None, EVENTTYPE='onload', EVENTROUTE="/"):
        """ Фронт-энд скрипт привязывающийся к компоненту единственное назначение которого - это слать событие на сервер """
        from react import document, send_event;  # pylint: disable=E0401
        if (el := document.getElementById(str(ID))):
            el.addEventListener(EVENTTYPE, lambda ev, id=str(ID): send_event(EVENTROUTE, ev) if ev.target.id == id else None)


    def bind(self, cmp: Cmp, evtype, handler: "server-side"):  # pylint: disable=W0221
        """
            cmp обязан быть в структуре dom и иметь id.
        """

        assert cmp._get_dom() is self

        self.eventers.add(
            type(self).eventer(cmp.id, evtype, self.reactroute)
        )
        handlers = self.handlers.setdefault(str(cmp.id), [])

        handlers.append( (evtype, handler) )



