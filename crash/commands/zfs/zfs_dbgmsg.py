# -*- coding: utf-8 -*-
# vim:set shiftwidth=4 softtabstop=4 expandtab textwidth=79:

import gdb
from typing import Callable, Any
from crash.commands.zfs.zfs_util import symbol_address
from crash.commands.zfs.List import List
from crash.commands.zfs.cast import Cast
from crash.commands.zfs.Pipe import PipeableCommand
import datetime,getopt

class ZfsDbgmsgArg():
    ts : bool= False
    addr : bool = False
    def __init__(self, ts: bool = False, addr : bool = False):
        self.ts = ts
        self.addr = addr

class ZfsDbgmsg(gdb.Command):
    def __init__(self):
        super().__init__("zfs_dbgmsg", gdb.COMMAND_DATA)

    # node is a zfs_dbgmsg_t*
    def print_msg(node : gdb.Value, arg : ZfsDbgmsgArg) -> None:
        strlen = int(node['zdm_size']) - node.type.target().sizeof
        if arg.addr:
            print("{} ".format(hex(node)), end="")
        if arg.ts:
            timestamp = datetime.datetime.fromtimestamp(int(node['zdm_timestamp']))
            print("{}: ".format(timestamp.strftime('%Y-%m-%dT%H:%M:%S')), end="")

        print("{}".format(node['zdm_msg'].string(encoding='utf-8', length=strlen)))

    def invoke(self, arg : str, from_tty : Any) -> None:
        print(arg)
        optlist, args = getopt.getopt(arg.split(), 'v')
        verbosity = 0
        if len(args) != 0:
            print("Improper arguments to ::zfs_dbgmsg: {}\n".format(args))
            return
        for (opt, arg) in optlist:
            if opt != '-v':
                print ("Improper flag to ::zfs_dbgmsg: {}\n".format(opt))
                return
            elif arg != '':
                print ("Improper value to ::zfs_dbgmsg: {}\n".format(arg))
                return
            verbosity += 1

        zda = ZfsDbgmsgArg(verbosity >= 1, verbosity >= 2)
        proc_list = symbol_address("zfs_dbgmsgs", "procfs_list_t")
        list_addr = proc_list['pl_list'].address
        for node in PipeableCommand.executePipeline([list_addr], [List(), Cast('zfs_dbgmsg_t *')]):
            ZfsDbgmsg.print_msg(node, zda)

ZfsDbgmsg()
