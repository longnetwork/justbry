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
                Cmp('div', classes="cell")(btn := Cmp('button', classes="button is-primary mb-4")("Click")),
                Cmp('div', classes="cell")(anh := Cmp('a', classes="button is-primary mb-4")("Anchor")),                
                Cmp('div', classes="cell")(chk := Cmp('input', type="checkbox")("Checkbox")),
                Cmp('div', classes="cell")(
                    Cmp('div', classes="select")(
                        sel := Cmp('select')(
                            Cmp('option')("option1"),
                            Cmp('option')("option2"),
                        )
                    )
                ),
                
            ),
            Cmp('textarea', classes="textarea", readonly=True, rows="20",)(
                info := Cmp('text')
            )
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
    

    print(dom.render())

    
    return await dom.response()


app = Justbry(
    debug=True,
    routes=[
        Route('/', homepage)
    ],
)





