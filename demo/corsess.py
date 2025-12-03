#! /usr/bin/env python3
# -*- coding: utf-8 -*-

import random, string, asyncio


from justbry import Justbry, Middleware, CORSMiddleware, SessionMiddleware, RedirectResponse
from justbry.domreact import DomReact, Cmp as _Cmp

class Cmp(_Cmp): pass

class DomView(DomReact):
    # pylint: disable=W0201,W0622
    
    @staticmethod
    def icon_text(iconame, icotext):
        return Cmp('span', classes="icon-text")(
            Cmp('span', clasess="icon")( Cmp('i', classes=iconame) ),
            icotext,
        )

    @staticmethod
    def input_field(iconname, label, type='text', placeholder='', error=''):
        cmp = Cmp('div', classes="field")(
            Cmp('label', classes="label")(label),
            Cmp('div', classes="control has-icons-left")(
                Cmp('input', classes="input", type=type, placeholder=placeholder, autocomplete="off"),
                Cmp('span', classes="icon is-small is-left")(Cmp('i', classes=iconname)),
                
            ),
            Cmp('p', name='error', classes="help is-danger")(_error := Cmp('text', error)),
        )
        cmp.error = _error;  # cmp.error.attrs.literal="text"
        return cmp        

    @staticmethod
    def button_react(iconname, label, type: "submit | button | reset" = 'button', *, form=None):
        cmp = Cmp('button', name='react-button', classes="button is-link", type=type)
        if form is not None:
            cmp.attrs.form = form
            
        cmp.add(
            Cmp('span', classes="icon is-small")(Cmp('i', classes=iconname)),
            Cmp('span')(label),        
        )
    
        return cmp

    @staticmethod
    @DomReact.brython
    def react_scripts():
        # pylint: disable=E0401
        
        from browser import document

        for b in document.select("button[name^='react-button']"):
            b.bind('click', lambda ev, btn=b: btn.classList.add("is-loading"))


    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        cls = type(self)
        
        self.body.add(
        
            Cmp('div', classes="container")(

                Cmp('div', classes="columns is-justify-content-center")(Cmp('div', classes="column is-two-fifths")(
                    Cmp('div', classes="message is-link")(
                        Cmp('div', classes="message-body")(_info := Cmp('text'))
                    )
                )),
                
                Cmp('div', classes="columns is-justify-content-center")(Cmp('div', classes="column is-two-fifths")(
                    # onsubmit="return false;" - если reload контролируем сами через await self.locate()
                    _form := Cmp('form', id='form', classes="box", onsubmit="return false;")(
                        _login := cls.input_field("fas fa-user", "Login",
                                                  type='text',
                                                  placeholder="Enter Login",
                                                  error=""),
                        _password := cls.input_field("fas fa-lock", "Password",
                                                     type='password',
                                                     placeholder="Enter Password",
                                                     error=""),
                        _button := cls.button_react("fas fa-arrow-right", "Submit", type='submit', form='form'),
                    )
                )),
            ),

            Cmp('script', type="text/python", id='spa')(  # id - имя модуля доступного через import в brython-скриптах
                cls.react_scripts(),
            ),
        )

        self.info = _info
        self.form = _form
        self.login = _login
        self.password = _password
        self.button = _button

        self.form.bind('submit', self.submit)

    async def submit(self, ev):
        login = password = ''
        for el in ev.get('currentTarget', {}).get('elements', []):
            if el.get('type') == 'text':
                login = el.get('value', '').strip()
            elif el.get('type') == 'password':
                password = el.get('value', '').strip()

        # DB Access Simulate
        
        for c in "⓵⓶⓷✌":
            self.info.attrs.literal = c
            await self.update()
            await asyncio.sleep(0.75)
        
        self.info.attrs.literal = f"login: {login}<br>password: {password}"
        self.button.dirty()
        
        await self.update()

        await asyncio.sleep(0.75)

        # await self.locate("https://github.com/longnetwork/justbry")
        await self.locate("/")

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
                   allow_origins=["*"],
                   allow_credentials=False,
                   allow_methods=["*"],
                   allow_headers=["*"]),  
    ],
)


# XXX Порядок маршрутов может иметь значение

@app.route('/')
async def web(request):
    if 'id' not in request.session:
        request.session['id'] = ''.join(random.choice(string.ascii_letters) for i in range(16))

    await asyncio.sleep(2)

    return RedirectResponse("/page")

@app.route('/page')
async def page(request):

    dom = DomView()

    print(f"morphhash={hash(dom.body)}, dom_id={dom.dom_id}")
    
    return await DomView().response(request)
 


print(f"Routes: {app.routes}")
print(f"Middlewares: {app.user_middleware}")





