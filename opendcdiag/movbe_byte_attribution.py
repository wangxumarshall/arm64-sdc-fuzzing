#!/usr/bin/env python3
"""
Byte-level attribution analysis for movbe_dump SDC samples.

Established facts:
  - actual           = true original input[i]  (reconstructed[index]==actual, 9/9)
  - logged_input     = the CORRUPTED reload of data->input[i]
  - swapped[j]       = bswap32(input[j])  (the store data written in the hot path)
  - 32-bit match tests: logged_input == bswap32(actual) -> 0/9
                         logged_input in swapped[] elsewhere   -> 0/9
                         logged_input in input[] nearby         -> 3/9 (within +/-4 CL)

This script does THREE byte-level analyses on all 9 samples:

(1) 4-BYTE SLIDING WINDOW  [strongest / most falsifiable]
    Treat input[] and swapped[] as little-endian byte buffers and slide a
    4-byte window over ALL byte offsets (not just element-aligned ones).
    If logged_input appears at a NON-element-aligned offset (m = start%4 != 0),
    the load literally read a 4-byte span straddling two adjacent elements --
    direct evidence of a byte-granular address misresolution in the load path.
    Expected accidental hit rate per sample: ~ (#windows)/2^32 ~ 5e-7, so ANY
    non-aligned hit is highly significant.

(2) PER-BYTE ATTRIBUTION (same byte position, +/-4 cachelines)
    For each byte position k of logged_input, find nearby input[j]/swapped[j]
    whose byte k equals it.  Records nearest j per byte.  Classifies each
    sample: all 4 / partial(2-3) / none(0-1) bytes attributable.

(3) MIN-BYTE-DIFFERENCE  nearest element
    Nearest input[j] and swapped[j] (by count of differing bytes) within
    +/-4 cachelines, to see if logged_input is "almost" a real neighbor.

A random baseline (1000 trials over the same buffers) gives expected counts so
significance is judgeable.
"""
import struct, random

M = (1 << 31) - 1
A = 48271
BUFSIZE = 1 << 14

def lcg_next(s): return (A * s) % M
def generate32_sequence(seed, n):
    state = seed; out = []
    for _ in range(n):
        state = lcg_next(state); lo = state & 0xffff
        state = lcg_next(state); hi = state & 0xffff
        out.append((lo | (hi << 16)) & 0xffffffff)
    return out
def bswap32(x):
    return (((x & 0xFF) << 24) | ((x & 0xFF00) << 8) |
            ((x & 0xFF0000) >> 8) | ((x & 0xFF000000) >> 24)) & 0xFFFFFFFF

SAMPLES = [
    (1711090087, 7281,  0xD9AC5B04, 0x55CD219B),
    (1072812489, 6957,  0x7A791E57, 0x20966DA5),
    (1072812489, 12518, 0x37CC785B, 0xAA8E052B),
    (1047109210, 8764,  0x376C8DA4, 0x82103ADC),
    (763356360,  150,   0x17FBEF55, 0xC64B4698),
    (1314873594, 1303,  0x3276B190, 0x19E741C8),
    (1711090087, 7515,  0xE7BB53D8, 0xEDAA9FEB),
    (1711090087, 10692, 0x685CB1E8, 0x6C1A7598),
    (1711090087, 15732, 0x42419715, 0x1BF3A599),
]
SEEDS = sorted(set(s[0] for s in SAMPLES))
INPUT = {sd: generate32_sequence(sd, BUFSIZE) for sd in SEEDS}
SWAPPED = {sd: [bswap32(v) for v in INPUT[sd]] for sd in SEEDS}
for (sd, idx, lin, act) in SAMPLES:
    assert INPUT[sd][idx] == act
    assert SWAPPED[sd][idx] == bswap32(act)

def to_bytes(arr): return b''.join(struct.pack('<I', v) for v in arr)
INB = {sd: to_bytes(INPUT[sd]) for sd in SEEDS}
SWB = {sd: to_bytes(SWAPPED[sd]) for sd in SEEDS}

HALF = 4 * 16                 # +/-4 cachelines = +/-64 elements = +/-256 bytes
def window_lo_hi(idx):
    lo = max(0, idx * 4 - HALF * 4)
    hi = min(BUFSIZE * 4 - 4, idx * 4 + HALF * 4)   # inclusive start upper bound
    return lo, hi

def b3b2b1b0(v):              # MSB-first hex byte string, matching dump format
    return f"{(v>>24)&0xFF:02X}{(v>>16)&0xFF:02X}{(v>>8)&0xFF:02X}{v&0xFF:02X}"

