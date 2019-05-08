# -*- coding: utf-8 -*-
# vim:set shiftwidth=4 softtabstop=4 expandtab textwidth=79:

import gdb
from elftools.elf.elffile import ELFFile
from elftools.elf.sections import SymbolTableSection

#
# XXX: check that all that needs to run with sudo
#

#
# In order to calculate the KASLR offset in Linux we compare the
# offset of _stext in the running systems (through /proc/kallsyms)
# and vmlinux (the kernel binary).
# 
# _stext is used to set the initial stack pointer for the kernel
# and call the necessary functions to set up a minimal C runtime
# for the kernel. We chose it because it's been there "forever"
# it's architecture independent, and its value doesn't change
# once the kernel is running.
#
def CalculateKASLROffset(vmlinux):
    print("Calculating KASLR Offset...")
    vmlinux_offset = -1
    with open(vmlinux, 'rb') as f:
        elf = ELFFile(f)
        section = elf.get_section_by_name('.symtab')

        #
        # TODO: This loop takes around 30 seconds on my computer which
        # makes startup painful. This is a problem of Python's elftools.
        # There also exists the section.get_symbol_by_name() method
        # which is actually worse, because it doesn't stop once the
        # symbol name is found.
        #
        vmlinux_stext = None
        for sym in section.iter_symbols():
            if sym.name == "_stext":
                vmlinux_stext = sym
                break
        assert vmlinux_stext != None, "_stext not found in vmlinux"
        vmlinux_offset = vmlinux_stext['st_value']
        del elf

    kallsyms_offset = -1
    with open("/proc/kallsyms", 'r') as f:
        for line in f:
            if line.strip().endswith("_stext"):
                kallsyms_offset = int(line.split()[0], 16)
    assert kallsyms_offset != -1, "_stext not found in /proc/kallsyms"

    print("KASLR offset: ", hex(kallsyms_offset - vmlinux_offset))
    return kallsyms_offset - vmlinux_offset

def LoadVmlinux(vmlinux):
    kaslr_offset = CalculateKASLROffset(vmlinux)
    result = gdb.execute("add-symbol-file {} -o {:#x}"
                         .format(vmlinux, kaslr_offset),
                         to_string=True)
    print(result)
