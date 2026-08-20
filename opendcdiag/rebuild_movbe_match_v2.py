#!/usr/bin/env python3
"""
Second-pass analysis after the surprising step-3 result.

Finding: the reconstructed RNG sequence at the trigger index equals the
sample's *actual* value, NOT the logged *input* value (9/9 samples).

This script:
  1. Confirms reconstructed[index] == actual for all 9 samples.
  2. Searches whether `actual` (= reconstructed[index], the true original
     input value) also appears at some OTHER index j in the same array.
  3. For completeness, also searches whether the logged `input` (the value
     that actually appeared in the failure log, i.e. the corrupted reload)
     appears elsewhere in the array.
"""
M = (1 << 31) - 1
A = 48271
BUFSIZE = 1 << 14

def lcg_next(s): return (A * s) % M

def generate32_sequence(seed, n):
    state = seed
    out = []
    for _ in range(n):
        state = lcg_next(state); lo = state & 0xffff
        state = lcg_next(state); hi = state & 0xffff
        out.append((lo | (hi << 16)) & 0xffffffff)
    return out

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
arrays = {sd: generate32_sequence(sd, BUFSIZE) for sd in SEEDS}

print("="*82)
print("CONFIRM: reconstructed[index] == actual ?  (and == logged input ?)")
print("="*82)
print(f"{'seed':>11} {'idx':>6}  {'reconstructed':>12} {'actual':>12} {'logged_input':>13}  recon==act  recon==inp")
act_ok = inp_ok = 0
for (sd, idx, inp, act) in SAMPLES:
    r = arrays[sd][idx]
    ea = (r == act); ei = (r == inp)
    act_ok += ea; inp_ok += ei
    print(f"{sd:>11} {idx:>6}  0x{r:08X}   0x{act:08X}   0x{inp:08X}     {str(ea):>5}        {str(ei):>5}")
print(f"\n  reconstructed[index] == actual      : {act_ok}/9")
print(f"  reconstructed[index] == logged_input: {inp_ok}/9")

print()
print("="*82)
print("SEARCH: does `actual` (= true original value at index) appear at")
print("any OTHER index j in the same 16384-element array?")
print("="*82)
hits_actual = 0
for (sd, idx, inp, act) in SAMPLES:
    arr = arrays[sd]
    ms = [j for j,v in enumerate(arr) if v == act and j != idx]
    print(f"\n  seed={sd} idx={idx} actual=0x{act:08X} (=reconstructed[{idx}]):")
    if ms:
        hits_actual += 1
        print(f"    HIT at j={ms} (distances {[j-idx for j in ms[:8]]})")
    else:
        print(f"    no other position j (j!={idx}) equals actual.  "
              f"[arr[index] is the only occurrence]")

print()
print("="*82)
print("CROSS-CHECK: does the logged `input` (the value printed in the log,")
print("i.e. the corrupted reload) appear anywhere in the array?")
print("="*82)
hits_input = 0
for (sd, idx, inp, act) in SAMPLES:
    arr = arrays[sd]
    ms = [j for j,v in enumerate(arr) if v == inp]
    print(f"\n  seed={sd} idx={idx} logged_input=0x{inp:08X}:")
    if ms:
        hits_input += 1
        print(f"    found at j={ms} (incl. possibly j=={idx}? {'yes' if idx in ms else 'no'})")
    else:
        print(f"    logged_input does NOT appear anywhere in the array.")

print()
print("="*82)
print("SUMMARY")
print("="*82)
print(f"  reconstructed[index] == actual       : {act_ok}/9  (RNG reconstruction is correct)")
print(f"  actual appears at another index j     : {hits_actual}/9  (stale-data-from-elsewhere?)")
print(f"  logged_input appears anywhere in array : {hits_input}/9")
