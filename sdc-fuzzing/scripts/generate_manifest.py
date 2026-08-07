#!/usr/bin/env python3
"""generate_manifest.py — emit the 100-case manifest for sdc-fuzzing.

Generates cases/manifest.json: a list of 100 case dicts, each a parameter set
for engine/mrueig (the parameterized Eigen-MC driver). The 100 cases are split
across 7 families (DESIGN.md §5). All cases share the SAME trigger machine code
(eigen_cabidrv.o) — only the external parameters vary, preserving the trigger
signature (F1).

Families (total = 100):
  A  scale-scan        20   N in {256,384,512,768,1024}
  B  density-scan      15   density_p in {0.05..0.20}
  C  diag-dominance    10   diag_d in {2,3,4,6,8}
  D  seed-diversity    25   25 distinct (matrix_seed, rhs_seed), N=256 fixed
  E  mode-compare      10   mode 1 (8) vs mode 0 (2)
  F  iteration-depth   10   K in {1500,2500,3000,5000}
  G  load-window       10   load_seconds / cpuset size

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
BASE_LOAD = "144-178,180-191"   # same-socket (pkg 19062) excluding 179
BASE_LOAD_SECS = 60
TARGET_CORE = 179


def case(cid: str, family: str, *, N=BASE_N, density=BASE_P, diag=BASE_D,
         mseed=BASE_MS, rseed=BASE_RS, mode=BASE_MODE, iters=BASE_K,
         load_cpuset=BASE_LOAD, load_seconds=BASE_LOAD_SECS) -> dict:
    return {
        "id": cid,
        "family": family,
        "matrix_dim": N,
        "density_p": density,
        "diag_dominance": diag,
        "matrix_seed": mseed,
        "rhs_seed": rseed,
        "mode": mode,
        "iterations": iters,
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
    """Scale scan: N >= 256 threshold (F2)."""
    out = []
    plan = [(256, 5), (384, 5), (512, 5), (768, 3), (1024, 2)]
    seeds = [12345, 22222, 33333, 44444, 55555, 66666, 77777]
    i = 0
    for N, cnt in plan:
        for _ in range(cnt):
            i += 1
            out.append(case(f"core179-repro-A{i:02d}", "A-scale",
                            N=N, mseed=seeds[(i-1) % len(seeds)],
                            rseed=seeds[(i) % len(seeds)] + 1, iters=3000))
    return out[:20]


def build_family_B() -> list[dict]:
    """Density scan around the verified 0.10 (F3 neighborhood)."""
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
    """Diagonal dominance (SPD strength)."""
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
    Tests F3 — corruption fixed at elem[0] regardless of matrix content."""
    out = []
    for i in range(25):
        ms = 50000 + i * 137
        rs = 60000 + i * 211
        out.append(case(f"core179-repro-D{i+1:02d}", "D-seed",
                        mseed=ms, rseed=rs))
    return out


def build_family_E() -> list[dict]:
    """Mode compare: mode 1 (numeric-only, high rate) vs mode 0 (compute-both,
    ~1/4 rate per F6). 8 mode-1 + 2 mode-0."""
    out = []
    for i in range(8):
        out.append(case(f"core179-repro-E{i+1:02d}", "E-mode",
                        mode=1, mseed=70000+i, rseed=80000+i))
    for i in range(2):
        out.append(case(f"core179-repro-E{9+i:02d}", "E-mode",
                        mode=0, mseed=70008+i, rseed=80008+i,
                        iters=3000))  # same K to keep rate comparable
    return out


def build_family_F() -> list[dict]:
    """Iteration depth: does deeper K linearly raise capture count (F5)."""
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
    """Load window: load_seconds and cpuset subset (F2 >=47 core threshold)."""
    out = []
    # (load_seconds, cpuset_size_note). cpuset is same-socket excluding 179.
    # Base load_cpuset "144-178,180-191" = 47 cores (verified).
    windows = [
        (30, "144-178,180-191"),   # shorter window
        (45, "144-178,180-191"),
        (60, "144-178,180-191"),   # verified baseline
        (75, "144-178,180-191"),   # max safe (avoid hang, §11.3)
        (60, "150-178,180-191"),   # 41 cores — below threshold? probe lower bound
        (60, "160-178,180-191"),   # 35 cores
        (60, "170-178,180-191"),   # 29 cores
        (60, "144-170,180-191"),   # 47 cores, different subset
        (45, "144-165,180-191"),   # 43 cores
        (30, "144-160,180-191"),   # 39 cores
    ]
    i = 0
    for secs, cpuset in windows:
        i += 1
        out.append(case(f"core179-repro-G{i:02d}", "G-load",
                        load_seconds=secs, load_cpuset=cpuset,
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
        "version": 1,
        "engine": "engine/mrueig",
        "trigger_machine_code": "engine/eigen_cabidrv.o (Eigen 5.0 SimplicialCholesky::factorize, -fno-exceptions -fno-rtti, libc-only)",
        "root_cause_ref": "opendcdiag/docs/sdc1-01-02-core179-diagnostics/CORE179_SDC_ROOTCAUSE_REPORT.md",
        "judge": "crc_x_full_vector: CRC32C(x) != golden => reproduction (corruption fixed at x[0])",
        "target_machine_required": "4-socket 192-core Kunpeng 920 (core 179 must exist); current host lacks cpu179",
        "safety": "timeout-wrapped, load_seconds <= 75 to avoid the report's hang (§11.3)",
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
    return 0


if __name__ == "__main__":
    sys.exit(main())
