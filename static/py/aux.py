# -*- coding: utf-8 -*-
# pylint: disable=E0401,W0123

# from ast import literal_eval

from javascript import JSON

from browser.session_storage import storage as _s

from browser.local_storage import storage as _l



def helloworld(): print("Hello World")


class GMeta(type):
    def __getattr__(cls, name): return None;  # Не существующий атрибут в G возвращает None вместо исключения
    
class G(metaclass=GMeta):                     # Глобальное Хранилище переменных в памяти
    pass

class _S:
    def __setattr__(self, name, value):
        _s[name] = JSON.stringify(value)
    def __getattribute__(self, name):
        val = _s.get(name)
        if val is None: return None
        return JSON.parse(val)
S = _S();                                     # Хранилище переменных в sessionStorage браузера

class _L:
    def __setattr__(self, name, value):
        _l[name] = JSON.stringify(value)
    def __getattribute__(self, name):
        val = _l.get(name)
        if val is None: return None
        return JSON.parse(val)
L = _L();                                     # Хранилище переменных в localStorage браузера



