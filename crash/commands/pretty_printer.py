# -*- coding: utf-8 -*-
# vim:set shiftwidth=4 softtabstop=4 expandtab textwidth=79:

from crash.commands.sdb import SDBCommand,registerSDBCommand
from crash.commands.zfs.zfs_util import parse_type
from typing import Dict, Iterable, Type
import gdb

#
# Commands that are designed to format a specific type of data.
#
class PrettyPrinter(SDBCommand):
    allPrinters : Dict[str, Type["PrettyPrinter"]] = {}
    def __init__(self):
        super().__init__()

    @staticmethod
    def registerCmd(c : Type[SDBCommand]) -> None:
        assert c.inputType is not None
        assert issubclass(c, PrettyPrinter), '{} not instance of PrettyPrinter'.format(c)
        PrettyPrinter.allPrinters[c.inputType] = c
        
    def pretty_print(self, input : gdb.Value) -> None:
        raise NotImplementedError

    # Invoke the pretty_print function on each input, checking types as we go.
    def call(self, input : Iterable[gdb.Value]) -> None:
        t = parse_type(self.inputType)
        for i in input:
            if i.type != t:
                raise TypeError('command "{}" does not handle input of type {}'.format(
                    self.cmdName,
                    i.type))

            self.pretty_print(i)

class PrettyPrint(SDBCommand):
    cmdName = 'pp'
    def __init__(self, arg=""):
        super().__init__()

    def call(self, input : Iterable[gdb.Value]):
        baked = [ (parse_type(t), c) for t, c in PrettyPrinter.allPrinters.items() ]
        hasInput = False
        for i in input:
            hasInput = True

            try:
                for t, c in baked:
                    if i.type == t and hasattr(c, "pretty_print"):
                        c().pretty_print([i])
                        raise StopIteration
            except StopIteration:
                continue

            # error
            raise TypeError('command "{}" does not handle input of type {}'.format(
                self.cmdName,
                i.type))
        # If we got no input and we're the last thing in the pipeline, we're
        # probably the first thing in the pipeline. Print out the available
        # pretty-printers.
        if not hasInput and self.islast:
            print("The following types have pretty-printers:")
            print("\t%-20s %-20s" % ("PRINTER", "TYPE"))
            for t, c in baked:
                if hasattr(c, "pretty_print"):
                    print("\t%-20s %-20s" % (c().cmdName, t))

registerSDBCommand(PrettyPrint)
