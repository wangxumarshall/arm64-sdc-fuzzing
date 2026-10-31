#!/bin/bash
# patch_movbe_l1d_variants.sh
#
# Binary-patch the CONFIRMED trigger movbe_l1d to produce single-instruction
# variants, keeping ALL other bytes (ldr/str addressing mode, register alloc,
# scheduling) byte-identical. This isolates ONE variable — the pre-str ALU
# instruction's identity (rev vs mul vs add vs nop) — without perturbing the
# AGU/L1D timing the way a C rewrite or a hand-written asm rewrite would
# (see memory movbe-l1d-variants-schedule-sensitivity).
#
# Patch target: rev w3,w4  (bytes 83 08 c0 5a, LE) at file offset 0xbae7c
#   = virtual addr 0xbae7c (LOAD seg 0: fileoff == vaddr, confirmed).
#
# Variants (replace ONLY this 4-byte instruction):
#   movbe_l1d_patch_mul  : rev -> mul w3,w4,w4  (83 7c 04 1b)  HIGH current
#   movbe_l1d_patch_add  : rev -> add w3,w4,w4  (83 00 04 0b)  LOW current
#   movbe_l1d_patch_nop : rev -> nop            (1f 20 03 d5)  no current
# (baseline = the unpatched movbe_l1d, which we run as-is.)
#
# DECISION: if baseline (rev) triggers AND mul/add/nop variants diverge, the
# pre-str instruction's transient current is a modulating variable. If they
# all trigger identically, current is NOT the variable (it's the AGU/L1D path
# adjacency alone). Either way, no compiler confound because nothing else
# moved.
#
# NOTE: the patched binary still has the TEST registered under the SAME name
# "movbe_l1d" (we only changed instruction bytes, not the test list). So we
# run all three variants by running --enable=movbe_l1d on each patched copy;
# the log filename disambiguates them.
set -u
cd /home/sdc/root/arm64-sdc-fuzzing/opendcdiag
SRC=./builddir/opendcdiag
OFF=0xbae7c                       # file offset of rev w3,w4
ORIG=$(xxd -s $OFF -l 4 -p "$SRC") # expect 8308c05a
echo "orig bytes at $OFF: $ORIG (expect 8308c05a = rev w3,w4)"
if [ "$ORIG" != "8308c05a" ]; then
  echo "!! offset mismatch — aborting (binary changed, recompute offset)"
  exit 1
fi

declare -A PATCH
PATCH[mul]=837c041b     # mul w3,w4,w4
PATCH[add]=8300040b     # add w3,w4,w4  (note: 0b not b0)
PATCH[nop]=1f2003d5     # nop

for v in mul add nop; do
  OUT="./builddir/opendcdiag_${v}"
  cp "$SRC" "$OUT"
  printf "$(echo ${PATCH[$v]} | sed 's/../\\x&/g')" > /tmp/_bytes_$v
  # write 4 bytes at offset
  dd if=/tmp/_bytes_$v of="$OUT" bs=1 seek=$((OFF)) count=4 conv=notrunc 2>/dev/null
  echo "=== patched $v: ${PATCH[$v]} -> $OUT ==="
  # verify via objdump at the patched offset
  objdump -d --start-address=$OFF --stop-address=$((OFF+4)) "$OUT" 2>/dev/null | grep -E "$OFF|mul|add|nop"
  echo
done

echo "=== sanity: baseline unchanged, run a 5s smoke (should still trigger eventually) ==="
echo "Patched binaries ready in builddir/ — run with --enable=movbe_l1d on each."