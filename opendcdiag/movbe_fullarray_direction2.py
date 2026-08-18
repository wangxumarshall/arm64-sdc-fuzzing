#!/usr/bin/env python3
"""Full-array + directionality (optimized: indexed baseline)."""
import struct, random
from collections import defaultdict

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
    res = []
    for start in range(0, len(buf) - 3):
        if struct.unpack('<I', buf[start:start+4])[0] == target:
            j = start // 4; m = start - j * 4
            res.append({'start': start, 'j': j, 'm': m, 'elem_delta': j - idx})
    return res

# ---- per-sample real scan (slow but only 9 samples) ----
print("=" * 92)
print("FULL-ARRAY SCAN: logged_input as 4-byte LE window over ENTIRE input[]/swapped[]")
print("  aligned m=0 = whole-element read; misaligned m!=0 = byte straddle (addr corrupt)")
print("=" * 92)
print(f"{'#':>2} {'seed':>11} {'idx':>6} {'logged_input':>13} {'array':>9} "
      f"{'m':>2} {'j':>6} {'j-idx':>7} {'sign':>5}")
print("-" * 92)
tot_align_in = tot_align_sw = tot_mis_in = tot_mis_sw = 0
hits_neg = hits_pos = hits_zero = 0
per_sample = []
sample_has_any = 0
prev_unmatched = [7281, 6957, 12518, 150, 1303, 10692]
focus_detail = []
for n, (sd, idx, lin, act) in enumerate(SAMPLES, 1):
    mi = slide_window_full(INB[sd], idx, lin)
    ms = slide_window_full(SWB[sd], idx, lin)
    allhits = [('input', h) for h in mi] + [('swapped', h) for h in ms]
    deltas = []; bk = fw = 0
    for arr_name, h in allhits:
        if h['m'] == 0:
            if arr_name == 'input': tot_align_in += 1
            else: tot_align_sw += 1
        else:
            if arr_name == 'input': tot_mis_in += 1
            else: tot_mis_sw += 1
        d = h['elem_delta']; deltas.append(d)
        if d < 0:   bk += 1; hits_neg += 1
        elif d > 0: fw += 1; hits_pos += 1
        else:              hits_zero += 1
        print(f"{n:>2} {sd:>11} {idx:>6} 0x{lin:08X}    {arr_name:>7} "
              f"{h['m']:>2} {h['j']:>6} {d:>+7d} {'<-' if d<0 else '->' if d>0 else '==':>5}")
    if not allhits:
        print(f"{n:>2} {sd:>11} {idx:>6} 0x{lin:08X}    NO HIT in either array (full scan)")
    if allhits: sample_has_any += 1
    cat = ('BACKWARD-ONLY' if (bk and not fw) else
           'FORWARD-ONLY'  if (fw and not bk) else
           'MIXED' if (bk and fw) else 'NONE')
    per_sample.append((idx, cat, deltas))
    if idx in prev_unmatched:
        focus_detail.append((idx, deltas, allhits))

print()
print("=" * 92)
print("DIRECTIONALITY TALLY (all hits, both arrays, aligned+misaligned; j==idx excluded)")
print("=" * 92)
print(f"  backward (j < idx) : {hits_neg}")
print(f"  forward  (j > idx) : {hits_pos}")
print(f"  self     (j == idx): {hits_zero}  (should be 0 by construction)")
print(f"  TOTAL hits         : {hits_neg + hits_pos + hits_zero}")
print()
print("Per-sample direction classification:")
for (idx, cat, deltas) in per_sample:
    print(f"  idx={idx:>6}: {cat:<14}  deltas={deltas}")
print()
print("Hit-count breakdown by array & alignment:")
print(f"  input[]   aligned   : {tot_align_in}")
print(f"  input[]   misaligned: {tot_mis_in}")
print(f"  swapped[] aligned   : {tot_align_sw}")
print(f"  swapped[] misaligned: {tot_mis_sw}")

# ---- baseline via index (fast): for random target, aligned hits occur when
#      target == input[j] or == swapped[j] for some j. Precompute value->positions
#      for each seed, both arrays. Misaligned windows: precompute the set of all
#      4-byte LE windows at non-aligned offsets (huge: 16384*3 per array = ~50k),
#      store in a set for membership test. ----
print()
print("=" * 92)
print("BASELINE: random 32-bit targets, full-array scan, 2000 trials x 9 samples")
print("=" * 92)
# precompute aligned value->list of (array,j) and misaligned-window set per seed
aligned_index = {}     # seed -> {value: [('input'/'swapped', j), ...]}
misalign_set = {}      # seed -> set of 4-byte windows at m in {1,2,3}
for sd in SEEDS:
    ai = defaultdict(list)
    for j, v in enumerate(INPUT[sd]):  ai[v].append(('input', j))
    for j, v in enumerate(SWAPPED[sd]): ai[v].append(('swapped', j))
    aligned_index[sd] = ai
    s = set()
    buf_in = INB[sd]; buf_sw = SWB[sd]
    for start in range(len(buf_in) - 3):
        j = start // 4; m = start - j * 4
        if m != 0:
            s.add(struct.unpack('<I', buf_in[start:start+4])[0])
    for start in range(len(buf_sw) - 3):
        j = start // 4; m = start - j * 4
        if m != 0:
            s.add(struct.unpack('<I', buf_sw[start:start+4])[0])
    misalign_set[sd] = s

random.seed(246)
b_align = b_mis = 0
b_neg = b_pos = 0
b_any = 0
trials = 2000
for t in range(trials):
    for (sd, idx, lin, act) in SAMPLES:
        tgt = random.getrandbits(32)
        ai = aligned_index[sd]
        if tgt in ai:
            for (arr, j) in ai[tgt]:
                if j == idx: continue
                b_align += 1
                d = j - idx
                if d < 0: b_neg += 1
                elif d > 0: b_pos += 1
                b_any = 1
        if tgt in misalign_set[sd]:
            # any misaligned hit (we don't enumerate all j here, just count occurrences)
            b_mis += 1
            b_any = 1
N = trials * 9
print(f"  aligned hits total        : {b_align}/{N}  (~{b_align/N:.4f}/scan)")
print(f"  misaligned hit scans      : {b_mis}/{N}   (~{b_mis/N:.2e}/scan)")
print(f"  backward (j<idx) aligned   : {b_neg}")
print(f"  forward  (j>idx) aligned   : {b_pos}")
print(f"  scans with >=1 aligned hit : {b_any}/{N}  (~{b_any/N:.4f}/scan)")
print(f"  [aligned expected per scan ~ (2*16384)/2^32 ~ 7.6e-6; observed {b_align/N:.2e}]")

print()
print("=" * 92)
print("FOCUS: 6 samples previously unmatched within +/-4 cachelines")
print("=" * 92)
for (idx, deltas, allhits) in focus_detail:
    if deltas:
        print(f"  idx={idx:>6}: NOW HAS full-array hit(s):")
        for arr, h in allhits:
            print(f"       {arr:>7} m={h['m']} j={h['j']} j-idx={h['elem_delta']:+d}")
    else:
        print(f"  idx={idx:>6}: STILL NO HIT in full input[]/swapped[] scan -> "
              f"source NOT in input[]/swapped[] (out of search scope)")
