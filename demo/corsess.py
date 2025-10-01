#! /usr/bin/env python3
# -*- coding: utf-8 -*-

import random, string


from justbry import Justbry, Middleware, CORSMiddleware, SessionMiddleware, RedirectResponse
from justbry.domreact import DomReact, Cmp


dom = DomReact(
    container := Cmp('div')(
    
        info := Cmp('text'),
    ),

    # onsubmit="return false;" предотвращает авто-перезагрузку браузером страницы после submit
    # form := Cmp('form')(
    form := Cmp('form', onsubmit="return false;")(
        Cmp('input', type="text", name="login", value="login"),
        Cmp('input', type="text", name="password", value="password"),

        # Браузеры после события submit автоматически перезагружают текущую страницу
        Cmp('input', type="submit", name="submit", value="submit"),  
    ),
)


async def submit(ev):
    info.attrs.literal = str(ev)
    
    await dom.update()

form.bind('submit', submit)



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

    return RedirectResponse("/page")

@app.route('/page')
async def page(request):

    if 'id' not in request.session:
        request.session['id'] = ''.join(random.choice(string.ascii_letters) for i in range(16))

    info.attrs.literal = "session_id: " + request.session['id']
    
    return await dom.response()



print(f"Routes: {app.routes}")






