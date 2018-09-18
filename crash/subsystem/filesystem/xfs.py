# -*- coding: utf-8 -*-
# vim:set shiftwidth=4 softtabstop=4 expandtab textwidth=79:

from crash.infra import CrashBaseClass, export
from crash.types.list import list_for_each_entry
from crash.util import container_of, decode_uuid_t, decode_flags
from crash.subsystem.storage import register_bio_decoder, block_device_name
import gdb

# XFS inode locks
XFS_IOLOCK_EXCL     = 0x01
XFS_IOLOCK_SHARED   = 0x02
XFS_ILOCK_EXCL      = 0x04
XFS_ILOCK_SHARED    = 0x08
XFS_MMAPLOCK_EXCL   = 0x10
XFS_MMAPLOCK_SHARED = 0x20

XFS_LOCK_MASK       = 0x3f

XFS_LOCK_FLAGS = {
    XFS_IOLOCK_EXCL     : "XFS_IOLOCK_EXCL",
    XFS_IOLOCK_SHARED   : "XFS_IOLOCK_SHARED",
    XFS_ILOCK_EXCL      : "XFS_ILOCK_EXCL",
    XFS_ILOCK_SHARED    : "XFS_ILOCK_SHARED",
    XFS_MMAPLOCK_EXCL   : "XFS_MMAPLOCK_EXCL",
    XFS_MMAPLOCK_SHARED : "XFS_MMAPLOCK_SHARED",
}

XFS_LI_EFI              = 0x1236
XFS_LI_EFD              = 0x1237
XFS_LI_IUNLINK          = 0x1238
XFS_LI_INODE            = 0x123b  # aligned ino chunks, var-size ibufs
XFS_LI_BUF              = 0x123c  # v2 bufs, variable sized inode bufs
XFS_LI_DQUOT            = 0x123d
XFS_LI_QUOTAOFF         = 0x123e

XFS_LI_TYPES = {
    XFS_LI_EFI : "XFS_LI_EFI",
    XFS_LI_EFD : "XFS_LI_EFD",
    XFS_LI_IUNLINK : "XFS_LI_IUNLINK",
    XFS_LI_INODE : "XFS_LI_INODE",
    XFS_LI_BUF : "XFS_LI_BUF",
    XFS_LI_EFI : "XFS_LI_EFI",
    XFS_LI_DQUOT : "XFS_LI_DQUOT",
    XFS_LI_QUOTAOFF : "XFS_LI_QUOTAOFF",
}

XFS_BLI_HOLD            = 0x01
XFS_BLI_DIRTY           = 0x02
XFS_BLI_STALE           = 0x04
XFS_BLI_LOGGED          = 0x08
XFS_BLI_INODE_ALLOC_BUF = 0x10
XFS_BLI_STALE_INODE     = 0x20
XFS_BLI_INODE_BUF       = 0x40

XFS_BLI_FLAGS = {
    XFS_BLI_HOLD              :         "HOLD",
    XFS_BLI_DIRTY             :        "DIRTY",
    XFS_BLI_STALE             :        "STALE",
    XFS_BLI_LOGGED            :       "LOGGED",
    XFS_BLI_INODE_ALLOC_BUF   : "INODE_ALLOC",
    XFS_BLI_STALE_INODE       :  "STALE_INODE",
    XFS_BLI_INODE_BUF         :    "INODE_BUF",
}

XBF_READ        = (1 << 0)  # buffer intended for reading from device
XBF_WRITE       = (1 << 1)  # buffer intended for writing to device
XBF_MAPPED      = (1 << 2)  # buffer mapped (b_addr valid)
XBF_ASYNC       = (1 << 4)  # initiator will not wait for completion
XBF_DONE        = (1 << 5)  # all pages in the buffer uptodate
XBF_DELWRI      = (1 << 6)  # buffer has dirty pages
XBF_STALE       = (1 << 7)  # buffer has been staled, do not find it
XBF_ORDERED     = (1 << 11) # use ordered writes
XBF_READ_AHEAD  = (1 << 12) # asynchronous read-ahead
XBF_LOG_BUFFER  = (1 << 13) # this is a buffer used for the log

