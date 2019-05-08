# -*- coding: utf-8 -*-
# vim:set shiftwidth=4 softtabstop=4 expandtab textwidth=79:

import gdb
import argparse
from typing import Callable, Any

def symbol_address(symbol, typename="void"):
    type = gdb.lookup_type(typename).pointer()
    sym = gdb.lookup_global_symbol(symbol)
    if sym == None:
        sym = gdb.lookup_symbol(symbol)[0]
    if sym != None:
        return sym.value().address.cast(type)
    return None

def sizeof(name : str) -> int:
    typ = gdb.lookup_type(name)
    return typ.sizeof

def offsetof(name : str, field_name : str) -> int:
    typ = gdb.lookup_type(name)
    for field in typ.fields():
        if field.name != field_name:
            continue
        return field.bitpos / 8
    return -1

def enum_lookup(type, field):
    val = gdb.lookup_type(type).fields()[field].name
    return val.split('_', 2)[-1]
