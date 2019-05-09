# -*- coding: utf-8 -*-
# vim:set shiftwidth=4 softtabstop=4 expandtab textwidth=79:
#
# TODO - add dva command
#

import gdb
from crash.commands.zfs.Pipe import PipeableCommand
from crash.commands.zfs.zfs_util import symbol_address
from crash.commands.zfs.zfs_util import enum_lookup

SPA_MINBLOCKSHIFT = 9

SPA_LSIZEBITS = 16
SPA_PSIZEBITS = 16
SPA_ASIZEBITS = 24

SPA_COMPRESSBITS = 7
SPA_VDEVBITS =     24

SPA_DVAS_PER_BP = 3

BP_EMBEDDED_TYPE_DATA = 0
BP_EMBEDDED_TYPE_MOOCH_BYTESWAP = 1
BP_EMBEDDED_TYPE_REDACTED = 2

P2PHASE =     lambda x, align : ((x) & ((align) - 1))
BF64_DECODE = lambda x, low, len : P2PHASE(x >> low, 1 << len)
BF64_GET =    lambda x, low, len : BF64_DECODE(x, low, len)
BF64_GET_SB = lambda x, low, len, shift, bias : (BF64_GET(x, low, len) + bias) << shift

DVA_GET_ASIZE =  lambda dva : BF64_GET_SB(dva['dva_word'][0], 0, SPA_ASIZEBITS, SPA_MINBLOCKSHIFT, 0)
DVA_GET_VDEV =   lambda dva : BF64_GET(dva['dva_word'][0], 32, SPA_VDEVBITS)
DVA_GET_OFFSET = lambda dva : BF64_GET_SB(dva['dva_word'][1], 0, 63, SPA_MINBLOCKSHIFT, 0)
DVA_IS_EMPTY =   lambda dva : dva['dva_word'][0] == 0 and dva['dva_word'][1] == 0

BP_IS_GANG =     lambda bp : False if BP_IS_EMBEDDED(bp) else True 
BP_IS_HOLE =     lambda bp : not BP_IS_EMBEDDED(bp) and DVA_IS_EMPTY(bp['blk_dva'][0])
BP_IS_REDACTED = lambda bp : BP_IS_EMBEDDED(bp) and BPE_GET_ETYPE(bp) == BP_EMBEDDED_TYPE_REDACTED

BPE_GET_ETYPE = lambda bp : BF64_GET(bp['blk_prop'], 40, 8)
BPE_GET_LSIZE = lambda bp : BF64_GET_SB(bp['blk_prop'], 0, 25, 0, 1)
BPE_GET_PSIZE = lambda bp : BF64_GET_SB(bp['blk_prop'], 25, 7, 0, 1)

BP_GET_LSIZE = lambda bp : BPE_GET_LSIZE(bp) if BP_IS_EMBEDDED(bp) else BF64_GET_SB(bp['blk_prop'], 0, SPA_LSIZEBITS, SPA_MINBLOCKSHIFT, 1)
BP_GET_PSIZE = lambda bp : 0 if BP_IS_EMBEDDED(bp) else BF64_GET_SB(bp['blk_prop'], 16, SPA_PSIZEBITS, SPA_MINBLOCKSHIFT, 1)

BP_GET_COMPRESS =   lambda bp : BF64_GET(bp['blk_prop'], 32, SPA_COMPRESSBITS)
BP_IS_EMBEDDED =    lambda bp : BF64_GET(bp['blk_prop'], 39, 1)
BP_GET_CHECKSUM =   lambda bp : ZIO_CHECKSUM_OFF if BP_IS_EMBEDDED(bp) else BF64_GET(bp['blk_prop'], 40, 8)
BP_GET_TYPE =       lambda bp : BF64_GET(bp['blk_prop'], 48, 8)
BP_GET_LEVEL =      lambda bp : BF64_GET(bp['blk_prop'], 56, 5)
BP_GET_DEDUP =      lambda bp : BF64_GET(bp['blk_prop'], 62, 1)
BP_GET_BYTEORDER =  lambda bp : BF64_GET(bp['blk_prop'], 63, 1)
BP_PHYSICAL_BIRTH = lambda bp : 0 if BP_IS_EMBEDDED(bp) else bp['blk_phys_birth'] if bp['blk_phys_birth'] else bp['blk_birth'] 
BP_GET_FILL =       lambda bp : 1 if BP_IS_EMBEDDED(bp) else bp['blk_fill'] 


