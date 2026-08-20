#!/usr/bin/env python3
"""
Reconstruct movbe_dump input arrays from LCG seed and check whether each
sample's `actual` value equals some *other* real element of the same input
array (i.e. evidence that the load read a stale/wrong but real array element).

RNG reconstruction (derived from framework/random.cpp):
  - Engine: std::minstd_rand  (LCG: x_{n+1} = (48271 * x_n) mod (2^31 - 1))
  - Global engine state after `-s LCG:N` = N  (reloadGlobalState: istringstream >> engine)
  - test_init runs in the child main thread with thread_num = -1, so
    thread_local_rng() == rng_for_thread(-1) == the GLOBAL engine buffer.
    random_init_thread() is only called for thread_num>=0 (in thread_runner),
    never for -1, so the global buffer is NOT re-seeded per-thread before init.
  - Therefore data->input[i] = generate32(global) for i = 0..16383, consuming
    the global LCG starting from state N.
  - generate32 for minstd_rand (framework/random.cpp:258):
        lo = next() & 0xffff
        hi = next() & 0xffff
        return lo | (hi << 16)
    where next() advances the LCG one step and returns the new state.
  - Note: no per-thread mixin enters this path (mixin only applies to
    thread_num>=0 engines). This is the key difference from the GEMM case.

Ground-truth check (step 3): for each sample, the reconstructed array at the
trigger index MUST equal the logged `input` value. If it doesn't, the formula
is wrong and we stop.
"""
import sys

M = (1 << 31) - 1  # 2147483647
A = 48271
BUFSIZE = 1 << 14  # 16384

def lcg_next(state):
    return (A * state) % M

def generate32_sequence(seed, n):
    """Reproduce EngineWrapper<minstd_rand>::generate32 called n times,
    starting from global state == seed. Returns list of n uint32."""
    state = seed
    out = []
    for _ in range(n):
        state = lcg_next(state)         # first sample
        lo = state & 0xffff
        state = lcg_next(state)         # second sample
        hi = state & 0xffff
        out.append((lo | (hi << 16)) & 0xffffffff)
    return out

# (seed, index, input, actual) for the 9 samples
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

def main():
    arrays = {}
    for seed in SEEDS:
        arrays[seed] = generate32_sequence(seed, BUFSIZE)

    print("=" * 78)
    print("STEP 3: ground-truth check (reconstructed[index] == logged input?)")
    print("=" * 78)
    all_ok = True
    for (seed, idx, inp, actual) in SAMPLES:
        arr = arrays[seed]
        got = arr[idx]
        ok = (got == inp)
        all_ok &= ok
        print(f"  seed={seed:11d} idx={idx:6d}  reconstructed=0x{got:08X}  "
              f"logged=0x{inp:08X}  {'OK' if ok else '*** MISMATCH ***'}")
    print()
    if not all_ok:
        print("!!! Ground-truth check FAILED. Reconstructed values do not match")
        print("!!! the logged input. The RNG reconstruction formula is wrong.")
        print("!!! Aborting before doing the match (it would be meaningless).")
        # Print a few first elements to help debug
        for seed in SEEDS:
            arr = arrays[seed]
            print(f"  seed={seed}: first 8 = "
                  + " ".join(f"0x{v:08X}" for v in arr[:8]))
        sys.exit(1)

    print("=" * 78)
    print("STEP 4: search each `actual` across ALL 16384 positions of its array")
    print("        (looking for j != index with array[j] == actual)")
    print("=" * 78)
    hits = 0
    for (seed, idx, inp, actual) in SAMPLES:
        arr = arrays[seed]
        # find ALL positions j (j != idx) where arr[j] == actual
        matches = [j for j, v in enumerate(arr) if v == actual and j != idx]
        # also note whether the trigger index itself happens to equal actual
        # (it shouldn't, since input != actual by definition of a failure)
        self_match = (arr[idx] == actual)
        print()
        print(f"  seed={seed:11d} index={idx:6d} input=0x{inp:08X} "
              f"actual=0x{actual:08X}")
        if matches:
            hits += 1
            # show first few matches + min distance
            shown = matches[:8]
            dists = [j - idx for j in matches]
            nearest = min(matches, key=lambda j: abs(j - idx))
            print(f"    >>> HIT: {len(matches)} position(s) j where array[j]==actual")
            print(f"    first matches: {shown}{' ...' if len(matches)>8 else ''}")
            print(f"    nearest j={nearest}  (distance j-index={nearest-idx}, "
                  f"abs={abs(nearest-idx)})")
            print(f"    distances (j-index) for shown: {dists[:8]}")
        else:
            print(f"    no hit: actual 0x{actual:08X} does not appear at any")
            print(f"    position j (!= {idx}) in this 16384-element array.")
            if self_match:
                print(f"    (note: arr[{idx}] itself == actual, but that's the")
                print(f"     trigger position and is excluded by definition.)")
    print()
    print("=" * 78)
    print(f"SUMMARY: {hits}/9 samples had actual appear elsewhere in the array.")
    print("=" * 78)
    if hits > 0:
        print("!! At least one `actual` matched a real element at a DIFFERENT")
        print("!! index => direct evidence that the failing load returned a")
        print("!! real (but wrong) value from elsewhere in the input buffer.")
    else:
        print("No sample's `actual` matched any other real array element.")
        print("This does NOT exclude the stale-data hypothesis: the corrupted")
        print("value may originate from a register / cache line / other thread's")
        print("buffer, none of which are in this 16384-element search scope.")

if __name__ == "__main__":
    main()
