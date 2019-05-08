# -*- coding: utf-8 -*-
# vim:set shiftwidth=4 softtabstop=4 expandtab textwidth=79:

import gdb
import argparse
from typing import Callable, Any
from crash.commands.zfs.zfs_util import parse_type

class PipeableCommand():
    allPipeableCommands = {}

    def __init__(self, cmdname, createGdb=True, inputType=None):
        PipeableCommand.allPipeableCommands[cmdname] = type(self)

        self.cmdName = cmdname
        self.inputType = inputType
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
                    try:
                        pipeline.append(PipeableCommand.allPipeableCommands[cmdname](args))
                    except KeyError as e:
                        print('No command named "{}" found'.format(cmdname))
                        return

                pipeline[-1].setIsLast()

                try:
                    for o in PipeableCommand.executePipeline(input, pipeline):
                        print(o)
                except Exception as e:
                    print(e)
                    return
        dynamicClass()

    # input should be an iterable of gdb.Value's
    # args should be an array of instances of subclasses of PipeableCommand
    def executePipeline(first_input, args):
        # if this stage wants its input in a certain type, insert a
        # "coerce" stage before it
        if args[-1].inputType is not None:
            args.insert(-1, Coerce(args[-1].inputType, auxError='for "{}" command'.format(args[-1].cmdName)))
        if len(args) == 1:
            this_input = first_input
        else:
            this_input = PipeableCommand.executePipeline(first_input, args[:-1])
        yield from args[-1].call(this_input)

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

class Coerce(PipeableCommand):
    def __init__(self, arg="void *", auxError=''):
        super().__init__('coerce')
        self.auxError = auxError
        self.type = parse_type(arg).strip_typedefs().unqualified()
        if self.type.code is not gdb.TYPE_CODE_PTR:
            raise TypeError('can only coerce to pointer types, not {} ({})'.format(arg, self.type))

    def coerce(self, obj):
        tt = obj.type.strip_typedefs().unqualified()

        # same type is fine
        if tt == self.type:
            return obj

        # "void *" can be coerced to any pointer type
        if tt.code is gdb.TYPE_CODE_PTR and tt.target().code is gdb.TYPE_CODE_VOID:
            return obj.cast(self.type)

        # integers can be coerced to any pointer typo
        if tt.code is gdb.TYPE_CODE_INT:
            return obj.cast(self.type)

        # "type" can be coerced to "type *"
        if obj.address is not None and obj.address.type.strip_typedefs().unqualified() == self.type:
            return obj.address.cast(self.type)

        raise TypeError("can not coerce {} to {} {}".format(tt, self.type, self.auxError))

    def call(self, input):
        for i in input:
            yield self.coerce(i)
Coerce()

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
            raise Exception('Invalid member string "{}"'.format(memberString))
        operator = match.group(1)
        member = match.group(2)
        memberString = match.group(3)
        if operator == '.' or operator == '->':
            if strictChecking:
                if operator == '->' and value.type.code != gdb.TYPE_CODE_PTR:
                    raise TypeError('Cannot access non-pointer with "->"')
                if operator == '.' and value.type.code == gdb.TYPE_CODE_PTR:
                    raise TypeError('Cannot access pointer with "."')
            value = value[member]
        elif operator == '[':
            if strictChecking:
                if member[-1] != '[':
                    raise SyntaxError('Missing ] in index expression "[{}"'.format(member))
            idx = int(member[:-1])
            if value.type.code != gdb.TYPE_CODE_PTR and value.type.code != gdb.TYPE_CODE_ARRAY:
                raise TypeError('Cannot index into non-pointer value {}'.format(value))
            itemsize = value.type.target().sizeof
            value = value[idx]
        else:
            assert False, 'Unknown operator "{}"'.format(operator)

#    if value.type.strip_typedefs().code == gdb.TYPE_CODE_STRUCT:
#        value = value.address
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