# flags used only as arguments to access routines
XBF_LOCK        = (1 << 14) # lock requested
XBF_TRYLOCK     = (1 << 15) # lock requested, but do not wait
XBF_DONT_BLOCK  = (1 << 16) # do not block in current thread

# flags used only internally
_XBF_PAGES      = (1 << 18) # backed by refcounted pages
_XBF_RUN_QUEUES = (1 << 19) # run block device task queue
_XBF_KMEM       = (1 << 20) # backed by heap memory
_XBF_DELWRI_Q   = (1 << 21) # buffer on delwri queue
_XBF_LRU_DISPOSE = (1 << 24) # buffer being discarded

XFS_BUF_FLAGS = {
    XBF_READ             : "READ",
    XBF_WRITE            : "WRITE",
    XBF_MAPPED           : "MAPPED",
    XBF_ASYNC            : "ASYNC",
    XBF_DONE             : "DONE",
    XBF_DELWRI           : "DELWRI",
    XBF_STALE            : "STALE",
    XBF_ORDERED          : "ORDERED",
    XBF_READ_AHEAD       : "READ_AHEAD",
    XBF_LOCK             : "LOCK",       # should never be set
    XBF_TRYLOCK          : "TRYLOCK",    # ditto
    XBF_DONT_BLOCK       : "DONT_BLOCK", # ditto
    _XBF_PAGES           : "PAGES",
    _XBF_RUN_QUEUES      : "RUN_QUEUES",
    _XBF_KMEM            : "KMEM",
    _XBF_DELWRI_Q        : "DELWRI_Q",
    _XBF_LRU_DISPOSE     : "LRU_DISPOSE",
}

XFS_ILOG_CORE      = 0x001
XFS_ILOG_DDATA     = 0x002
XFS_ILOG_DEXT      = 0x004
XFS_ILOG_DBROOT    = 0x008
XFS_ILOG_DEV       = 0x010
XFS_ILOG_UUID      = 0x020
XFS_ILOG_ADATA     = 0x040
XFS_ILOG_AEXT      = 0x080
XFS_ILOG_ABROOT    = 0x100
XFS_ILOG_DOWNER    = 0x200
XFS_ILOG_AOWNER    = 0x400
XFS_ILOG_TIMESTAMP = 0x4000

XFS_ILI_FLAGS = {
    XFS_ILOG_CORE      : "CORE",
    XFS_ILOG_DDATA     : "DDATA",
    XFS_ILOG_DEXT      : "DEXT",
    XFS_ILOG_DBROOT    : "DBROOT",
    XFS_ILOG_DEV       : "DEV",
    XFS_ILOG_UUID      : "UUID",
    XFS_ILOG_ADATA     : "ADATA",
    XFS_ILOG_AEXT      : "AEXT",
    XFS_ILOG_ABROOT    : "ABROOT",
    XFS_ILOG_DOWNER    : "DOWNER",
    XFS_ILOG_AOWNER    : "AOWNER",
    XFS_ILOG_TIMESTAMP : "TIMESTAMP",
}

XFS_MOUNT_WSYNC         = (1 << 0)
XFS_MOUNT_UNMOUNTING    = (1 << 1)
XFS_MOUNT_DMAPI         = (1 << 2)
XFS_MOUNT_WAS_CLEAN     = (1 << 3)
XFS_MOUNT_FS_SHUTDOWN   = (1 << 4)
XFS_MOUNT_DISCARD       = (1 << 5)
XFS_MOUNT_NOALIGN       = (1 << 7)
XFS_MOUNT_ATTR2         = (1 << 8)
XFS_MOUNT_GRPID         = (1 << 9)
XFS_MOUNT_NORECOVERY    = (1 << 10)
XFS_MOUNT_DFLT_IOSIZE   = (1 << 12)
XFS_MOUNT_SMALL_INUMS   = (1 << 14)
XFS_MOUNT_32BITINODES   = (1 << 15)
XFS_MOUNT_NOUUID        = (1 << 16)
XFS_MOUNT_BARRIER       = (1 << 17)
XFS_MOUNT_IKEEP         = (1 << 18)
XFS_MOUNT_SWALLOC       = (1 << 19)
XFS_MOUNT_RDONLY        = (1 << 20)
XFS_MOUNT_DIRSYNC       = (1 << 21)
XFS_MOUNT_COMPAT_IOSIZE = (1 << 22)
XFS_MOUNT_FILESTREAMS   = (1 << 24)
XFS_MOUNT_NOATTR2       = (1 << 25)

