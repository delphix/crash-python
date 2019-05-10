# -*- coding: utf-8 -*-
# vim:set shiftwidth=4 softtabstop=4 expandtab textwidth=79:

import gdb
import argparse
from crash.commands.zfs.zfs_util import symbol_address
from crash.commands.zfs.Pipe import Locator

class Dbuf(Locator):
    def __init__(self, arg=""):
        super().__init__('dbuf', outputType="dmu_buf_impl_t*")

    def pretty_print(self, dbufs):
        print ("{:>20} {:>8} {:>4} {:>8} {:>5} {:>20}".format("addr",
            "object", "lvl", "blkid", "holds", "os"))
        for dbuf in dbufs:
            print ("{:>20} {:>8d} {:>4d} {:>8d} {:>5d} {:>20}".format(
                hex(dbuf),
                int(dbuf['db']['db_object']),
                int(dbuf['db_level']),
                int(dbuf['db_blkid']),
                int(dbuf['db_holds']['rc_count']),
                hex(dbuf['db_objset'])))

    def noInput(self):
        dbuf_hash = symbol_address("dbuf_hash_table")
        mask = dbuf_hash['hash_table_mask']
        table = dbuf_hash['hash_table']

        for i in range(0, mask):
            db = table[i]
            while db:
                yield db
                db = db['db_hash_next']

Dbuf()

