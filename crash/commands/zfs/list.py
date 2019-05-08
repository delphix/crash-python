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
            yield gdb.Value(int(node) - offset)
            node = node['next']

List()
