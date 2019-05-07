# -*- coding: utf-8 -*-
# vim:set shiftwidth=4 softtabstop=4 expandtab textwidth=79:

import gdb
import argparse
from typing import Callable, Any
from crash.commands.zfs.Pipe import PipeableCommand

class List(PipeableCommand):
    """ walk list """

    def __init__(self, arg=""):
        super().__init__('list')

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
        for listaddr in input:
            yield from List.walk(listaddr)

    def invoke(self, argstr, from_tty):
        for node in List(argstr).call([]):
            print(node)

List()
