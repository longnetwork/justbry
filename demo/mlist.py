#! /usr/bin/env python3
# -*- coding: utf-8 -*-

import contextlib, asyncio, traceback


import justbry
from justbry import Justbry, Route
from justbry.dommorph import DomMorph, Cmp


dom = DomMorph(

    uls := Cmp('div', classes="container")(
        *( (ul := Cmp('ul'))(Cmp('b')(f"Lorem Ipsum {ul.id}")) for _ in range(8))
    )
)

print(dom.render())



@contextlib.asynccontextmanager
async def morphing(_app):

    task = None; log = justbry.getLogger()
    
    async def demomorphing():

        try:

            cnt = 0
            while True:
                await dom.update(); await asyncio.sleep(0.5)

                del uls[0]
                uls.add( u := Cmp('ul')( b := Cmp('b')) )
                b.add(f"Lorem Ipsum {u.id}")

                u.attrs.classes = ['has-text-primary', 'has-text-link', 'has-text-info', 'has-text-success', 'has-text-warning', 'has-text-danger'][cnt % 6]

                cnt += 1

        except Exception:
            traceback.print_exc()
    
    try:
        log.info("Start Morphing Task")
        task = asyncio.create_task(demomorphing())
        yield
    finally:
        log.info("Stop Morphing Task")
        if task:
            task.cancel(); task = None
            


app = Justbry(
    debug=True,
    routes=[
        Route('/', dom.response)
    ],

    lifespan=morphing,
)





