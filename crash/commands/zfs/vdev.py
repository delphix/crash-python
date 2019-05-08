# -*- coding: utf-8 -*-
# vim:set shiftwidth=4 softtabstop=4 expandtab textwidth=79:

import gdb
from crash.commands.zfs.Pipe import PipeableCommand
from typing import Callable, Any
from crash.commands.zfs.zfs_util import enum_lookup


class Vdev(PipeableCommand):
    def __init__(self, args = ""):
        super(Vdev, self).__init__("vdev")

    def vdev_print(vdev, indent):
        vdev = vdev.cast(gdb.lookup_type('vdev_t').pointer())
        level = 0
        if "root" in str(vdev['vdev_ops']['vdev_op_type']):
            print("\t%-18s %-7s %-4s %s" % ("ADDR", "STATE", "AUX",
                    "DESCRIPTION"))
            print("\t--------------------------------------------------")

        if vdev['vdev_path'] != 0:
            print("\t%s %s %s %*s" % (hex(vdev),
                enum_lookup('vdev_state_t', vdev['vdev_state']),
                enum_lookup('vdev_aux_t', vdev['vdev_stat']['vs_aux']),
                indent, vdev['vdev_path'].string()))
        else:
            print("\t%s %s %s %*s" % (hex(vdev),
                enum_lookup('vdev_state_t', vdev['vdev_state']),
                enum_lookup('vdev_aux_t', vdev['vdev_stat']['vs_aux']),
                indent, vdev['vdev_ops']['vdev_op_type'].string()))
            level = 2

    def get_children(self, vdev):
        vdev = vdev.cast(gdb.lookup_type('vdev_t').pointer())
        for cid in range(0, vdev['vdev_children']):
            cvd = vdev['vdev_child'][cid]
            if not self.islast:
                yield cvd

    def call(self, input):
        self.indent = 10
        if self.islast:
            for vdev in input:
                Vdev.vdev_print(vdev, 0)
        else:
            for vdev in input:
                yield from self.get_children(vdev)

Vdev()
