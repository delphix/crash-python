# -*- coding: utf-8 -*-
# vim:set shiftwidth=4 softtabstop=4 expandtab textwidth=79:

import gdb
import argparse
from crash.commands.zfs.Pipe import PipeableCommand
from crash.commands.zfs.Pipe import Locator
from crash.commands.zfs.Pipe import PrettyPrint
from crash.commands.zfs.avl import Avl
from crash.commands.zfs.cast import Cast

class RangeTree(Locator):
    def __init__(self, arg=""):
        super().__init__('range_tree', outputType="range_tree_t*")

    def pretty_print_one(self, rt):
        print("{}: range tree of {} entries, {} bytes".format(
            rt,
            rt['rt_root']['avl_numnodes'],
            rt['rt_space']))
        for node in PipeableCommand.executePipeline([rt], [RangeSeg(), PrettyPrint()]):
            pass

    def pretty_print(self, rts):
        for rt in rts:
            self.pretty_print_one(rt)
RangeTree()

class RangeSeg(Locator):
    def __init__(self, args=""):
        super().__init__("range_seg",
                outputType="range_seg_t*",
                inputTypes={"range_tree_t*": self.range_seg_from_range_tree})

    # arg is iterable of gdb.Value of type range_seg_t*
    def pretty_print(self, segs):
        for seg in segs:
            print("    [{} {}) (length {})".format(
                hex(seg['rs_start']),
                hex(seg['rs_end']),
                hex(seg['rs_end'] - seg['rs_start'])))

    # arg is gdb.Value of type range_tree_t*
    # need to yield gdb.Value's of type range_seg_t*
    def range_seg_from_range_tree(self, rt):
        yield from PipeableCommand.executePipeline([rt['rt_root'].address],
            [Avl(), Cast('range_seg_t *')])
RangeSeg()