XFS_MOUNT_FLAGS = {
    XFS_MOUNT_WSYNC         : "WSYNC",
    XFS_MOUNT_UNMOUNTING    : "UNMOUNTING",
    XFS_MOUNT_DMAPI         : "DMAPI",
    XFS_MOUNT_WAS_CLEAN     : "WAS_CLEAN",
    XFS_MOUNT_FS_SHUTDOWN   : "FS_SHUTDOWN",
    XFS_MOUNT_DISCARD       : "DISCARD",
    XFS_MOUNT_NOALIGN       : "NOALIGN",
    XFS_MOUNT_ATTR2         : "ATTR2",
    XFS_MOUNT_GRPID         : "GRPID",
    XFS_MOUNT_NORECOVERY    : "NORECOVERY",
    XFS_MOUNT_DFLT_IOSIZE   : "DFLT_IOSIZE",
    XFS_MOUNT_SMALL_INUMS   : "SMALL_INUMS",
    XFS_MOUNT_32BITINODES   : "32BITINODES",
    XFS_MOUNT_NOUUID        : "NOUUID",
    XFS_MOUNT_BARRIER       : "BARRIER",
    XFS_MOUNT_IKEEP         : "IKEEP",
    XFS_MOUNT_SWALLOC       : "SWALLOC",
    XFS_MOUNT_RDONLY        : "RDONLY",
    XFS_MOUNT_DIRSYNC       : "DIRSYNC",
    XFS_MOUNT_COMPAT_IOSIZE : "COMPAT_IOSIZE",
    XFS_MOUNT_FILESTREAMS   : "FILESTREAMS",
    XFS_MOUNT_NOATTR2       : "NOATTR2",
}



