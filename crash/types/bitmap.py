#!/usr/bin/python3
# vim:set shiftwidth=4 softtabstop=4 expandtab textwidth=79:

import gdb

from math import log

from crash.infra import CrashBaseClass, export

class TypesBitmapClass(CrashBaseClass):
    __types__ = [ 'unsigned long' ]
    __type_callbacks__ = [ ('unsigned long', 'setup_ulong') ]

    bits_per_ulong = None

    @classmethod
    def check_bitmap_type(cls, bitmap):
        if ((bitmap.type.code != gdb.TYPE_CODE_ARRAY or
             bitmap[0].type.code != cls.unsigned_long_type.code or
             bitmap[0].type.sizeof != cls.unsigned_long_type.sizeof) and
            (bitmap.type.code != gdb.TYPE_CODE_PTR or
             bitmap.type.target().code != cls.unsigned_long_type.code or
             bitmap.type.target().sizeof != cls.unsigned_long_type.sizeof)):
            raise TypeError("bitmaps are expected to be arrays of unsigned long not `{}'"
                            .format(bitmap.type))

    @classmethod
    def setup_ulong(cls, gdbtype):
        cls.bits_per_ulong = gdbtype.sizeof * 8

    @export
    @classmethod
    def for_each_set_bit(cls, bitmap, size_in_bytes=None):
        cls.check_bitmap_type(bitmap)

        if size_in_bytes is None:
            size_in_bytes = bitmap.type.sizeof

        # FIXME: callback not workie?
        cls.bits_per_ulong = cls.unsigned_long_type.sizeof * 8

        size = size_in_bytes * 8
        idx = 0
        bit = 0
        while size > 0:
            ulong = bitmap[idx]

            if ulong != 0:
                for off in range(min(size, cls.bits_per_ulong)):
                    if ulong & 1 != 0:
                        yield bit
                    bit += 1
                    ulong >>= 1
            else:
                bit += cls.bits_per_ulong

            size -= cls.bits_per_ulong
            idx += 1

    @classmethod
    def _find_first_set_bit(cls, val):
        r = 1

        if val == 0:
            return 0

        if (val & 0xffffffff) == 0:
            val >>= 32
            r += 32

        if (val & 0xffff) == 0:
            val >>= 16
            r += 16

        if (val & 0xff) == 0:
            val >>= 8
            r += 8

        if (val & 0xf) == 0:
            val >>= 4
            r += 4

        if (val & 0x3) == 0:
            val >>= 2
            r += 2

        if (val & 0x1) == 0:
            val >>= 1
            r += 1

        return r

    @export
    @classmethod
    def find_first_set_bit(cls, bitmap, size_in_bytes=None):
        cls.check_bitmap_type(bitmap)

        if size_in_bytes is None:
            size_in_bytes = bitmap.type.sizeof

        elements = size_in_bytes // cls.unsigned_long_type.sizeof

        for n in range(0, elements):
            if bitmap[n] == 0:
                continue

            v = cls._find_first_set_bit(bitmap[n])
            if v > 0:
                return n * (cls.unsigned_long_type.sizeof << 3) + v

        return 0

    @classmethod
    def _find_last_set_bit(cls, val):
        r = cls.unsigned_long_type.sizeof << 3

        if val == 0:
            return 0

        if (val & 0xffffffff00000000) == 0:
            val <<= 32
            r -= 32

        if (val & 0xffff000000000000) == 0:
            val <<= 16
            r -= 16

        if (val & 0xff00000000000000) == 0:
            val <<= 8
            r -= 8

        if (val & 0xf000000000000000) == 0:
            val <<= 4
            r -= 4

        if (val & 0xc000000000000000) == 0:
            val <<= 2
            r -= 2

        if (val & 0x8000000000000000) == 0:
            val <<= 1
            r -= 1

        return r

    @export
    @classmethod
    def find_last_set_bit(cls, bitmap, size_in_bytes=None):
        cls.check_bitmap_type(bitmap)

        if size_in_bytes is None:
            size_in_bytes = bitmap.type.sizeof

        elements = size_in_bytes // cls.unsigned_long_type.sizeof

        for n in range(elements - 1, -1, -1):
            if bitmap[n] == 0:
                continue

            v = cls._find_last_set_bit(bitmap[n])
            if v > 0:
                return n * (cls.unsigned_long_type.sizeof << 3) + v

        return 0
