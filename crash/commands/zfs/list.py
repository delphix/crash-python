# -*- coding: utf-8 -*-
# vim:set shiftwidth=4 softtabstop=4 expandtab textwidth=79:

import gdb
import argparse
from typing import Callable, Any
from crash.commands.zfs.Pipe import AbstractContainer

class List(AbstractContainer):
    """ walk list """

    def __init__(self, arg=""):
        super().__init__('list', inputType='list_t*')

    def walk(self, list):
        offset = int(list['list_offset'])
        first_node = list['list_head'].address
        node = first_node['next']
        while node != first_node:
            yield gdb.Value(int(node) - offset).cast(gdb.lookup_type('void').pointer())
            node = node['next']

List()

class LinuxList(AbstractContainer):
    """ walk linux list_head """

    def __init__(self, arg=""):
        super().__init__('linux_list', inputType='struct list_head *')
        parser = argparse.ArgumentParser(description = "walk a linux list")
        parser.add_argument('offset', default=0, type=int, nargs='?', help='offset of list_head in structure')
        self.args = parser.parse_args(gdb.string_to_argv(arg))

    def walk(self, llist):
        node = llist['next']
        while node != llist:
            yield gdb.Value(int(node) - self.args.offset).cast(gdb.lookup_type('void').pointer())
            node = node['next']
LinuxList()
