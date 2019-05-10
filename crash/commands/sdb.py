# -*- coding: utf-8 -*-
# vim:set shiftwidth=4 softtabstop=4 expandtab textwidth=79:

import gdb
import subprocess
import sys
import shlex
import traceback
from typing import Iterable,List
from crash.commands.zfs.zfs_util import parse_type

#
# Some "abstract" subclasses of SDBCommand have their own registration logic
# (Walkers, PrettyPrinter), so we walk through the mro for the class and call
# register for each one. Any class that gets subclassed that doesn't have
# registration logic should define a registerCmd function that does nothing.
#
allSDBCommands = {}
def registerSDBCommand(c : type) -> None:
    for c2 in c.__mro__:
        # We skip registering c with c, because if it needs to register itself
        # it can do so, and this avoids double-calling other registration
        # functions in leaf classes that don't override registerCmd to be a
        # no-op.
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

    def registerByName(name : str, c : type) -> None:
        allSDBCommands[name] = c

        #
        # We create an inner class that dispatches the gdb invoke call to the
        # actual command's invoke method. This enables the current
        # registration mechanism, instead of the default gdb.Command mechanism
        # where the constructor is also the register function.
        #
        class gdbCmd(gdb.Command):
            def __init__(self):
                gdbCmdname = name
                if hasattr(c, "gdbCmdName"):
                    gdbCmdname = c.gdbCmdName
                super().__init__(gdbCmdname, gdb.COMMAND_DATA)
            def invoke(self, argstr : str, from_tty : bool) -> None:
                c().invoke(argstr, from_tty)

        gdbCmd()
        
    def registerCmd(c : type) -> None:
        if not issubclass(c, SDBCommand):
            raise TypeError("{} is not a subclass of {}".format(c, SDBCommand))
        if not hasattr(c, "cmdName"):
            raise TypeError("{} does not define cmdName".format(c))

        if isinstance(c.cmdName, str):
            SDBCommand.registerByName(c.cmdName, c)
        else:
            try:
                for cname in c.cmdName:
                    SDBCommand.registerByName(cname, c)
            except TypeError as e:
                print('Invalid cmdName type in {}'.format(c))
                raise e

    #
    # This function gets called from the gdbCmd inner class above, and
    # contains the core pipeline logic.
    #
    def invoke(self, argstr : str, from_tty : bool) -> None:
        shell_cmd = None
        # Parse the argument string. Each pipeline stage is delimited by
        # a pipe character "|". If there is a "!" character detected, then
        # pipe all the remaining output into a subshell.
        all_tokens = shlex.shlex(argstr, posix=False, punctuation_chars="|!")
        all_tokens.wordchars += '();<>&[]'
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

        # Build the pipeline by constructing each of the commands we want to
        # use and building a list of them.
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

        # If we have a !, redirect stdout to a shell process. This avoids
        # having to have a custom printing function that we pass around and
        # use everywhere. We'll fix stdout to point back to the normal stdout
        # at the end.
        if shell_cmd is not None:
            shell_proc = subprocess.Popen(shell_cmd, shell=True, stdin=subprocess.PIPE, encoding='utf-8')
            old_stdout = sys.stdout
            sys.stdout = shell_proc.stdin

        try:
            # If the last step in the pipeline isn't a PipeableCommand, it's
            # not going to yield anything. We call executePipelineTerm in that
            # case so that we don't run into an issue where the pipeline
            # doesn't pull properly because of generator quirks.
            if not isinstance(pipeline[-1], PipeableCommand):
                SDBCommand.executePipelineTerm([], pipeline)
            else:
                for o in SDBCommand.executePipeline([], pipeline):
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

    # Run the pipeline, and yield the output. This function recurses through
    # the pipeline, providing each stage with the earlier stage's outputs as
    # input.
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

    # Run a pipeline that ends in a non-pipeable command. This function is
    # very similar to executePipeline, but it doesn't yield any results.
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

#
# A pipe command that massages its input types into the a different type. This
# usually involves stripping typedefs or qualifiers, adding pointers to go
# from a struct to a struct *, or casting an int or void * to the appropriate
# pointer type.
#
class Coerce(PipeableCommand):
    cmdName = 'coerce'
    def __init__(self, arg : str = "void *", auxError : str = ''):
        super().__init__()
        self.auxError = auxError
        self.type = parse_type(arg)
        if self.type.code is not gdb.TYPE_CODE_PTR:
            raise TypeError('can only coerce to pointer types, not {}'.format(self.type))

    def coerce(self, obj : gdb.Value) -> gdb.Value:
        # same type is fine
        if obj.type == self.type:
            return obj

        # "void *" can be coerced to any pointer type
        if obj.type.code is gdb.TYPE_CODE_PTR and obj.type.target().code is gdb.TYPE_CODE_VOID:
            return obj.cast(self.type)

        # integers can be coerced to any pointer typo
        if obj.type.code is gdb.TYPE_CODE_INT:
            return obj.cast(self.type)

        # "type" can be coerced to "type *"
        if obj.address is not None and obj.address.type == self.type:
            return obj.address.cast(self.type)

        raise TypeError("can not coerce {} to {} {}".format(obj.type, self.type, self.auxError))

    def call(self, input):
        for i in input:
            yield self.coerce(i)

registerSDBCommand(Coerce)
