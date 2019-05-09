# -*- coding: utf-8 -*-
# vim:set shiftwidth=4 softtabstop=4 expandtab textwidth=79:

import gdb
import argparse
from crash.commands.zfs.Pipe import Locator, PipeableCommand
from typing import Callable, Any
from crash.commands.zfs.zfs_util import symbol_address
from crash.commands.zfs.avl import Avl
from crash.commands.zfs.cast import Cast
from crash.commands.zfs.vdev import Vdev
from crash.commands.zfs.metaslab import Metaslab

class Spa(Locator):
    def __init__(self, args=""):
        super().__init__('spa', outputType="spa_t*",
            inputTypes={"spa_t*": self.spa_from_spa})
        try:
            parser = argparse.ArgumentParser(description = "spa command")
            parser.add_argument('-v', '--vdevs',action='store_true',
                    help='vdevs flag' )
            parser.add_argument('-m', '--metaslab',action='store_true',
                    help='metaslab flag' )
            parser.add_argument('-H', '--histogram',action='store_true',
                    help='histogram flag' )
            self.args = parser.parse_args(gdb.string_to_argv(args))
            self.arg_string = ""
            if self.args.metaslab:
                self.arg_string += "-m"

        except:
            pass

    def pretty_print(self, spas):
        print("{:14} {}".format("ADDR", "NAME"))
        print("%s" % ('-' * 60))
        for spa in spas:
            print("{:14} {}".format(hex(spa), spa['spa_name'].string()))
            if self.args.vdevs:
                vdevs = PipeableCommand.executePipeline(
                        [spa], [Vdev()])
                Vdev(self.arg_string).pretty_print(vdevs, 5)

    def spa_from_spa(self, spa):
        yield spa

    def noInput(self):
        input = PipeableCommand.executePipeline(
                [symbol_address("spa_namespace_avl")],
                [Avl(), Cast('spa_t *')])
        for spa in input:
            yield spa

Spa()
