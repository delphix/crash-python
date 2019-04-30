# -*- coding: utf-8 -*-
# vim:set shiftwidth=4 softtabstop=4 expandtab textwidth=79:

import gdb
from crash.infra import CrashBaseClass, export
from crash.util import array_size, struct_has_member
from crash.types.list import list_for_each_entry
from crash.exceptions import DelayedAttributeError
from crash.types.bitmap import find_first_set_bit, find_last_set_bit
from crash.types.bitmap import find_next_set_bit, find_next_zero_bit
from crash.types.page import Page

class TypesPerCPUClass(CrashBaseClass):
    __types__ = [ 'char *', 'struct pcpu_chunk', 'struct percpu_counter' ]
    __symvals__ = [ '__per_cpu_offset', 'pcpu_base_addr', 'pcpu_slot',
                    'pcpu_nr_slots', '__cpu_possible_mask',
                    'cpu_possible_mask', 'pcpu_group_offsets' ]
    __minsymvals__ = ['__per_cpu_start', '__per_cpu_end' ]
    __minsymbol_callbacks__ = [ ('__per_cpu_start', 'setup_per_cpu_size'),
                             ('__per_cpu_end', 'setup_per_cpu_size') ]
    __symbol_callbacks__ = [ ('__per_cpu_offset', 'setup_nr_cpus'),
                             ('__cpu_possible_mask', 'setup_last_cpu'),
                             ('cpu_possible_mask', 'setup_last_cpu') ]

    dynamic_offset_cache = None

    # TODO: put this somewhere else - arch?
    # This is x86-specific.  gdb.current_target().base_offset would also
    # work but that means /proc/kcore access won't work.
    @classmethod
    def setup_kaslr_offset(cls):
        offset = int(gdb.lookup_minimal_symbol("_text").value().address)
        offset -= int(gdb.lookup_minimal_symbol("phys_startup_64").value().address)
        offset -= 0xffffffff80000000

        # This can sometimes be zero even if target.base_offset is not.
        # It can happen when external debuginfo is not required since
        # the .percpu..data section will retain a 0 offset.
        cls.kaslr_offset = offset

    @classmethod
    def setup_per_cpu_size(cls, symbol):
        try:
            size = cls.__per_cpu_end - cls.__per_cpu_start
        except DelayedAttributeError:
            pass

        cls.static_ranges = { cls.__per_cpu_start : size }
        cls.module_ranges = {}

    @classmethod
    def setup_last_cpu(cls, symbol):
        cls.last_cpu = find_last_set_bit(symbol.value()['bits'])

    @classmethod
    def setup_nr_cpus(cls, ignored):
        cls.nr_cpus = array_size(cls.__per_cpu_offset)

        # piggyback on this as it seems those minsymbols at the time of
        # their callback yield offset of 0
        cls.setup_kaslr_offset()

    @classmethod
    def __add_to_offset_cache(cls, base, start, end):
        cls.dynamic_offset_cache.append((base + start, base + end))

    @classmethod
    def __setup_dynamic_offset_cache_area_map(cls, chunk):
        used_is_negative = None
        chunk_base = int(chunk["base_addr"]) - int(cls.pcpu_base_addr)
        # __per_cpu_start is adjusted by KASLR, but dynamic offsets are
        # not, so we have to subtract the offset
        chunk_base += int(cls.__per_cpu_start) - cls.kaslr_offset

        off = 0
        start = None
        _map = chunk['map']
        map_used = int(chunk['map_used'])

        # Prior to 3.14 commit 723ad1d90b56 ("percpu: store offsets
        # instead of lengths in ->map[]"), negative values in map
        # meant the area is used, and the absolute value is area size.
        # After the commit, the value is area offset for unused, and
        # offset | 1 for used (all offsets have to be even). The value
        # at index 'map_used' is a 'sentry' which is the total size |
        # 1. There is no easy indication of whether kernel includes
        # the commit, unless we want to rely on version numbers and
        # risk breakage in case of backport to older version. Instead
        # employ a heuristic which scans the first chunk, and if no
        # negative value is found, assume the kernel includes the
        # commit.
        if used_is_negative is None:
            used_is_negative = False
            for i in range(map_used):
                val = int(_map[i])
                if val < 0:
                    used_is_negative = True
                    break

        if used_is_negative:
            for i in range(map_used):
                val = int(_map[i])
                if val < 0:
                    if start is None:
                        start = off
                else:
                    if start is not None:
                        cls.__add_to_offset_cache(chunk_base, start, off)
                        start = None
                off += abs(val)
            if start is not None:
                cls.__add_to_offset_cache(chunk_base, start, off)
        else:
            for i in range(map_used):
                off = int(_map[i])
                if off & 1 == 1:
                    off -= 1
                    if start is None:
                        start = off
                else:
                    if start is not None:
                        cls.__add_to_offset_cache(chunk_base, start, off)
                        start = None
            if start is not None:
                off = int(_map[map_used]) - 1
                cls.__add_to_offset_cache(chunk_base, start, off)


    @classmethod
    def __setup_dynamic_offset_cache_bitmap(cls, chunk):
        group_offset = int(cls.pcpu_group_offsets[0])
        size_in_bytes = int(chunk['nr_pages']) * Page.PAGE_SIZE
        size_in_bits = size_in_bytes << 3
        start = -1
        end = 0

        chunk_base = int(chunk["base_addr"]) - int(cls.pcpu_base_addr)
        cls.__add_to_offset_cache(chunk_base, 0, size_in_bytes)

    @classmethod
    def __setup_dynamic_offset_cache(cls):
        # TODO: interval tree would be more efficient, but this adds no 3rd
        # party module dependency...
        cls.dynamic_offset_cache = list()
        use_area_map = struct_has_member(cls.pcpu_chunk_type, 'map')
        for slot in range(cls.pcpu_nr_slots):
            for chunk in list_for_each_entry(cls.pcpu_slot[slot], cls.pcpu_chunk_type, 'list'):
                if use_area_map:
                    cls.__setup_dynamic_offset_cache_area_map(chunk)
                else:
                    cls.__setup_dynamic_offset_cache_bitmap(chunk)

    def __is_percpu_var(self, var):
        if self.is_percpu_static_var(var):
            return True

        if self.is_module_percpu_var(var):
            return True
        return False

    def __is_percpu_var_dynamic(self, var):
        if self.dynamic_offset_cache is None:
            self.__setup_dynamic_offset_cache()

        var = int(var)
        # TODO: we could sort the list...
        for (start, end) in self.dynamic_offset_cache:
            if var >= start and var < end:
                return True

        return False

    @export
    def add_static_percpu_range(self, start, size):
        self.static_ranges[start] = size

    @export
    def add_module_percpu_range(self, start, size):
        self.module_ranges[start] = size

    # The resolved percpu address
    def _is_static_percpu_address(self, addr):
        for start in self.static_ranges:
            size = self.static_ranges[start]
            for cpu in range(0, self.last_cpu):
                offset = int(__per_cpu_offset[cpu]) + start
                if addr >= offset and addr < offset + size:
                    return True
        return False

    # The percpu virtual address
    def is_static_percpu_var(self, addr):
        for start in self.static_ranges:
            for cpu in range(0, self.last_cpu):
                size = self.static_ranges[start]
                if addr >= start and addr < start + size:
                    return True
        return False

    # The percpu virtual address
    def is_module_percpu_var(self, addr):
        for start in self.module_ranges:
            for cpu in range(0, self.last_cpu):
                size = self.module_ranges[start]
                if addr >= start and addr < start + size:
                    return True
        return False

    @export
    def is_percpu_var(self, var):
        if isinstance(var, gdb.Symbol):
            var = var.value().address
        if self.is_static_percpu_var(var):
            return True
        if self.is_module_percpu_var(var):
            return True
        if self.__is_percpu_var_dynamic(var):
            return True
        return False

    def get_percpu_var_nocheck(self, var, cpu=None, is_symbol=False, nr_cpus=None):
        if nr_cpus is None:
            nr_cpus = self.last_cpu
        if cpu is None:
            vals = {}
            for cpu in range(0, nr_cpus):
                vals[cpu] = self.get_percpu_var_nocheck(var, cpu, is_symbol)
            return vals

        addr = self.__per_cpu_offset[cpu]
        if addr > 0:
            addr += var.cast(self.char_p_type)
            if self.is_static_percpu_var(var):
                addr -= self.__per_cpu_start

                # if we got var from symbol, it means KASLR relocation was
                # applied to the offset, it was applied also to __per_cpu_start,
                # which cancels out.
                # If var wasn't a symbol, we have to undo the adjustion to
                # __per_cpu_start, otherwise we get a bogus address
                if not is_symbol:
                    addr += self.kaslr_offset

        vartype = var.type
        return addr.cast(vartype).dereference()

    @export
    def get_percpu_var(self, var, cpu=None, nr_cpus=None):
        orig_var = var
        # Percpus can be:
        # - actual objects, where we'll need to use the address.
        # - pointers to objects, where we'll need to use the target
        # - a pointer to a percpu object, where we'll need to use the
        #   address of the target
        is_symbol = False
        if isinstance(var, gdb.Symbol) or isinstance(var, gdb.MinSymbol):
            var = var.value()
            is_symbol = True
        if not isinstance(var, gdb.Value):
            raise TypeError("Argument must be gdb.Symbol or gdb.Value")
        if var.type.code != gdb.TYPE_CODE_PTR:
            var = var.address
        if not self.is_percpu_var(var):
            var = var.address
        if var is None or not self.is_percpu_var(var):
            raise TypeError("Argument {} does not correspond to a percpu pointer.".format(orig_var))
        return self.get_percpu_var_nocheck(var, cpu, is_symbol, nr_cpus)

    @export
    def percpu_counter_sum(self, var):
        if isinstance(var, gdb.Symbol):
            var = var.value()

        if not (var.type == self.percpu_counter_type or
                (var.type.code == gdb.TYPE_CODE_PTR and
                 var.type.target() == self.percpu_counter_type)):
            raise TypeError("var must be gdb.Symbol or gdb.Value describing `{}' not `{}'"
                                .format(self.percpu_counter_type, var.type))

        total = int(var['count'])

        v = get_percpu_var(var['counters'])
        for cpu in v:
            total += int(v[cpu])

        return total
