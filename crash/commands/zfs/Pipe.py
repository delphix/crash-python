# -*- coding: utf-8 -*-
# vim:set shiftwidth=4 softtabstop=4 expandtab textwidth=79:

import gdb
import argparse
import traceback
from typing import Callable, Any
from crash.commands.zfs.zfs_util import parse_type
import subprocess
import io
import sys


def print_to_string(*args, **kwargs):
    output = io.StringIO()
    print(*args, file=output, **kwargs)
    contents = output.getvalue()
    output.close()
    return contents

class PipeableCommand(gdb.Command):
    allPipeableCommands = {}

    def __init__(self, cmdname, gdbCmdname=None, inputType=None):
        if gdbCmdname is None:
            gdbCmdname = cmdname
        super().__init__(gdbCmdname, gdb.COMMAND_DATA)

        PipeableCommand.allPipeableCommands[cmdname] = type(self)

        self.cmdName = cmdname
        self.inputType = inputType
        self.islast = False

        rv = self.call([])
        assert (rv is not None and rv.__iter__ is not None), "{}.call() does not return an iterable".format(type(self).__name__)

    def invoke(self, argstr, from_tty):
        shell_cmd = None
        shell_split = argstr.split('!')
        argstr = shell_split[0]
        if len(shell_split) > 2:
            print("Multiple ! not supported")
            return
        elif len(shell_split) == 2:
            shell_cmd = shell_split[1].strip()

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
        pipeline.append(type(self)(pipe_stages[0]))
        for stage in pipe_stages[1:]:
            (cmdname, space, args) = stage.strip().partition(' ')
            try:
                pipeline.append(PipeableCommand.allPipeableCommands[cmdname](args))
            except KeyError as e:
                print('No command named "{}" found'.format(cmdname))
                return

        pipeline[-1].setIsLast()

        if shell_cmd is not None:
            shell_proc = subprocess.Popen(shell_cmd, shell=True, stdin=subprocess.PIPE, encoding='utf-8')
            old_stdout = sys.stdout
            sys.stdout = shell_proc.stdin

        try:
            for o in PipeableCommand.executePipeline(input, pipeline):
                print(o)

            if shell_cmd is not None:
                shell_proc.stdin.flush()
                shell_proc.stdin.close()

        except BrokenPipeError:
            pass
        except Exception as e:
            traceback.print_exc()
            print(e)
            return
        finally:
            if shell_cmd is not None:
                sys.stdout = old_stdout
                shell_proc.wait()


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

#
# A Locator is a command that locates objects of a given type.
# Subclasses declare that they produce a given outputType
# (the type being located), and they provide a method for each
# input type that they can search for objects of this type.
# Additionally, subclasses can pretty-print the given outputType.
#
class Locator(PipeableCommand):
    allLocators = {}

    def __init__(self, cmdname, outputType, inputTypes={}):
        super().__init__(cmdname)
        self.outputType = outputType
        self.inputTypes = inputTypes
        Locator.allLocators[outputType] = type(self)

    # subclass may provide this
    #def pretty_print(self, input):
    #    raise NotImplementedError

    # subclass may override this
    def noInput(self):
        raise TypeError('command "{}" requires an input'.format(
            self.cmdName))

    def caller(self, input):
        baked = [ (parse_type(k).strip_typedefs().unqualified(), f) for k, f in self.inputTypes.items() ]
        out_type = parse_type(self.outputType)
        hasInput = False
        for i in input:
            i_type = i.type.strip_typedefs().unqualified()
            hasInput = True

            # try subclass-specified input types first, so that they can override any other behavior
            try:
                for t, f in baked:
                    if i_type == t:
                        yield from f(i)
                        raise StopIteration
            except StopIteration:
                continue

            # try passthrough of output type
            # note, this may also be handled by subclass-specified input types
            if i_type == out_type:
                yield i
                continue

            # try walkers
            try:
                for o in Walk().call([i]):
                    o.cast(out_type)
                    yield o
                continue
            except TypeError:
                pass

            # error
            raise TypeError('command "{}" does not handle input of type {} (base type {})'.format(
                self.cmdName,
                i.type,
                i_type))
        if not hasInput:
            yield from self.noInput()

    def call(self, input):
        if self.islast and hasattr(self, "pretty_print"):
            self.pretty_print(self.caller(input))
        else:
            yield from self.caller(input)

class AbstractContainer(PipeableCommand):
    allAbstractContainers = {}

    def __init__(self, cmdname, inputType):
        super().__init__(cmdname)
        self.inputType = inputType
        AbstractContainer.allAbstractContainers[self.inputType] = type(self)

    # subclass must override this
    # obj is a gdb.Value of type inputType
    def walk(self, obj):
        raise NotImplementedError

    def call(self, input):
        for i in input:
            yield from self.walk(i)

# XXX it would be nice if we could make this a Locator, and rely on the logic in there
# XXX to handle the input type matching.  Unfortunately I think we'd have to ensure
# XXX that this gets instantiated last (after Locator.allLocators is fully populated)
class Walk(PipeableCommand):
    def __init__(self, arg=""):
        super().__init__('walk')

    def call(self, input):
        baked = [ (parse_type(k).strip_typedefs().unqualified(), c) for k, c in AbstractContainer.allAbstractContainers.items() ]
        hasInput = False
        for i in input:
            hasInput = True
            i_type = i.type.strip_typedefs().unqualified()

            try:
                for t, c in baked:
                    if i_type == t:
                        yield from c().walk(i)
                        raise StopIteration
            except StopIteration:
                continue

            raise TypeError('no walker found for input of type {} (base type {})'.format(
                i.type,
                i_type))
        if not hasInput:
            print("The following types have walkers:")
            print("\t%-20s %-20s" % ("WALKER", "TYPE"))
            for t, c in baked:
                print("\t%-20s %-20s" % (c().cmdName, t))
            raise TypeError('no input given to walk')
Walk()

# find a Locator whose outputType matches our input, and call its pretty_print()
# XXX it would be nice if we could make this a Locator, and rely on the logic in there
# XXX to handle the input type matching.  Unfortunately I think we'd have to ensure
# XXX that this gets instantiated last (after Locator.allLocators is fully populated)
class PrettyPrint(PipeableCommand):
    def __init__(self, arg=""):
        super().__init__('pp')

    def call(self, input):
        baked = [ (parse_type(t).strip_typedefs().unqualified(), c) for t, c in Locator.allLocators.items() ]
        hasInput = False
        for i in input:
            hasInput = True
            i_type = i.type.strip_typedefs().unqualified()

            try:
                for t, c in baked:
                    if i_type == t and hasattr(c, "pretty_print"):
                        if not self.islast:
                            yield i
                        c().pretty_print([i])
                        raise StopIteration
            except StopIteration:
                continue

            # error
            raise TypeError('command "{}" does not handle input of type {} (base type {})'.format(
                self.cmdName,
                i.type,
                i_type))
        if not hasInput:
            print("The following types have pretty-printers:")
            print("\t%-20s %-20s" % ("PRINTER", "TYPE"))
            for t, c in baked:
                if hasattr(c, "pretty_print"):
                    print("\t%-20s %-20s" % (c().cmdName, t))
            raise TypeError('no input given to pp')

PrettyPrint()

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