def slide_window(buf, idx, target):
    """Return list of dicts for 4-byte LE windows == target, within +/-4 CL."""
    lo, hi = window_lo_hi(idx)
    res = []
    for start in range(lo, hi + 1):
        if struct.unpack('<I', buf[start:start+4])[0] == target:
            j = start // 4
            m = start - j * 4
            res.append({'start': start, 'j': j, 'm': m,
                        'bytedelta': start - idx * 4,
                        'elem_delta': j - idx})
    return res

def byte_pos(v, k):           # k=0 LSB .. 3 MSB
    return (v >> (8 * k)) & 0xFF

# ---------------------------------------------------------------- analysis (1)
print("=" * 88)
print("ANALYSIS 1: 4-BYTE SLIDING WINDOW (byte-granular address misresolution test)")
print("  Does logged_input appear as a 4-byte LE window over input[]/swapped[]")
print("  at a NON-element-aligned offset (m = start%4 != 0)?  Such a hit means the")
print("  load spanned two adjacent elements -> byte-level load-address corruption.")
print("=" * 88)
aligned_hits = misaligned_hits = 0
for (sd, idx, lin, act) in SAMPLES:
    mi = slide_window(INB[sd], idx, lin)
    ms = slide_window(SWB[sd], idx, lin)
    print(f"\n  seed={sd} idx={idx} logged_input=0x{lin:08X} [{b3b2b1b0(lin)}]")
    for label, ms_ in (("input[]", mi), ("swapped[]", ms)):
        if not ms_:
            print(f"    {label}: no 4-byte window match within +/-4 CL")
            continue
        for h in ms_:
            kind = "ALIGNED (m=0, full element)" if h['m'] == 0 else \
                   f"MISALIGNED (m={h['m']}, byte-straddle!)"
            if h['m'] == 0: aligned_hits += 1
            else: misaligned_hits += 1
            print(f"    {label}: {kind}  start_byte={h['start']} j={h['j']} "
                  f"(elem_delta={h['elem_delta']:+d}, byte_delta={h['bytedelta']:+d})")
print(f"\n  >>> aligned full-element hits   (m=0) : {aligned_hits}/9-sample-scans")
print(f"  >>> MISALIGNED byte-straddle hits(m!=0): {misaligned_hits}/9-sample-scans  "
      f"[random expected ~ {9*(2*HALF*4)/2**32:.1e}]")

# ------------------------------------------------------ analysis (2) per-byte
print("\n" + "=" * 88)
print("ANALYSIS 2: PER-BYTE ATTRIBUTION (same byte position k, +/-4 cachelines)")
print("  For each byte k of logged_input, find nearest input[j]/swapped[j] whose")
print("  byte k equals it.  byte0=LSB(addr+0) ... byte3=MSB(addr+3).")
print("=" * 88)
cat_all = cat_part = cat_none = 0
for (sd, idx, lin, act) in SAMPLES:
    lo, hi = window_lo_hi(idx)
    jlo, jhi = lo // 4, hi // 4 + 1
    inp = INPUT[sd]; swp = SWAPPED[sd]
    print(f"\n  seed={sd} idx={idx} logged_input=0x{lin:08X} "
          f"= bytes b3..b0 [{b3b2b1b0(lin)}]")
    attributed = 0
    srcs = []
    for k in range(4):
        bk = byte_pos(lin, k)
        # nearest same-position match in input[] then swapped[]
        best_in = best_sw = None
        for j in range(jlo, jhi):
            if j == idx: continue
            d = abs(j - idx)
            if byte_pos(inp[j], k) == bk and (best_in is None or d < best_in[1]):
                best_in = (j, d)
            if byte_pos(swp[j], k) == bk and (best_sw is None or d < best_sw[1]):
                best_sw = (j, d)
        line = f"    byte{k}(=0x{bk:02X}): "
        if best_in and best_sw:
            d = best_in[1]; d2 = best_sw[1]
            chosen = ('input', best_in) if d <= d2 else ('swapped', best_sw)
            srcs.append((chosen[0], chosen[1][0], k))
            attributed += 1
            line += (f"input[j={best_in[0]} Δ{best_in[1]:+d}] AND "
                     f"swapped[j={best_sw[0]} Δ{best_sw[1]:+d}] -> {chosen[0]}")
        elif best_in:
            srcs.append(('input', best_in[0], k)); attributed += 1
            line += f"input[j={best_in[0]} Δ{best_in[1]:+d}]"
        elif best_sw:
            srcs.append(('swapped', best_sw[0], k)); attributed += 1
            line += f"swapped[j={best_sw[0]} Δ{best_sw[1]:+d}]"
        else:
            line += "NO same-position match in +/-4 CL"
        print(line)
    distinct_j = len(set((s[0], s[1]) for s in srcs))
    if attributed == 4:   cat_all += 1
    elif attributed >= 2: cat_part += 1
    else:                 cat_none += 1
    print(f"    -> {attributed}/4 bytes attributable; "
          f"distinct source (array,j) = {distinct_j}; "
          f"{'ALL-4' if attributed==4 else 'PARTIAL' if attributed>=2 else 'NOISE'}")

