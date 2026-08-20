#!/usr/bin/env python3
"""
Store-forwarding hypothesis test for movbe_dump SDC samples.

Context (established last round):
  - actual   = the TRUE original input[i] value  (reconstructed[index] == actual, 9/9)
  - logged input / golden = the CORRUPTED reload of data->input[i]
  - swapped[i] (true) = bswap32(input[i]) = bswap32(actual)   (written by the
    store `data->swapped[i] = val` right before the folded reload)

movbe_dump.cpp hot path:
    val = data->input[i];            # load1 (clean, becomes actual via reg path)
    val = bswap32(val);
    data->swapped[i] = val;          # STORE to swapped[i]
    val = bswap32(val);              # folded into a RELOAD of input[i]  (load2)
    if (val != data->input[i]) ...   # load3 / load4 / load5 = logged input/golden

Hypothesis under test:
  Is the corrupted reload (logged input/golden) exactly the value that was
  just STORED to swapped[i]?  i.e.  bswap32(actual) == logged_input ?
  (store-forwarding / address-misresolution giving the load the store's data
   instead of input[i]'s data.)

If that exact match rate is low, extend the search:
  (B) does logged_input appear anywhere in the swapped[] array at j != i?
      (store from a *different* iteration / neighboring address forwarded)
  (C) does logged_input appear among input[] elements in the cacheline(s)
      neighboring i?  (load picked up a real adjacent cacheline element)
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

def bswap32(x):
    return ( ((x & 0x000000FF) << 24) |
             ((x & 0x0000FF00) << 8)  |
             ((x & 0x00FF0000) >> 8)  |
             ((x & 0xFF000000) >> 24) ) & 0xFFFFFFFF

# (seed, index, logged_input, actual)   [logged_input == logged_golden for all 9]
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

# reconstructed true input arrays
INPUT = {sd: generate32_sequence(sd, BUFSIZE) for sd in SEEDS}
# swapped[j] = bswap32(input[j])  (the store data written in the hot path)
SWAPPED = {sd: [bswap32(v) for v in INPUT[sd]] for sd in SEEDS}

# sanity: confirm actual == INPUT[index] and bswap32(actual) == SWAPPED[index]
print("="*84)
print("SANITY: actual == true_input[index]  and  bswap32(actual) == true_swapped[index]")
print("="*84)
for (sd, idx, lin, act) in SAMPLES:
    ti = INPUT[sd][idx]
    sw = SWAPPED[sd][idx]
    bsa = bswap32(act)
    assert ti == act,  f"actual!=input[{idx}] for seed {sd}"
    assert sw == bsa,  f"bswap32(actual)!=swapped[{idx}] for seed {sd}"
    print(f"  seed={sd:>11} idx={idx:>6}  input[i]=0x{ti:08X}  swapped[i]=0x{sw:08X}  "
          f"bswap32(actual)=0x{bsa:08X}   OK")
print()

# ------------------------------------------------------------------- STEP A
print("="*84)
print("STEP A (core hypothesis): bswap32(actual) == logged_input ?")
print("  i.e. did the corrupted reload receive EXACTLY the value stored to")
print("  swapped[i] right before it?  (store-forwarding of the same index)")
print("="*84)
hitA = 0
for (sd, idx, lin, act) in SAMPLES:
    cand = bswap32(act)              # = true swapped[i]
    ok = (cand == lin)
    hitA += ok
    print(f"  seed={sd:>11} idx={idx:>6}  bswap32(actual)=0x{cand:08X}  "
          f"logged_input=0x{lin:08X}  {'>>> HIT' if ok else 'no'}")
print(f"\n  STEP A hits: {hitA}/9\n")

# ------------------------------------------------ STEP B (extended: swapped[])
print("="*84)
print("STEP B (extended): does logged_input appear in the swapped[] array at")
print("any index j (j != i)?  i.e. corrupted reload == store data of a DIFFERENT")
print("position.  Reports all j and distance j-i.")
print("="*84)
hitB = 0
for (sd, idx, lin, act) in SAMPLES:
    sw = SWAPPED[sd]
    ms = [j for j,v in enumerate(sw) if v == lin and j != idx]
    self_match = (sw[idx] == lin)   # same as Step A
    print(f"\n  seed={sd:>11} idx={idx:>6} logged_input=0x{lin:08X}")
    if self_match:
        print(f"    [j==i (Step A): swapped[{idx}]==logged_input]")
    if ms:
        hitB += 1
        ds = [(j, j-idx) for j in ms[:10]]
        nearest = min(ms, key=lambda j: abs(j-idx))
        print(f"    HIT at j!={idx}: count={len(ms)}; first={ms[:10]}; "
              f"nearest j={nearest} (dist {nearest-idx})")
    else:
        print(f"    no j!={idx} in swapped[] equals logged_input.")
print(f"\n  STEP B hits (logged_input found in swapped[] at j!=i): {hitB}/9\n")

# --------------------------------- STEP C (extended: input[] neighboring cachelines)
print("="*84)
print("STEP C (extended): does logged_input appear among input[] elements in")
print("cachelines NEIGHBORING index i?  input[] is 64-B aligned, 16 uint32 per")
print("64-B cacheline.  We scan cachelines [-4 .. +4] around i's cacheline.")
print("="*84)
hitC_self = 0   # logged_input == input[j] for j in neighbor window (incl. same CL, j!=i)
hitC_anywhere = 0
for (sd, idx, lin, act) in SAMPLES:
    arr = INPUT[sd]
    cl = (idx // 16) * 16
    lo = max(0, cl - 4*16)
    hi = min(BUFSIZE, cl + 5*16)   # 4 cachelines before, current, 4 after
    ms = [j for j in range(lo, hi) if arr[j] == lin and j != idx]
    # also whole-array for reference
    allms = [j for j,v in enumerate(arr) if v == lin and j != idx]
    print(f"\n  seed={sd:>11} idx={idx:>6} cacheline_base={cl} "
          f"window=[{lo},{hi}) logged_input=0x{lin:08X}")
    if ms:
        hitC_self += 1
        print(f"    NEIGHBOR HIT: j={ms} (distances {[j-idx for j in ms]})")
    else:
        print(f"    no neighbor-window hit.")
    if allms:
        hitC_anywhere += 1
        nearest = min(allms, key=lambda j: abs(j-idx))
        cl_j = (nearest//16)*16
        print(f"    [whole-array ref: logged_input found at j={allms[:6]}{'...' if len(allms)>6 else ''}; "
              f"nearest={nearest} dist={nearest-idx} "
              f"(idx CL {cl}, hit CL {cl_j}, CL-diff={(cl_j-cl)//16})]")
print(f"\n  STEP C: neighbor-window hits: {hitC_self}/9 ; "
      f"whole-array hits (ref): {hitC_anywhere}/9\n")

# ----------------------------------------------------------- bonus: input[] same-index sanity already covered
print("="*84)
print("OVERALL")
print("="*84)
print(f"  Step A  bswap32(actual)==logged_input (store fwd SAME index) : {hitA}/9")
print(f"  Step B  logged_input in swapped[] at j!=i                   : {hitB}/9")
print(f"  Step C  logged_input in input[] neighbor cachelines         : {hitC_self}/9")
