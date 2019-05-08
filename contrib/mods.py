#!/usr/bin/python3
# vim:set shiftwidth=4 softtabstop=4 expandtab textwidth=79:

from crash.types.list import list_for_each_entry
import gdb
import os

def find(name, path):
    for root, dirs, files in os.walk(path):
        if name in files:
            return os.path.join(root, name)

#
# XXX: Copied from "crash/kernel.py"
#
def get_module_sections(module):
    attrs = module['sect_attrs']
    out = []
    for sec in range(0, attrs['nsections']):
        attr = attrs['attrs'][sec]
        name = attr['name'].string()
        if name == '.text':
            continue
        out.append("-s {} {:#x}".format(name, int(attr['address'])))

    return " ".join(out)

init_uts_ns = gdb.lookup_symbol('init_uts_ns')[0].value()
release = init_uts_ns['name']['release'].string()
path = "/lib/modules/{}".format(release)

modules = gdb.lookup_symbol('modules')[0].value()
module_type = gdb.lookup_type('struct module')
for module in list_for_each_entry(modules, module_type, 'list'):
    modname = "{}.ko".format(module['name'].string())
    modpath = find(modname, path)
    if not modpath and modname.find('_') != -1:
        modname = modname.replace('_', '-')
        modpath = find(modname, path)
    if not modpath:
        print("Couldn't find {} under {}.".format(module['name'], path))
        continue
    sections = get_module_sections(module)
    gdb.execute("add-symbol-file {} {:#x} {}"
            .format(modpath, int(module['core_layout']['base']), sections))
