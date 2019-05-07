# -*- coding: utf-8 -*-
# vim:set shiftwidth=4 softtabstop=4 expandtab textwidth=79:

import gdb
from crash.commands.zfs.Pipe import PipeableCommand

class Print(PipeableCommand):
    def __init__(self, arg=""):
        super().__init__('print', False)
        self.args = arg
    def call(self, input):
        for i in input:
            if i.type.code == gdb.TYPE_CODE_PTR:
                #print(i.type, hex(i))
                cmd = "(*({}){})".format(i.type, hex(i))
            else:
                cmd = "({}){}".format(i.type, hex(i))
            if self.args is not None and len(self.args) > 0:
                cmd += "." + self.args
            #print(cmd)
            yield gdb.parse_and_eval(cmd)
Print()
