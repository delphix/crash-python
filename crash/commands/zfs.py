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

def symbol_address(symbol, typename="void"):
    type = gdb.lookup_type(typename).pointer()
    sym = gdb.lookup_global_symbol(symbol)
    if sym == None:
        sym = gdb.lookup_symbol(symbol)[0]
    if sym != None:
        return sym.value().address.cast(type)
    return None

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

class ZfsDbgmsgArg():
    ts : bool= False
    addr : bool = False
    def __init__(self, ts: bool = False, addr : bool = False):
        self.ts = ts
        self.addr = addr

class ZfsDbgmsg(gdb.Command):
    def __init__(self):
        super(ZfsDbgmsg, self).__init__("zfs_dbgmsg", gdb.COMMAND_DATA)

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
        for node in List.walk(list_addr, gdb.lookup_type('struct zfs_dbgmsg').pointer()):
            ZfsDbgmsg.print_msg(node, zda)

ZfsDbgmsg()

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

class Avl(gdb.Command):
    """ walk avl tree """

    def __init__(self):
        super(Avl, self).__init__('avl', gdb.COMMAND_DATA)

    def walk(tree, type=gdb.lookup_type('void').pointer()):
        # XXX if tree is typed, verify that it's the expected type,
        # otherwise cast?

        assert type.code == gdb.TYPE_CODE_PTR

        avl_tree_type = gdb.lookup_type('struct avl_tree').pointer()
        typed_tree = tree.cast(avl_tree_type)
        offset = int(typed_tree.dereference()['avl_offset'])
        root = typed_tree['avl_root']
        yield from Avl.helper(root, offset, type)

    def helper(node, offset, type):
        if node == 0:
            return
        lchild = node.dereference()['avl_child'][0]
        yield from Avl.helper(lchild, offset, type)

        yield gdb.Value(int(node) - offset).cast(type)

        rchild = node.dereference()['avl_child'][1]
        yield from Avl.helper(rchild, offset, type)

    def invoke(self, argstr, from_tty):
        parser = argparse.ArgumentParser(prog='avl')
        parser.add_argument('addr')
        args = parser.parse_args(gdb.string_to_argv(argstr))
        for node in Avl.walk(gdb.Value(int(args.addr, 0))):
            print(node)

Avl()
