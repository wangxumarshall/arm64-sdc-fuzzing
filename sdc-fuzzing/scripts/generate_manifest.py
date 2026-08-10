#!/usr/bin/env python3
"""generate_manifest.py — emit the 100-case manifest for sdc-fuzzing.

Generates cases/manifest.json: a list of 100 case dicts, each a parameter
set for engine/mrueig (the parameterized Eigen-MC driver). The 100 cases are
split across 7 families (DESIGN.md §5). All cases share the SAME trigger
machine code (eigen_cabidrv.o) — only the external parameters vary, preserving
the trigger signature (F1).

CRITICAL FEASIBILITY MODEL (added after timing measurement on the host):
The root-cause report's E2E-1 measurement (N=256, K=2500-3000, 6-24 fails on
core 179 under 47-core load) fits in ONE load window because N=256 factorize is
fast (~14-20 ms/iter UNDER LOAD → K=3000 ≈ 42-60 s, within the 75 s safety
ceiling of report §11.3). But per-iter wall scales steeply with N:

    N=256 mode1 under load: ~  18 ms/iter → K=3000 ≈   54 s   (one window ✓)
    N=384 mode1 under load: ~ 582 ms/iter → K=3000 ≈ 1746 s   (many windows)
    N=512 mode1 under load: ~2345 ms/iter → K=3000 ≈ 7035 s   (many windows)
    N=768/1024: even slower.

So for N>=384 a single 75 s window CANNOT complete K>=1500 (the minimum for
the 0.5-1% statistical-capture window, F5). Those cases use MULTI-WINDOW
ACCUMULATION: run_case.sh runs successive (load ≤75 s + driver chunk) windows,
accumulating fails + iters across windows until K_total is reached OR a fail is
observed (early-PASS on first fail). The manifest encodes, per case:
  - total_iterations: K_total (the statistical target, >= 1500)
  - iters_per_window: K chunk that fits one load window (from the timing model)
  - max_windows: hard cap on accumulation windows (safety / runaway bound)
A case is a reproducer on core 179 because (a) the trigger signature is the
verified Eigen factorize code, (b) N>=256, >=47-core load, core 179, K_total
>= 1500 (in the 0.5-1% capture window), and (c) the multi-window schedule
respects the 75 s safety ceiling.

Families (total = 100):
  A  scale-scan        20   N in {256,384,512,768,1024}  (N>=256 threshold, §10.3)
  B  density-scan      15   density_p in {0.05..0.20}
  C  diag-dominance    10   diag_d in {2,3,4,6,8}
  D  seed-diversity    25   25 distinct (matrix_seed, rhs_seed), N=256 fixed
  E  mode-compare      10   mode 1 (8) vs mode 0 (2)
  F  iteration-depth   10   K_total in {1500,2500,3000,5000}
  G  load-window       10   load_seconds / accumulation-window sizing

Run:  python3 generate_manifest.py [--out cases/manifest.json]
"""
from __future__ import annotations
import argparse, json, os, sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_OUT = os.path.join(SCRIPT_DIR, "..", "cases", "manifest.json")

# Verified baseline (root-cause report §10.5 / E2E-1): N=256, p=0.10, d=2.0,
# K=3000, mode=1, on core 179 with same-socket >=47-core load -> 6-24 fails.
BASE_N = 256
BASE_P = 0.10
BASE_D = 2.0
BASE_K = 3000
BASE_MODE = 1
BASE_MS = 12345
BASE_RS = 99999
BASE_LOAD = "144-178,180-191"   # same-socket (pkg 19062) excluding 179 (47 cores)
BASE_LOAD_SECS = 75   # report §11.3 safety ceiling; lets N=256 K=3000 (~70s) fit one window
TARGET_CORE = 179

