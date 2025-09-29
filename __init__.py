# -*- coding: utf-8 -*-
"""
    Модуль justbry как надстройка над starlette и точка импорта системных классов
"""

import re, weakref, gzip, base64, inspect, logging
from ast import literal_eval
import asyncio

import warnings

from starlette.applications import Starlette

from starlette.middleware import Middleware
from starlette.middleware.cors import CORSMiddleware;                      # noqa
from starlette.middleware.sessions import SessionMiddleware;               # noqa
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.authentication import AuthenticationMiddleware;  # noqa

from starlette.authentication import (                                     # noqa
    AuthCredentials, AuthenticationBackend, AuthenticationError, SimpleUser,
)

from starlette.staticfiles import StaticFiles as _StaticFiles

from starlette.routing import (                                            # noqa
    Route, WebSocketRoute, Mount, Host,
)

from starlette.responses import (                                          # noqa
    Response, HTMLResponse, PlainTextResponse, JSONResponse, RedirectResponse,
    StreamingResponse, FileResponse, 
)

from starlette.endpoints import (
    HTTPEndpoint, WebSocketEndpoint, 
)

from starlette.background import BackgroundTask, BackgroundTasks;          # noqa


from .utils import getLogger as _getLogger

def getLogger():
    return _getLogger('uvicorn')


class VersionMiddleware(BaseHTTPMiddleware):
    """
        Чтобы заставить браузеры перегружать кешируемые модули импорта
        ( Как альтернатива прямого задания разных каталогов в `pythonpath: ['py_v=...']` при вызове brython() )

        Мы просто убиваем из имени каталога статических файлов py суффикс _v=... чтобы файлы обнаруживались в каталоге
        без этого суффикса
    """
    async def dispatch(self, request, call_next):
        
        raw_path = request.scope.get('raw_path')
        path = request.scope.get('path')
        
        if raw_path:
            request.scope['raw_path'] = re.sub(br'_v=.+?/', b'/', raw_path, count=1)
        if path:
            request.scope['path'] = re.sub(r'_v=.+?/', '/', path, count=1)
            
        return await call_next(request)


class StaticFiles(_StaticFiles):
    """
        Добавляет в поиск пакетный static (static по умолчанию)
    """
    staticroute = "/"
    name = "static"
    
    def __init__(self, *, directory=None, packages=None, html=False, check_dir=True, follow_symlink=False):
        packages = packages or []
        if ('justbry', 'static') not in packages:
            packages.append(('justbry', 'static'))

        directory = directory or "static"

        super().__init__(directory=directory, packages=packages, check_dir=False)

        self.config_checked = True;  # Чтобы для запуска демок не приходилось создавать пустую директорию static



class MorphEndpoint(WebSocketEndpoint):
    """
        Сокет один но обслуживает маршрут /dom/id(dom)

        websocket close codes:
            1000 CLOSE_NORMAL
            1001 CLOSE_GOING_AWAY (EndpointUnavailable)
            1002 CLOSE_PROTOCOL_ERROR
            1003 CLOSE_UNSUPPORTED (InvalidMessageType)
            1004 Reserved
            1005 CLOSED_NO_STATUS (Empty)
            1006 CLOSE_ABNORMAL
            1007 Unsupported payload (InvalidPayloadData)
            1008 Policy violation
            1009 CLOSE_TOO_LARGE (MessageTooBig)
            1010 Mandatory extension
            1011 Server error (InternalServerError)
            1012 Service restart
            1013 Try again later
            1014 Bad gateway
            1015 TLS handshake fail

            TODO Помним про безопасность, чтобы не слать от сервера данные не предназначенные другим сессиям
    """
    encoding = "text";  # FIXME brython на стороне браузера работает только со строками

    morphroute = "/dom/{dom_id}"

        
    doms = {};  # {str(id(dom)): dom, ...} удерживает dom пока не будут закрыты все сокеты
    
    async def on_connect(self, websocket):
        await websocket.accept()
        dom_id = str(websocket.path_params.get('dom_id'))
        if dom_id not in self.doms:
            await websocket.close(1008, "unknown dom_id")
                
    async def on_receive(self, websocket, data):
        if data == '_ping_':
            await websocket.send_text('_pong_');                        # Это преимущественно исходящий сокет
            return

        if not isinstance(data, str):
            await websocket.close(1003, "unsupported data")
            return
            
        if data.isdigit():                                            # morphhash
            dom =  self.doms.get(str(websocket.path_params.get('dom_id')))
            if not dom:
                await websocket.close(1008, "unknown dom_id")
                return
                
            async with dom.alock:
                morphhash = int(data)
                if morphhash in dom.responses:
                    body = dom.responses[morphhash][0]
                    dom.morphsockets[websocket] = (body, morphhash);  # Теперь dom может сам себя обновлять на стороне браузера
                    
                    # await websocket.send_text(data);                # _pong_
                    return

        await websocket.close(1008, "unknown morphhash")
                                                                      

    async def on_disconnect(self, websocket, close_code):
        
        dom_id = str(websocket.path_params.get('dom_id'))
        dom =  self.doms.get(dom_id)
        if not dom:
            if (log := getLogger()): log.warning("unknown dom")
            return
            
        async with dom.alock:
            
            _, morphhash = dom.morphsockets.pop(websocket, (None, None))

            # if close_code == 1001:
            if True:
                # Вкладка/браузер закрыли - подчистка ресурсов если morphhash больше не юзается
                # FIXME Избежать пробегания в цикле при использовании weakref на websocket 
                if not any( m == morphhash for _, m in dom.morphsockets.values()):
                    dom.responses.pop(morphhash, None)
                    if (log := getLogger()): log.info(f"Clean responses: {morphhash=}")
                    if not dom.responses:
                        self.doms.pop(dom_id, None)
                        if (log := getLogger()): log.info(f"Clean dom: {dom_id=}")


