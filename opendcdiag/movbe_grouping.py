#!/usr/bin/env python3
"""Group the 9 hits by |offset| and report byte-straddle detail for the
non-aligned ones, plus the access-sequence context from the disassembly.

Disassembly of movbe_run hot loop (aarch64, -O2, no vectorization/unroll):
  68: ldr  w5, [x1, x19, lsl #2]   ; load A:  input[i]          (addr = base + i*4)
  6c: rev  w2, w5                  ; bswap32
  70: str  w2, [x3, x19, lsl #2]   ; store:   swapped[i] = bswap
  74: ldr  w4, [x1, x19, lsl #2]   ; load B:  reload input[i]    <- CORRUPTED
  78: cmp  w4, w5
  loop: i in [0,16384), stride = 1 element (4 bytes), no unroll, scalar rev.

So the corrupted reload (load B) reads the SAME address as load A / the store.
A "hit at j" with delta = j - idx means load B returned the value that was
*correctly* present at input[j] (j != idx). For non-aligned hits (m!=0), the
4 bytes returned straddle input[j] and input[j+1].
"""
import struct

SAMPLES = [
    (1711090087, 7281,  0xD9AC5B04, 0x55CD219B, 'input', 0, 7079,  -202),
    (1072812489, 6957,  0x7A791E57, 0x20966DA5, 'input', 0, 1736,  -5221),
    (1072812489, 12518, 0x37CC785B, 0xAA8E052B, 'input', 2, 3010,  -9508),
    (1047109210, 8764,  0x376C8DA4, 0x82103ADC, 'input', 0, 8756,  -8),
    (763356360,  150,   0x17FBEF55, 0xC64B4698, 'input', 1, 35,    -115),
    (1314873594, 1303,  0x3276B190, 0x19E741C8, 'input', 2, 323,   -980),
    (1711090087, 7515,  0xE7BB53D8, 0xEDAA9FEB, 'input', 0, 7483,  -32),
    (1711090087, 10692, 0x685CB1E8, 0x6C1A7598, 'input', 3, 2670,  -8022),
    (1711090087, 15732, 0x42419715, 0x1BF3A599, 'input', 0, 15723, -9),
]

def b3b2b1b0(v): return f"{(v>>24)&0xFF:02X}{(v>>16)&0xFF:02X}{(v>>8)&0xFF:02X}{v&0xFF:02X}"

print("="*92)
print("ALL 9 HITS (sorted by |delta|), with alignment and byte-straddle detail")
print("="*92)
print(f"{'#':>2} {'idx':>6} {'delta':>7} {'|d|':>7} {'|d|*4B':>7} {'m':>2} "
      f"{'logged':>11} {'actual':>11}")
print("-"*92)
for n,(sd,idx,lin,act,arr,m,j,d) in enumerate(SAMPLES,1):
    print(f"{n:>2} {idx:>6} {d:>+7d} {abs(d):>7} {abs(d)*4:>6}B {m:>2} "
          f"0x{lin:08X} 0x{act:08X}")

# byte straddle detail for non-aligned
print()
print("="*92)
print("NON-ALIGNED HITS (m!=0): which bytes came from which element")
print("  LE layout: byte0=LSB(addr+0)..byte3=MSB(addr+3). A window at element j")
print("  with m=k spans bytes [j*4+k .. j*4+k+3], i.e. low (4-k) bytes of")
print("  input[j] as the high bytes, and high k bytes of input[j+1] as low bytes.")
print("="*92)
# reconstruct input arrays just to print the source bytes
M=(1<<31)-1; A=48271
def gen(seed,n):
    s=seed; o=[]
    for _ in range(n):
        s=(A*s)%M; lo=s&0xffff
        s=(A*s)%M; hi=s&0xffff
        o.append((lo|(hi<<16))&0xffffffff)
    return o
