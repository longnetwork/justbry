#! /usr/bin/env python3
# -*- coding: utf-8 -*-


from justbry import Justbry, Route, HTMLResponse
from justbry.domhtml import DomHtml, Cmp


dom = DomHtml(
    # <div data-theme="dark">
    #   <h1 class="title">Bulma</h1>
    # 
    #   <p class="subtitle">
    #     Modern CSS framework based on <a href="https://bulma.io">Flexbox</a>
    #   </p>
    # 
    #   <div class="message is-success">
    #     <div class="message-body">
    #       Changes successfully saved
    #     </div>
    #   </div>
    # 
    #   <div class="field">
    #     <input class="input" type="text" placeholder="Your Name">
    #   </div>
    # 
    #   <div class="field">
    #     <div class="select">
    #       <select><option>Select dropdown</option></select>
    #     </div>
    #   </div>
    # 
    #   <div class="buttons">
    #     <a class="button is-link is-soft">Save Changes</a>
    #     <a class="button is-danger is-soft">Cancel</a>
    #   </div>
    # </div>
    
    Cmp('div', data_theme="dark")(
        Cmp('h1', classes="title")("Bulma"),
        Cmp('p',  classes='subtitle')(
            "Modern CSS framework based on", Cmp('a', href="https://bulma.io")("JustBry")
        ),
        Cmp('div', classes="message is-success")(
            Cmp('div', classes="message-body")(
                "Changes successfully saved"
            )
        ),
        Cmp('div', classes="field")(
            Cmp('input', classes="input", type="text", placeholder="Your Name")
        ),
        Cmp('div', classes="field")(
            Cmp('div', classes="select")(
                Cmp('select')(Cmp('option')("Select dropdown"))
            )
        ),
        Cmp('div', classes="buttons")(
            Cmp('a', classes="button is-link is-soft")("Save Changes"),
            Cmp('a', classes="button is-danger is-soft")("Cancel"),
        ),
        
        "Lorem Ipsum", "Lorem Ipsum",
        Cmp('text', "Lorem Ipsum"), Cmp('text', "Lorem Ipsum"),
    ),    
)


print(dom.render())


async def spa(_request):
    return HTMLResponse(dom.render())


app = Justbry(
    debug=True,
    routes=[
        Route('/', spa)
    ]
)


