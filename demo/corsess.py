#! /usr/bin/env python3
# -*- coding: utf-8 -*-

import random, string


from justbry import Justbry, Middleware, CORSMiddleware, SessionMiddleware
from justbry.domhtml import DomHtml, Cmp



dom = DomHtml(
    container := Cmp('div')(
    
        info := Cmp('text'),
    ),
)

app = Justbry(
    debug = True,

    middleware = [
        Middleware(CORSMiddleware, allow_origins=["127.0.0.1:8000/"], allow_credentials=False),
                   
        Middleware(SessionMiddleware, secret_key=..., max_age=60 * 60 * 24 * 365, same_site='lax', https_only=False),  # max_age=None - до закрытия браузера
    ],
)


@app.route('/')
async def homepage(request):

    if 'id' not in request.session:
        request.session['id'] = ''.join(random.choice(string.ascii_letters) for i in range(16))

    info.attrs.literal = "session_id: " + request.session['id']
    
    return await dom.response()



