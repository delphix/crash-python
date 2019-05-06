# -*- coding: utf-8 -*-
# vim:set shiftwidth=4 softtabstop=4 expandtab textwidth=79:

import gdb
import argparse
from typing import Callable, Any

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
