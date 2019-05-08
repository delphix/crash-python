# -*- coding: utf-8 -*-
# vim:set shiftwidth=4 softtabstop=4 expandtab textwidth=79:

import gdb
import argparse
from crash.commands.zfs.Pipe import PipeableCommand
from crash.commands.zfs.avl import Avl
from crash.commands.zfs.cast import Cast

class RangeTree(PipeableCommand):
    def __init__(self, arg=""):
        super().__init__('range_tree', inputType="range_tree_t*")

    def walk(self, rt):
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
        for i in input:
            yield from self.walk(i)

RangeTree()