class Blkptr(PipeableCommand):
    """pretty print a zfs blkptr_t

NAME
  blkptr - display a zfs block pointer

SYNOPSIS
  cast blkptr_t* <address> | blkptr
  """

    def __init__(self, arg=""):
        super().__init__('blkptr', inputType="blkptr_t*")

    def print_blkptr_hole(bp, type):
        print("HOLE [L{:d} {}] size={:x}L birth={}L".format(
            int(BP_GET_LEVEL(bp)),
            type,
            int(BP_GET_LSIZE(bp)),
            bp['blk_birth']))

    def print_blkptr_redacted(bp, type):
        print("REDACTED [L{:d} {}] size={:x}L birth={}L".format(
            int(BP_GET_LEVEL(bp)),
            type,
            int(BP_GET_LSIZE(bp)),
            bp['blk_birth']))

    def print_blkptr_embedded(bp, type):
        print("EMBEDDED [L{:d} {}] et={} {} size={:x}L/{:x}P birth={}L".format(
            int(BP_GET_LEVEL(bp)),
            type,
            BPE_GET_ETYPE(bp),
            enum_lookup("enum zio_compress", BP_GET_COMPRESS(bp)),
            int(BPE_GET_LSIZE(bp)),
            int(BPE_GET_PSIZE(bp)),
            bp['blk_birth']))

    def print_blkptr_normal(bp, type):
        copyname = ["zero", "single", "double", "triple"]
        copies = 0

        for d in range(SPA_DVAS_PER_BP):
            dva = bp['blk_dva'][d]
            if DVA_GET_ASIZE(dva) == 0:
                break
            copies += 1
            print("DVA[{:d}]=<{:d}:{:x}:{:x}>".format(d,
                int(DVA_GET_VDEV(dva)),
                int(DVA_GET_OFFSET(dva)),
                int(DVA_GET_ASIZE(dva))))

        print("[L{} {}] {} {} {} {} {} {}".format(
            BP_GET_LEVEL(bp),
            type,
            enum_lookup("enum zio_checksum", BP_GET_CHECKSUM(bp)),
            enum_lookup("enum zio_compress", BP_GET_COMPRESS(bp)),
            'BE' if BP_GET_BYTEORDER(bp) == 0 else 'LE',
            'gang' if BP_IS_GANG(bp) else 'contiguous',
            'dedup' if BP_GET_DEDUP(bp) else 'unique',
            copyname[copies]))

        print("size={:x}L/{:x}P birth={}L/{}P fill={}".format(
            int(BP_GET_LSIZE(bp)),
            int(BP_GET_PSIZE(bp)),
            bp['blk_birth'],
            BP_PHYSICAL_BIRTH(bp),
            BP_GET_FILL(bp)))
        print("cksum={:x}:{:x}:{:x}:{:x}".format(
            int(bp['blk_cksum']['zc_word'][0]),
            int(bp['blk_cksum']['zc_word'][1]),
            int(bp['blk_cksum']['zc_word'][2]),
            int(bp['blk_cksum']['zc_word'][3])))

    def print_blkptr(self, bp):
        if bp == 0:
            print("<NULL>")
            return

        type = enum_lookup("enum dmu_object_type", BP_GET_TYPE(bp))

        if BP_IS_HOLE(bp):
            Blkptr.print_blkptr_hole(bp, type)
        elif BP_IS_REDACTED(bp):
            Blkptr.print_blkptr_redacted(bp, type)
        elif BP_IS_EMBEDDED(bp):
            Blkptr.print_blkptr_embedded(bp, type)
        else:
            Blkptr.print_blkptr_normal(bp, type)

    def call(self, input):
        if self.islast:
            for bp in input:
                self.print_blkptr(bp)
        else:
            yield from input

Blkptr()

