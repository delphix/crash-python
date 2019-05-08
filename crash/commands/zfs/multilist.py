# -*- coding: utf-8 -*-
# vim:set shiftwidth=4 softtabstop=4 expandtab textwidth=79:

import gdb
import argparse
from crash.commands.zfs.list import List
from crash.commands.zfs.Pipe import AbstractContainer

class MultiList(AbstractContainer):
    """ walk multilist """

    def __init__(self):
        super().__init__('multilist', inputType="multilist_t*")

    def walk(self, multilist):
        num_sublists = multilist['ml_num_sublists']
        sublists = multilist['ml_sublists']

        for i in range(num_sublists):
            sublist = sublists[i]['mls_list'].address
            yield from PipeableCommand.executePipeline([sublist], [List()])

MultiList()
