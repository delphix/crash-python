# -*- coding: utf-8 -*-
# vim:set shiftwidth=4 softtabstop=4 expandtab textwidth=79:

import gdb

#
# In terms of organization, this file is very different from the
# other files in the command/ subdirectory. It doesn't build all
# the Python abstractions created by pycrash and uses the plain
# GDB API mainly for two reasons:
#
# [1] We can reuse this file when running gdb against a userland
#     core dump from ztest.
#
# [2] We don't need to redeclare types and symbols in Python for
#     every command we write as forced by the CrashCommand model.
#     The benefits of this is that [a] development of new code
#     through `python-interactive` is easier (no need to declare
#     classes), [b] common functions like gen() and walkers can
#     be reused between commands in a straightforward manner.
#
#

class StackInfo():
    def __init__(self, function, offset, module):
        self.function = function
        self.offset = offset
        self.module = module

    def __str__(self):
        return "{0}+{1}".format(self.function, str(self.offset))

class Stacks(gdb.Command):
    stack_map = {}
    def __init__(self):
        super(Stacks, self).__init__("stacks", gdb.COMMAND_DATA)
        self.address = 0xffff000000000000;

    def iterate_threads():
        root = gdb.inferiors()[0]
        for thread in root.threads():
            thread.switch()
            yield thread

    def insert(lines, state, thread_num):
        key = state + ''.join(str(l) for l in lines)
        if (key in Stacks.stack_map):
            Stacks.stack_map[key][0] += 1
        else:
            Stacks.stack_map[key] = [1, lines, state, thread_num]

    def print_stacks():
        for key in Stacks.stack_map.keys():
            count = Stacks.stack_map[key][0]
            lines = Stacks.stack_map[key][1]
            state = Stacks.stack_map[key][2]
            num = Stacks.stack_map[key][3]
            match = len(list(filter(lambda line: "zfs" in line.module, lines))) > 0
            if match:
                print("STATE    COUNT   NUM")
                print("{0}  {1}     {2}".format(state, count, num))
                print('\n'.join(str(line) for line in lines))
                print("")
        print(len(Stacks.stack_map.keys()))

    def get_state(thread):
        if thread.is_running():
            return "RUNNING"
        if thread.is_exited():
            return "EXITED"
        if thread.is_stopped():
            return "STOPPED"

    def invoke(self, arg, from_tty):
        Stacks.stack_map = {}
        for thread in Stacks.iterate_threads():
            trace_lines=[]
            frame = gdb.newest_frame()
            while (frame != None):
                if frame.pc() < self.address:
                    break
                if (frame.function() is None):
                    function_name = frame.name()
                    trace_lines.append(StackInfo(function_name, None, ""))
                else:
                    function_name = frame.function().print_name
                    offset = hex(int(frame.pc()) - int(frame.function().value().address))
                    module = frame.function().symtab.objfile.filename
                    trace_lines.append(StackInfo(function_name, offset, module))
                frame = frame.older()
            Stacks.insert(trace_lines, Stacks.get_state(thread), thread.num)
        Stacks.print_stacks()

Stacks()
