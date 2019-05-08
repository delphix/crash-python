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
        def constructor(self2):
            gdb.Command.__init__(self2, cmdname, gdb.COMMAND_DATA)

        def iterate(self2, pipeline):
            if len(pipeline) == 1:
                yield from pipeline[0].call(self2.input)
            else:
                yield from pipeline[-1].call(self2.iterate(pipeline[:-1]))

        def invoke(self2, argstr, from_tty):
            pipe_stages = argstr.split('|')
            self2.input = []
            try:
                first_arg = pipe_stages[0]
                (beginning, space, last) = first_arg.strip().rpartition(' ')
                if len(last) != 0:
                    self2.input = [gdb.Value(int(last, 0))]
                    pipe_stages[0] = beginning
            except:
                pass

            pipeline = []
            pipeline.append(type(self)(pipe_stages[0]))
            for stage in pipe_stages[1:]:
                (cmdname, space, args) = stage.strip().partition(' ')
                pipeline.append(PipeableCommand.allPipeableCommands[cmdname](args))
            pipeline[-1].setIsLast()
            for o in self2.iterate(pipeline):
                print(o)

        gdbCommandClass = type(cmdname + 'Cmd', (gdb.Command,),
                {"__init__": constructor, "invoke": invoke, "iterate": iterate})
        gdbCommandClass()

    # subclass must override this, typically with a generator, i.e. it must use `yield`
    def call(self, input):
        assert "subclass must override"

    # called if this is the last thing in the pipeline
    def setIsLast(self):
        self.islast = True

class LineCount(PipeableCommand):
    def __init__(self, arg=""):
        super().__init__('wc')
    def call(self, input):
        i = 0
        for o in input:
            i += 1
        yield gdb.Value(i)
LineCount()

class Head(PipeableCommand):
    def __init__(self, arg=""):
        super().__init__('head')
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
        super().__init__('tail')
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
        super().__init__('member')
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
        super().__init__('filter')
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

class Null(PipeableCommand):
    def __init__(self, arg=""):
        super().__init__('null')

    def call(self, input):
        for i in input:
            pass
        return []
Null()

class Echo(PipeableCommand):
    def __init__(self, arg=""):
        super().__init__('echo')
        self.arg = arg

    def call(self, input):
        for o in self.arg.split():
            yield gdb.Value(int(o, 0))
        for o in input:
            yield o
Echo()

