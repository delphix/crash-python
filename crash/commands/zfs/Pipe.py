# -*- coding: utf-8 -*-
# vim:set shiftwidth=4 softtabstop=4 expandtab textwidth=79:

import gdb
import argparse
from typing import Callable, Any

class PipeableCommand():
    allPipeableCommands = {}

    def __init__(self, cmdname, createGdb=True):
        PipeableCommand.allPipeableCommands[cmdname] = type(self)
        self.islast = False
        rv = self.call([])
        assert (rv is not None and rv.__iter__ is not None), "{}.call() does not return an iterable".format(type(self).__name__)

        if not createGdb:
            return

        # Now we generate a dynamic dispatch class to invoke our pipeable command if it's invoked directly from gdb
        def __init__(self2):
            gdb.Command.__init__(self2, cmdname, gdb.COMMAND_DATA)
        def invoke(self2, argstr, from_tty):
            (first, space, last) = argstr.strip().rpartition(' ')
            inputs = []
            if len(last) != 0:
                inputs = [gdb.Value(int(last, 0))]

            for i in type(self)(first).call(inputs):
                print(i)

        gdbCommandClass = type(cmdname + 'Cmd', (gdb.Command,), {"__init__": __init__, "invoke": invoke})
        gdbCommandClass()

    # subclass must override
    # subclass must override this, typically with a generator, i.e. it must use `yield`
    def call(self, input):
        assert "subclass must override"

    # called if this is the last thing in the pipeline
    def setIsLast(self):
        self.islast = True

class LineCount(PipeableCommand):
    def __init__(self, arg=""):
        super(LineCount, self).__init__('wc')
    def call(self, input):
        i = 0
        for o in input:
            i += 1
        yield gdb.Value(i)
LineCount()

class Head(PipeableCommand):
    def __init__(self, arg=""):
        super(Head, self).__init__('head')
        try:
            parser = argparse.ArgumentParser(prog='head')
            parser.add_argument('count', type=int, default=10, nargs='?')
            self.args = parser.parse_args(gdb.string_to_argv(arg))
        except:
            pass

    def call(self, input):
        for o in input:
            if self.args.count == 0:
                break
            yield o
            self.args.count -= 1
Head()

from collections import deque
class Tail(PipeableCommand):
    def __init__(self, arg=""):
        super(Tail, self).__init__('tail')
        try:
            parser = argparse.ArgumentParser(prog='tail')
            parser.add_argument('count', type=int, default=10, nargs='?')
            self.args = parser.parse_args(gdb.string_to_argv(arg))
        except:
            pass

    def call(self, input):
        q = deque(maxlen=self.args.count)
        for o in input:
            q.append(o)
        for o in q:
            yield o
Tail()

class Member(PipeableCommand):
    def __init__(self, arg=""):
        super(Member, self).__init__('member')
        self.args = arg

    def call(self, input):
        for i in input:
            if i.type.code == gdb.TYPE_CODE_PTR:
                cmd = "(({}){})->{}".format(i.type, hex(i), self.args)
            else:
                cmd = "(({}){}).{}".format(i.type, hex(i), self.args)
            #print(cmd)
            yield gdb.parse_and_eval(cmd)
Member()

class Filter(PipeableCommand):
    def __init__(self, arg=""):
        super(Filter, self).__init__('filter')
        self.args = arg

    def call(self, input):
        for i in input:
            if i.type.code == gdb.TYPE_CODE_PTR:
                cmd = "(({}){})->{}".format(i.type, hex(i), self.args)
            else:
                cmd = "(({}){}).{}".format(i.type, hex(i), self.args)
            #print(cmd)
            if (int(gdb.parse_and_eval(cmd)) != 0):
                yield i
Filter()

class Pipe(gdb.Command):
    def __init__(self):
        super(Pipe, self).__init__('pipe', gdb.COMMAND_DATA)

    def iterate(self, pipeline):
        if len(pipeline) == 1:
            yield from pipeline[0].call(self.input)
        else:
            yield from pipeline[-1].call(self.iterate(pipeline[:-1]))

    def invoke(self, argstr, from_tty):
        if len(argstr) == 0:
            print("available commands:")
            for cmd in sorted (PipeableCommand.allPipeableCommands.keys()):
                print("    ", cmd)
            return

        split_cmds = [cmd.strip().partition(' ')[0:3:2] for cmd in argstr.split('|')]
        self.input = []
        try:
            self.input = [gdb.Value(int(split_cmds[0][0], 0))]
            split_cmds = split_cmds[1:]
        except:
            pass

        pipeline = []
        for name, arg in split_cmds:
            pipeline.append(PipeableCommand.allPipeableCommands[name](arg))
        pipeline[-1].setIsLast()
        for o in self.iterate(pipeline):
            print(o)

Pipe()

