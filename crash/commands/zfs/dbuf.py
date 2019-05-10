# -*- coding: utf-8 -*-
# vim:set shiftwidth=4 softtabstop=4 expandtab textwidth=79:

import gdb
import argparse
from crash.commands.zfs.zfs_util import symbol_address
from crash.commands.zfs.Pipe import Locator

class Dbuf(Locator):
    def __init__(self, arg=""):
        super().__init__('dbuf', outputType='dmu_buf_impl_t*')
        parser = argparse.ArgumentParser(prog='dbuf')
        parser.add_argument('-l', '--level', type=int,
                help='filter: only dbufs of this level' )
        parser.add_argument('-b', '--blkid', type=int,
                help='filter: only dbufs of this blkid' )
        parser.add_argument('-H', '--has-holds', action='store_true',
                help='filter: only dbufs that have nonzero holds' )
        try:
            self.args = parser.parse_args(gdb.string_to_argv(arg))
        except:
            pass

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

    def filter(self, db):
        if self.args.level and db['db_level'] != self.args.level:
            return False
        if self.args.blkid and db['db_blkid'] != self.args.blkid:
            return False
        if self.args.has_holds and db['db_holds']['rc_count'] == 0:
            return False
        return True

    def noInput(self):
        dbuf_hash = symbol_address("dbuf_hash_table")
        mask = dbuf_hash['hash_table_mask']
        table = dbuf_hash['hash_table']

        for i in range(0, mask):
            db = table[i]
            while db:
                if self.filter(db):
                    yield db
                db = db['db_hash_next']

Dbuf()

