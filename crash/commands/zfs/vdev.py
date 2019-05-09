# -*- coding: utf-8 -*-
# vim:set shiftwidth=4 softtabstop=4 expandtab textwidth=79:

import gdb
import argparse
from crash.commands.zfs.Pipe import Locator, PipeableCommand
from typing import Callable, Any
from crash.commands.zfs.zfs_util import enum_lookup

class Vdev(Locator):
    def __init__(self, args = ""):
        super().__init__("vdev",
                outputType="vdev_t*",
                inputTypes={"spa_t *": self.vdevs_from_spa, "vdev_t*": self.vdevs_from_vdev})
        # XXX add flag for "direct children (from vdev) only"?
        # XXX add flag for "top level vdevs (from spa) only"?
        try:
            parser = argparse.ArgumentParser(description = "vdev command")
            parser.add_argument('-m', '--metaslab',action='store_true',
                    default=False, help='metaslab flag' )
            self.args = parser.parse_args(gdb.string_to_argv(args))
        except:
            pass

    # arg is iterable of gdb.Value of type vdev_t*
    def pretty_print(self, vdevs, indent=0):
        print("".ljust(indent), "ADDR".ljust(18), "STATE".ljust(7),
                "AUX".ljust(4), "DESCRIPTION")
        print("".ljust(indent), "-" * 60)

        level = 0
        for vdev in vdevs:
            if vdev['vdev_path'] != 0:
                print("".ljust(indent), hex(vdev).ljust(18),
                     enum_lookup('vdev_state_t', vdev['vdev_state']).ljust(7),
                     enum_lookup('vdev_aux_t',
                        vdev['vdev_stat']['vs_aux']).ljust(4),
                     "".ljust(level),
                     vdev['vdev_path'].string())

            else:
                print("".ljust(indent), hex(vdev).ljust(18),
                     enum_lookup('vdev_state_t', vdev['vdev_state']).ljust(7),
                     enum_lookup('vdev_aux_t',
                        vdev['vdev_stat']['vs_aux']).ljust(4),
                     "".ljust(level),
                     vdev['vdev_ops']['vdev_op_type'].string())
                level = 2
            if self.args.metaslab:
                metaslabs = PipeableCommand.executePipeline( [vdev], [Metaslab()])
                Metaslab().pretty_print(metaslabs, indent + 5)


    # arg is gdb.Value of type spa_t*
    # need to yield gdb.Value's of type vdev_t*
    def vdevs_from_spa(self, spa):
        yield from self.vdevs_from_vdev(spa['spa_root_vdev'])

    # arg is gdb.Value of type vdev_t*
    # need to yield gdb.Value's of type vdev_t*
    def vdevs_from_vdev(self, vdev):
        yield vdev
        for cid in range(0, vdev['vdev_children']):
            cvd = vdev['vdev_child'][cid]
            yield from self.vdevs_from_vdev(cvd)

Vdev()
