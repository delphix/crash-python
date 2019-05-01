# -*- coding: utf-8 -*-
# vim:set shiftwidth=4 softtabstop=4 expandtab textwidth=79:

import gdb

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
