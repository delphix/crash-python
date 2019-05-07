# -*- coding: utf-8 -*-
# vim:set shiftwidth=4 softtabstop=4 expandtab textwidth=79:

import gdb
import argparse
from typing import Callable, Any
from crash.commands.zfs.Pipe import PipeableCommand

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

class Cast(PipeableCommand):
    """ walk list """

    def __init__(self, arg=""):
        super().__init__('cast')

        try:
            parser = argparse.ArgumentParser(prog='cast')
            parser.add_argument('cast_type', default=['void', '*'], nargs='*')
            self.args = parser.parse_args(gdb.string_to_argv(arg))
        except:
            pass

        self.args.cast_type = parse_type(' '.join(self.args.cast_type))


    def call(self, input):
        for listaddr in input:
            yield listaddr.cast(self.args.cast_type)

Cast()
