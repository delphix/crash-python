import gdb
from crash.commands import CrashCommandParser
import argparse
import os.path
from crash.types.task import TaskStateFlags as TF

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

# TODO doc string
# TODO replace wierd constant used to stop unwinding
# TODO print thread numbers for all matched (-a)

class FrameInfo():

    def __init__(self, function, offset, module):
        self.function = function
        self.offset = offset
        self.module = module

    def display_str(self):
        mod = ""
        if self.module and not self.module.startswith("vmlinux"): # TODO is this accurate?
            mod = " [" + self.module + "]"
        return self.location_str() + mod

    def location_str(self):
        offset = ""
        if self.offset is not None:
            offset = "+" + str(self.offset)
        return self.function + offset

class StackInfo():
    def __init__(self, frames, state, thread_id):
        self.frames = frames
        self.state = state
        self.thread_id = thread_id
        self.count = 1

    def get_key(self):
        return self.state + ''.join(f.location_str() for f in self.frames)

    def pretty_print(self):
        print("{0} {1} {2:>5}".format(str(self.thread_id).ljust(8), self.state.ljust(30), self.count))
        indent = '         '
        print(indent + ("\n" + indent).join(f.display_str() for f in self.frames))
        print("")

class Stacks(gdb.Command):
    #TODO fill this in
    """ Stacks documentation here"""

    def __init__(self):
        name = "stacks"
        super(Stacks, self).__init__(name, gdb.COMMAND_DATA)
        parser = CrashCommandParser(prog=name,description='Aggregate and count all unique stacks')
        parser.add_argument('-m', help='show stacks with a function in module M')
        parser.add_argument('-c', help='show stacks with function C')
        parser.add_argument('-t', help='show threads with status T') #TODO list optional states
        parser.add_argument('-f', action='store_true', help='force a refresh of the stacks cache')
        self.parser = parser

        self.stack_map = {}
        self.task_states = None

    def iterate_threads():
        root = gdb.inferiors()[0]
        for thread in root.threads():
            thread.switch()
            yield thread

    def insert(stack_map, frames, state, thread_num):
        stack_info = StackInfo(frames, state, thread_num)
        key = stack_info.get_key()
        if (key in stack_map):
            stack_map[key].count += 1
        else:
            stack_map[key] = stack_info

    def print_stacks(self, filter_module, filter_function, filter_state):
        matching_count=0

        for key, stack_info in sorted(self.stack_map.items(), key = lambda val: val[1].count, reverse=True):
            frames = stack_info.frames

            state_match = True
            module_match = True
            function_match = True
            if filter_state is not None:
                state_match = filter_state == stack_info.state # TODO maybe case insitive
            if filter_module is not None:
                module_match = any([filter_module == frame.module for frame in frames])
            if filter_function is not None:
                # filter is allowed to match '<function>' or '<function>+<offset>'
                function_match = any([frame.function == filter_function or frame.location_str() == filter_function for frame in frames])

            if state_match and module_match and function_match:
                stack_info.pretty_print()
                matching_count += 1

        print("Total unique stacks:", len(self.stack_map.keys())) # debug
        print("Matching unique stacks:", matching_count)

    # TODO can we just use TF?
    def setup_task_states(self):
        self.task_states = {
            TF.TASK_RUNNING         : "RUNNING",
            TF.TASK_INTERRUPTIBLE   : "INTERRUPTABLE",
            TF.TASK_UNINTERRUPTIBLE : "UNINTERRUPTABLE",
            TF.TASK_ZOMBIE          : "ZOMBIE",
            TF.TASK_STOPPED         : "STOPPED",
        }

        if hasattr(TF, 'TASK_SWAPPING'):
            self.task_states[TF.TASK_SWAPPING] = "SWAPPING"
        if hasattr(TF, 'TASK_DEAD'):
            self.task_states[TF.TASK_DEAD] = "DEAD"
        if hasattr(TF, 'TASK_TRACING_STOPPED'):
            self.task_states[TF.TASK_TRACING_STOPPED] = "TRACING_STOPPPED"
        if hasattr(TF, 'TASK_IDLE'):
            self.task_states[TF.TASK_IDLE] = "IDLE"

    def get_state(self, thread):
        state = thread.info.task_state()
        for bits in sorted(self.task_states.keys(), reverse=True):
            if (state & bits) == bits:
                return self.task_states[bits]
        return "unknown"

    def build_stack_map(self):
       stack_map = {}

       for thread in Stacks.iterate_threads():
           trace_lines=[]
           frame = gdb.newest_frame()
           while (frame != None):
               if frame.pc() < 0xffff000000000000: # Hack
                   break
               if (frame.function() is None):
                   function_name = frame.name()
                   if function_name is None:
                       function_name = hex(frame.pc())
                   trace_lines.append(FrameInfo(function_name, None, ""))
               else:
                   function_name = frame.function().print_name
                   offset = hex(int(frame.pc()) - int(frame.function().value().address))
                   module = os.path.splitext(os.path.basename(frame.function().symtab.objfile.filename))[0]
                   trace_lines.append(FrameInfo(function_name, offset, module))
               frame = frame.older()
           Stacks.insert(stack_map, trace_lines, self.get_state(thread), thread.num)
       return stack_map

    def invoke(self, arg, from_tty):
        argv = gdb.string_to_argv(arg)
        try:
            args = self.parser.parse_args(argv)
        except:
            self.parser.print_help() #TODO for -h, we end up printing message twice
            return

        if self.task_states is None:
            self.setup_task_states()

        if not any(self.stack_map) or args.f:
            self.stack_map = self.build_stack_map()

        print("THREAD   STATE                          COUNT")
        print("=============================================")
        self.print_stacks(args.m, args.c, args.t)

Stacks()
