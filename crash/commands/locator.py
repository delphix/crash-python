# -*- coding: utf-8 -*-
# vim:set shiftwidth=4 softtabstop=4 expandtab textwidth=79:

import gdb
from crash.commands.pretty_printer import PrettyPrinter
from crash.commands.sdb import PipeableCommand
from typing import Iterable, Dict, Callable
from crash.commands.zfs.zfs_util import parse_type
from crash.commands.walk import Walk

#
# A Locator is a command that locates objects of a given type.  Subclasses
# declare that they produce a given outputType (the type being located), and
# they provide a method for each input type that they can search for objects
# of this type.  Additionally, many locators are also PrettyPrinters, and can
# pretty print the things they find. There is some logic here to support that
# workflow.
#
class Locator(PipeableCommand):
    allLocators : Dict[str, type] = {}

    def __init__(self):
        super().__init__()
        self.inputType = None

    def registerCmd(c):
        Locator.allLocators[c.outputType] = c

    # subclass may override this
    def noInput(self):
        raise TypeError('command "{}" requires an input'.format(
            self.cmdName))

    def caller(self, input : Iterable[gdb.Value]) -> gdb.Value:
        baked = [ (parse_type(k).strip_typedefs().unqualified(), f) for k, f in self.inputTypes.items() ]
        out_type = parse_type(self.outputType)
        hasInput = False
        for i in input:
            i_type = i.type.strip_typedefs().unqualified()
            hasInput = True

            # try subclass-specified input types first, so that they can override any other behavior
            try:
                for t, f in baked:
                    if i_type == t:
                        yield from f(i)
                        raise StopIteration
            except StopIteration:
                continue

            # try passthrough of output type
            # note, this may also be handled by subclass-specified input types
            if i_type == out_type:
                yield i
                continue

            # try walkers
            try:
                for o in Walk().call([i]):
                    o.cast(out_type)
                    yield o
                continue
            except TypeError:
                pass

            # error
            raise TypeError('command "{}" does not handle input of type {} (base type {})'.format(
                self.cmdName,
                i.type,
                i_type))
        if not hasInput:
            yield from self.noInput()

    def call(self, input : Iterable[gdb.Value]) -> gdb.Value:
        # If this is a hybrid locator/pretty printer, this is where that is leveraged.
        if self.islast and isinstance(self, PrettyPrinter):
            self.pretty_print(self.caller(input))
        else:
            yield from self.caller(input)
