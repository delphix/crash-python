# -*- coding: utf-8 -*-
# vim:set shiftwidth=4 softtabstop=4 expandtab textwidth=79:

from crash.commands.sdb import SDBCommand,registerSDBCommand
from crash.commands.zfs.zfs_util import parse_type
from typing import Dict, Iterable
import gdb

#
# Commands that are designed to format a specific type of data.
#
class PrettyPrinter(SDBCommand):
    allPrinters : Dict[str, type] = {}
    def __init__(self):
        super().__init__()

    def registerCmd(c : type) -> None:
        assert c.inputType is not None
        PrettyPrinter.allPrinters[c.inputType] = c
        
    def pretty_print(self, input : gdb.Value) -> None:
        raise NotImplementedError
        
    def call(self, input : Iterable[gdb.Value]) -> None:
        t = parse_type(self.inputType).strip_typedefs().unqualified()
        for i in input:
            i_type = i.type.strip_typedefs().unqualified()
            if i_type != t:
                raise TypeError('command "{}" does not handle input of type {} (base type {})'.format(
                    self.cmdName,
                    i.type,
                    i_type))

            self.pretty_print(i)

class PrettyPrint(SDBCommand):
    cmdName = 'pp'
    def __init__(self, arg=""):
        super().__init__()

    def call(self, input : Iterable[gdb.Value]):
        baked = [ (parse_type(t).strip_typedefs().unqualified(), c) for t, c in PrettyPrinter.allPrinters.items() ]
        hasInput = False
        for i in input:
            hasInput = True
            i_type = i.type.strip_typedefs().unqualified()

            try:
                for t, c in baked:
                    if i_type == t and hasattr(c, "pretty_print"):
#                        if not self.islast:
#                            yield i
                        c().pretty_print([i])
                        raise StopIteration
            except StopIteration:
                continue

            # error
            raise TypeError('command "{}" does not handle input of type {} (base type {})'.format(
                self.cmdName,
                i.type,
                i_type))

registerSDBCommand(PrettyPrint)
