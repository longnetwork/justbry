#! /usr/bin/env python3
# -*- coding: utf-8 -*-


from justbry import Justbry, Route
from justbry.domhtml import DomHtml, Cmp


@DomHtml.brython
def tasks():
    # pylint: disable=E0401
    
    from browser import aio, document, html
    from random import random

    async def task(ident):
        cnt = 0
        while True:
            cnt += 1
            
            await aio.sleep(1 + random())

            document.attach(html.B(f"{ident}: {cnt}")); document.attach(html.BR())
            print(f"{ident}: {cnt}")

    for i in range(3):
        aio.run(task("task" + str(i)))


dom = DomHtml(
    Cmp('script', type="text/python")(
        tasks()
    ),
)


print(dom.render())



app = Justbry(
    debug=True,
    routes=[
        Route('/', dom.response),
    ]
)



