# -*- coding: utf-8 -*-
# vim:set shiftwidth=4 softtabstop=4 expandtab textwidth=79:

import gdb
import argparse
from typing import Callable, Any

#
# In terms of organization, this file is very different from the
# other files in the command/ subdirectory. It doesn't build all
# the Python abstractions created by pycrash and uses the plain
# GDB API mainly for two reasons:
#
# [1] We can reuse this file when running gdb against a userland
#     core dump from ztest.
#
# [2] We don't need to redeclare types and symbols in Python for
#     every command we write as forced by the CrashCommand model.
#     The benefits of this is that [a] development of new code
#     through `python-interactive` is easier (no need to declare
#     classes), [b] common functions like gen() and walkers can
#     be reused between commands in a straightforward manner.
#
# It is worth mentioning at this point that unlike the other
# pycrash commands, these are not prefixed with `py` (e.g.
# the Spa() class will generate `> spa`, not `> pyspa`)
#

def symbol_address(symbol):
    global_s = gdb.lookup_global_symbol(symbol)
    if global_s != None:
        return int(global_s.value().address)
    s = gdb.lookup_symbol(symbol)[0]
    if s != None:
        return int(s.value().address)
    return 0

def gen(tname, addr):
    return gdb.parse_and_eval('*({} *){}'.format(tname, hex(addr)))

def walk_avl_aux(addr, offset, cb):
    if addr == 0:
        return
    node = gen('avl_node_t', addr)
    lchild = int(node['avl_child'][0])
    rchild = int(node['avl_child'][1])
    walk_avl_aux(lchild, offset, cb)
    cb(addr - offset)
    walk_avl_aux(rchild, offset, cb)

def walk_avl(addr, cb):
    avl = gen('avl_tree_t', addr)
    root = int(avl['avl_root'])
    offset = int(avl['avl_offset'])
    walk_avl_aux(root, offset, cb)

class Spa(gdb.Command):
    def __init__(self):
        super(Spa, self).__init__("spa", gdb.COMMAND_DATA)

    def print_spa(addr):
        spa = gen('spa_t', addr)
        print("{:14} {}".format(hex(addr), spa['spa_name'].string()))

    def invoke(self, arg, from_tty):
        print("{:14} {}".format("ADDR", "NAME"))
        print("----------------------------------------")
        walk_avl(symbol_address("spa_namespace_avl"), Spa.print_spa)
Spa()

import datetime,getopt

def sizeof(name : str) -> int:
    typ = gdb.lookup_type(name)
    return typ.sizeof

def offsetof(name : str, field_name : str) -> int:
    typ = gdb.lookup_type(name)
    for field in typ.fields():
        if field.name != field_name:
            continue
        return field.bitpos / 8
    return -1

def walk_list(addr: int, cb : Callable[[int, Any], None], arg : Any) -> None:
    lis = gen('list_t', addr)
    head = int(lis['list_head']['next'])
    offset = int(lis['list_offset'])
    node = head
    while node != 0 and node != int(lis['list_head'].address):
        cb(node - offset, arg)
        node_fields = gen('list_node_t', node)
        node = int(node_fields['next'])

class ZfsDbgmsgArg():
    ts : bool= False
    addr : bool = False
    def __init__(self, ts: bool = False, addr : bool = False):
        self.ts = ts
        self.addr = addr

class ZfsDbgmsg(gdb.Command):
    def __init__(self):
        super(ZfsDbgmsg, self).__init__("zfs_dbgmsg", gdb.COMMAND_DATA)

    def print_msg(addr : int, arg : ZfsDbgmsgArg) -> None:
        msg = gen('zfs_dbgmsg_t', addr)
        strlen = int(msg['zdm_size']) - sizeof('zfs_dbgmsg_t')
        if arg.addr:
            print("{} ".format(hex(addr)), end="")
        if arg.ts:
            timestamp = datetime.datetime.fromtimestamp(int(msg['zdm_timestamp']))
            print("{}: ".format(timestamp.strftime('%Y-%m-%dT%H:%M:%S')), end="")

        print("{}\n".format(msg['zdm_msg'].string(encoding='utf-8', length=strlen)))

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
        proc_list = gen('procfs_list_t', symbol_address("zfs_dbgmsgs"))
        list_addr = int(proc_list['pl_list'].address)
        walk_list(list_addr, ZfsDbgmsg.print_msg, zda)

ZfsDbgmsg()

class Avl(gdb.Command):
    """ walk avl tree """

    def __init__(self):
        super(Avl, self).__init__('avl', gdb.COMMAND_DATA)

    def helper(node, offset):
        if node == 0:
            return
        lchild = node.dereference()['avl_child'][0]
        Avl.helper(lchild, offset)
        print(hex(int(node) - offset))
        rchild = node.dereference()['avl_child'][1]
        Avl.helper(rchild, offset)

    def execute(self, args):
        addr = gdb.Value(int(args.addr, 0))
        avl_tree_type = gdb.lookup_type('struct avl_tree')
        tree = addr.cast(avl_tree_type.pointer())
        offset = int(tree.dereference()['avl_offset'])
        root = tree['avl_root']
        Avl.helper(root, offset)

    def invoke(self, argstr, from_tty):
        parser = argparse.ArgumentParser(prog='avl')
        parser.add_argument('addr')
        Avl.execute(self, parser.parse_args(gdb.string_to_argv(argstr)))

Avl()
