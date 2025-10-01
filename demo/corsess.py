#! /usr/bin/env python3
# -*- coding: utf-8 -*-

import random, string


from justbry import Justbry, Middleware, CORSMiddleware, SessionMiddleware, RedirectResponse
from justbry.domreact import DomReact, Cmp


class DomView(DomReact):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.body.add(

            Cmp('div')(
                _info := Cmp('text'),
            ),

            # onsubmit="return false;" предотвращает авто-перезагрузку браузером страницы после submit
            _form := Cmp('form', onsubmit="return false;")(
                Cmp('input', type="text", name="login", value="login"),
                Cmp('input', type="text", name="password", value="password"),

                # Браузеры по умолчанию после события submit автоматически перезагружают текущую страницу
                Cmp('input', type="submit", name="submit", value="submit"),  
            ),
        )

        self.info = _info
        self.form = _form

        self.form.bind('submit', self.submit)

    async def submit(self, ev):
        self.info.attrs.literal = str(ev)
        
        await self.update()

    async def response(self, request=None):
        session_id = request and request.session['id']
        self.info.attrs.literal = f"session_id: {session_id}"
        
        return await super().response(request)


app = Justbry(
    debug = True,

    middleware = [
        Middleware(SessionMiddleware,
                   secret_key=...,
                   max_age=60 * 60 * 24 * 365,
                   same_site='lax', https_only=False),  # max_age=None - до закрытия браузера

        # XXX allow_credentials=True не совместим с allow_origins=["*"].
        # Если allow_credentials=True (кукисы и заголовки аутентификации разрешены), то нужно явно указать разрешенные домены
        Middleware(CORSMiddleware,
                   allow_origins=["http://127.0.0.1", "https://127.0.0.1"],
                   allow_credentials=True,
                   allow_methods=["*"],
                   allow_headers=["*"]),  
    ],
)


# XXX Порядок маршрутов может иметь значение

@app.route('/')
async def web(request):
    if 'id' not in request.session:
        request.session['id'] = ''.join(random.choice(string.ascii_letters) for i in range(16))

    return RedirectResponse("/page")

@app.route('/page')
async def page(request):
    return await DomView().response(request)
    


print(f"Routes: {app.routes}")
print(f"Middlewares: {app.user_middleware}")





