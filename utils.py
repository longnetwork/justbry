#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import logging


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









    
