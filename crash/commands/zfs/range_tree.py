# -*- coding: utf-8 -*-
# vim:set shiftwidth=4 softtabstop=4 expandtab textwidth=79:

import gdb
import argparse
from crash.commands.sdb import registerSDBCommand, SDBCommand
from crash.commands.locator import Locator
from crash.commands.pretty_printer import PrettyPrinter, PrettyPrint
from crash.commands.zfs.avl import Avl
from crash.commands.zfs.cast import Cast

class RangeTree(PrettyPrinter):
    cmdName = 'range_tree'
    inputType = 'range_tree_t *'
    def __init__(self, arg=""):
        super().__init__()

    def pretty_print(self, rt):
        print("{}: range tree of {} entries, {} bytes".format(
            rt,
            rt['rt_root']['avl_numnodes'],
            rt['rt_space']))
        SDBCommand.executePipelineTerm([rt], [RangeSeg(), PrettyPrint()])

registerSDBCommand(RangeTree)

class RangeSeg(Locator, PrettyPrinter):
    cmdName = 'range_seg'
    inputType = 'range_seg_t *'
    outputType = 'range_seg_t *'

    def __init__(self, args=""):
        super().__init__()
        self.inputTypes = {'range_tree_t *': self.range_seg_from_range_tree}

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
        yield from SDBCommand.executePipeline([rt['rt_root'].address],
            [Avl(), Cast('range_seg_t *')])

registerSDBCommand(RangeSeg)

