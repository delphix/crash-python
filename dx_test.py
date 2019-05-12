#!/usr/bin/env python3
import subprocess
import os
import sys
import io
import argparse
import difflib

parser = argparse.ArgumentParser(description = 'sdb integration tests')
parser.add_argument('-o', '--output', required=True, default = 'output', help='directory to store test results in')
parser.add_argument('-O', '--cmd_output', default = None, help='directory to store command results in')
parser.add_argument('-t', '--test', default=None, help='a single test to run')
args = parser.parse_args(sys.argv[1:])

tests = {'startup': '',
         'spa1': 'spa',
         'spav': 'spa -v',
         'spam': 'spa -m',
         'spa_vd': 'spa | vdev',
         'spa_vdm': 'spa | vdev -m',
         'spa_vd_ms': 'spa | vdev | metaslab',
         'long_pipe_allocating' : 'echo 0xffff8c4fe7634000 | cast "spa_t *" | member ->spa_normal_class->mc_rotor->mg_metaslab_tree | avl | cast "metaslab_t *" | member ->ms_allocating[0] | range_tree',
         'long_pipe_allocatable': 'echo 0xffff8c4fe7634000 | cast "spa_t *" | member ->spa_normal_class->mc_rotor->mg_metaslab_tree | avl | cast "metaslab_t *" | member ->ms_allocatable | range_tree',
         'stacks': 'stacks',
         'refcount': 'echo 0xffffffffc095e290 | cast zfs_refcount_t * | refcount',
         'refcount_void': 'echo 0xffffffffc095e290 | cast void * | refcount',
         'refcount_int': 'cc 0xffffffffc095e290 | refcount',
         'zfs_dbgmsg': 'zfs_dbgmsg',
         'zfs_dbgmsg_iter': 'echo 0xffffffffc09d1258 | cast list_t * | list | cast zfs_dbgmsg_t * | print',
         'metaslab_pp': 'echo 0xffff8c4fd22f8800 | cast metaslab_t * | metaslab',
         'pp': 'echo 0xffff8c4fd22f8800 | cast metaslab_t * | pp',
         'walk': 'echo 0xffffffffc09d1258 | cast list_t * | walk',
         'zio': 'spa | member ->spa_txg_zio[0] | zio',
         'blkptr': 'spa | member ->spa_meta_objset->os_rootbp | blkptr',
         'kmastat': 'kmastat',
         'multilist': 'echo 0xffff8c4fe855a440 |multilist',
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
        proc = subprocess.run('mypy --ignore-missing-imports crash/commands/zfs'.split(' '), stdout=outfile, stderr=subprocess.STDOUT)
        if proc.returncode != 0:
            print("FAIL")
            failures.append('mypy')
        else:
            print("PASS")
    except FileNotFoundError:
        print("FAIL")
        print("mypy not installed: Run `python3 -m pip install -U mypy; sudo ln -s ~/.local/bin/mypy /usr/bin/` to install.")
        failures.append('mypy')

proc = subprocess.Popen(('./crash.sh -m ' +
                         '../dump ../dump/vmlinux-4.15.0-47-generic ../dump/dump.201904221843').split(' '),
                        stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                        stderr=subprocess.STDOUT, encoding='utf-8')
for (name, command) in tests.items():
    if args.test is not None and (name != 'startup' and name != args.test):
        continue
    print("Running {}  ... ".format(name), end='', flush=True)
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
        with open('{}/{}.ex_out'.format(args.cmd_output, name), 'w') as cmd_out:
            cmd_out.writelines(output)

    with open('crash/commands/sdb_tests/{}.ex_out'.format(name), 'r') as ex_out:
        ex_output = list(ex_out)

    diff = list(difflib.unified_diff(ex_output, output))
    if len(diff) > 0:
        print("FAIL")
        failures.append(name)
        with open('{}/{}.diff'.format(args.output, name), 'w') as diff_out:
            diff_out.writelines(diff)
    else:
        print("PASS")

if len(failures) == 0:
    print("Test run passed!")
else:
    print("Test run failed. The following tests failed:")
    for failure in failures:
        print("    {}".format(failure))
