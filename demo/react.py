#! /usr/bin/env python3
# -*- coding: utf-8 -*-


from justbry import Justbry, Route
from justbry.domreact import DomReact, Cmp


async def homepage(request):
    """
        Не расшаренный dom
    """
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
            crl := Cmp('button', classes="button is-primary mb-4", data_payload='payload')("Clear"),
            
        )
    )


    async def update_info(ev):
        info.attrs.literal = str(ev)
        
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

    async def clear_info(ev):

        txt.dirty(value="Cleared")

        await dom.update()


    crl.bind('click', clear_info)

    
    print(dom.render())

    
    return await dom.response()


app = Justbry(
    debug=True,
    routes=[
        Route('/', homepage)
    ],
)


print(f"Routes: {app.routes}")