INPUT={sd:gen(sd,1<<14) for sd in sorted({s[0] for s in SAMPLES})}
for n,(sd,idx,lin,act,arr,m,j,d) in enumerate(SAMPLES,1):
    if m==0: continue
    lo_el = INPUT[sd][j]
    hi_el = INPUT[sd][j+1]
    lo_b = lo_el.to_bytes(4,'little')   # bytes of input[j],  addr = j*4
    hi_b = hi_el.to_bytes(4,'little')   # bytes of input[j+1]
    # window bytes [j*4+m .. j*4+m+3]: take (4-m) bytes from lo_b starting at m,
    # then m bytes from hi_b starting at 0
    win = lo_b[m:] + hi_b[:m]
    winval = int.from_bytes(win,'little')
    print(f"\n  #{n} idx={idx} delta={d} m={m}  logged=0x{lin:08X} [{b3b2b1b0(lin)}]")
    print(f"     input[j={j}]   = 0x{lo_el:08X} bytes(b3..b0) {b3b2b1b0(lo_el)}")
    print(f"     input[j+1={j+1}] = 0x{hi_el:08X} bytes(b3..b0) {b3b2b1b0(hi_el)}")
    print(f"     reconstructed window bytes(b3..b0) = {win.hex().upper()} "
          f"-> 0x{winval:08X}  {'== logged' if winval==lin else 'MISMATCH'}")
    # which original byte positions contributed
    print(f"     byte provenance (byte0..byte3 of logged):")
    for k in range(4):
        src_byte_addr = j*4 + m + k
        if src_byte_addr < (j+1)*4:
            src = f"input[{j}].byte{src_byte_addr - j*4} (=0x{lo_b[src_byte_addr-j*4]:02X})"
        else:
            off = src_byte_addr - (j+1)*4
            src = f"input[{j+1}].byte{off} (=0x{hi_b[off]:02X})"
        print(f"       logged.byte{k}=0x{(lin>>(8*k))&0xFF:02X}  <- {src}")

print()
print("="*92)
print("GROUPING by |delta| (element count and byte distance)")
print("="*92)
NEAR = []  # |d| <= ~8 elements / 32 bytes  (load-Q / store-forwarding scale)
MID  = []  # tens..hundreds of elements  (L1 cacheline / fill-buffer scale)
FAR  = []  # thousands of elements       (L1/L2 capacity scale)
for (sd,idx,lin,act,arr,m,j,d) in SAMPLES:
    ad = abs(d)
    if ad <= 8:       NEAR.append((idx,d,m))
    elif ad <= 256:   MID.append((idx,d,m))
    else:             FAR.append((idx,d,m))
print(f"\n  NEAR (|d|<=8 elems, <=32B)  : {len(NEAR)} hits")
for (idx,d,m) in NEAR:
    print(f"       idx={idx:>6} delta={d:>+6d} ({abs(d)*4}B back)  m={m}")
print(f"\n  MID  (9..256 elems, 36B..1KB): {len(MID)} hits")
for (idx,d,m) in MID:
    print(f"       idx={idx:>6} delta={d:>+6d} ({abs(d)*4}B back)  m={m}")
print(f"\n  FAR  (>256 elems, >1KB)    : {len(FAR)} hits")
for (idx,d,m) in FAR:
    print(f"       idx={idx:>6} delta={d:>+6d} ({abs(d)*4}B back)  m={m}")

print()
print("="*92)
print("HARDWARE-STRUCTURE CAPACITY REFERENCE (aarch64, Kunpeng 920)")
print("="*92)
print("""  Load queue / store-forwarding buffer : tens of entries, ~64-128 B window
      -> can only explain NEAR group (|d|<=8, <=32B).
  L1 data cache line                      : 64 B = 16 uint32
      -> explains MID group if delta is a few cachelines; |d| up to ~256
         elements = up to ~16 cachelines back, within L1 (32-48KB, 8-12 way).
  L1 capacity                             : 128 cores share L1 per-core ~64KB
      -> FAR group (|d|>256 elems / >1KB) sits INSIDE L1 capacity but spans
         many cachelines; cannot be a single store-fwd/line event. More
         consistent with 'stale L1 cacheline / wrong tag hit' or
         'cross-iteration aliasing' than with load-Q residue.
  Note: no loop unroll / no vectorization (scalar rev, stride=1). So there is
      NO fixed unroll-step or prefetch-window constant for near hits to match.
      The -8/-9/-32 near values are NOT multiples of a loop structure -> they
      reflect physical buffer geometry, not software stride.""")
