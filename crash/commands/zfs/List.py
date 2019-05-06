# -*- coding: utf-8 -*-
# vim:set shiftwidth=4 softtabstop=4 expandtab textwidth=79:

import gdb
import argparse
from typing import Callable, Any

class List(gdb.Command):
    """ walk list """

    def __init__(self):
        super(List, self).__init__('list', gdb.COMMAND_DATA)

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

    def invoke(self, argstr, from_tty):
        parser = argparse.ArgumentParser(prog='list')
        parser.add_argument('addr')
        args = parser.parse_args(gdb.string_to_argv(argstr))
        for node in List.walk(gdb.Value(int(args.addr, 0))):
            print(node)

List()