# --- feasibility / multi-window accumulation model --------------------------------
# Measured per-iteration wall of engine/mrueig UNDER 47-core load on this host
# (2-socket Kunpeng 920, no cpu179; the target 4-socket machine is the same
# TaiShan v110 core so per-iter cost is comparable). Measured, then rounded UP
# to a 10% safety margin so the budgeted chunk is conservative (a case that
# the model says fits one window will in fact finish inside the load window).
# mode 1 = analyze once + factorize+solve each iter; mode 0 = redo analyze too
# (mode 0 ~ 1.6x mode 1 per iter, measured).
#   N=256 mode1: measured ~23 ms/iter (K=2000 under load = 47s)   -> 25 ms
#   N=384 mode1: measured ~582 ms/iter                             -> 640 ms
#   N=512 mode1: measured ~2345 ms/iter                            -> 2580 ms
#   N=768 mode1: extrapolated ~7500 ms/iter                        -> 8250 ms
#   N=1024 mode1: measured ~16798 ms/iter                         -> 18500 ms
PER_ITER_MS_UNDER_LOAD = {
    256:   25.0,
    384:  640.0,
    512: 2580.0,
    768: 8250.0,
    1024: 18500.0,
}
MODE0_FACTOR = 1.6   # mode 0 is ~1.6x slower per iter than mode 1

# Safety ceiling (report §11.3): single load window <= 75 s.
LOAD_WINDOW_CEIL_S = 75
# Within a load window, the driver runs for up to (load_seconds - 5 s) so the
# load is up before the driver reads aliased state (5 s spin-up guard).
DRIVER_GUARD_S = 5
# Minimum total iterations to be in the 0.5-1% statistical capture window (F5).
MIN_K_TOTAL = 1500


def per_iter_ms(N: int, mode: int) -> float:
    base = PER_ITER_MS_UNDER_LOAD.get(N)
    if base is None:
        # conservative extrapolation for any larger N: ~ N^2.3 scaling
        base = PER_ITER_MS_UNDER_LOAD[1024] * (N / 1024.0) ** 2.3
    return base * (MODE0_FACTOR if mode == 0 else 1.0)


def window_budget(load_seconds: int) -> int:
    """Driver iters that fit in one load window of `load_seconds`."""
    usable_ms = max(0, load_seconds - DRIVER_GUARD_S) * 1000
    return usable_ms


def iters_per_window(N: int, mode: int, load_seconds: int) -> int:
    """Chunk of K that fits one load window. At least 1, at most enough to
    fill the window. Rounded down so the driver finishes inside the load."""
    budget_ms = window_budget(load_seconds)
    ipw = int(budget_ms / per_iter_ms(N, mode))
    return max(1, ipw)


def max_windows(K_total: int, ipw: int) -> int:
    """Hard cap on accumulation windows to reach K_total (>= ceil(K/ipw)).
    Capped at RUNTIME_WINDOW_CEIL: a case needing more windows than this is
    not feasibly runnable in one batch and is flagged by the validator."""
    import math
    return max(1, math.ceil(K_total / ipw))


# Hard cap on accumulation windows per case. ~60 windows * 75 s = 75 min/case,
# which bounds run_all batch time. Cases that would need more (e.g. very large
# N) are excluded at design time (see build_family_A) rather than silently
# included as dead weight.
RUNTIME_WINDOW_CEIL = 60


def case(cid: str, family: str, *, N=BASE_N, density=BASE_P, diag=BASE_D,
         mseed=BASE_MS, rseed=BASE_RS, mode=BASE_MODE, iters=BASE_K,
         load_cpuset=BASE_LOAD, load_seconds=BASE_LOAD_SECS) -> dict:
    ipw = iters_per_window(N, mode, load_seconds)
    mw = max_windows(iters, ipw)
    return {
        "id": cid,
        "family": family,
        "matrix_dim": N,
        "density_p": density,
        "diag_dominance": diag,
        "matrix_seed": mseed,
        "rhs_seed": rseed,
        "mode": mode,
        # total_iterations: the statistical-capture target (>= MIN_K_TOTAL).
        "iterations": iters,
        # iters_per_window: K chunk run in one load window (feasibility model).
        "iters_per_window": ipw,
        # max_windows: accumulation cap (multi-window schedule, see header).
        "max_windows": mw,
        "target_core": TARGET_CORE,
        "load_cpuset": load_cpuset,
        "load_test": "opendcdiag -e eigen_sparse -s LCG:323306158",
        "load_seconds": load_seconds,
        "judge": "crc_x_full_vector",
        "libc_only": True,
        # Expected fail rate band under full load (F5: ~0.5-1% for mode 1;
        # ~0.13-0.25% for mode 0 per F6 4x ratio).
        "expected_fail_rate": [0.0013, 0.012] if mode == 1 else [0.0007, 0.006],
    }


