# -*- coding: utf-8 -*-
# vim:set shiftwidth=4 softtabstop=4 expandtab textwidth=79:

import gdb
import sys
import os.path
import crash.arch
import crash.arch.x86_64
import crash.arch.ppc64
from crash.infra import CrashBaseClass, export
from crash.types.list import list_for_each_entry
from crash.types.percpu import get_percpu_var, add_module_percpu_range
from crash.types.list import list_for_each_entry
import crash.cache.tasks
import crash.cache.syscache
from crash.types.task import LinuxTask
from elftools.elf.elffile import ELFFile
from crash.util import get_symbol_value

class CrashKernelError(RuntimeError):
    pass

class ModinfoMismatchError(ValueError):
    def __init__(self, attribute, path, value, expected_value):
        self.path = path
        self.value = value
        self.expected_value = expected_value
        self.attribute = attribute

    def __str__(self):
        return "module {} has mismatched {} (got `{}' expected `{}')".format(
                    self.path, self.attribute, self.value, self.expected_value)

class ModVersionMismatchError(ModinfoMismatchError):
    def __init__(self, path, module_value, expected_value):
        super(ModVersionMismatchError, self).__init__('vermagic',
                                                   path, module_value,
                                                   expected_value)

class ModSourceVersionMismatchError(ModinfoMismatchError):
    def __init__(self, path, module_value, expected_value):
        super(ModSourceVersionMismatchError, self).__init__('srcversion',
                                                   path, module_value,
                                                   expected_value)
LINUX_KERNEL_PID = 1

