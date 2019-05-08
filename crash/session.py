# -*- coding: utf-8 -*-
# vim:set shiftwidth=4 softtabstop=4 expandtab textwidth=79:

import gdb
import sys

from crash.infra import autoload_submodules
from crash.kernel import CrashKernel as kernel, CrashKernelError

class Session(object):
    """
    crash.Session is the main driver component for crash-python

    The Session class loads the kernel, kernel modules, debuginfo,
    and vmcore and auto loads any sub modules for autoinitializing
    commands and subsystems.

    The debuginfo options below have defaults associated with them.
    Please see crash.kernel.CrashKernel for documentation.

    Args:
        vmlinux_debuginfo (list of str, optional): Paths to discover
            debuginfo for vmlinux
        modules (list of str, optional): Paths to discover modules
        modules_debuginfo (list of str, optional): Paths to discover
            debuginfo for modules
        debug (bool, optional, default=False): Whether to enable verbose
            debugging output
    """


    def __init__(self, vmlinux_debuginfo=None, modules=None,
                 modules_debuginfo=None, debug=False):
        print("crash-python initializing...")
        self.kernel = kernel(vmlinux_debuginfo=vmlinux_debuginfo,
                             module_path=modules,
                             module_debuginfo_path=modules_debuginfo)

        autoload_submodules('crash.cache')
        autoload_submodules('crash.subsystem')
        autoload_submodules('crash.commands')

        try:
            self.kernel.setup_tasks()
            self.kernel.load_modules(verbose=False)
        except CrashKernelError as e:
            print(str(e))
            print("Further debugging may not be possible.")
            return

        if self.kernel.crashing_thread:
            try:
                result = gdb.execute("thread {}"
                                      .format(self.kernel.crashing_thread.num),
                                     to_string=True)
                if debug:
                    print(result)
            except gdb.error as e:
                print("Error while switching to crashed thread: {}"
                                                                .format(str(e)))
                print("Further debugging may not be possible.")
                return

            print("Backtrace from crashing task (PID {:d}):"
                  .format(self.kernel.crashing_thread.ptid[1]))
            gdb.execute("where")
