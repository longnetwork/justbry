#! /usr/bin/env python3
# -*- coding: utf-8 -*-


from justbry import Justbry, Route
from justbry.domreact import DomReact, Cmp


async def homepage(request):
    """
        Не расшаренный dom
    """

    @DomReact.brython
    def emitter_scripts():
        # pylint: disable=E0401
        
        from javascript import JSON
        from browser import document, window

        def emit_data(payload=None):
            """
                Передатчик фронт-енд данных через механизм react.
                В бак-енде:
                  - внедряется: Cmp('script', type='application/json', name='emitter', data_payload=...)
                  - и биндится: self.emitter.bind('change', self.emit_data)
                Во фронт-енде юзается по месту emit_data(...)
            """
            if (emitter := document.select_one("[name='emitter']")):
                emitter.attrs['data-payload'] = JSON.stringify(payload)
                emitter.dispatchEvent(window.Event.new('change'))


        # Демо передачи данных при клике на 'emit-button'
        if (btn := document.select_one("button[name='emit-button']")):
            btn.bind('click', lambda _ev: emit_data({
                'timestamp': (now := window.Date.new()).getTime() / 1000,
                'tzoffset': now.getTimezoneOffset() * 60,
                'language': window.navigator.language,
            }))

    
    dom = DomReact(
        Cmp('div', classes="box")(
            Cmp('div', classes="grid")(
                Cmp('div', classes="cell")(btn := Cmp('button', classes="button is-primary mb-4", data_payload='payload')("Click")),
                Cmp('div', classes="cell")(anh := Cmp('a', classes="button is-primary mb-4", data_payload='payload')("Anchor")),                
                Cmp('div', classes="cell")(chk := Cmp('input', type="checkbox", data_payload='payload')("Checkbox")),
                Cmp('div', classes="cell")(
                    Cmp('div', classes="select")(
                        sel := Cmp('select', data_payload='payload')(
                            Cmp('option')("option1"),
                            Cmp('option')("option2"),
                        )
                    )
                ),
                Cmp('div', classes="cell")(inp := Cmp('input', type="input", classes="input", placeholder="Text", data_payload=True)),
                Cmp('div', classes="cell")(kbd := Cmp('input', type="input", classes="input", placeholder="Keys", data_payload=True)),
            ),

            Cmp('div', classes="box")(
                frm := Cmp('form', onsubmit="return false;", data_payload='payload', name='form')(
                    Cmp('div', classes="field")(Cmp('input', type="input", classes="input", name="login")),
                    Cmp('div', classes="field")(Cmp('input', type="input", classes="input", name="passw")),

                    Cmp('div', classes="field is-grouped")(
                        Cmp('p', classes="control is-expanded")(
                            Cmp('input', classes="button input", type="file", name="file", multiple=True)
                        ),
                        Cmp('p', classes="control")(
                            Cmp('input', type="submit", classes="button", name="submit")
                        ),
                    )
                )
            ),

            
            txt := Cmp('textarea', classes="textarea", readonly=True, rows="20",)(
                info := Cmp('text')
            ),

            Cmp('div', classes="level")(
                Cmp('div', classes="level-left")(Cmp('div', classes="level-item")(
                    crl := Cmp('button', classes="button is-primary m-4", data_payload='payload')("Clear"),
                )),
                Cmp('div', classes="level-right")(Cmp('div', classes="level-item")(
                    Cmp('button', name='emit-button', classes="button is-primary m-4", data_payload='payload')("Emit")
                ))
            )
            
        ),

        emitter := Cmp('script', type='application/json', name='emitter', data_payload=...),  # Эмиттер внешних данных через симулированное событие change

        Cmp('script', type='text/python')(
            emitter_scripts(),  # Внедрение необходимых фронт-енд скриптов
        )
    )


    async def update_info(req):
        # info.attrs.literal = str(req.event)
        txt.dirty(value=str(req.event))
        
        await dom.update()

    # dom.bind(btn, 'click', update_info)
    # dom.bind(anh, 'click', update_info)
    # dom.bind(chk, 'click', update_info)
    # dom.bind(sel, 'click', update_info)

    btn.bind('click', update_info)
    anh.bind('click', update_info)
    chk.bind('click', update_info)
    sel.bind('click', update_info)

    inp.bind('input', update_info)
    kbd.bind('keypress', update_info)
    
    # frm.bind('mouseover', update_info)
    
    frm.bind('submit', update_info)

    async def clear_info(_req):

        # info.attrs.literal = "Cleared"
        txt.dirty(value="Cleared")

        await dom.update()

    crl.bind('click', clear_info)


    async def emit_data(req):
        target = req.event.get('currentTarget', {})
        data_payload = target.get('data-payload', '');  # Возможно json.loads(data_payload)
        
        info.attrs.literal = data_payload
        # txt.dirty(value=data_payload)

        await dom.update()

    emitter.bind('change', emit_data)

    
    print(dom.render())

    
    return await dom.response()


app = Justbry(
    debug=True,
    routes=[
        Route('/', homepage)
    ],
)


print(f"Routes: {app.routes}")


