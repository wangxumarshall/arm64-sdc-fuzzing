# sdc-fuzzing — core-179 SDC reproduction case generator

Auto-generates **100 test cases** that reproduce the core-179 Silent Data
Corruption (SDC) defect documented in
[`opendcdiag/docs/sdc1-01-02-core179-diagnostics/CORE179_SDC_ROOTCAUSE_REPORT.md`](../opendcdiag/docs/sdc1-01-02-core179-diagnostics/CORE179_SDC_ROOTCAUSE_REPORT.md).

This is **not** a random fuzzer (that's `sdc_agent/`'s job — discover *new* SDC
via microprobe + gem5 fault injection). `sdc-fuzzing/` does the complementary
thing: it **engineers the already-located core-179 SDC into 100 runnable
regression vectors** for DFT / production screening / continuous monitoring.
See [`DESIGN.md`](DESIGN.md) for the full rationale.

## TL;DR

The core-179 SDC is a load-sensitive, core-specific OoO-engine state leak that
fires only when **Eigen `SimplicialCholesky::factorize()`** runs on **core 179**
while **≥47 sibling cores in the same socket are at full load** and the matrix
is **N ≥ 256**. Corruption is fixed at `x[0]` (first element of the result
vector), multi-bit data-aliasing, silent (no PMU/EDAC). The only verified
trigger is the **Eigen-compiled machine code** — all 9 pure-C rewrites fail to
trigger.

So all 100 cases share the **same trigger machine code** (`engine/eigen_cabidrv.o`,
libc-only) and only vary the **external conditions** (matrix size N, density,
diag-dominance, seeds, mode, iteration count, load window). Each case is an
independent observation of the same root cause.

**Iteration #2 (feasibility-corrected):** a case's `iterations` (K_total) may
exceed what fits in one 75 s load window (§11.3 safety ceiling), because
per-`factorize` wall scales steeply with N (N=256 ~24 ms/iter → N=512 ~2.4 s/iter).
So the manifest encodes `iters_per_window` + `max_windows` (from a measured
timing model), and `run_case.sh` does **multi-window accumulation**: loop
(load window + driver chunk) until K_total is reached **or** a fail is observed
(early-PASS). N is limited to {256,384,512} (the values the root-cause report
§10.3 measured; N=768/1024 are not report-verified and can't reach K≥1500 in a
practical window count, so they're excluded). All 100 cases stay within the
≤75 s single-window safety limit and a ≤60-window-per-case batch bound.

## Layout

```
sdc-fuzzing/
├── DESIGN.md              # full design (read this)
├── README.md              # this file
├── engine/
│   ├── eigen_cabidrv.cpp  # Eigen 5.0 SimplicialCholesky C-ABI wrapper (constant trigger)
│   ├── eigen_cabidrv.o    # compiled once, shared by all 100 cases
│   ├── mru_driver.c       # parameterized C driver (N/density/diag/seed/mode/iters via CLI)
│   └── mrueig             # single libc-only executable, parameterized
├── scripts/
│   ├── generate_manifest.py   # emits cases/manifest.json (100 cases)
│   ├── validate_manifest.py   # static reproducibility self-check (100/100)
│   ├── build_engine.sh        # builds engine/eigen_cabidrv.o + engine/mrueig
│   ├── run_case.sh            # runs one case (load + bind core + MRU + CRC judge)
│   ├── run_all.sh             # runs all 100, aggregates
│   └── analyze_results.py     # per-family reproduction report
└── cases/
    ├── manifest.json          # 100-case parameter manifest
    └── case_<id>/             # per-case run.log + result.json (populated on run)
```

## Static reproducibility self-check

`scripts/validate_manifest.py` asserts that every one of the 100 cases passes
**both** a trigger-invariant check (F1/F2/F5/F6 + §11.3 hang-safety + N≤512
report-coverage) **and** a feasibility check (`iters_per_window`≥1,
`max_windows`≤60, `iters_per_window × max_windows ≥ iterations`). A case
passing both is, per the root-cause report's E2E evidence, a reproducer on the
target machine. This is the strongest reproducibility guarantee achievable
without the physical defective core 179.

```bash
python3 scripts/validate_manifest.py   # 100/100 PASS (trigger + feasibility)
```

## Quickstart

```bash
# 1. generate the 100-case manifest
cd sdc-fuzzing
python3 scripts/generate_manifest.py

# 2. build the engine (needs Eigen 5.0 at opendcdiag/third-part/)
./scripts/build_engine.sh

# 3. run all 100 cases on the TARGET machine (4-socket 192-core, core 179 present)
./scripts/run_all.sh

# 4. aggregate
python3 scripts/analyze_results.py
```

## Target machine requirement

**Reproduction requires the 4-socket 192-core Kunpeng 920 (the root-cause
report's machine, with core 179 present).** The current development host is
2-socket / 128-core (cores 0-127, no cpu179), so `taskset -c 179` fails here
and reproduction cannot be confirmed locally. On this host, `build_engine.sh`
+ a single-core `run_case.sh` smoke (expect 0 fails, F5) validates that the
mechanism works; actual reproduction needs the target machine.

For local mechanism smoke (no reproduction expected):
```bash
CASE_TARGET_CORE=0 ./scripts/run_case.sh core179-repro-A01   # expect INCONCLUSIVE (healthy core)
```

## Judgment

- **PASS** = `total_fails > 0` (reproduction observed in some window;
  corruption always at `x[0]`, which is inside the CRC window). Log records
  fail count + rate + windows run.
- **INCONCLUSIVE** = `total_fails == 0` over all windows run (which reached
  K_total). The SDC is transient (0.5-1% per-iter rate under load), so a
  0-fail batch is a probability event, not a design failure — rerun in fresh
  load windows.
- **Negative control**: same case bound to a healthy core (e.g. 176) must
  return 0 fails. Single-core (no load) must also return 0 fails.

## Safety

Every load window is `timeout`-wrapped, ≤ 75 s, with a 5 s spin-up guard and a
3 s settle between windows. Hard cap `max_windows ≤ 60` per case (≤75 min).
Never run all-192-core long-duration load (root-cause report §11.3: corruption
can propagate to control flow and hang the machine).

## Families (100 cases)

| Family | # | Varies | Verifies |
|--------|---|--------|----------|
| A-scale | 20 | N ∈ {256,384,512} | F2: N≥256 threshold (§10.3 verified 256/512) |
| B-density | 15 | density 0.05–0.20 | indirect-addressing pressure |
| C-diag | 10 | diag-dominance 2–8 | SPD numerical conditioning |
| D-seed | 25 | 25 distinct (matrix,rhs) seeds | F3: corruption fixed at elem[0] regardless of matrix |
| E-mode | 10 | mode 1 (8) vs mode 0 (2) | F6: numeric-only ≈ 4× compute-both rate |
| F-iters | 10 | K ∈ {1500,2500,3000,5000} | F5: deeper K → more captures (K=5000 multi-window) |
| G-load | 10 | load_seconds / cpuset size | F2: ≥47-core threshold |
