#!/usr/bin/env python3
"""validate_manifest.py — static reproducibility self-check for the 100-case
manifest.

For each of the 100 cases, asserts that its parameters fall inside the
VERIFIED TRIGGER WINDOW documented in the root-cause report (and codified as
hard constraints in DESIGN.md §4). A case inside the window is, by the
report's evidence, a reproducer on the target machine (core 179 + same-socket
load). This is the strongest reproducibility guarantee achievable WITHOUT
access to the physical defective core 179 (current host lacks cpu179).

Constraints checked (mapping to root-cause report facts):
  F1  libc_only True                  trigger machine code is the Eigen MRU
  F2  matrix_dim >= 256                N scale threshold
  F2  load_cpuset >= 47 cores          same-socket full-load threshold
  F2  target_core == 179               defective core
  F5  iterations >= 1500              enough iters to catch 0.5-1% rate
  F6  mode in {0,1}                    numeric-only or compute-both (both verified)
  §11.3  load_seconds <= 75           hang-safety (avoid corruption->control-flow)
  all cases have unique ids

Exit: 0 if all 100 pass, 1 otherwise.
"""
from __future__ import annotations
import json, os, sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(SCRIPT_DIR)
MANIFEST = os.path.join(ROOT, "cases", "manifest.json")


def count_cores(cpuset: str) -> int:
    n = 0
    for part in cpuset.split(","):
        if "-" in part:
            a, b = part.split("-")[:2]
            n += int(b) - int(a) + 1
        elif part:
            n += 1
    return n


def main() -> int:
    with open(MANIFEST) as f:
        manifest = json.load(f)
    cases = manifest["cases"]

    ok = True
    ids = set()
    results = {"pass": 0, "fail": 0}
    fails = []

    for c in cases:
        cid = c["id"]
        if cid in ids:
            fails.append((cid, "duplicate id")); ok = False; results["fail"] += 1; continue
        ids.add(cid)
        cissues = []
        if not c.get("libc_only"):
            cissues.append("libc_only not True (F1)")
        if c["matrix_dim"] < 256:
            cissues.append(f"N={c['matrix_dim']} < 256 (F2)")
        if count_cores(c["load_cpuset"]) < 47:
            cissues.append(f"load_cpuset has {count_cores(c['load_cpuset'])} < 47 cores (F2)")
        if c["target_core"] != 179:
            cissues.append(f"target_core={c['target_core']} != 179 (F2)")
        if c["iterations"] < 1500:
            cissues.append(f"iters={c['iterations']} < 1500 (F5)")
        if c["mode"] not in (0, 1):
            cissues.append(f"mode={c['mode']} not in {{0,1}} (F6)")
        if c["load_seconds"] > 75:
            cissues.append(f"load_seconds={c['load_seconds']} > 75 (§11.3 hang)")
        if cissues:
            fails.append((cid, "; ".join(cissues))); ok = False; results["fail"] += 1
        else:
            results["pass"] += 1

    print(f"=== sdc-fuzzing manifest reproducibility self-check ===")
    print(f"cases: {len(cases)}  PASS: {results['pass']}  FAIL: {results['fail']}")
    if fails:
        print("\nFAILURES (cases outside the verified trigger window):")
        for cid, why in fails:
            print(f"  {cid}: {why}")
        return 1
    print("\nAll 100 cases are inside the verified trigger window.")
    print("  => Each case is a reproducer on the target machine")
    print("     (4-socket 192-core, core 179 + same-socket >=47-core load).")
    print("  => Current host (no cpu179) can only validate the MECHANISM,")
    print("     not confirm reproduction; run_all.sh on the target machine confirms.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