print(f"\n  >>> all 4 bytes attributable : {cat_all}/9")
print(f"  >>> partial (2-3)            : {cat_part}/9")
print(f"  >>> noise (0-1)              : {cat_none}/9")

# ------------------------------------------------- analysis (3) min byte diff
print("\n" + "=" * 88)
print("ANALYSIS 3: NEAREST ELEMENT BY BYTE-DIFFERENCE (within +/-4 cachelines)")
print("  Closest input[j] / swapped[j] to logged_input; #bytes that match (of 4).")
print("=" * 88)
for (sd, idx, lin, act) in SAMPLES:
    inp = INPUT[sd]; swp = SWAPPED[sd]
    lo, hi = window_lo_hi(idx); jlo, jhi = lo // 4, hi // 4 + 1
    best_in = best_sw = None
    for j in range(jlo, jhi):
        if j == idx: continue
        di = sum(1 for k in range(4) if byte_pos(inp[j], k) == byte_pos(lin, k))
        ds = sum(1 for k in range(4) if byte_pos(swp[j], k) == byte_pos(lin, k))
        if best_in is None or di > best_in[1]: best_in = (j, di)
        if best_sw is None or ds > best_sw[1]: best_sw = (j, ds)
    bi = best_in[1] if best_in else -1
    bs = best_sw[1] if best_sw else -1
    bj_in = best_in[0] if best_in else -1
    bj_sw = best_sw[0] if best_sw else -1
    print(f"  seed={sd} idx={idx} logged=0x{lin:08X}: "
          f"nearest input[j={bj_in}] matches {bi}/4 bytes "
          f"(diff {4-bi}); nearest swapped[j={bj_sw}] matches {bs}/4 bytes (diff {4-bs})")

# ----------------------------------------------------- baseline (random)
print("\n" + "=" * 88)
print("BASELINE: random 32-bit target values vs same buffers (1000 trials/sample)")
print("=" * 88)
random.seed(12345)
b_aligned = b_misalign = 0
b_attr_all = b_attr_none = 0
trials = 1000
for t in range(trials):
    for (sd, idx, lin, act) in SAMPLES:
        tgt = random.getrandbits(32)
        mi = slide_window(INB[sd], idx, tgt)
        ms = slide_window(SWB[sd], idx, tgt)
        for h in mi + ms:
            if h['m'] == 0: b_aligned += 1
            else:           b_misalign += 1
        # per-byte attribution count (same-position, +/-4 CL)
        lo, hi = window_lo_hi(idx); jlo, jhi = lo//4, hi//4+1
        inp = INPUT[sd]; swp = SWAPPED[sd]
        atr = 0
        for k in range(4):
            bk = (tgt >> (8*k)) & 0xFF
            ok = False
            for j in range(jlo, jhi):
                if j == idx: continue
                if (inp[j] >> (8*k)) & 0xFF == bk or (swp[j] >> (8*k)) & 0xFF == bk:
                    ok = True; break
            if ok: atr += 1
        if atr == 4: b_attr_all += 1
        if atr <= 1: b_attr_none += 1
print(f"  aligned full-element hits   : {b_aligned}/{trials*9} "
      f"(~{b_aligned/(trials*9):.3f} per scan)")
print(f"  MISALIGNED byte-straddle hits: {b_misalign}/{trials*9} "
      f"(~{b_misalign/(trials*9):.4f} per scan)")
print(f"  all-4-bytes attributable      : {b_attr_all}/{trials*9} "
      f"(~{b_attr_all/(trials*9):.3f} per scan)  <-- random false-positive rate")
print(f"  noise(0-1 byte)              : {b_attr_none}/{trials*9} "
      f"(~{b_attr_none/(trials*9):.3f} per scan)")