class XFSFileSystem(CrashBaseClass):
    __types__ = [ 'struct xfs_log_item',
                  'struct xfs_buf_log_item',
                  'struct xfs_inode_log_item',
                  'struct xfs_efi_log_item',
                  'struct xfs_efd_log_item',
                  'struct xfs_dq_logitem',
                  'struct xfs_qoff_logitem',
                  'struct xfs_inode',
                  'struct xfs_mount *',
                  'struct xfs_buf *' ]
    __type_callbacks__ = [
        ('struct xfs_ail', '_detect_ail_version') ]
    __symbol_callbacks__ = [
            ('xfs_buf_bio_end_io', '_register_xfs_buf_bio_end_io') ]

    @classmethod
    def _register_xfs_buf_bio_end_io(cls, sym):
        register_bio_decoder(sym, cls.decode_xfs_buf_bio_end_io)

    @classmethod
    def decode_xfsbuf(cls, xfsbuf):

        chain = {
            'description' : "{:x} xfsbuf: offset {}, size {}, block number {}".format(
                int(xfsbuf), xfsbuf['b_file_offset'],
                xfsbuf['b_buffer_length'], xfsbuf['b_bn']),
            'fstype' : 'xfs',
            'xfsbuf' : xfsbuf,
        }
        return chain

    @classmethod
    def decode_xfs_buf_bio_end_io(cls, bio):
        xfsbuf = bio['bi_private'].cast(cls.xfs_buf_p_type)
        fstype = "xfs"
        devname = block_device_name(bio['bi_bdev'])
        chain = {
            'description' : "{:x} bio: {} buffer on {}".format(int(bio), fstype, devname),
            'bio' : bio,
            'fstype' : fstype,
            'devname' : devname,
            'next' : xfsbuf,
            'decode' : cls.decode_xfsbuf,
        }

        return chain


    @classmethod
    def _detect_ail_version(cls, gdbtype):
        if 'ail_head' in gdbtype:
            cls.ail_head_name = 'ail_head'
        else:
            cls.ail_head_name = 'xa_ail'

    @export
    @classmethod
    def xfs_inode(cls, vfs_inode):
        """
        Converts a VFS inode to a xfs inode

        This method converts a struct inode to a struct xfs_inode.

        Args:
            vfs_inode (gdb.Value<struct inode>): The struct inode to convert
                to a struct xfs_inode

        Returns:
            gdb.Value<struct xfs_inode>: The converted struct xfs_inode
        """
        return container_of(vfs_inode, cls.xfs_inode, 'i_vnode')

    @export
    @classmethod
    def xfs_mount(cls, sb):
        """
        Converts a VFS superblock to a xfs mount

        This method converts a struct super_block to a struct xfs_mount *

        Args:
            super_block (gdb.Value<struct super_block>): The struct super_block
                to convert to a struct xfs_fs_info.

        Returns:
            gdb.Value<struct xfs_mount *>: The converted struct xfs_mount
        """
        return sb['s_fs_info'].cast(cls.xfs_mount_p_type)

    @export
    @staticmethod
    def xfs_mount_flags(mp):
        return decode_flags(mp['m_flags'], XFS_MOUNT_FLAGS)

    @export
    @staticmethod
    def xfs_mount_uuid(mp):
        return decode_uuid_t(mp['m_sb']['sb_uuid'])

    @export
    @staticmethod
    def xfs_mount_version(mp):
        return int(mp['m_sb']['sb_versionnum']) & 0xf

    @export
    @classmethod
    def xfs_for_each_ail_entry(cls, ail):
        """
        Iterates over the XFS Active Item Log and returns each item

        Args:
            ail (gdb.Value<struct xfs_ail>): The XFS AIL to iterate

        Yields:
            gdb.Value<struct xfs_log_item>
        """
        head = ail[cls.ail_head_name]
        for item in list_for_each_entry(head, cls.xfs_log_item_type, 'li_ail'):
            yield item

    @export
    @classmethod
    def xfs_for_each_ail_log_item(cls, mp):
        """
        Iterates over the XFS Active Item Log and returns each item

        Args:
            mp (gdb.Value<struct xfs_mount>): The XFS mount to iterate

        Yields:
            gdb.Value<struct xfs_log_item>
        """
        for item in cls.xfs_for_each_ail_entry(mp['m_ail']):
            yield item

    @classmethod
    def item_to_buf_log_item(cls, item):
        """
        Converts an xfs_log_item to an xfs_buf_log_item

        Args:
            item (gdb.Value<struct xfs_log_item>): The log item to convert

        Returns:
            gdb.Value<struct xfs_buf_log_item>

        Raises:
            TypeError: The type of log item is not XFS_LI_BUF
        """
        if item['li_type'] != XFS_LI_BUF:
            raise TypeError("item is not a buf log item")
        return container_of(item, cls.xfs_buf_log_item_type, 'bli_item')

    @classmethod
    def item_to_inode_log_item(cls, item):
        """
        Converts an xfs_log_item to an xfs_inode_log_item

        Args:
            item (gdb.Value<struct xfs_log_item>): The log item to convert

        Returns:
            gdb.Value<struct xfs_inode_log_item>

        Raises:
            TypeError: The type of log item is not XFS_LI_INODE
        """
        if item['li_type'] != XFS_LI_INODE:
            raise TypeError("item is not an inode log item")
        return container_of(item, cls.xfs_inode_log_item_type, 'ili_item')

    @classmethod
    def item_to_efi_log_item(cls, item):
        """
        Converts an xfs_log_item to an xfs_efi_log_item

        Args:
            item (gdb.Value<struct xfs_log_item>): The log item to convert

        Returns:
            gdb.Value<struct xfs_efi_log_item>

        Raises:
            TypeError: The type of log item is not XFS_LI_EFI
        """
        if item['li_type'] != XFS_LI_EFI:
            raise TypeError("item is not an EFI log item")
        return container_of(item, cls.xfs_efi_log_item_type, 'efi_item')

    @classmethod
    def item_to_efd_log_item(cls, item):
        """
        Converts an xfs_log_item to an xfs_efd_log_item

        Args:
            item (gdb.Value<struct xfs_log_item>): The log item to convert

        Returns:
            gdb.Value<struct xfs_efd_log_item>

        Raises:
            TypeError: The type of log item is not XFS_LI_EFD
        """
        if item['li_type'] != XFS_LI_EFD:
            raise TypeError("item is not an EFD log item")
        return container_of(item, cls.xfs_efd_log_item_type, 'efd_item')

    @classmethod
    def item_to_dquot_log_item(cls, item):
        """
        Converts an xfs_log_item to an xfs_dquot_log_item

        Args:
            item (gdb.Value<struct xfs_log_item>): The log item to convert

        Returns:
            gdb.Value<struct xfs_dquot_log_item>

        Raises:
            TypeError: The type of log item is not XFS_LI_DQUOT
        """
        if item['li_type'] != XFS_LI_DQUOT:
            raise TypeError("item is not an DQUOT log item")
        return container_of(item, cls.xfs_dq_logitem_type, 'qli_item')

    @classmethod
    def item_to_quotaoff_log_item(cls, item):
        """
        Converts an xfs_log_item to an xfs_quotaoff_log_item

        Args:
            item (gdb.Value<struct xfs_log_item>): The log item to convert

        Returns:
            gdb.Value<struct xfs_quotaoff_log_item>

        Raises:
            TypeError: The type of log item is not XFS_LI_QUOTAOFF
        """
        if item['li_type'] != XFS_LI_QUOTAOFF:
            raise TypeError("item is not an QUOTAOFF log item")
        return container_of(item, cls.xfs_qoff_logitem_type, 'qql_item')

    @export
    @classmethod
    def xfs_log_item_typed(cls, item):
        """
        Returns the log item converted from the generic type to the actual type

        Args:
            item (gdb.Value<struct xfs_log_item>): The struct xfs_log_item to
                convert.

        Returns:
            Depending on the item type, one of:
            gdb.Value<struct xfs_buf_log_item_type>
            gdb.Value<struct xfs_inode_log_item_type>
            gdb.Value<struct xfs_efi_log_item_type>
            gdb.Value<struct xfs_efd_log_item_type>
            gdb.Value<struct xfs_dq_logitem>
            int (for UNLINK item)

        Raises:
            RuntimeError: An unexpected item type was encountered
        """
        li_type = int(item['li_type'])
        if li_type == XFS_LI_BUF:
            return cls.item_to_buf_log_item(item)
        elif li_type == XFS_LI_INODE:
            return cls.item_to_inode_log_item(item)
        elif li_type == XFS_LI_EFI:
            return cls.item_to_efi_log_item(item)
        elif li_type == XFS_LI_EFD:
            return cls.item_to_efd_log_item(item)
        elif li_type == XFS_LI_IUNLINK:
            # There isn't actually any type information for this
            return li_type
        elif li_type == XFS_LI_DQUOT:
            return cls.item_to_dquot_log_item(item)
        elif li_type == XFS_LI_QUOTAOFF:
            return cls.item_to_quotaoff_log_item(item)
        raise RuntimeError("Unknown AIL item type {:x}".format(li_type))

    @export
    @classmethod
    def xfs_format_xfsbuf(cls, buf):
        state = ""
        bflags = []
        b_flags = int(buf['b_flags'])

        for flag in XFS_BUF_FLAGS.keys():
            if flag & b_flags:
                bflags.append(XFS_BUF_FLAGS[flag])

        if buf['b_pin_count']['counter']:
            state += "P"
        if buf['b_sema']['count'] >= 0:
            state += "L"

        return ("blockno={} b_flags={} [state={}]"
                .format(buf['b_bn'], "|".join(bflags), state))

    @export
    @classmethod
    def xfs_for_each_ail_log_item_typed(cls, mp):
        """
        Iterates over the XFS Active Item Log and returns each item, resolved
        to the specific type.

        Args:
            mp (gdb.Value<struct xfs_mount>): The XFS mount to iterate

        Yields:
            Depending on the item type, one of:
            gdb.Value<struct xfs_buf_log_item_type>
            gdb.Value<struct xfs_inode_log_item_type>
            gdb.Value<struct xfs_efi_log_item_type>
            gdb.Value<struct xfs_efd_log_item_type>
            gdb.Value<struct xfs_dq_logitem>
        """
        for item in cls.xfs_for_each_ail_log_item(mp):
            yield cls.xfs_log_item_typed(item)