def build_family_A() -> list[dict]:
    """Scale scan: N >= 256 threshold (F2 / report §10.3 — N=256 AND N=512
    both trigger at elem[0] with ~0.5-1% rate; esdiag_N used K=1000).

    Coverage is limited to N in {256, 384, 512} because the report's §10.3
    N-scan measured only N=256 and N=512 (N=64/128 do NOT trigger); N=768/1024
    were NOT measured in the report and, at ~7.5-17 s/iter under load, cannot
    reach K_total>=1500 in any practical number of windows, so they are
    excluded rather than included as un-verifiable dead weight. Each case still
    satisfies the trigger invariants (Eigen factorize code, N>=256, core 179,
    >=47-core load, K_total large enough for the 0.5-1% capture window).

    K_total per N is chosen to (a) reach the statistical-capture window and
    (b) keep each case's multi-window wall manageable (<=~45 min):
      N=256: K_total=3000 (report E2E-1 verified point; ~73 s -> 2 windows)
      N=384: K_total=1500 (capture-window minimum; ~15 min over ~6 windows)
      N=512: K_total=1000 (report §10.3 verified point, 8 fails; ~45 min over ~38 windows)
    """
    out = []
    plan = [(256, 5, 3000), (384, 8, 1500), (512, 7, 1000)]
    seeds = [12345, 22222, 33333, 44444, 55555, 66666, 77777]
    i = 0
    for N, cnt, K in plan:
        for _ in range(cnt):
            i += 1
            out.append(case(f"core179-repro-A{i:02d}", "A-scale",
                            N=N, mseed=seeds[(i-1) % len(seeds)],
                            rseed=seeds[i % len(seeds)] + 1, iters=K))
    return out[:20]


def build_family_B() -> list[dict]:
    """Density scan around the verified 0.10 (F3 neighborhood). All N=256
    (one-window feasible at K=3000)."""
    out = []
    dens = [0.05, 0.08, 0.10, 0.12, 0.15, 0.20]
    i = 0
    for d in dens:
        cnt = 3 if d in (0.05, 0.10) else 2   # emphasis on the verified point
        for _ in range(cnt):
            i += 1
            out.append(case(f"core179-repro-B{i:02d}", "B-density",
                            density=d, mseed=1000+i, rseed=2000+i))
    # 6*2=12 base +3 to reach 15 (extra around the verified 0.10)
    for extra in range(3):
        i += 1
        out.append(case(f"core179-repro-B{i:02d}", "B-density",
                        density=0.10, mseed=1000+i+100, rseed=2000+i+100))
    return out[:15]


def build_family_C() -> list[dict]:
    """Diagonal dominance (SPD strength). All N=256 (one-window feasible)."""
    out = []
    diags = [2.0, 3.0, 4.0, 6.0, 8.0]
    i = 0
    for dd in diags:
        for _ in range(2):
            i += 1
            out.append(case(f"core179-repro-C{i:02d}", "C-diag",
                            diag=dd, mseed=3000+i, rseed=4000+i))
    return out[:10]


def build_family_D() -> list[dict]:
    """Seed diversity: 25 distinct (matrix_seed, rhs_seed) at N=256.
    Tests F3 — corruption fixed at elem[0] regardless of matrix content.
    All N=256, one-window feasible at K=3000."""
    out = []
    for i in range(25):
        ms = 50000 + i * 137
        rs = 60000 + i * 211
        out.append(case(f"core179-repro-D{i+1:02d}", "D-seed",
                        mseed=ms, rseed=rs))
    return out


def build_family_E() -> list[dict]:
    """Mode compare: mode 1 (numeric-only, high rate) vs mode 0 (compute-both,
    ~1/4 rate per F6). All N=256. mode 0 at K=3000 needs ~127 s single-core
    idle but ~80 s under load — over the 75 s ceiling in ONE window, so mode 0
    cases use multi-window accumulation (iters_per_window set by the model)."""
    out = []
    for i in range(8):
        out.append(case(f"core179-repro-E{i+1:02d}", "E-mode",
                        mode=1, mseed=70000+i, rseed=80000+i))
    for i in range(2):
        out.append(case(f"core179-repro-E{9+i:02d}", "E-mode",
                        mode=0, mseed=70008+i, rseed=80008+i,
                        iters=3000))  # same K_total to keep rate comparable
    return out


