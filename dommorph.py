#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
    Рендер DOM с сокетом динамического обновления
"""
# pylint: disable=W0621,W0123,W0622


import sys, asyncio, gzip, json, random

from time import time

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

    DOMSALT = random.randint(1, 2**64 - 1) % sys.hash_info.modulus

    THROTTLING = 3600;              # Допустимое время удержания данных зомби-рендеров (с не открытыми сокетами)

    def __init__(self, /, *body_components, static="/", version=None, **kwargs):

        super().__init__(*body_components, static=static, version=version, **kwargs)

        self.headers = {
            # 'Cache-Control': "private, no-cache, no-store, max-age=0, must-revalidate",
            # 'Pragma': "no-cache",
            # 'Expires': "0",
        }

        self.dom_id = str( (id(self) * 31 + self.DOMSALT) % sys.hash_info.modulus )

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

        self.morphsockets = {};  # {websocket: [deepcopy(self.body), morphhash, bodyhash, closetime]}
        self.responses = {};     # {morphhash: [deepcopy(self.body), HTMLResponse(self.render()), bodyhash, resptime]}

        # XXX Starlette не async обработчики запускает в threadpool автоматом (оборачивает в awaitable объект)

        self.alock = asyncio.Lock()


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

            XXX Важно структуру морфинга планировать так чтобы не было коллизий связанных с тем, что в одном
                "пакете" морфинга есть и изменение id компонента (вместе с атрибутами) а потом и его содержимого.
                Текстовые компоненты (как содержимое) желательно оборачивать в нейтральные тэги.
        """

        if cmp.tag in {Cmp.NODE_TEXT} or _cmp.tag in {Cmp.NODE_TEXT}:
            # У этих тегов нет дочерних и атрибутов. literal у них это не атрибуты а содержимое

            # Текстовая нода и их может быть много в родителе и они не имеют id, - поэтому
            # обновляем через innerHTML родителя. Для оптимизации (индивидуального обновления)
            # можно и НУЖНО оборачивать такие ноды в "нейтральные" теги (например <span>)
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

    @staticmethod
    @DomHtml.brython
    def gzip():
        """
            Стандартные модули brython zlib/gzip работают очень медленно, поэтому используем нативное api браузера
            ( базовые примеры: https://gist.github.com/Explosion-Scratch/357c2eebd8254f8ea5548b0e6ac7a61b )
        """
        # pylint: disable=E0401,W0612

        from browser import window

        (String, TextEncoder, TextDecoder,                                   # noqa
         CompressionStream, DecompressionStream,
         Response, Uint8Array,
         btoa, atob,                                                         # noqa
         js_eval) = (window.String, window.TextEncoder, window.TextDecoder,  # noqa
                     window.CompressionStream, window.DecompressionStream,
                     window.Response, window.Uint8Array,
                     window.btoa, window.atob,
                     window.eval)

        def toBase64(data: "arrayBuffer"):  # NOTE: base64 увеличивает размер данных примерно на 33%
            # apply разворачивает в кучу параметров и есть ограничение на их число (32768 == 0x8000), поэтому заменяем на чанки
            u = Uint8Array.new(data)
            return btoa(''.join([String.fromCharCode.apply(None, u.subarray(i, i + 0x8000)) for i in range(0, u.length, 0x8000)]))

        def compress(s: 'str') -> "Promise of blob":
            cs = CompressionStream.new('gzip')
            compressed_stream = Response.new(s).body.pipeThrough(cs)
            response = Response.new(compressed_stream)
            return response.blob()

        def decompress(b: 'js blob') -> "Promise of str":
            ds = DecompressionStream.new('gzip')
            decompressed_stream = b.stream().pipeThrough(ds)
            response = Response.new(decompressed_stream)
            return response.text();  # всегда utf-8
            
            


    @staticmethod
    @DomHtml.brython
    def morpher(MORPHROUTE="/", RELOAD_TIMEOUT=1.5):
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
                - преобразуемые в объекты через ast.literal_eval(repr(...)) (или json) строки

        """
        # pylint: disable=E0401,W0601,W0602

        # from ast import literal_eval
        from javascript import JSON
        from browser import console, document, window, websocket, timer
        from morpher import decompress

        if websocket.supported:  # WebSocket supported

            ws = None; morphhash = '';  # morphhash во фронт-энде в globals
            wsconnect_timer = None;     # Reconnect Time


            def morphing(data):    # Морфинг DOM
                console.time("Dom Morphing time:")

                global morphhash;  # noqa

                if not morphhash: return

                if isinstance(data, str): data = JSON.parse(data);  # FIXME literal_eval Багованный (всерает ковычки лишними escap-ами \\)

                if not data: return

                updids = [];       # Из-за возможной смены id требуется два прохода (со сменой id во втором отдельном проходе: el.id = str(id))

                for d in data:
                    match d:
                        case "outerHTML", _id, _, str() as outerHTML if _id is not None:  # outerHTML уже содержит новый id
                            el = document.getElementById(str(_id))
                            if el:
                                el.outerHTML = outerHTML

                        case "innerHTML", _id, id, str() as innerHTML if _id is not None:
                            el = document.getElementById(str(_id))
                            if el:
                                el.innerHTML = innerHTML
                            if id is not None and id != _id: updids.append( (el, id) )

                        case "attrs", _id, id, dict() as attrs if _id is not None:
                            el = document.getElementById(str(_id))
                            if el:
                                attrs = { k.replace('_', '-'): v for k, v in attrs.items() }
                                for k, v in list(el.attrs.items()):
                                    if k == 'id': continue
                                    if k not in attrs:
                                        del el.attrs[k]

                                for k, v in attrs.items():
                                    if k in {'classes', 'class', 'className'}:
                                        el.attrs['class'] = v
                                        continue

                                    if k == 'data-props':
                                        for k, v in v.items():
                                            setattr(el, k, v)
                                        continue

                                    if isinstance(v, bool):
                                        setattr(el, k, v)
                                        if v:
                                            el.attrs[k] = ""
                                        else:
                                            try: del el.attrs[k]
                                            except: pass
                                        continue

                                    el.attrs[k] = v
                                    # if k in {'value', 'href', 'src', 'action', }:  # FIXME полный список
                                    if k in {'value', }:
                                        setattr(el, k, v)
                            if id is not None and id != _id: updids.append( (el, id) )

                        case "remove", _id, _, _ if _id is not None:
                            el = document.getElementById(str(_id))
                            if el:
                                el.remove()

                        case "afterbegin", _id, id, str() as outerHTML if _id is not None:
                            el = document.getElementById(str(_id))
                            if el:
                                el.insertAdjacentHTML('afterbegin', outerHTML)
                            if id is not None and id != _id: updids.append( (el, id) )

                        case "beforeend", _id, id, str() as outerHTML if _id is not None:
                            el = document.getElementById(str(_id))
                            if el:
                                el.insertAdjacentHTML('beforeend', outerHTML)
                            if id is not None and id != _id: updids.append( (el, id) )

                # XXX Из-за возможной зависимости ids (например в списках элементов), должны работать по
                # готовым ссылкам на элементы чьи ids обновляются
                notfounds = set()
                for el, id in updids:
                    if el:
                        el.id = str(id)
                    else:
                        notfounds.add(str(id))
                if notfounds:
                    console.debug(f"Dom Morphing not Found ids: {notfounds}")

                # FIXME Когда меняются аттрибуты и id браузер не хочет корректно пересчитать стили без "пинка"
                node = document.createTextNode(""); document.body.appendChild(node); _ = document.body.offsetHeight; document.body.removeChild(node)

                console.timeEnd("Dom Morphing time:")

            def _open(ev):
                global morphhash, wsconnect_timer;  # noqa

                if not morphhash:
                    # Первичный запуск (обычная загрузка страницы)
                    # ev.srcElement.send("_ping_")
                    el = document.getElementsByName("morphhash"); el = el and el[0]
                    if el:
                        morphhash = el.content
                        ev.srcElement.send(morphhash);  # Если сервер не перезапускался то morphhash не изменился
                        
                        console.info(f"Morpher open: {morphhash=}")
                    return

                # Это крайний случай восстановления через reload страницы после критического сбоя
                # (перегрузки сервера или дропа WiFi), когда morphhash не действительный гарантировано
                console.warn(f"Morpher Restore: {morphhash=}")
                # timer.set_timeout(window.location.replace, int(RELOAD_TIMEOUT * 1000 / 3), window.location.href)
                window.location.replace(window.location.href)
                return

                
            def _close(ev):
                global morphhash, wsconnect_timer;  # noqa
                
                console.warn(f"Morpher Close: {morphhash=} with {ev.code} {ev.reason}")

                # При остановке сервера 1012, потом при попытках подключения 1006
                # 1005 - при reload браузера через кнопку
                # 1006 - при восстановлении из заморозки (freeze) вкладки

                # Наш сервер сам возвращает только:
                #  1008 - unknown dom_id / unknown morphhash (так как там уже другие хеши)
                #  1003 - unsupported data ( assertion data in socket-request)

                # Бесшовное восстановление связи на текущем morphhash кроме критических случаев,
                # которые должны выйти на перезагрузку страницы так или иначе
                if ev.code not in {1008, }:
                    morphhash = '';  # Станет из document.getElementsByName("morphhash") при _open()

                wsconnect_timer = timer.set_timeout(start_wsconnect_cycle, int(RELOAD_TIMEOUT * 1000))

            def _message(ev):
                global morphhash;  # noqa

                try:
                    if isinstance(ev.data, str):
                        if ev.data == '_pong_':                # XXX Сервер сам пингует сокеты без нашего участия
                            return

                        if ev.data.startswith('_href_'):
                            href = ev.data[6:]

                            console.info(f"Morpher Realod: {morphhash=}")
                            window.location.assign(href)
                            return
                            
                        return 
                    
                    console.debug(f"Dom Morphing size: {ev.data.size} bytes")

                    decompress(ev.data).then(morphing)

                except Exception as e:
                    console.error("Dom Morphing:", e)

            def stop_wsconnect_cycle():
                global wsconnect_timer
                if wsconnect_timer: timer.clear_timeout(wsconnect_timer); wsconnect_timer = None

            def start_wsconnect_cycle():
                """ Инициализация websocket и попытки подключения """
                global ws, wsconnect_timer

                # Очищаем старый таймер, чтобы они не накладывались друг на друга
                stop_wsconnect_cycle()

                # Если сетевой интерфейс на ПК вообще выключен, не спамим впустую, - просто планируем следующую проверку
                if hasattr(window.navigator, 'onLine') and not window.navigator.onLine:
                    console.warn(f"Morpher Down with offLine: {morphhash=}, Waiting...")
                    wsconnect_timer = timer.set_timeout(start_wsconnect_cycle, int(RELOAD_TIMEOUT * 1000))
                    return

                # Попытка создать новый WebSocket для проверки связи...
                try:
                    # Старый сокет умер, создаем абсолютно новый объект
                    ws = websocket.WebSocket(MORPHROUTE)
                    ws.bind('open', _open)
                    ws.bind('close', _close)
                    ws.bind('message', _message)
                except Exception as e:
                    console.error(f"Morpher Down with {e}: {morphhash=}, Waiting...")
                    # Если упало даже создание объекта, пробуем снова через таймаут
                    wsconnect_timer = timer.set_timeout(start_wsconnect_cycle, int(RELOAD_TIMEOUT * 1000 * 3))

            # Дополнительная страховка: если включили кабель/Wi-Fi, мгновенно пинаем реконнект, не дожидаясь таймера
            try: window.bind('online', lambda ev: start_wsconnect_cycle())
            except: pass

            # Мобильные браузере рвут соединение сокета в фоне если вкладка свернута и нужно корректно восстановить
            # связь без принудительного window.location.replace(window.location.href) в _open()
            def _visibilitychange(_ev):
                global morphhash, ws;  # noqa
                # Если пользователь развернул браузер или разблокировал экран
                if document.visibilityState == 'visible':
                    # Если сокет не существует или он НЕ в состоянии OPEN после фона, то форсируем мгновенный реконнект 
                    if not ws or ws.readyState != window.WebSocket.OPEN:
                        start_wsconnect_cycle()
                
            try: document.bind('visibilitychange', _visibilitychange);  # resume
            except: pass

            # Это необходимо что бы закрытие сокета шло до того как пойдет новый запрос при обновлении страницы
            # (Chromium подглючивает на этом месте: https://issues.chromium.org/issues/40839988)
            def _beforeunload(_ev):
                global morphhash, ws;  # noqa
                if ws and ws.readyState == window.WebSocket.OPEN: ws.close()

            try: window.bind('beforeunload', _beforeunload)
            except: pass
            

            start_wsconnect_cycle();  # Первый коннект при загрузке страницы

        else:
            console.error("Web Sockets are not supported")


    def throttling(self):
        """
            Подчистка зомби
        """
        ctime = time() - self.THROTTLING

        workers = set(m for _, m, *_ in self.morphsockets.values());             # Все для которых открыты сокеты (существующие сокеты)
        zombies = set(m for m, (*_, t) in self.responses.items() if t < ctime);  # Рендеры (morphhash), которые были уже давно
        zombies -= workers
        if zombies:
            for m in zombies: self.responses.pop(m, None)
            if (log := getLogger()): log.debug(f"Clean {len(zombies)} zombies")        

    async def response(self, _request=None):
        """
            Может быть открыта иная вкладка, иной инстанц, иная сессия, и т.д. - поэтому
            у нас много self.morphsockets но self.morphroute один уникальный для данного dom

            XXX Пока не будет self.update() body не изменится (морфинг накопительным итогом)

            self.morphsockets = {};  # {websocket: [deepcopy(self.body), morphhash, bodyhash, closetime]}
            self.responses = {};     # {morphhash: [deepcopy(self.body), HTMLResponse(self.render()), bodyhash, resptime]}

            FIXME: Лучшее место для подчистки устаревших ресурсов там где выделяются новые

        """
        async with self.alock:
            # Обязаны проверить зомби-morphhash созданные ботами без скриптов (без открытия сокетов)
            # Все для которых долго не открыты сокеты - зомби (долго закрытые из-за заморозки вкладки браузером)
            try:
                # self.throttling();  # Глобальная подчистка в MorphEndpoint

                morphhash = hash(self.body)
                # Даже если интеграции виджетов при первом рендере изменят morphhash, то это ни на что не влияет,
                # так как morphhash фиксируется для связи с сервером а фактический морфинг определяется действительными
                # изменениями в body

                if morphhash not in self.responses:
                    self.morphhash.attrs.content = str(morphhash)

                    render = self.render(); bodyhash = hash(self.body);  # self.render() может динамически изменить self.body

                    # Фактическое body после первого рендера
                    self.responses[morphhash] = [ deepcopy(self.body), render, bodyhash, time() ];

                else:
                    render = self.responses[morphhash][1];  # XXX Кешированный рендер

                return HTMLResponse(render, headers=self.headers)
                
            finally:
                self.morphendpoint.doms[self.dom_id] = self;  # Регистрация в морфинге
                

    async def update(self):
        """
            XXX:  update() холостая когда нету изменений и нужна оптимизация по hash из-за частых deepcopy при
                  обновлении из фоновых процессов, которые вынуждены предполагают что прошлый update() еще до
                  открытия сокета браузером не прошел и нужен повторный update()

                  update() из обработчиков eventers вызывается когда действительно есть обновления dom и deepcopy
                  под блокировкой оправдано с точки зрения оптимизации.

                  FIXME По тестам рекусивный hash всего лишь в 2 раза быстрее deepcopy
        """
        async with self.alock:

            if not self.morphsockets: return False

            bodyhash = hash(self.body); bodycopy = None

            # Далее работаем со снимком body в данный момент (ниже есть переключение await и self.body может меняться во вне)

            updates = []

            for socket, (_body, _, _bodyhash, closetime) in list(self.morphsockets.items()):
                # Закрытые сокеты вне работы - они либо будут очищены либо вновь открыты
                if not closetime and bodyhash != _bodyhash:   # Есть изменения dom

                    bodycopy = bodycopy or deepcopy(self.body);  # Однократная deepcopy

                    diffs = list(self.compare_dom(bodycopy, _body))
                    if diffs:
                        # Просев дубликатов
                        udiffs = []
                        for d in diffs:
                            if d not in udiffs:
                                udiffs.append(d)

                        updates.append(socket.send_bytes( gzip.compress(json.dumps(udiffs).encode()) ))

                    # morphhash менять нельзя, чтобы работала очистка self.responses при закрытии сокета
                    # То есть morphhash - это первый хешь при первой отдачи response на сторону браузера
                    # [bodycopy, morphhash, bodyhash, closetime]
                    
                    self.morphsockets[socket][0] = bodycopy; self.morphsockets[socket][2] = bodyhash;

            if updates:
                results = await asyncio.gather(*updates, return_exceptions=True)
                for e in results:
                    if isinstance(e, Exception):
                        if (log := getLogger()): log.exception(e)


            return bool(updates);  # False когда холостая отработка


    async def locate(self, href = '/'):
        async with self.alock:
            updates = []
            for socket, _ in list(self.morphsockets.items()):
                updates.append(socket.send_text( f"_href_{href}" ))

            if updates:
                results = await asyncio.gather(*updates, return_exceptions=True)
                for e in results:
                    if isinstance(e, Exception):
                        if (log := getLogger()): log.exception(e)

            return bool(updates)





