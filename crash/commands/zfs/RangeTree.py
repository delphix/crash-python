# -*- coding: utf-8 -*-
# vim:set shiftwidth=4 softtabstop=4 expandtab textwidth=79:

import gdb
import argparse
from crash.commands.zfs.Pipe import PipeableCommand
from crash.commands.zfs.Avl import Avl
from crash.commands.zfs.cast import Cast

class RangeTree(PipeableCommand):
    def __init__(self, arg=""):
        super().__init__('range_tree')

    def walk(self, treeaddr):
        rt = treeaddr.cast(gdb.lookup_type('range_tree_t').pointer())
        if self.islast:
            print("{}: range tree of {} entries, {} bytes".format(
                rt,
                rt['rt_root']['avl_numnodes'],
                rt['rt_space']))
        for node in PipeableCommand.executePipeline([rt['rt_root'].address],
                [Avl(), Cast('range_seg_t *')]):
            if self.islast:
                print("    [{} {}) (length {})".format(
                    hex(node['rs_start']),
                    hex(node['rs_end']),
                    hex(node['rs_end'] - node['rs_start'])))
            else:
                yield node

    def call(self, input):
        for treeaddr in input:
            yield from self.walk(treeaddr)

RangeTree()

