#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
    Рендер DOM с сокетом динамического обновления
"""
# pylint: disable=W0621,W0123,W0622


import asyncio, base64, gzip

from copy import deepcopy


from .utils import find_slice

from .domhtml import DomHtml, Cmp

from . import getLogger, MorphEndpoint, HTMLResponse


class DomMorph(DomHtml):
    """
        Изменяемая часть DOM - только body
    """

    # glock = asyncio.Lock()
                  
    morphendpoint = MorphEndpoint;  # Один маршрут сокета с параметром на все dom


    def __init__(self, /, *body_components, static="/", version=None):

        super().__init__(*body_components, static=static, version=version)


        self.dom_id = str(id(self))

        baseroute = self.morphendpoint.morphroute.rsplit('/', 1)[0] or "/dom"
        
        self.morphroute = baseroute + '/' + str(self.dom_id)

        self.head.add(
            morphhash := Cmp('meta', name="morphhash", content=""),
            
            Cmp('script', type="text/python", id='morpher')(    # XXX id это имя модуля доступного через import и не может содержать '-'
            
                # type(self).gzip,                              # Утилиты компрессии доступны через import morpher
                # DomHtml.brython(type(self).gzip)(),           # Эквивалент
                type(self).gzip(),                              # Эквивалент если DomMorph.gzip отдекорирована через @DomHtml.brython
                
                type(self).morpher(MORPHROUTE=self.morphroute),  # Может быть перегружен в наследника как статический метод
            )           
        )

        self.morphhash = morphhash;  # self.morphhash.attrs.content = str(hash(self.body)) при response

        # Чтобы не апдэйтить все body а лишь изменяющуюся часть через web-socket 
        # нам нужно отдельно хранить копии того что отдано в бразуер

        self.morphsockets = {};  # {websocket: (deepcopy(self.body), morphhash)}
        self.responses = {};     # {morphhash: (deepcopy(self.body), HTMLResponse(self.render()))}

        # XXX Starlette не async обработчики запускает в threadpool автоматом (оборачивает в awaitable объект)
        
        self.alock = asyncio.Lock()


    async def response(self, _request=None):
        """
            Может быть открыта иная вкладка, иной инстанц, иная сессия, и т.д. - поэтому
            у нас много self.morphsockets но self.morphroute один уникальный для данного dom

            XXX Пока не будет self.update() body не изменится (морфинг накопительным итогом)

        """
        self.morphendpoint.doms[self.dom_id] = self

        async with self.alock:

            body = deepcopy(self.body); morphhash = hash(body)

            if morphhash not in self.responses:
                self.morphhash.attrs.content = str(morphhash)
                self.responses[morphhash] = ( body, HTMLResponse(self.render()) )
            
            return self.responses[morphhash][1];  # HTMLResponse(self.render()) XXX Кешированный рендер


    @staticmethod
    def compare_dom(cmp, _cmp) -> """
                                   ('outerHTML', _id, id, outerHTML) |
                                   ('attrs', _id, id, attrs) |
                                   ('innerHTML', _id, id, innerHTML) |
                                   ('remove', _id, None, None) |
                                   ('afterbegin', _id, id, outerHTML) |
                                   ('beforeend', _id, id, outerHTML) |
                                   """:
        """
            В порядке рендера сверху-вниз, слева-направо (генератор).
            `cmp` корень дерева в бакэнде
            `_cmp` то что уже отдано ранее на сторону фронт-энда (браузера)

            `_id` ссылается на id на стороне браузера, но в outerHTML может быть уже другой id
        """

        if cmp.tag in {Cmp.NODE_TEXT, Cmp.SCRIPT_TEXT} or _cmp.tag in {Cmp.NODE_TEXT, Cmp.SCRIPT_TEXT}:
            # У этих тегов нет дочерних и атрибутов. literal у них это не атрибуты а содержимое
            
            # Текстовая нода и их может быть много в родителе и они не имеют id, - поэтому
            # обновляем через innerHTML родителя. Для оптимизации (индивидуального обновления)
            # можно и НУЖНО оборачивать такие ноды в "нейтральные" теги (например <div> или <p>)            
            if cmp != _cmp:
                _cmp_parent_id = None
                try: _cmp_parent_id = getattr(_cmp._parent, 'id', None)
                except ReferenceError: pass
                cmp_parent_id = None
                try: cmp_parent_id = getattr(cmp._parent, 'id', None)
                except ReferenceError: pass
                cmp_parent_inner = None
                try: cmp_parent_inner = (inner := getattr(cmp._parent, 'inner', None)) and inner()
                except ReferenceError: pass

                yield 'innerHTML', _cmp_parent_id, cmp_parent_id, cmp_parent_inner

            return
        
        if cmp.tag != _cmp.tag:  # Это замена всего outerHTML данного тега (тег другой)
            yield 'outerHTML', _cmp.id, cmp.id, cmp.outer();  # ..., str
                
        else:
            # Тег не поменялся
            if cmp.literal != _cmp.literal or cmp.id != _cmp.id:
                # А атрибуты поменялись - это изменение нужно обработать отдельно на стороне браузера
                yield 'attrs', _cmp.id, cmp.id, cmp._attrs;    # ..., dict

            if len(cmp._childs) == len(_cmp._childs):
                # Дочерние структуры у тегов одинаковы и мы углубляемся по дереву childs чтобы найти точку начала различий
                for child, _child in zip(cmp._childs, _cmp._childs):
                    yield from DomMorph.compare_dom(child, _child);  
            else:
                # yield 'innerHTML', _cmp.id, cmp.id, cmp.inner();  # Этого достаточно если без оптимизации
                
                # Оптимизация обновления длинных списков возможна в парадигме:
                # - Добавление в начало;
                # - добавление в конец;
                # - удаление с концов;
                if len(cmp._childs) < len(_cmp._childs):
                    # Удаление при условии что новых не добавляется и сохраняется порядок компонентов

                    pos = find_slice(_cmp._childs, cmp._childs)
                    if pos < 0:
                        yield 'innerHTML', _cmp.id, cmp.id, cmp.inner();     # Не получается
                    else:
                        removed = _cmp._childs[: pos] + _cmp._childs[pos + len(cmp._childs):]
                        for c in removed:                                    # Удаление лишнего
                            yield 'remove', c.id, None, None
                    
                else:
                    # Расширяем дочерние компоненты сохраняя порядок следования
                    
                    pos = find_slice(cmp._childs, _cmp._childs)
                    if pos < 0:
                        yield 'innerHTML', _cmp.id, cmp.id, cmp.inner();     # Не получается
                    else:
                        afterbegin = cmp._childs[: pos]
                        beforeend = cmp._childs[pos + len(_cmp._childs):]

                        for c in reversed(afterbegin):
                            yield 'afterbegin', _cmp.id, cmp.id, c.outer()
                        for c in beforeend:
                            yield 'beforeend', _cmp.id, cmp.id, c.outer()

    @DomHtml.brython
    @staticmethod
    def gzip():
        """
            Стандартные модули brython zlib/gzip работают очень медленно, поэтому используем нативное api браузера
            ( базовые примеры: https://gist.github.com/Explosion-Scratch/357c2eebd8254f8ea5548b0e6ac7a61b )

            TODO: Когда появится фикс позволяющий отправлять bytes через browser.json, тогда слой
                  кодирования base64 можно будет исключить
                  Уже появился!
        """
        # pylint: disable=E0401,W0612


        from browser import window
        
        (String, TextEncoder, TextDecoder, 
         CompressionStream, DecompressionStream,
         Response, Uint8Array,
         btoa, atob,
         js_eval) = (window.String, window.TextEncoder, window.TextDecoder, 
                     window.CompressionStream, window.DecompressionStream,
                     window.Response, window.Uint8Array,
                     window.btoa, window.atob,
                     window.eval)


        def compress(s: 'str string') -> "Promise of base64 string":    # Сжимает примерно в два раза
            byteArray = TextEncoder.new().encode(s);  # utf-8
            cs = CompressionStream.new('gzip')
            writer = cs.writable.getWriter(); writer.write(byteArray); writer.close();
            reader = Response.new(cs.readable).arrayBuffer();  # Promise (awaitable)

            return reader.then( lambda data:  # Промис с навешанной лямбдой
                                btoa(String.fromCharCode.apply(None, Uint8Array.new(data))) )

        def decompress(b: 'base64 string') -> "Promise of str string":  # base64 увеличивает размер данных примерно на 33%
            # byteArray = Uint8Array.new([ord(c) for c in atob(b)]);  # ord ~ charCodeAt(0)
            byteArray = js_eval(f"Uint8Array.from(atob('{b}'), char => char.charCodeAt(0));");  # speed-up x6
            cs = DecompressionStream.new('gzip')
            writer = cs.writable.getWriter(); writer.write(byteArray); writer.close();
            reader = Response.new(cs.readable).arrayBuffer()

            return reader.then( lambda data:  # Промис с навешанной лямбдой
                                TextDecoder.new().decode(data) )
                                


            
    @DomHtml.brython
    @staticmethod
    def morpher(MORPHROUTE="/"):
        """
            Фронт-энд скрипт в заголовке страницы для наблюдения за изменением Dom и
            динамическим обновлением изменившейся части в реальном времени

            Инжектируется во фронт-енд через вызов, который сразу возвращает literal:
                type(self).morpher(MORPHROUTE=morphroute);  # Может быть перегружен в наследника как статический метод

            FIXME brython может только строки сокетить

            XXX Событий сокета биндить можно несколько (на строне баузера), при этом первый
                параметр в обработчиках - объект события ev:
                    ev.srcElement - указывает на открытый сокет и допустимо ev.srcElement.send("...");
                    ev.data       - Входящие строковые данные;


            Соглашение по данным в сокетах:
                - преобразуемые в объекты через ast.literal_eval(repr(...)) строки
            
        """
        # pylint: disable=E0401,W0601,W0602

        from ast import literal_eval
        
        from browser import console, document, window
        from morpher import decompress
        

        websocket = window.WebSocket.new if hasattr(window, 'WebSocket') and window.WebSocket else None

        if websocket:  # WebSocket supported
            
            ws = websocket(MORPHROUTE); morphhash = '';  # morphhash во фронт-энде в globals

            def morphing(data):  # Морфинг DOM
                global morphhash

                if not morphhash: return

                if isinstance(data, str): data = literal_eval(data);  # До 2-х раз медленнее eval но безопасней

                if not data: return
                
                for d in data:
                    match d:
                        case "outerHTML", _id, _, str(outerHTML) if _id is not None:  # outerHTML уже содержит новый id
                            el = document.getElementById(str(_id))
                            if el:
                                el.outerHTML = outerHTML
                        case "innerHTML", _id, id, str(innerHTML) if _id is not None:
                            el = document.getElementById(str(_id))
                            if el:
                                el.innerHTML = innerHTML
                                if id is not None and id != _id:
                                    el.id = str(id)
                        case "attrs", _id, id, dict(attrs) if _id is not None:
                            el = document.getElementById(str(_id))
                            if el:
                                for k, v in list(el.attrs.items()):
                                    if k == 'id': continue
                                    if k not in attrs:
                                        del el.attrs[k]
                                for k, v in attrs.items():
                                    if k in {'classes', '_class', 'class_', 'class', 'className'}:
                                        el.attrs['class'] = v
                                        continue
                                    if isinstance(v, bool):
                                        setattr(el, k, v)
                                        continue
                                    if isinstance(v, str):
                                        el.attrs[k] = v
                                        continue
                                    el.attrs[k] = v
                                if id is not None and id != _id:
                                    el.id = str(id)
                        case "remove", _id, _, _ if _id is not None:
                            el = document.getElementById(str(_id))
                            if el:
                                el.remove()
                        case "afterbegin", _id, id, str(outerHTML) if _id is not None:
                            el = document.getElementById(str(_id))
                            if el:
                                el.insertAdjacentHTML('afterbegin', outerHTML)
                                if id is not None and id != _id:
                                    el.id = str(id)
                        case "beforeend", _id, id, str(outerHTML) if _id is not None:
                            el = document.getElementById(str(_id))
                            if el:
                                el.insertAdjacentHTML('beforeend', outerHTML)
                                if id is not None and id != _id:
                                    el.id = str(id)                


            def _open(ev):
                global morphhash;  # Этот код при инжекции во фронт-энд попадает как глобальный код (без строки декларации функции)
                
                # ev.srcElement.send("ping")
                el = document.getElementsByName("morphhash"); el = el and el[0]
                if el:
                    morphhash = el.content
                    ev.srcElement.send(morphhash)
                    console.info(f"Morpher open: {morphhash=}")

            def _close(_ev):
                global morphhash
                
                console.warn(f"Morpher Close: {morphhash=}")

                if morphhash:
                    # window.location.reload(True)
                    # window.location.assign(window.location.href)
                    window.location.replace(window.location.href)

            def _message(ev):
                console.debug(f"Dom Morphing size: {len(ev.data)} bytes")
                try:                    
                    if ev.data == 'pong': return
                    
                    decompress(ev.data).then(morphing)
                        

                except Exception as e:
                    console.error(f"Dom Morphing: {e}")

        
            ws.bind('open', _open)
            ws.bind('close', _close)
            ws.bind('message', _message)

            # Это необходимо что бы закрытие сокета шло до того как пойдет новый запрос при обновлении страницы
            # (Chromium подглючивает на этом месте: https://issues.chromium.org/issues/40839988)
            window.addEventListener('beforeunload', lambda ev: ws.close() if ws.readyState == window.WebSocket.OPEN else None)

        else:
            console.error("Web Sockets are not supported")



    async def update(self):

        async with self.alock:

            # update вызывается когда действительно есть обновления dom и deepcopy под блокировкой оправдано с точки зрения оптимизации
            body = deepcopy(self.body)
            
            # Далее работаем со снимком body в данный момент (ниже есть переключение await и self.body может меняться во вне)

            updates = []
            for socket, (_body, morphhash) in list(self.morphsockets.items()):
                if body != _body:   # Есть изменения dom
                    
                    diffs = list(self.compare_dom(body, _body))
                    if diffs:                        
                        updates.append(socket.send_text( base64.b64encode(gzip.compress(repr(diffs).encode())).decode() ))
                        _body = body
                    # morphhash менять нельзя, что работала очистка self.responses при закрытии сокета
                    self.morphsockets[socket] = (_body, morphhash)

            if updates:
                results = await asyncio.gather(*updates, return_exceptions=True)
                for e in results:
                    if isinstance(e, Exception):
                        if (log := getLogger()): log.exception(e)

        
