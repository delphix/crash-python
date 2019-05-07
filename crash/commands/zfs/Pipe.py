# -*- coding: utf-8 -*-
# vim:set shiftwidth=4 softtabstop=4 expandtab textwidth=79:

import gdb
import argparse
from typing import Callable, Any

class PipeableCommand():
    allPipeableCommands = {}

    def __init__(self, cmdname):
        PipeableCommand.allPipeableCommands[cmdname] = type(self)
        rv = self.call([])
        assert (rv is not None and rv.__iter__ is not None), "{}.call() does not return an iterable".format(type(self).__name__)

    # subclass must override
    # must be overridden by a generator, i.e. it must use `yield`
    def call(self, input):
        assert "subclass must override"

class PipeList(PipeableCommand):

    def __init__(self, arg=""):
        super(PipeList, self).__init__('list')
        try:
            parser = argparse.ArgumentParser(prog='list')
            parser.add_argument('addr', default=None)
            self.args = parser.parse_args(gdb.string_to_argv(arg))
        except:
            pass

    def walk(list, type=gdb.lookup_type('void').pointer()):
        # XXX if tree is typed, verify that it's the expected type,
        # otherwise cast?

        assert type.code == gdb.TYPE_CODE_PTR

        list_type = gdb.lookup_type('struct list').pointer()
        typed_list = list.cast(list_type)
        offset = int(typed_list.dereference()['list_offset'])
        first_node = typed_list['list_head'].address
        node = first_node['next']
        while node != first_node:
            yield gdb.Value(int(node) - offset).cast(type)
            node = node['next']

    def call(self, input):
        if len(input) == 0:
            input = [gdb.Value(int(self.args.addr, 0))]

        for listaddr in input:
            yield from PipeList.walk(listaddr, gdb.lookup_type('zfs_dbgmsg_t').pointer())

PipeList("0")

class Pipe(gdb.Command):
    """ walk list """

    def __init__(self):
        super(Pipe, self).__init__('pipe', gdb.COMMAND_DATA)

    def iterate(pipeline):
        if len(pipeline) == 1:
            yield from pipeline[0].call([])
        else:
            yield from pipeline[-1].call(Pipe.iterate(pipeline[:-1]))

    def invoke(self, argstr, from_tty):
        split_cmds = [cmd.strip().partition(' ')[0:3:2] for cmd in argstr.split('|')]
        pipeline = []
        for name, arg in split_cmds:
            pipeline.append(PipeableCommand.allPipeableCommands[name](arg))
        for o in Pipe.iterate(pipeline):
            print(o)

Pipe()

