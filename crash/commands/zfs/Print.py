# -*- coding: utf-8 -*-
# vim:set shiftwidth=4 softtabstop=4 expandtab textwidth=79:

import gdb
from crash.commands.zfs.Pipe import PipeableCommand

class Print(PipeableCommand):
    def __init__(self, arg=""):
        super(Print, self).__init__('print')
    def call(self, input):
        for i in input:
            print(i.type, i)
            yield gdb.parse_and_eval("*({}){}".format(i.type, i))
Print()

