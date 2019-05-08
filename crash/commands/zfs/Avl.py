# -*- coding: utf-8 -*-
# vim:set shiftwidth=4 softtabstop=4 expandtab textwidth=79:

import gdb
import argparse
from typing import Callable, Any
from crash.commands.zfs.Pipe import PipeableCommand

class Avl(PipeableCommand):
    """ walk avl tree """

    def __init__(self, arg=""):
        super().__init__('avl')

    def walk(tree):
        # XXX if tree is typed, verify that it's the expected type,
        # otherwise cast?

        avl_tree_type = gdb.lookup_type('struct avl_tree').pointer()
        typed_tree = tree.cast(avl_tree_type)
        offset = int(typed_tree.dereference()['avl_offset'])
        root = typed_tree['avl_root']
        yield from Avl.helper(root, offset)

    def helper(node, offset):
        if node == 0:
            return
        lchild = node.dereference()['avl_child'][0]
        yield from Avl.helper(lchild, offset)

        yield gdb.Value(int(node) - offset)

        rchild = node.dereference()['avl_child'][1]
        yield from Avl.helper(rchild, offset)

    def call(self, input):
        for treeaddr in input:
            yield from Avl.walk(treeaddr)

Avl()