class ReactEndpoint(HTTPEndpoint):
    """
        TODO Помним про безопасность, чтобы не слать от сервера данные не предназначенные другим сессиям
    """

    reactroute = "/evt/{dom_id}"

    doms = weakref.WeakValueDictionary();  # {str(id(dom)): dom, ...} Будет удерживаться пока есть в MorphEndpoint.doms
    
    async def post(self, request):  # XXX put не безопасный для CORS
        dom =  self.doms.get(str(request.path_params.get('dom_id')))
        if not dom:
            return Response(status_code=404);                         # Not Found 
            
        try:

            request_body = await request.body();  # Строка base64 сжатых байт

            if request_body == b'_ping_':
                return Response(b'_pong_', status_code=202)


            data = gzip.decompress( base64.b64decode(request_body) )

            if (log := getLogger()): log.debug(f"event: {data}")
            
            event = literal_eval(data.decode('utf-8'))

            fromid = str(event.get('fromid'))

            handlers = dom.handlers.get(fromid)
            if not handlers: return Response(status_code=422);        # Unprocessable Entity 

            event_type = event['type']

            exc = None
            for evtype, handler in handlers:                          # [ (evtype, handler), ... ]
                if evtype == event_type:
                    try:
                        # handler может быть обычной функцией, либо async-функцией, - тогда handler(event) создаст awaitable-объект
                        # lambda возвращающая coroutine также допустима
                        # XXX handlers исполняются в пределах одного dom в порядке назначения
                        # FIXME Подумать над оптимизациями связанными с назначениями многих ReactEndpoint вместо одного на всех
                        #       
                        ret = handler(event)
                        if asyncio.iscoroutine(ret):
                            await ret
                            
                    except Exception as e:
                        if (log := getLogger()): log.exception(e)
                        exc = e
                
            if not exc:
                return Response(status_code=202);          # Accepted 
            else:
                return Response(status_code=500);                     # Internal Server Error
            
        except Exception as e:
            if (log := getLogger()): log.exception(e)
            return Response(status_code=406);                         # Not Acceptable 
            
            

class Justbry(Starlette):

    def __init__(self, debug=False,
                 routes=None,
                 middleware=None,
                 exception_handlers=None,
                 on_startup=None, on_shutdown=None, lifespan=None):


        middleware = middleware or []

        if not any(issubclass(m.cls, VersionMiddleware) for m in middleware):
            middleware.insert(0, (Middleware(VersionMiddleware)))


        routes = routes or []
        
        if not any(isinstance(r, Mount) and isinstance(r.app, StaticFiles) for r in routes):
            routes.append(Mount(StaticFiles.staticroute, StaticFiles(), name=StaticFiles.name))


        if not any(isinstance(r, WebSocketRoute) and inspect.isclass(r.app) and issubclass(r.app, MorphEndpoint) for r in routes):
            # Порядок имеет значение из-за assert-проверок в маршрутах на тип протокола и тип метода запроса
            routes.insert(0, WebSocketRoute(MorphEndpoint.morphroute, MorphEndpoint))

        if not any(isinstance(r, Route) and inspect.isclass(r.app) and issubclass(r.app, ReactEndpoint) for r in routes):
            # Порядок имеет значение из-за assert-проверок в маршрутах на тип протокола и тип метода запроса
            routes.insert(0, Route(ReactEndpoint.reactroute, ReactEndpoint))

        if debug:
            if (log := getLogger()): log.setLevel(logging.DEBUG)


        super().__init__(debug=debug,
                         routes=routes,
                         middleware=middleware,
                         exception_handlers=exception_handlers,
                         on_startup=on_startup, on_shutdown=on_shutdown, lifespan=lifespan)


    # Это перегруженные методы и декораторы Starlette app для автоматизации правильного порядка вставки маршрутов
    
    def add_route(self, *args, **kwargs):
        super().add_route(*args, **kwargs)
        route = self.router.routes.pop(-1); self.router.routes.insert(2, route)
        
    def add_websocket_route(self, *args, **kwargs):
        super().add_websocket_route(*args, **kwargs)
        route = self.router.routes.pop(-1); self.router.routes.insert(2, route)

    def route(self, path, methods = None, name = None, include_in_schema = True):
        warnings.warn(
            "The `route` decorator is deprecated, and will be removed in version 1.0.0. "
            "Refer to https://www.starlette.io/routing/ for the recommended approach.",
            DeprecationWarning,
        )

        def decorator(func):
            self.add_route(
                path,
                func,
                methods=methods,
                name=name,
                include_in_schema=include_in_schema,
            )
            return func

        return decorator

    def websocket_route(self, path, name = None):
        warnings.warn(
            "The `websocket_route` decorator is deprecated, and will be removed in version 1.0.0. "
            "Refer to https://www.starlette.io/routing/#websocket-routing for the recommended approach.",
            DeprecationWarning,
        )

        def decorator(func):
            self.add_websocket_route(path, func, name=name)
            return func

        return decorator








