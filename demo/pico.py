#! /usr/bin/env python3
# -*- coding: utf-8 -*-


from justbry import Justbry, Route, HTMLResponse
from justbry.domhtml import DomHtml, Cmp


dom = DomHtml(
    Cmp('div', classes="container")(
        Cmp('h1')("PicoCSS"),
        Cmp('p')(
            "Modern CSS framework based on", Cmp('a', href="https://picocss.com/", target="_blank")("Semantic HTML")
        ),
        Cmp('blockquote', style="background-color: #CBFCE1;")(
            "Changes successfully saved"
        ),
        Cmp('form')(
            Cmp('fieldset')(
                Cmp('input', type="text", placeholder="<Your Name>"),
                Cmp('select')(Cmp('option')("Select dropdown")),
                Cmp('div', role="group")(
                    Cmp('button', aria_current="true")("Save Changes"),
                    Cmp('button', classes="secondary")("Cancel"),
                ),                
            ),
        ),
        
        "Lorem Ipsum", "<Lorem Ipsum>",
        Cmp('text', "Lorem Ipsum"), Cmp('text', "<Lorem Ipsum>"),

        Cmp('textarea')("""
            Lorem Ipsum
            <Lorem Ipsum>
        """),
    ),
)
dom.head[dom.head.childs.index(dom.css)] = Cmp('link', rel="stylesheet", href = "/pico.min.css")

print(dom.render())


async def spa(_request):
    return HTMLResponse(dom.render())


app = Justbry(
    debug=True,
    routes=[
        Route('/', spa)
    ]
)


