# -*- coding: utf-8 -*-
# vim:set shiftwidth=4 softtabstop=4 expandtab textwidth=79:

import gdb
import argparse
from typing import Callable, Any

class PipeableCommand():
    allPipeableCommands = {}

    def __init__(self, cmdname):
        PipeableCommand.allPipeableCommands[cmdname] = type(self)
        self.islast = False
        rv = self.call([])
        assert (rv is not None and rv.__iter__ is not None), "{}.call() does not return an iterable".format(type(self).__name__)

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

class Pipe(gdb.Command):
    def __init__(self):
        super(Pipe, self).__init__('pipe', gdb.COMMAND_DATA)

    def iterate(self, pipeline):
        if len(pipeline) == 1:
            yield from pipeline[0].call(self.input)
        else:
            yield from pipeline[-1].call(self.iterate(pipeline[:-1]))

    def invoke(self, argstr, from_tty):
        split_cmds = [cmd.strip().partition(' ')[0:3:2] for cmd in argstr.split('|')]
        self.input = []
        if len(split_cmds) > 0:
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

