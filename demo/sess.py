#! /usr/bin/env python3
# -*- coding: utf-8 -*-

import random, string


from justbry import Justbry, Route, Middleware, SessionMiddleware
from justbry.domhtml import DomHtml, Cmp



dom = DomHtml(
    Cmp('div', classes="container")(
    
        info := Cmp('text'),
    ),
)

async def homepage(request):

    if 'id' not in request.session:
        request.session['id'] = ''.join(random.choice(string.ascii_letters) for i in range(16))


    info.attrs.literal = "session_id: " + request.session['id']

    print(dom.render())

    
    return await dom.response()


app = Justbry(
    debug = True,

    middleware = [
        Middleware(SessionMiddleware, secret_key=..., max_age=60 * 60 * 24 * 365, same_site='lax', https_only=False)
    ],
    
    routes = [
        Route('/', homepage)
    ],
)

# app.add_middleware(SessionMiddleware, secret_key=..., max_age=60*60*24*365, same_site='lax', https_only=False);  # max_age=None - до закрытия браузера





