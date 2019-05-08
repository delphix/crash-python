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

        our_class = type(self)

        # dynamically generate a new class to invoke our pipeable command when it's invoked directly from gdb
        class dynamicClass(gdb.Command):
            def __init__(self2):
                gdb.Command.__init__(self2, cmdname, gdb.COMMAND_DATA)

            def invoke(self2, argstr, from_tty):
                pipe_stages = argstr.split('|')
                input = []
                try:
                    first_arg = pipe_stages[0]
                    (beginning, space, last) = first_arg.strip().rpartition(' ')
                    if len(last) != 0:
                        input = [gdb.Value(int(last, 0))]
                        pipe_stages[0] = beginning
                except:
                    pass

                pipeline = []
                pipeline.append(our_class(pipe_stages[0]))
                for stage in pipe_stages[1:]:
                    (cmdname, space, args) = stage.strip().partition(' ')
                    pipeline.append(PipeableCommand.allPipeableCommands[cmdname](args))

                pipeline[-1].setIsLast()

                for o in PipeableCommand.executePipeline(input, pipeline):
                    print(o)
        dynamicClass()

    # input should be an iterable of gdb.Value's
    # args should be an array of instances of subclasses of PipeableCommand
    def executePipeline(input, args):
        if len(args) == 1:
            yield from args[0].call(input)
        else:
            yield from args[-1].call(PipeableCommand.executePipeline(input, args[:-1]))

    # subclass must override this, typically with a generator, i.e. it must use `yield`
    def call(self, input):
        raise NotImplementedError

    # called if this is the last thing in the pipeline
    def setIsLast(self):
        self.islast = True

class Pipe(gdb.Command):
    def __init__(self):
        super().__init__('pipe', gdb.COMMAND_DATA)

    def invoke(self, argstr, from_tty):
        print("pipeable commands:")
        for cmd in sorted (PipeableCommand.allPipeableCommands.keys()):
            print("    ", cmd)
Pipe()

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

import re
def parseMember(value, memberString, strictChecking=False):
    regexp = re.compile('(\.|->|\[)([a-zA-Z0-9_\]]*)(.*)')
    while len(memberString) > 0:
        match = regexp.match(memberString)
        if not match:
            raise Exception("Invalid member string {}".format(memberString))
        operator = match.group(1)
        member = match.group(2)
        memberString = match.group(3)
        if operator == '.' or operator == '->':
            if strictChecking:
                if operator == '->' and value.type.code != gdb.TYPE_CODE_PTR:
                    raise InvalidAccessException('Cannot access non-pointer with "->"')
                if operator == '.' and value.type.code == gdb.TYPE_CODE_PTR:
                    raise InvalidAccessException('Cannot access pointer with "."')
            value = value[member]
        elif operator == '[':
            if strictChecking:
                if member[-1] != '[':
                    raise InvalidAccessException('Missing ] in index expression [{}'.format(member))
            idx = int(member[:-1])
            if value.type.code != gdb.TYPE_CODE_PTR and value.type.code != gdb.TYPE_CODE_ARRAY:
                raise InvalidAccessException('Cannot index into non-pointer value {}'.format(value))
            itemsize = value.type.target().sizeof
            value = value[idx]
        else:
            assert False, 'Unknown operator {}'.format(operator)

    if value.type.strip_typedefs().code == gdb.TYPE_CODE_STRUCT:
        value = value.address
    return value

class Member(PipeableCommand):
    def __init__(self, arg=""):
        super().__init__('member')
        self.args = arg

    def call(self, input):
        for i in input:
            yield parseMember(i, self.args)

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


