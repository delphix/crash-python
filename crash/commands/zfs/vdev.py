# -*- coding: utf-8 -*-
# vim:set shiftwidth=4 softtabstop=4 expandtab textwidth=79:

import gdb
from crash.commands.zfs.Pipe import Locator
from typing import Callable, Any
from crash.commands.zfs.zfs_util import enum_lookup

class Vdev(Locator):
    def __init__(self, args = ""):
        super().__init__("vdev",
                outputType="vdev_t*",
                inputTypes={"spa_t*": self.vdevs_from_spa, "vdev_t*": self.vdevs_from_vdev})
        # XXX add flag for "direct children (from vdev) only"?
        # XXX add flag for "top level vdevs (from spa) only"?

    # arg is iterable of gdb.Value of type vdev_t*
    def print(self, vdevs):
        print("\t%-18s %-7s %-4s %s" % ("ADDR", "STATE", "AUX",
                "DESCRIPTION"))
        print("\t--------------------------------------------------")

        for vdev in vdevs:
            if vdev['vdev_path'] != 0:
                print("\t%s %s %s %s" % (hex(vdev),
                    enum_lookup('vdev_state_t', vdev['vdev_state']),
                    enum_lookup('vdev_aux_t', vdev['vdev_stat']['vs_aux']),
                    vdev['vdev_path'].string()))
            else:
                print("\t%s %s %s %s" % (hex(vdev),
                    enum_lookup('vdev_state_t', vdev['vdev_state']),
                    enum_lookup('vdev_aux_t', vdev['vdev_stat']['vs_aux']),
                    vdev['vdev_ops']['vdev_op_type'].string()))

    # arg is gdb.Value of type spa_t*
    # need to yield gdb.Value's of type vdev_t*
    def vdevs_from_spa(self, spa):
        yield spa['spa_root_vdev']
        yield from self.vdevs_from_vdev(spa['spa_root_vdev'])

    # arg is gdb.Value of type vdev_t*
    # need to yield gdb.Value's of type vdev_t*
    def vdevs_from_vdev(self, vdev):
        for cid in range(0, vdev['vdev_children']):
            cvd = vdev['vdev_child'][cid]
            yield cvd
            yield from self.vdevs_from_vdev(cvd)

    def call(self, input):
        for spa in input:
            for v in self.vdevs_from_spa(spa):
                if self.islast:
                    self.print([v])
                yield v

Vdev()
