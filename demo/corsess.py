#! /usr/bin/env python3
# -*- coding: utf-8 -*-

import random, string


from justbry import Justbry, Middleware, CORSMiddleware, SessionMiddleware
from justbry.domreact import DomReact, Cmp


dom = DomReact(
    container := Cmp('div')(
    
        info := Cmp('text'),
    ),

    # onsubmit="return false;" предотвращает авто-перезагрузку браузером страницы после submit
    form := Cmp('form', onsubmit="return false;")(
    # form := Cmp('form')(
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
        Middleware(CORSMiddleware, allow_origins=["127.0.0.1:8000"], allow_credentials=True),  # allow_credentials=True не совместим с allow_origins=["*"]
                   
        Middleware(SessionMiddleware, secret_key=..., max_age=60 * 60 * 24 * 365, same_site='lax', https_only=False),  # max_age=None - до закрытия браузера
    ],
)


# XXX Порядок маршрутов может иметь значение

@app.route('/')
async def home(request):

    if 'id' not in request.session:
        request.session['id'] = ''.join(random.choice(string.ascii_letters) for i in range(16))

    info.attrs.literal = "session_id: " + request.session['id']
    
    return await dom.response()



print(f"Routes: {app.routes}")






