# -*- coding: utf-8 -*-
# vim:set shiftwidth=4 softtabstop=4 expandtab textwidth=79:

import gdb
import argparse
from crash.commands.sdb import registerSDBCommand, SDBCommand
from crash.commands.locator import Locator
from crash.commands.pretty_printer import PrettyPrinter
from crash.commands.zfs.zfs_util import print_histogram

class Metaslab(Locator, PrettyPrinter):
    cmdName = 'metaslab'
    inputType = 'metaslab_t *'
    outputType = 'metaslab_t *'

    def __init__(self, args = ""):
        super().__init__()
        self.inputTypes = {'vdev_t *': self.metaslab_from_vdev,
                           'metaslab_t *': self.metaslab_from_metaslab}
        try:
            parser = argparse.ArgumentParser(prog='metaslab')
            parser.add_argument('-H', '--histogram',action='store_true',
                    default=False, help='histogram flag' )
            self.args = parser.parse_args(gdb.string_to_argv(args))
        except:
            pass

    def pretty_print(self, metaslabs, indent=0):
        first_time = True
        for msp in metaslabs:
            if first_time:
                print("".ljust(indent), "ADDR".ljust(22), "ID".ljust(5),
                        "OFFSET".ljust(20), "FREE".ljust(8), "FRAG".rjust(10),
                        "UCMU".rjust(10))
                print("".ljust(indent), '-' * 70)
                first_time = False

            sm = msp['ms_sm']
            print("".ljust(indent), "{0:#0{1}x}".format(int(msp), 16).ljust(22),
                    str(msp['ms_id']).ljust(5),
                    "{0:#0{1}x}".format(int(msp['ms_start']), 16).ljust(20), end='')
            if (int(msp['ms_fragmentation'] == -1)):
                print('-'.rjust(10))
            else:
                print(str(msp['ms_fragmentation']).rjust(10))
            if self.args.histogram:
                if sm != 0:
                    histogram = sm['sm_phys']['smp_histogram']
                    print_histogram(histogram, 32, sm['sm_shift'])

    def metaslab_from_metaslab(self, msp):
        yield msp

# XXX - removed because of circular dependencies when importing Vdev class
#
#    def metaslab_from_spa(self, spa):
#        vdevs = SDBCommand.executePipeline([spa], [Vdev()])
#        for vd in vdevs:
#            yield from self.metaslab_from_vdev(vd)

    def metaslab_from_vdev(self, vdev):
        for m in range(0, vdev['vdev_ms_count']):
            msp = vdev['vdev_ms'][m]
            yield msp

registerSDBCommand(Metaslab)
