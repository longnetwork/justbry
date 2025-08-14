#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import asyncio, logging


def memoized(func):
    """
        Декоратор константного кеша
    """
    
    memory = {}

    if asyncio.iscoroutinefunction(func):
        async def wrap(*args, **kwargs):
            if (key := hash(repr(( *args, *sorted(kwargs.items()) )))) not in memory:
                memory[key] = await func(*args, **kwargs)
            return memory[key]            
    else:
        def wrap(*args, **kwargs):
            if (key := hash(repr(( *args, *sorted(kwargs.items()) )))) not in memory:
                memory[key] = func(*args, **kwargs)
            return memory[key]
        
    wrap.__name__ = func.__name__
    return wrap


def lrucache(size, clear=lambda: False):
    """
        LRU кэш с предикатом полной очистки clear
        
        Прореживание кеша при заполнение - до половины `size` (`size` - желательная степень двойки)

        XXX popitem() начиная с версии 3.7 удаляет не случайный ключ а всегда последний, поэтому его
            нельзя использовать так как начиная с версии 3.7 словари упорядочены в порядке добавления ключей
    """
    
    assert size >= 0; assert callable(clear)

    
    def decor(func):

        cache = {}
        
        if asyncio.iscoroutinefunction(func):
            async def wrap(*args, **kwargs):

                if clear(): cache.clear()

                if (key := hash(repr(( *args, *sorted(kwargs.items()) )))) not in cache:
                    if len(cache) >= size:  # Прореживание    
                        half = dict(list(cache.keys())[0: 1 + size // 2]); cache.clear(); cache.update(half)
                    
                    cache[key] = await func(*args, **kwargs)
                
                return cache[key]            

        else:
            def wrap(*args, **kwargs):

                if clear(): cache.clear()

                if (key := hash(repr(( *args, *sorted(kwargs.items()) )))) not in cache:
                    if len(cache) >= size:  # Прореживание    
                        half = dict(list(cache.keys())[0: 1 + size // 2]); cache.clear(); cache.update(half)
                    
                    cache[key] = func(*args, **kwargs)
                
                return cache[key]
                    
        wrap.__name__ = func.__name__
        return wrap

    return decor    

def find_slice(inlist, subslice) -> "position or -1":
    for idx in range(len(inlist) - len(subslice) + 1):
        if inlist[idx: idx + len(subslice)] == subslice:
            return idx
    return -1




def getLogger(name):
    if name in logging.root.manager.loggerDict:  # pylint: disable=E1101
        logger = logging.getLogger(name)
        if logger.hasHandlers():
            return logger
        else:
            return None
    else:
        return None









    
