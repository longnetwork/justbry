#! /usr/bin/env python3
# -*- coding: utf-8 -*-


from justbry import Justbry, Route
from justbry.domreact import DomReact, Cmp



@DomReact.brython
def resizer():
    """
        Библиотека:
            import resizer; resizer.bind(...)

        Основано на: https://phuoc.ng/collection/html-dom/create-resizable-split-views/
    """
    # pylint: disable=E0401,W0612
    
    from browser import document
    

    def bind(splitter_id, direction: "h | v"):

        direction = direction.lower()[0]; assert direction in "hv"

        
        splitter = document.getElementById(splitter_id)
        before_side = splitter.previousElementSibling
        after_side = splitter.nextElementSibling

        x, y = 0, 0

        before_width, before_height = 0, 0

        def mouse_move_handler(ev):            
            dx, dy = ev.clientX - x, ev.clientY - y

            match direction:
                case 'h':
                    before_side.style.width = f"{((before_width + dx) * 100) / splitter.parentNode.getBoundingClientRect().width}%"
                    document.body.style.cursor = 'col-resize'
                case 'v':
                    before_side.style.height = f"{((before_height + dy) * 100) / splitter.parentNode.getBoundingClientRect().height}%"
                    document.body.style.cursor = 'row-resize'
            
            before_side.style.userSelect = 'none'
            before_side.style.pointerEvents = 'none'
            after_side.style.userSelect = 'none'
            after_side.style.pointerEvents = 'none'
            
        def mouse_up_handler(_ev):
            document.body.style.removeProperty('cursor')
            
            before_side.style.removeProperty('user-select')
            before_side.style.removeProperty('pointer-events')
            after_side.style.removeProperty('user-select')
            after_side.style.removeProperty('pointer-events')

            document.removeEventListener('mousemove', mouse_move_handler);
            document.removeEventListener('mouseup', mouse_up_handler);

            
        def mouse_down_handler(ev):
            nonlocal x, y, before_width, before_height
            
            x, y = ev.clientX, ev.clientY
            
            before_width, before_height = before_side.getBoundingClientRect().width, before_side.getBoundingClientRect().height

            document.addEventListener('mousemove', mouse_move_handler)
            document.addEventListener('mouseup', mouse_up_handler)


        splitter.addEventListener('mousedown', mouse_down_handler)



class HSplitter(Cmp):
    
    def __init__(self, divide: "initil in %" = 50, **attrs):

        if not isinstance(divide, str):
            divide = str(divide) + "%"


        classes = "is-flex is-flex-direction-row"
        if (c := attrs.get('classes')): classes += " " + c
        attrs['classes'] = classes

        style = "border: 1px solid var(--bulma-light);"
        if (s := attrs.get('style')): style += " " + s
        attrs['style'] = style


        super().__init__('div', **attrs)


        self.add(
            left := Cmp('div', classes="is-flex is-align-items-center is-justify-content-center", style=f"width: {divide};"),
            splitter := Cmp(
                'div',
                classes="is-flex has-background-light is-align-items-center",
                style="width: 16px; height: 100%; cursor: col-resize; user-select: none;",
            ),
            right := Cmp('div', classes="is-flex is-align-items-center is-justify-content-center is-flex-grow-1"),

            Cmp('script', type="text/python")(
                f"import resizer; resizer.bind({splitter.id}, 'h')"
            )
        )

        splitter.add(
            Cmp('span', classes="icon is-small")(
                Cmp('i', classes="fas fa-grip-lines-vertical fa-xs")
            )
        )

        self.left = left
        self.splitter = splitter
        self.right = right
        

class VSplitter(Cmp):
    """
        Основан на: https://phuoc.ng/collection/html-dom/create-resizable-split-views/

        fa-grip-lines
        fa-grip-lines-vertical
    """
    
    def __init__(self, divide: "initil in %" = 50, **attrs):

        if not isinstance(divide, str):
            divide = str(divide) + "%"


        classes = "is-flex is-flex-direction-column"
        if (c := attrs.get('classes')): classes += " " + c
        attrs['classes'] = classes

        style = "border: 1px solid var(--bulma-light);"
        if (s := attrs.get('style')): style += " " + s
        attrs['style'] = style


        super().__init__('div', **attrs)


        self.add(
            top := Cmp('div', classes="is-flex is-justify-content-center is-align-items-center", style=f"height: {divide};"),
            splitter := Cmp(
                'div',
                classes="is-flex has-background-light is-justify-content-center",
                style="width: 100%; height: 16px; cursor: row-resize; user-select: none;",
            ),
            bottom := Cmp('div', classes="is-flex is-justify-content-center is-align-items-center is-flex-grow-1"),

            Cmp('script', type="text/python")(
                f"import resizer; resizer.bind({splitter.id}, 'v')"
            )
        )

        splitter.add(
            Cmp('span', classes="icon is-small")(
                Cmp('i', classes="fas fa-grip-lines fa-xs")
            )
        )

        self.top = top
        self.splitter = splitter
        self.bottom = bottom



async def homepage(request):

    dom = DomReact(
        h := HSplitter(divide = 75, style = "height: 14rem; width: 100%;"),
        v := VSplitter(divide = 25, style = "height: 14rem; width: 100%;"),
        s := HSplitter(divide = 25, style = "height: 28rem; width: 100%;"),
    )
    h.left.add("Left"); h.right.add("Right")
    v.top.add("Top"); v.bottom.add("Bottom")

    s.left.add("Left");
    s.right.add(v := VSplitter(divide = 25, style = "height: 100%; width: 100%;")); v.top.add("Top"); v.bottom.add("Bottom")


    dom.head.add(
        Cmp('script', type="text/python", id='resizer')(  # Внедрение библиотеки скриптов
            resizer()
        )
    )


    print(dom.render())
    
    return await dom.response()


app = Justbry(
    debug=True,
    routes=[
        Route('/', homepage)
    ],
)





