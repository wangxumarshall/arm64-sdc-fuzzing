#!/usr/bin/env python3
"""
Full-array + directionality analysis for movbe_dump SDC samples.

For ALL 9 samples (focus on the 6 previously-unmatched):
  1. Search the ENTIRE input[] and swapped[] arrays (all 16384 elements) for:
       (a) aligned full 32-bit element match (m=0)
       (b) NON-aligned 4-byte sliding-window match (m=1,2,3)
         -> byte-granular address straddle across two adjacent elements
  2. For every hit, record offset (j - idx) and its SIGN.
     Classify each sample's hits as:
       - backward-only  (all j < idx)   <- "stale older data"
       - forward-only  (all j > idx)
       - mixed
       - none
  3. Report the global sign distribution of all hits across all samples,
     separately for input[] and swapped[], and separately for aligned vs
     misaligned windows.
  4. Calibrate against a random baseline (1000 trials) using the same
     full-array scan and same directionality tally.

Random-expected misaligned hits per full-array scan ~ (16384*3*2)/2^32 ~ 2.3e-5,
so any misaligned hit is highly significant.
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

def slide_window_full(buf, idx, target):
    """All 4-byte LE windows == target across the WHOLE array (all byte offsets)."""
    res = []
    for start in range(0, len(buf) - 3):
        if struct.unpack('<I', buf[start:start+4])[0] == target:
            j = start // 4
            m = start - j * 4
            res.append({'start': start, 'j': j, 'm': m,
                        'elem_delta': j - idx,
                        'byte_delta': start - idx * 4})
    return res

def b3b2b1b0(v):
    return f"{(v>>24)&0xFF:02X}{(v>>16)&0xFF:02X}{(v>>8)&0xFF:02X}{v&0xFF:02X}"

# ------------------------------------------------------------- per-sample scan
print("=" * 92)
print("FULL-ARRAY SCAN: logged_input as 4-byte LE window over ENTIRE input[]/swapped[]")
print("  (aligned m=0 = whole-element read of a real element; misaligned m!=0 = byte")
print("   straddle across two adjacent elements = byte-level load-address corruption)")
print("=" * 92)
print(f"{'#':>2} {'seed':>11} {'idx':>6} {'logged_input':>13} {'array':>9} "
      f"{'m':>2} {'j':>6} {'j-idx':>7} {'sign':>5}")
print("-" * 92)

# tallies
tot_aligned_in = tot_aligned_sw = 0
tot_misalign_in = tot_misalign_sw = 0
hits_neg = hits_pos = hits_zero = 0   # across ALL hits (aligned+misalign, both arrays), excluding j==idx
per_sample_class = []   # (idx, category, list-of-deltas)
sample_has_any = 0

for n, (sd, idx, lin, act) in enumerate(SAMPLES, 1):
    mi = slide_window_full(INB[sd], idx, lin)
    ms = slide_window_full(SWB[sd], idx, lin)
    # exclude the trivial self-hit at j==idx, m==0 IF logged_input happened to equal input[idx]
    # (by construction logged_input != actual == input[idx], so no self hit; but guard anyway)
    allhits = []
    for h in mi: allhits.append(('input',  h))
    for h in ms: allhits.append(('swapped',h))
    deltas = []
    catsigned = {'backward': 0, 'forward': 0, 'self': 0}
    for arr_name, h in allhits:
        is_align = (h['m'] == 0)
        if arr_name == 'input':
            if is_align: tot_aligned_in += 1
            else:       tot_misalign_in += 1
        else:
            if is_align: tot_aligned_sw += 1
            else:       tot_misalign_sw += 1
        d = h['elem_delta']
        if d < 0:      catsigned['backward'] += 1; hits_neg += 1
        elif d > 0:    catsigned['forward'] += 1;  hits_pos += 1
        else:          catsigned['self'] += 1;      hits_zero += 1
        deltas.append(d)
        print(f"{n:>2} {sd:>11} {idx:>6} 0x{lin:08X}    {arr_name:>7} "
              f"{h['m']:>2} {h['j']:>6} {d:>+7d} {'<-' if d<0 else '->' if d>0 else '==':>5}")
    if not allhits:
        print(f"{n:>2} {sd:>11} {idx:>6} 0x{lin:08X}    NO HIT in either array (full scan)")
    # classify direction of this sample
    if catsigned['backward'] and not catsigned['forward']:
        cat = 'BACKWARD-ONLY'
    elif catsigned['forward'] and not catsigned['backward']:
        cat = 'FORWARD-ONLY'
    elif catsigned['backward'] and catsigned['forward']:
        cat = 'MIXED'
    else:
        cat = 'NONE'
    if allhits: sample_has_any += 1
    per_sample_class.append((idx, cat, deltas))

print()
print("=" * 92)
print("DIRECTIONALITY TALLY (all hits, both arrays, aligned+misaligned; j==idx excluded)")
print("=" * 92)
tot = hits_neg + hits_pos  # self (j==idx) shouldn't happen for logged_input != input[idx]
print(f"  backward  (j < idx, 'older data') : {hits_neg}")
print(f"  forward   (j > idx, 'newer data')  : {hits_pos}")
print(f"  self      (j == idx)               : {hits_zero}  (should be 0 by construction)")
print(f"  TOTAL hits                          : {tot}")
print()
print("Per-sample direction classification:")
for (idx, cat, deltas) in per_sample_class:
    ds = deltas if deltas else []
    print(f"  idx={idx:>6}: {cat:<14}  deltas={ds}")
print()
print("Hit-count breakdown by array & alignment:")
print(f"  input[]   aligned (m=0)   : {tot_aligned_in}")
print(f"  input[]   misaligned(m!=0): {tot_misalign_in}")
print(f"  swapped[] aligned (m=0)   : {tot_aligned_sw}")
print(f"  swapped[] misaligned(m!=0): {tot_misalign_sw}")

# ------------------------------------------------------------------- baseline
print()
print("=" * 92)
print("BASELINE: random 32-bit targets, full-array scan, 1000 trials x 9 samples")
print("=" * 92)
random.seed(246)
b_align_in = b_align_sw = b_mis_in = b_mis_sw = 0
b_neg = b_pos = 0
b_any = 0
trials = 1000
for t in range(trials):
    for (sd, idx, lin, act) in SAMPLES:
        tgt = random.getrandbits(32)
        mi = slide_window_full(INB[sd], idx, tgt)
        ms = slide_window_full(SWB[sd], idx, tgt)
        had = False
        for h in mi:
            if h['m']==0: b_align_in += 1
            else:         b_mis_in += 1
            d = h['elem_delta']
            if d<0: b_neg += 1
            elif d>0: b_pos += 1
            had = True
        for h in ms:
            if h['m']==0: b_align_sw += 1
            else:         b_mis_sw += 1
            d = h['elem_delta']
            if d<0: b_neg += 1
            elif d>0: b_pos += 1
            had = True
        if had: b_any += 1
N = trials * 9
print(f"  input[]   aligned hits   : {b_align_in}/{N}  (~{b_align_in/N:.4f}/scan)")
print(f"  input[]   misaligned hits: {b_mis_in}/{N}   (~{b_mis_in/N:.2e}/scan)")
print(f"  swapped[] aligned hits   : {b_align_sw}/{N}  (~{b_align_sw/N:.4f}/scan)")
print(f"  swapped[] misaligned hits: {b_mis_sw}/{N}   (~{b_mis_sw/N:.2e}/scan)")
print(f"  backward (j<idx)         : {b_neg}")
print(f"  forward  (j>idx)         : {b_pos}")
print(f"  scans with >=1 hit       : {b_any}/{N}  (~{b_any/N:.4f}/scan)")
print(f"  [direction is meaningless for baseline since idx position in array is")
print(f"   arbitrary vs a random target; shown for completeness]")

# ------------------------------------------- summarize previously-unmatched 6
print()
print("=" * 92)
print("FOCUS: the 6 samples previously unmatched within +/-4 cachelines")
print("=" * 92)
prev_unmatched_idx = [7281, 6957, 12518, 150, 1303, 10692]
for (idx, cat, deltas) in per_sample_class:
    if idx in prev_unmatched_idx:
        if deltas:
            print(f"  idx={idx:>6}: NOW HAS full-array hit(s) -> {cat}, deltas={deltas}")
        else:
            print(f"  idx={idx:>6}: STILL NO HIT in full input[]/swapped[] scan -> "
                  f"source NOT in input[]/swapped[] (out of search scope)")
