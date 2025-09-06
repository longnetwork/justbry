#! /usr/bin/env python3
# -*- coding: utf-8 -*-

import time

from justbry import Justbry, Route
from justbry.domhtml import DomHtml, Cmp


def helloworld1():
    # pylint: disable=E0401
    
    import aux;  # импорт в браузере запросом к StaticFiles
    aux.helloworld()

@DomHtml.brython
def helloworld2(cnt=2):
    # pylint: disable=E0401
    
    import aux;  # импорт в браузере запросом к StaticFiles
    for _ in range(cnt):
        aux.helloworld()


dom = DomHtml(
    " - Hello World - - Hello World - ",
    """
         - Hello World - 
         - Hello World - 
    """,
    Cmp('script', type="text/python")("""
        print("Hello World")
        print("Hello World")
    """),
    Cmp('script', type="text/python")(
        lambda cnt=2: [ print("Hello World") for _ in range(cnt) ]
    ),
    Cmp('script', type="text/python")(
        helloworld1,
        helloworld1
    ),
    Cmp('script', type="text/python")(
        helloworld2()
    ),


    # ~ Cmp('div', id='interpreter_id', contenteditable=True, classes="content"),
    
    # ~ Cmp('script', type="text/python")("""
        # ~ from interpreter import Interpreter
        
        # ~ Interpreter('interpreter_id', title="Brython", globals=None, locals=None, rows=30, cols=120, default_css=True)
    # ~ """),

    
    version = time.time(),  # В место этого может быть hash от всех значимых файлов в static/

    
)

print(dom.render())



app = Justbry(
    debug=True,
    routes=[
        Route('/', dom.response)
    ]
)



