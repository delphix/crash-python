#!/usr/bin/env python3
import subprocess
import os
import sys
import io
import argparse
import difflib

DUMPDIR="/net/pharos/export/cores/sdb/dumps/"

def process_dump(failures, dumpfile, directory, kernel):
    proc = subprocess.Popen(('./crash.sh -m ' + directory + " " +
        directory +  kernel + " " + directory + dumpfile).split(" "),
        stdin=subprocess.PIPE, stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT, encoding='utf-8')
    for (name, command) in tests.items():
        if args.test is not None and (name != 'startup' and name != args.test):
            continue
        print("\tRunning {}  ... ".format(name), end='', flush=True)
        proc.stdin.write(command + '\n')
        proc.stdin.flush()
        output = []
        line = proc.stdout.readline(4)
        while line != 'sdb>':
            if not line.endswith('\n'):
                line += proc.stdout.readline()
            assert len(line.rstrip('\n').splitlines()) <= 1
            output.append(line)
            line = proc.stdout.readline(4)

        if args.cmd_output:
            with open('{}/{}.{}.ex_out'.format(args.cmd_output, name, dumpfile), 'w') as cmd_out:
                cmd_out.writelines(output)

        with open('crash/commands/sdb_tests/{}.{}.ex_out'.format(name, dumpfile), 'r') as ex_out:
            ex_output = list(ex_out)

        diff = list(difflib.unified_diff(ex_output, output))
        if len(diff) > 0:
            print("FAIL")
            failures.append(name)
            with open('{}/{}.diff'.format(args.output, name), 'w') as diff_out:
                diff_out.writelines(diff)
        else:
            print("PASS")


parser = argparse.ArgumentParser(description = 'sdb integration tests')
parser.add_argument('-o', '--output', required=True, default = 'output', help='directory to store test results in')
parser.add_argument('-O', '--cmd_output', default = None, help='directory to store command results in')
parser.add_argument('-t', '--test', default=None, help='a single test to run')
args = parser.parse_args(sys.argv[1:])

tests = {'startup': '',
         'spa1': 'spa',
         'spav': 'spa -v',
         'spavm': 'spa -vm',
         'spavmw': 'spa -vmw',
         'spa_vd': 'spa | vdev',
         'spa_vdm': 'spa | vdev -m',
         'spa_vd_ms': 'spa | vdev | metaslab',
         'long_pipe_allocating' : 'spa rpool | cast "spa_t *" | member ->spa_normal_class->mc_rotor->mg_metaslab_tree | avl | cast "metaslab_t *" | member ->ms_allocating[0] | range_tree',
         'long_pipe_allocatable': 'spa rpool | cast "spa_t *" | member ->spa_normal_class->mc_rotor->mg_metaslab_tree | avl | cast "metaslab_t *" | member ->ms_allocatable | range_tree',
         'stacks': 'stacks',
         'refcount': 'lookup ARC_mru | member ->arcs_size | address | cast zfs_refcount_t * | refcount',
         'refcount': 'lookup ARC_mru | member ->arcs_size | refcount',
         'refcount_void': 'lookup ARC_mru | member ->arcs_size | address | cast void * | refcount',
         'refcount_int': 'lookup ARC_mru | member ->arcs_size | cc | refcount  ',
         'zfs_dbgmsg': 'zfs_dbgmsg',
         'zfs_dbgmsg_iter': 'lookup zfs_dbgmsgs | member ->pl_list | address | cast list_t * | list | cast zfs_dbgmsg_t * | print',
         'metaslab_pp': 'spa rpool | vdev 0 | member ->vdev_ms[0] | cast metaslab_t * | metaslab',
         'pp': 'spa rpool | vdev 0 | member ->vdev_ms[0] | cast metaslab_t * | pp',
         'walk': 'lookup zfs_dbgmsgs | member ->pl_list | address | cast list_t * | walk',
         'zio': 'spa | member ->spa_txg_zio[0] | zio',
         'blkptr': 'spa | member ->spa_meta_objset->os_rootbp | blkptr',
         'kmastat': 'kmastat',
         'multilist': 'lookup ARC_mru | member->arcs_list[1] | multilist',
         'dbuf': 'dbuf',
         'dbuf_filter': 'dbuf --level=0 -b 3',
         'dbuf_dnode': 'dbuf --level=0 -b 3 -H | head 4 | tail 1 | member ->db_dnode_handle->dnh_dnode | dbuf',
         'metaslab_selection': 'spa rpool | vdev 0 | metaslab 50 58 3 | member ->ms_id'
         }

failures = []
os.chdir(os.path.dirname(os.path.realpath(__file__)))
print("Running mypy  ... ", end='', flush=True)
with open('{}/mypy.out'.format(args.output), 'w') as outfile:
    try:
        proc = subprocess.run('mypy crash/commands/zfs'.split(' '), stdout=outfile, stderr=subprocess.STDOUT)
        if proc.returncode != 0:
            print("FAIL")
            failures.append('mypy')
        else:
            print("PASS")
    except FileNotFoundError:
        print("FAIL")
        print("mypy not installed: Run `python3 -m pip install -U mypy; sudo ln -s ~/.local/bin/mypy /usr/bin/` to install.")
        failures.append('mypy')

for dumpfile in os.scandir(DUMPDIR):
    if dumpfile.name.startswith('dump.'):
        print("Testing against {}".format(dumpfile.name))
        process_dump(failures, dumpfile.name, DUMPDIR,
            'vmlinux-4.15.0-48-generic')

if len(failures) == 0:
    print("Test run passed!")
else:
    print("Test run failed. The following tests failed:")
    for failure in failures:
        print("    {}".format(failure))
