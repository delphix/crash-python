#!/bin/bash

if [[ "$EUID" -ne "0" ]]; then
	echo "Must be run as root"
	exit 1
fi

export PYTHONPATH="/usr/local/lib/python3.6/site-packages:$PYTHONPATH"
export LD_LIBRARY_PATH="/usr/local/lib:$LD_LIBRARY_PATH"
export PATH="/opt/gdb-python/bin:/usr/local/bin:$PATH"

VMLINUX="/usr/lib/debug/boot/vmlinux-$(uname -r)"

_cleanup() {
    rm -rf "$TMPDIR"
}

TMPDIR=$(mktemp -d /tmp/crash.XXXXXX)
trap _cleanup EXIT

GDBINIT="$TMPDIR/gdbinit"

cat <<EOF >"$GDBINIT"

set python print-stack full
set height 0
set print pretty on

python
from kcore.target import Target
target = Target("$VMLINUX", debug=False)
end

target drgn /proc/kcore

python
import crash.session
x = crash.session.Session(None, None, None)
target.unregister()
del target
end
EOF

gdb -nh -x "$GDBINIT"
