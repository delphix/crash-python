# -*- coding: utf-8 -*-
# vim:set shiftwidth=4 softtabstop=4 expandtab textwidth=79:

import gdb
from crash.commands.sdb import registerSDBCommand
from crash.commands.sdb import PipeableCommand
from crash.commands.zfs.zfs_util import parse_type
from typing import Iterable, Dict

#
# Commands that are designed to iterate over data structures that can contain
# arbitrary data types.
#
class Walker(PipeableCommand):
    allWalkers : Dict[str, type] = {}
    def __init__(self):
        super().__init__()

    def registerCmd(c : type) -> None:
        Walker.allWalkers[c.inputType] = c

    def walk(self, input : Iterable[gdb.Value]) -> gdb.Value:
        raise NotImplementedError

    # Iterate over the inputs and call the walk command on each of them,
    # verifying the types as we go.
    def call(self, input : Iterable[gdb.Value]) -> gdb.Value:
        t = parse_type(self.inputType).strip_typedefs().unqualified()
        for i in input:
            i_type = i.type.strip_typedefs().unqualified()
            if i_type != t:
                raise TypeError('command "{}" does not handle input of type {} (base type {})'.format(
                    self.cmdName,
                    i.type,
                    i_type))

            yield from self.walk(i)

# A convenience command that will automatically dispatch to the appropriate
# walker based on the type of the input data.
class Walk(PipeableCommand):
    cmdName = 'walk'
    def __init__(self, arg=""):
        super().__init__()

    def call(self, input):
        baked = [ (parse_type(k).strip_typedefs().unqualified(), c) for k, c in Walker.allWalkers.items() ]
        hasInput = False
        for i in input:
            hasInput = True
            i_type = i.type.strip_typedefs().unqualified()

            try:
                for t, c in baked:
                    if i_type == t:
                        yield from c().walk(i)
                        raise StopIteration
            except StopIteration:
                continue

            print("The following types have walkers:")
            print("\t%-20s %-20s" % ("WALKER", "TYPE"))
            for t, c in baked:
                print("\t%-20s %-20s" % (c().cmdName, t))
            raise TypeError('no walker found for input of type {} (base type {})'.format(
                i.type,
                i_type))
        # If we got no input and we're the last thing in the pipeline, we're
        # probably the first thing in the pipeline. Print out the available
        # walkers.
        if not hasInput and self.islast:
            print("The following types have walkers:")
            print("\t%-20s %-20s" % ("WALKER", "TYPE"))
            for t, c in baked:
                print("\t%-20s %-20s" % (c().cmdName, t))

registerSDBCommand(Walk)
