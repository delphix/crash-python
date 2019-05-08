#!/bin/bash

if [[ "$EUID" -ne "0" ]]; then
	echo "Must be run as root"
	exit 1
fi

TOP=$(git rev-parse --show-toplevel 2>/dev/null)
if [[ -z "$TOP" ]]; then
	echo "Must be run inside the git repsitory."
	exit 1
fi

export PYTHONPATH="/usr/local/lib/python3.6/site-packages:$PYTHONPATH"
export LD_LIBRARY_PATH="/usr/local/lib:$LD_LIBRARY_PATH"
export PATH="/usr/local/bin:$PATH"

GDB="/usr/local/bin/gdb"
VMLINUX="/usr/lib/debug/boot/vmlinux-$(uname -r)"

GDBINIT=$(mktemp)
trap "rm '$GDBINIT'" EXIT

STEXT_KALLSYMS=$(awk '$3 == "_stext" { print $1 }' /proc/kallsyms)
STEXT_VMLINUX=$(nm "$VMLINUX" | awk '$3 == "_stext" { print $1 }')

OFFSET=$(python -c "print(int('$STEXT_KALLSYMS', 16) - int('$STEXT_VMLINUX', 16))")

pushd "$TOP" >/dev/null
rm -rf ./build/lib/crash
python3 setup.py build >/dev/null
popd >/dev/null

#
# XXX: This is a terrible hack, but since Ubuntu ships it's own kernel
# modules for ZFS, we end up having two of each ZFS related module
# installed under /lib/modules/$RELEASE. Thus, when we attempt to load
# the ZFS module symbols via the "mods.py" file below, it will use the
# first module it finds under /lib/modules/$RELEASE, and this happens to
# be the Ubuntu-shipped modules, not our Delphix modules. This is
# problematic since we're running the Delphix modules, not the Ubuntu
# modules for ZFS. Thus, to avoid this confusion, and coerce the
# "mods.py" logic to find the Delphix modules, we rename the Ubuntu
# modules on the fly, here.
#
find /lib/modules/$(uname -r)/kernel/zfs -name '*.ko' -exec mv {} {}.orig \;

cat <<EOF >"$GDBINIT"
set python print-stack full
set height 0
set print pretty on

add-symbol-file $VMLINUX -o $OFFSET
target core /proc/kcore

python
sys.path.insert(0, '$TOP/build/lib')
end

python
import crash.session
x = crash.session.Session(None, None, None)
end
EOF

$GDB -nh -x "$GDBINIT"
