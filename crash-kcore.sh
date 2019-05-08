#!/bin/bash

if [[ "$EUID" -ne "0" ]]; then
    echo "must be root"
    exit 1
fi

GDB="/usr/local/bin/gdb"
VMLINUX="/usr/lib/debug/boot/vmlinux-$(uname -r)"

GDBINIT=$(mktemp)
trap "rm '$GDBINIT'" EXIT

STEXT_KALLSYMS=$(awk '$3 == "_stext" { print $1 }' /proc/kallsyms)
STEXT_VMLINUX=$(nm "$VMLINUX" | awk '$3 == "_stext" { print $1 }')

OFFSET=$(python -c "print(int('$STEXT_KALLSYMS', 16) - int('$STEXT_VMLINUX', 16))")

cat <<EOF >"$GDBINIT"
add-symbol-file $VMLINUX -o $OFFSET
core-file /proc/kcore
EOF

$GDB -nh -x "$GDBINIT"