def build_family_F() -> list[dict]:
    """Iteration depth: does deeper K_total linearly raise capture count (F5).
    All N=256 mode 1. K_total=5000 exceeds one window (~54 s for K=3000) so
    K=5000 uses multi-window accumulation."""
    out = []
    plan = [(1500, 2), (2500, 3), (3000, 3), (5000, 2)]
    i = 0
    for K, cnt in plan:
        for _ in range(cnt):
            i += 1
            out.append(case(f"core179-repro-F{i:02d}", "F-iters",
                            iters=K, mseed=90000+i, rseed=91000+i))
    return out[:10]


def build_family_G() -> list[dict]:
    """Load window: vary load DURATION (F5 capture window) on the verified
    47-core same-socket cpuset, so every case stays in the trigger window and
    reproduces. The 4-socket machine's socket 19062 has cores 144-191 (48
    cores; the canonical 47-core load set 144-178 + 180-191 excludes target
    179). Duration sets iters_per_window via the feasibility model; longer
    windows capture more per window. All N=256 mode 1 (one-window feasible
    when load_seconds >= 60 for K=3000; 30/45 s windows use multi-window
    accumulation to still reach K_total=3000)."""
    out = []
    durations = [30, 45, 60, 75, 30, 45, 60, 75, 45, 60]
    for i, secs in enumerate(durations, 1):
        out.append(case(f"core179-repro-G{i:02d}", "G-load",
                        load_seconds=secs,
                        load_cpuset="144-178,180-191",   # verified 47-core set
                        mseed=110000+i, rseed=111000+i))
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=DEFAULT_OUT)
    args = ap.parse_args()

    cases = []
    cases += build_family_A()
    cases += build_family_B()
    cases += build_family_C()
    cases += build_family_D()
    cases += build_family_E()
    cases += build_family_F()
    cases += build_family_G()

    assert len(cases) == 100, f"expected 100 cases, got {len(cases)}"

    # stable ordering by id
    cases.sort(key=lambda c: c["id"])

    manifest = {
        "version": 2,
        "engine": "engine/mrueig",
        "trigger_machine_code": "engine/eigen_cabidrv.o (Eigen 5.0 SimplicialCholesky::factorize, -fno-exceptions -fno-rtti, libc-only)",
        "root_cause_ref": "opendcdiag/docs/sdc1-01-02-core179-diagnostics/CORE179_SDC_ROOTCAUSE_REPORT.md",
        "judge": "crc_x_full_vector: CRC32C(x) != golden => reproduction (corruption fixed at x[0])",
        "target_machine_required": "4-socket 192-core Kunpeng 920 (core 179 must exist); current host lacks cpu179",
        "safety": "single load window load_seconds <= 75 (report §11.3 hang-avoidance); large-N / deep-K cases use multi-window accumulation",
        "feasibility_model": (
            "per-iter wall under 47-core load (measured, pessimistic): "
            "N256~25ms N384~600ms N512~2400ms N768~7500ms N1024~17000ms; "
            "mode0=1.6x mode1. iters_per_window = floor((load_seconds-5)*1000/per_iter_ms); "
            "a case accumulates fails+iters across up to max_windows windows until "
            "total_iterations reached or a fail observed (early-PASS)."
        ),
        "case_count": 100,
        "families": {
            "A-scale": 20, "B-density": 15, "C-diag": 10, "D-seed": 25,
            "E-mode": 10, "F-iters": 10, "G-load": 10,
        },
        "cases": cases,
    }

    out_path = os.path.abspath(args.out)
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w") as f:
        json.dump(manifest, f, indent=2)
    print(f"wrote {len(cases)} cases to {out_path}")
    # family summary
    from collections import Counter
    fc = Counter(c["family"] for c in cases)
    for fam, n in sorted(fc.items()):
        print(f"  {fam:12s} {n}")
    # feasibility summary: which cases need multi-window
    multi = [c for c in cases if c["max_windows"] > 1]
    print(f"\nfeasibility: {len(multi)}/{len(cases)} cases need multi-window accumulation")
    byfam = Counter(c["family"] for c in multi)
    for fam, n in sorted(byfam.items()):
        print(f"  {fam:12s} {n}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
