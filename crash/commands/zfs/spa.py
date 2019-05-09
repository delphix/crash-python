# -*- coding: utf-8 -*-
# vim:set shiftwidth=4 softtabstop=4 expandtab textwidth=79:

import gdb
import argparse
from crash.commands.zfs.Pipe import PipeableCommand
from typing import Callable, Any
from crash.commands.zfs.zfs_util import symbol_address
from crash.commands.zfs.avl import Avl
from crash.commands.zfs.cast import Cast
from crash.commands.zfs.vdev import Vdev

class Spa(PipeableCommand):
    def __init__(self, arg=""):
        super().__init__('spa', inputType="spa_t*")
        parser = argparse.ArgumentParser(description = "spa command")
        parser.add_argument('-v', '--vdevs',action='store_true',
                help='vdevs flag' )
        parser.add_argument('-m', '--metaslab',action='store_true',
                help='metaslab flag' )
        parser.add_argument('-H', '--histogram',action='store_true',
                help='histogram flag' )
        self.args = parser.parse_args(gdb.string_to_argv(arg))

    def print_spa(self, spa):
        print("{:14} {}".format(hex(spa), spa['spa_name'].string()))
        if self.args.vdevs:
            vdev = Vdev()
            vdev.args = self.args
            Vdev.vdev_print(spa['spa_root_vdev'], 0)
            for child in vdev.get_children(spa['spa_root_vdev']):
                Vdev.vdev_print(child, 10)
            print("")


    def call(self, input):
        if isinstance(input, list) and len(input) == 0:
            input = PipeableCommand.executePipeline(
                    [symbol_address("spa_namespace_avl")],
                    [Avl(), Cast('spa_t *')])
        hasInput = False
        if self.islast:
            for spa in input:
                if not hasInput:
                    print("{:14} {}".format("ADDR", "NAME"))
                    print("----------------------------------------")
                hasInput = True
                self.print_spa(spa)
        else:
            for spa in input:
                hasInput = True
                yield spa
        if not hasInput:
            yield from self.call(PipeableCommand.executePipeline(
                    [symbol_address("spa_namespace_avl")],
                    [Avl(), Cast('spa_t*')]))
            #yield from PipeableCommand.executePipeline(
            #        [symbol_address("spa_namespace_avl")],
            #        [Avl(), Spa()])

Spa()
