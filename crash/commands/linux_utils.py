# -*- coding: utf-8 -*-
# vim:set shiftwidth=4 softtabstop=4 expandtab textwidth=79:

from crash.commands.sdb import PipeableCommand
import gdb
from typing import Iterable
import argparse

#
# For a value declared with __percpu, ouptput a pointer to the instance of the
# value for each CPU.
#
class PerCpuMember(PipeableCommand):
    cmdName = 'perCpuMember'
    def __init__(self, arg : str = ""):
        super().__init__()
        try:
            parser = argparse.ArgumentParser(prog='perCpuMember')
            parser.add_argument('member', type=str, nargs='?')
            self.args = parser.parse_args(gdb.string_to_argv(arg))
        except:
            pass

    def nth_bit_set(bit_array : gdb.Value, n : int) -> bool:
        bits_per_long = gdb.lookup_type("unsigned long").sizeof * 8
        x = bit_array[n // bits_per_long] & (1 << (n % bits_per_long))
        return x != 0

    def call(self, input : Iterable[gdb.Value]) -> Iterable[gdb.Value]:
        nr_cpu_ids = int(gdb.lookup_symbol("nr_cpu_ids")[0].value())
        cpu_possible_mask = gdb.lookup_symbol("__cpu_possible_mask")[0].value()['bits']
        per_cpu_offset = gdb.lookup_symbol("__per_cpu_offset")[0].value()

        # List of pointers to bases of per cpu storage regions
        per_cpu_bases = []
        for cpu in range(0, nr_cpu_ids):
            if PerCpuMember.nth_bit_set(cpu_possible_mask, cpu):
                per_cpu_bases.append(per_cpu_offset[cpu])

        for x in input:
            # When using __percpu members, the value stored in the member in the struct
            # not a pointer of the type declared but an offset into per cpu storage.
            offset = int(x[self.args.member])

            dst_type = x[self.args.member].type

            for base in per_cpu_bases:
                yield (base + offset).cast(dst_type)
