# -*- coding: utf-8 -*-
# pylint: disable=E0401,W0123

from browser.local_storage import storage


def helloworld(): print("Hello World")


class GMeta(type):
    def __getattr__(cls, name): return None;  # Не существующий атрибут в G возвращает None вместо исключения
    
class G(metaclass=GMeta):                     # Глобальное Хранилище переменных в памяти
    pass


class _S:
    
    def __setattr__(self, name, value):
        storage[name] = repr(value)
        
    def __getattribute__(self, name):
        val = storage.get(name)
        if val is None: return None
        if isinstance(val, (bool, int, float, complex, list, tuple, range, set, frozenset, dict, str, bytes, bytearray, memoryview)):
            return eval(val)

        raise TypeError("eval is not safe")
S = _S();                                     # Хранилище переменных в localStorage браузера


