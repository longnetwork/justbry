#! /usr/bin/env python3
# -*- coding: utf-8 -*-

import contextlib, asyncio, traceback


import justbry
from justbry import Justbry, Route
from justbry.dommorph import DomMorph, Cmp


dom = DomMorph(
    buttons := Cmp('div', classes="container")(
        *( Cmp('button', classes=button_classes)("Button") for button_classes in ('button',
                                                                                  'button is-link',
                                                                                  'button is-primary',
                                                                                  'button is-info',
                                                                                  'button is-success',
                                                                                  'button is-warning',
                                                                                  'button is-danger',) )
    ),

    boxes := Cmp('div', classes="container")(
        *( Cmp('label', classes="control")(Cmp('input', type="radio", checked=False)("Box")) for i in range(7) )
    ),

    rline := Cmp('div', classes="container")(
        Cmp('p')(
            "Lorem Ipsum Lorem Ipsum Lorem Ipsum Lorem Ipsum Lorem Ipsum"
        )
    ),

    dlist := Cmp('div', classes="container")(
        Cmp('ul')(
            Cmp('b')("Lorem Ipsum")
        )
    )
)

print(dom.render())


@contextlib.asynccontextmanager
async def morphing(_app):

    task = None; log = justbry.getLogger()
    
    async def demomorphing():

        try:

            def _btn_gen():
                while True:
                    yield from buttons  # enumerate childs
            btn_gen = _btn_gen()

            def _box_gen():
                while True:
                    yield from boxes   # enumerate childs
            box_gen = _box_gen()

            cnt = 0
            
            while True:

                btn = next(btn_gen)
                classes = btn.attrs.classes.split(' ')
                if "is-dark" not in classes:
                    classes.append("is-dark")
                else:
                    classes.remove("is-dark")
                btn.attrs.classes = ' '.join(classes)

                    
                box = next(box_gen)
                input_type = box[0].attrs.type
                if input_type == "radio": input_type = "checkbox"
                elif input_type == "checkbox": input_type = "radio"
                box[0].attrs.type = input_type
                box[0].attrs.checked = not box[0].attrs.checked

                
                rline_literal = rline[0][0].attrs.literal
                rline_literal = rline_literal[-1] + rline_literal[:-1]

                if cnt % 4 == 0: rline[0] = Cmp('b')(rline_literal)
                if cnt % 8 == 0: rline[0] = Cmp('i')(rline_literal)
                if cnt % 12 == 0: rline[0] = Cmp('s')(rline_literal)
                if cnt % 16 == 0: rline[0] = Cmp('p')(rline_literal)
                    
                rline[0][0].attrs.literal = rline_literal


                if (cnt // 8) % 2 == 0:
                    dlist[0].insert(0, Cmp('li')(f"-{cnt & 7} Lorem Ipsum"))
                    # dlist[0].insert(0, Cmp('li')(f"- Lorem Ipsum"))
                    
                    dlist[0].append(Cmp('li')(f"+{cnt & 7} Lorem Ipsum"))
                    # dlist[0].append(Cmp('li')(f"+ Lorem Ipsum"))
                    
                else:
                    del dlist[0][0]
                    del dlist[0][-1]
                
                
                await dom.update(); await asyncio.sleep(0.5)

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





