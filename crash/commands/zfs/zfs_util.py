# -*- coding: utf-8 -*-
# vim:set shiftwidth=4 softtabstop=4 expandtab textwidth=79:

import gdb
import argparse
import os.path
from typing import Callable, Any
from os.path import commonprefix

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


def enum_lookup(enum_type_name, value):
    """ return a string which is the short name of the enum value
    (truncating off the common prefix """
    fields = gdb.lookup_type(enum_type_name).fields()
    prefix = os.path.commonprefix([ f.name for f in fields ])
    return fields[value].name[prefix.rfind('_')+1:]

def parse_type(typestr):
    typestr = typestr.strip()
    val = None
    ptr_count = 0
    while typestr.endswith('*'):
        typestr = typestr[:-1]
        ptr_count += 1
    val = gdb.lookup_type(typestr.strip())
    while ptr_count > 0:
        ptr_count -= 1
        val = val.pointer()
    return val
