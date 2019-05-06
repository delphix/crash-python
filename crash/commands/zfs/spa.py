# -*- coding: utf-8 -*-
# vim:set shiftwidth=4 softtabstop=4 expandtab textwidth=79:

import gdb
import argparse
from typing import Callable, Any
from .zfs_util import symbol_address
from .Avl import Avl

class Spa(gdb.Command):
    def __init__(self):
        super(Spa, self).__init__("spa", gdb.COMMAND_DATA)

    def print_spa(spa):
        print("{:14} {}".format(hex(spa), spa['spa_name'].string()))

    def invoke(self, arg, from_tty):
        print("{:14} {}".format("ADDR", "NAME"))
        print("----------------------------------------")
        for spa in Avl.walk(symbol_address("spa_namespace_avl"), gdb.lookup_type('struct spa').pointer()):
            Spa.print_spa(spa)
	
Spa()

