# -*- coding: utf-8 -*-
# vim:set shiftwidth=4 softtabstop=4 expandtab textwidth=79:

import gdb
import argparse
from crash.commands.zfs.List import List
from crash.commands.zfs.Pipe import PipeableCommand

class MultiList(PipeableCommand):
    """ walk multilist """

    def __init__(self):
        super().__init__('multilist')

    def walk(multilist):
        # XXX if tree is typed, verify that it's the expected type,
        # otherwise cast?

        list_type = gdb.lookup_type('struct multilist').pointer()
        typed_list = multilist.cast(list_type)
        num_sublists = typed_list['ml_num_sublists']
        sublists = typed_list['ml_sublists']

        for i in range(num_sublists):
            sublist = sublists[i]['mls_list'].address
            yield from PipeableCommand.executePipeline([sublist], [List()])

    def call(self, input):
        for listaddr in input:
            yield from MultiList.walk(listaddr)

MultiList()

