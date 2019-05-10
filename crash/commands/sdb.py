# -*- coding: utf-8 -*-
# vim:set shiftwidth=4 softtabstop=4 expandtab textwidth=79:

import gdb
import subprocess
import sys
import shlex
import traceback
from typing import Iterable,List
from crash.commands.zfs.zfs_util import parse_type

allSDBCommands = {}
def registerSDBCommand(c : type) -> None:
    for c2 in c.__mro__:
        if hasattr(c2, "registerCmd") and c2 != c:
            c2.registerCmd(c)

#
# This class is the superclass of all commands intended for use with SDB. The
# distinguishing feature of SDB commands is that they take an input to their
# `call` method.
#
class SDBCommand(object):
    inputType = None
    def __init__(self):
        self.islast = False

    def registerCmd(c : type) -> None:
        if not issubclass(c, SDBCommand):
            raise TypeError("{} is not a subclass of {}".format(c, SDBCommand))
        if not hasattr(c, "cmdName"):
            raise TypeError("{} does not define cmdName".format(c))
        allSDBCommands[c.cmdName] = c
        
        class gdbCmd(gdb.Command):
            def __init__(self):
                gdbCmdname = c.cmdName
                if hasattr(c, "gdbCmdName"):
                    gdbCmdname = c.gdbCmdName
                super().__init__(gdbCmdname, gdb.COMMAND_DATA)
            def invoke(self, argstr : str, from_tty : bool) -> None:
                c().invoke(argstr, from_tty)

        gdbCmd()

    def invoke(self, argstr : str, from_tty : bool) -> None:
        shell_cmd = None
        # Parse the argument string. Each pipeline stage is delimited by
        # a pipe character "|". If there is a "!" character detected, then
        # pipe all the remaining output into a subshell.
        all_tokens = shlex.split(argstr, posix=False)
        pipe_stages = []
        tokens = []
        for n, token in enumerate(all_tokens):
            if token == '|':
                pipe_stages.append(' '.join(tokens))
                tokens = []
            elif token == '!':
                pipe_stages.append(' '.join(tokens))
                if any(t == '!' for t in all_tokens[n + 1:]):
                    print("Multiple ! not supported")
                    return
                shell_cmd = ' '.join(all_tokens[n + 1:])
                break
            else:
                tokens.append(token)
        else:
            # We didn't find a !, so all remaining tokens are part of
            # the last pipe
            pipe_stages.append(' '.join(tokens))

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
                pipeline.append(allSDBCommands[cmdname](args))
            except KeyError as e:
                print('No command named "{}" found'.format(cmdname))
                return

        pipeline[-1].setIsLast()

        if shell_cmd is not None:
            shell_proc = subprocess.Popen(shell_cmd, shell=True, stdin=subprocess.PIPE, encoding='utf-8')
            old_stdout = sys.stdout
            sys.stdout = shell_proc.stdin

        try:
            if not isinstance(pipeline[-1], PipeableCommand):
                SDBCommand.executePipelineTerm(input, pipeline)
            else:
                for o in SDBCommand.executePipeline(input, pipeline):
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


    def executePipeline(first_input : Iterable[gdb.Value], args : List[object]) -> gdb.Value:
        # if this stage wants its input in a certain type, insert a
        # "coerce" stage before it
        if args[-1].inputType is not None:
            args.insert(-1, Coerce(args[-1].inputType, auxError='for "{}" command'.format(args[-1].cmdName)))
        if len(args) == 1:
            this_input = first_input
        else:
            this_input = SDBCommand.executePipeline(first_input, args[:-1])
        yield from args[-1].call(this_input)

    def executePipelineTerm(first_input : Iterable[gdb.Value], args : List[object]) -> gdb.Value:
        # if the last stage wants its input in a certain type, insert a
        # "coerce" stage before it
        assert not isinstance(args[-1], PipeableCommand)
        if args[-1].inputType is not None:
            args.insert(-1, Coerce(args[-1].inputType, auxError='for "{}" command'.format(args[-1].cmdName)))
        if len(args) == 1:
            this_input = first_input
        else:
            this_input = SDBCommand.executePipeline(first_input, args[:-1])
        args[-1].call(this_input)

    # subclass must override this, typically with a generator, i.e. it must use `yield`
    def call(self, input : Iterable[gdb.Value]) -> Iterable[gdb.Value]:
        raise NotImplementedError

    # called if this is the last thing in the pipeline
    def setIsLast(self):
        self.islast = True

#
# Commands whose call function yields an iterable of some kind; usually a
# generator, for performance reasons.
#
class PipeableCommand(SDBCommand):
    def __init__(self):
        super().__init__()
        rv = self.call([])
        assert (rv is not None and rv.__iter__ is not None), "{}.call() does not return an iterable".format(type(self).__name__)

    def registerCmd(c : type) -> None:
        pass

class Coerce(PipeableCommand):
    cmdName = 'coerce'
    def __init__(self, arg : str = "void *", auxError : str = ''):
        super().__init__()
        self.auxError = auxError
        self.type = parse_type(arg).strip_typedefs().unqualified()
        if self.type.code is not gdb.TYPE_CODE_PTR:
            raise TypeError('can only coerce to pointer types, not {} ({})'.format(arg, self.type))

    def coerce(self, obj : gdb.Value) -> gdb.Value:
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

registerSDBCommand(Coerce)