class CrashKernel(CrashBaseClass):
    __types__ = [ 'struct module', 'char *' ]
    __symvals__ = [ 'modules', 'init_task' ]
    __symbols__ = [ 'runqueues']


    def __init__(self, vmlinux_debuginfo=None, module_path=None,
                 module_debuginfo_path=None, verbose=False):
        """
        Initialize a basic kernel semantic debugging session.

        This means that we load the following:
        - Kernel image symbol table (and debuginfo, if not integrated)
          relocated to the base offset used by kASLR
        - Kernel modules that were loaded on the the crashed system (again,
          with debuginfo if not integrated)
        - Percpu ranges used by kernel module
        - Architecture-specific details
        - Linux tasks populated into the GDB thread table

        If kernel module files and debuginfo cannot be located, backtraces
        may be incomplete if the addresses used by the modules are crossed.
        Percpu ranges will be properly loaded regardless.

        For arguments that accept paths to specify a base directory to be
        used, the entire directory structure will be read and cached to
        speed up subsequent searches.  Still, reading large directory trees
        is a time consuming operation and being exact as possible will
        improve startup time.

        Args:
            vmlinux_debuginfo (string, None for defaults): The location
                of the separate debuginfo file corresponding to the kernel
                being debugged.

                None (or unspecified) uses the defaults, which will search
                - <loaded kernel path>.debug
                - ./vmlinux-<kernel version>.debug
                - /usr/lib/debug/.build-id/xx/<build-id>.debug
                - /usr/lib/debug/<loaded kernel path>.debug
                - /usr/lib/debug/boot/<loaded kernel name>.debug
                - /usr/lib/debug/boot/vmlinux-<kernel version>

            module_path (string, None for defaults): The base directory to
                be used to search for kernel modules (e.g. module.ko) to be
                used to load symbols for the kernel being debugged.

                None (or unspecified) uses the defaults, which will search
                - ./modules
                - /usr/lib/modules/$version

            module_debuginfo_path (string, None for defaults): The base
                directory to search for debuginfo matching the kernel
                modules already loaded.

                None (or unspecified) uses the defaults, which will search
                - ./modules.debug
                - /usr/lib/debug/.build-id/xx/<build-id>.debug
                - /usr/lib/debug/lib/modules/$version
        Raises:
            RuntimeError: If the kernel debuginfo cannot be loaded or
                          universally available symbols cannot be found.

        """
        self.findmap = {}
        obj = gdb.objfiles()[0]
        kernel = os.path.basename(obj.filename)
        debugroot = "/usr/lib/debug"

        version = self.extract_version()

        if vmlinux_debuginfo is None:
            x = [ "{}.debug".format(kernel)]
            x.append("vmlinux-{}.debug".format(version))
            x.append("{}/{}.debug".format(debugroot, kernel))
            x.append("{}/boot/{}.debug".format(debugroot,
                                               os.path.basename(kernel)))
            x.append("{}/boot/vmlinux-{}.debug".format(debugroot, version))

            self.vmlinux_debuginfo = x

        elif (isinstance(vmlinux_debuginfo, list) and
              len(vmlinux_debuginfo) > 0 and
              isinstance(vmlinux_debuginfo[0], str)):
            self.vmlinux_debuginfo = vmlinux_debuginfo
        elif isinstance(vmlinux_debuginfo, str):
            self.vmlinux_debuginfo = [ vmlinux_debuginfo ]
        else:
            raise TypeError("vmlinux_debuginfo must be str or list of str")

        if verbose:
            print("vmlinux_debuginfo={}".format(self.vmlinux_debuginfo))

        if module_path is None:
            x = [ "modules" ]
            x.append("/lib/modules/{}".format(version))

            self.module_path = x
        elif (isinstance(module_path, list) and
              isinstance(module_path[0], str)):
            self.module_path = module_path
        elif isinstance(module_path, str):
            self.module_path = [ module_path ]
        else:
            raise TypeError("module_path must be str or list of str")

        if verbose:
            print("module_path={}".format(self.module_path))

        if module_debuginfo_path is None:
            x = [ "modules.debug" ]
            x.append("{}/lib/modules/{}".format(debugroot, version))
            self.module_debuginfo_path = x
        elif (isinstance(module_debuginfo_path, list) and
              isinstance(module_debuginfo_path[0], str)):
            self.module_debuginfo_path = module_debuginfo_path
        elif isinstance(module_debuginfo_path, str):
            self.module_debuginfo_path = [ module_debuginfo_path ]
        else:
            raise TypeError("module_debuginfo_path must be str or list of str")

        if verbose:
            print("module_debuginfo_path={}".format(self.module_debuginfo_path))

        # We need separate debuginfo.  Let's go find it.
        if not obj.has_symbols():
            print("Loading debug symbols for vmlinux")
            for path in [self.build_id_path(obj)] + self.vmlinux_debuginfo:
                try:
                    obj.add_separate_debug_file(path)
                    if obj.has_symbols():
                        break
                except gdb.error as e:
                    pass

        if not obj.has_symbols():
            raise CrashKernelError("Couldn't locate debuginfo for {}"
                                    .format(kernel))

        self.vermagic = self.extract_vermagic()

        archname = obj.architecture.name()
        archclass = crash.arch.get_architecture(archname)
        self.arch = archclass()

        self.target = gdb.current_target()
        if self.target.shortname == 'kdumpfile':
            self.vmcore = self.target.kdump
            self.target.fetch_registers = self.fetch_registers

        self.crashing_thread = None

    # When working without a symbol table, we still need to be able
    # to resolve version information.
    def get_minsymbol_as_string(self, name):
        sym = gdb.lookup_minimal_symbol(name).value()

        return sym.address.cast(self.char_p_type).string()

    def extract_version(self):
        try:
            uts = get_symbol_value('init_uts_ns')
            return release['release'].string()
        except (AttributeError, NameError):
            pass

        banner = self.get_minsymbol_as_string('linux_banner')

        return banner.split(' ')[2]

    def extract_vermagic(self):
        try:
            magic = get_symbol_value('vermagic')
            return magic.string()
        except (AttributeError, NameError):
            pass

        return self.get_minsymbol_as_string('vermagic')

    def extract_modinfo_from_module(self, modpath):
        try:
            f = open(modpath, 'rb')
        except:
            return None

        d = None
        try:
            elf = ELFFile(f)
            modinfo = elf.get_section_by_name('.modinfo')

            d = {}
            for line in modinfo.data().split(b'\x00'):
                val = line.decode('utf-8')
                if val:
                    eq = val.index('=')
                    d[val[0:eq]] = val[eq + 1:]
        except Exception as e:
            print(e)
            del d
            d = None

        del elf
        f.close()
        return d

    def fetch_registers(self, register):
        thread = gdb.selected_thread()
        return self.arch.fetch_register(thread, register.regnum)

    @export
    @classmethod
    def for_each_module(cls):
        for module in list_for_each_entry(cls.modules, cls.module_type,
                                          'list'):
            yield module

    def get_module_sections(self, module):
        attrs = module['sect_attrs']
        out = []
        for sec in range(0, attrs['nsections']):
            attr = attrs['attrs'][sec]
            name = attr['name'].string()
            if name == '.text':
                continue
            out.append("-s {} {:#x}".format(name, int(attr['address'])))

        return " ".join(out)

    def check_module_version(self, modpath, module):
        modinfo = self.extract_modinfo_from_module(modpath)

        vermagic = None
        if 'vermagic' in modinfo:
            vermagic = modinfo['vermagic']

        if vermagic != self.vermagic:
            raise ModVersionMismatchError(modpath, vermagic, self.vermagic)

        mi_srcversion = None
        if 'srcversion' in modinfo:
            mi_srcversion = modinfo['srcversion']

        mod_srcversion = None
        if 'srcversion' in module.type:
            mod_srcversion = module['srcversion'].string()

        if mi_srcversion != mod_srcversion:
            raise ModSourceVersionMismatchError(modpath, mi_srcversion,
                                                mod_srcversion)

    def load_modules(self, verbose=False, debug=False):
        version = crash.cache.syscache.utsname.release
        print("Loading modules for {}".format(version), end='')
        if verbose:
            print(":", flush=True)
        failed = 0
        loaded = 0
        for module in self.for_each_module():
            modname = "{}".format(module['name'].string())
            modfname = "{}.ko".format(modname)
            found = False
            for path in self.module_path:
                modpath = self.find_module_file(modfname, path)
                if not modpath:
                    continue

                try:
                    self.check_module_version(modpath, module)
                except ModinfoMismatchError as e:
                    if verbose:
                        print(str(e))
                    continue

                found = True

                if 'module_core' in module.type:
                    addr = int(module['module_core'])
                else:
                    addr = int(module['core_layout']['base'])

                if debug:
                    print("Loading {} at {:#x}".format(modpath, addr))
                elif verbose:
                    print("Loading {} at {:#x}".format(modname, addr))
                else:
                    print(".", end='')
                    sys.stdout.flush()

                sections = self.get_module_sections(module)

                percpu = int(module['percpu'])
                if percpu > 0:
                    sections += " -s .data..percpu {:#x}".format(percpu)
                    add_module_percpu_range(percpu, int(module['percpu_size']))

                try:
                    result = gdb.execute("add-symbol-file {} {:#x} {}"
                                            .format(modpath, addr, sections),
                                         to_string=True)
                except gdb.error as e:
                    raise CrashKernelError("Error while loading module `{}': {}"
                                           .format(modname, str(e)))
                if debug:
                    print(result)

                objfile = gdb.lookup_objfile(modpath)
                if not objfile.has_symbols():
                    self.load_module_debuginfo(objfile, modpath, verbose)
                elif debug:
                    print(" + has debug symbols")

                break

            if not found:
                if failed == 0:
                    print()
                print("Couldn't find module file for {}".format(modname))
                failed += 1
            else:
                loaded += 1
            if (loaded + failed) % 10 == 10:
                print(".", end='')
                sys.stdout.flush()
        print(" done. ({} loaded".format(loaded), end='')
        if failed:
            print(", {} failed)".format(failed))
        else:
            print(")")

        # We shouldn't need this again, so why keep it around?
        del self.findmap
        self.findmap = {}

    def find_module_file(self, name, path):
        if not path in self.findmap:
            self.findmap[path] = {}

            for root, dirs, files in os.walk(path):
                for filename in files:
                    nname = filename.replace('-', '_')
                    self.findmap[path][nname] = os.path.join(root, filename)
        try:
            nname = name.replace('-', '_')
            return self.findmap[path][nname]
        except KeyError:
            return None

    @staticmethod
    def build_id_path(objfile):
        build_id = objfile.build_id
        return ".build_id/{}/{}.debug".format(build_id[0:2], build_id[2:])

    def try_load_debuginfo(self, objfile, path, verbose):
        try:
            if verbose:
                print(" + Loading debuginfo: {}".format(path))
            objfile.add_separate_debug_file(path)
            if objfile.has_symbols():
                return True
        except gdb.error as e:
            print(e)

        return False

    def load_module_debuginfo(self, objfile, modpath=None, verbose=False):
        if modpath is None:
            modpath = objfile.filename
        if ".gz" in modpath:
            modpath = modpath.replace(".gz", "")
        filename = "{}.debug".format(os.path.basename(modpath))
        filepath = None

        build_id_path = self.build_id_path(objfile)

        for path in self.module_debuginfo_path:
            filepath = "{}/{}".format(path, build_id_path)
            if self.try_load_debuginfo(objfile, filepath, verbose):
                break

            filepath = self.find_module_file(filename, path)
            if filepath and self.try_load_debuginfo(objfile, filepath, verbose):
                break

        if not objfile.has_symbols():
            print("Could not locate debuginfo for {}".format(modpath))

    def setup_tasks(self):
        gdb.execute('set print thread-events 0')

        task_list = self.init_task['tasks']

        rqs = get_percpu_var(self.runqueues)
        rqscurrs = {int(x["curr"]) : k for (k, x) in rqs.items()}

        self.pid_to_task_struct = {}

        print("Loading tasks...", end='')
        sys.stdout.flush()

        task_count = 0
        tasks = []
        for taskg in list_for_each_entry(task_list, self.init_task.type,
                                         'tasks', include_head=True):
            tasks.append(taskg)
            for task in list_for_each_entry(taskg['thread_group'],
                                            self.init_task.type,
                                            'thread_group'):
                tasks.append(task)

        try:
            crashing_cpu = int(get_symbol_value('crashing_cpu'))
        except Exception as e:
            crashing_cpu = None

        for task in tasks:
            cpu = None
            regs = None
            active = int(task.address) in rqscurrs
            if active and self.target.shortname == 'kdumpfile':
                cpu = rqscurrs[int(task.address)]
                regs = self.vmcore.attr.cpu[cpu].reg

            ltask = LinuxTask(task, active, cpu, regs)
            ptid = (LINUX_KERNEL_PID, task['pid'], 0)

            try:
                thread = gdb.selected_inferior().new_thread(ptid, ltask)
            except gdb.error as e:
                print("Failed to setup task @{:#x}".format(int(task.address)))
                continue

            thread.name = task['comm'].string()

            if active and crashing_cpu is not None and cpu == crashing_cpu:
                self.crashing_thread = thread

            self.arch.setup_thread_info(thread)

            if not active:
                self.arch.fetch_register_scheduled_inactive(thread, -1)

            ltask.attach_thread(thread)
            ltask.set_get_stack_pointer(self.arch.get_stack_pointer)

            crash.cache.tasks.cache_task(ltask)

            task_count += 1
            if task_count % 100 == 0:
                print(".", end='')
                sys.stdout.flush()
        print(" done. ({} tasks total)".format(task_count))

        gdb.selected_inferior().executing = False
