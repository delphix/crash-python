# -*- coding: utf-8 -*-
# vim:set shiftwidth=4 softtabstop=4 expandtab textwidth=79:

import gdb
import argparse
from .List import List

class MultiList(gdb.Command):
    """ walk multilist """

    def __init__(self):
        super(MultiList, self).__init__('multilist', gdb.COMMAND_DATA)

    def walk(multilist, type=gdb.lookup_type('void').pointer()):
        # XXX if tree is typed, verify that it's the expected type,
        # otherwise cast?

        assert type.code == gdb.TYPE_CODE_PTR

        list_type = gdb.lookup_type('struct multilist').pointer()
        typed_list = multilist.cast(list_type)
        num_sublists = typed_list['ml_num_sublists']
        sublists = typed_list['ml_sublists']

        for i in range(num_sublists):
            sublist = sublists[i]['mls_list'].address
            for node in List.walk(sublist, type):
                yield node

    def invoke(self, argstr, from_tty):
        parser = argparse.ArgumentParser(prog='multilist')
        parser.add_argument('addr')
        args = parser.parse_args(gdb.string_to_argv(argstr))
        for node in MultiList.walk(gdb.Value(int(args.addr, 0))):
            print(node)

MultiList()

