# -*- coding: utf-8 -*-
# vim:set shiftwidth=4 softtabstop=4 expandtab textwidth=79:

import gdb
from crash.commands.pretty_printer import PrettyPrinter
from crash.commands.sdb import PipeableCommand, SDBCommand
from typing import Iterable, Dict, Callable, Type
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
    allLocators : Dict[str, Type['Locator']] = {}
    outputType = ''
    inputTypes : Dict[str, Callable[[Iterable[gdb.Value]], gdb.Value]] =  {}
    
    def __init__(self):
        super().__init__()
        # We unset the inputType here so that the pipeline doesn't add a
        # coerce before us and ruin our ability to dispatch based on multiple
        # input types. For pure locators, an inputType wouldn't be set, but
        # hybrid Locators and PrettyPrinters will set an inputType so that
        # PrettyPrint can dispatch to them. By unsetting the inputType in the
        # instance, after registration is complete, PrettyPrint continues to
        # work, and the pipeline logic doesn't see an inputType to coerce to.
        self.inputType = None

    @staticmethod
    def registerCmd(c : Type[SDBCommand]) -> None:
        assert issubclass(c, Locator), '{} not instance of Locator'.format(c)
        assert c.outputType != ''
        Locator.allLocators[c.outputType] = c

    # subclass may override this
    def noInput(self):
        raise TypeError('command "{}" requires an input'.format(
            self.cmdName))

    # Dispatch to the appropriate instance function based on the type of the
    # input we receive.
    def caller(self, input : Iterable[gdb.Value]) -> gdb.Value:
        baked = [ (parse_type(k), f) for k, f in self.inputTypes.items() ]
        out_type = parse_type(self.outputType)
        hasInput = False
        for i in input:
            hasInput = True

            # try subclass-specified input types first, so that they can override any other behavior
            try:
                for t, f in baked:
                    if i.type == t:
                        yield from f(i)
                        raise StopIteration
            except StopIteration:
                continue

            # try passthrough of output type
            # note, this may also be handled by subclass-specified input types
            if i.type == out_type:
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
            raise TypeError('command "{}" does not handle input of type {}'.format(
                self.cmdName,
                i.type))
        if not hasInput:
            yield from self.noInput()

    def call(self, input : Iterable[gdb.Value]) -> gdb.Value:
        # If this is a hybrid locator/pretty printer, this is where that is leveraged.
        if self.islast and isinstance(self, PrettyPrinter):
            self.pretty_print(self.caller(input))
        else:
            yield from self.caller(input)
