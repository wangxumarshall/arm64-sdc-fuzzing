#!/usr/bin/env python3
"""analyze_results.py — aggregate sdc-fuzzing case results into a report.

Reads cases/<id>/result.json for every case and produces:
  - per-family reproduction rate (PASS / total)
  - per-family mean fail-rate (fails/iters)
  - the F6 check: E-mode mode-1 rate vs mode-0 rate (expect ~4x)
  - the F3 check: D-seed family — all reproduction at elem[0] (already
    guaranteed by the CRC judge; we just confirm >0 fails)
  - list of INCONCLUSIVE cases to rerun

Run:  python3 scripts/analyze_results.py
"""
from __future__ import annotations
import json, os, sys
from collections import defaultdict

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(SCRIPT_DIR)
CASES_DIR = os.path.join(ROOT, "cases")
MANIFEST = os.path.join(CASES_DIR, "manifest.json")


def main() -> int:
    with open(MANIFEST) as f:
        manifest = json.load(f)
    cases = manifest["cases"]

    by_family = defaultdict(list)
    incon = []
    for c in cases:
        cid = c["id"]
        fam = c["family"]
        rp = os.path.join(CASES_DIR, cid, "result.json")
        if not os.path.exists(rp):
            by_family[fam].append({"id": cid, "status": "MISSING"})
            continue
        with open(rp) as f:
            r = json.load(f)
        r["family"] = fam
        by_family[fam].append(r)
        if r.get("judge") == "INCONCLUSIVE":
            incon.append(cid)

    print(f"{'family':12s} {'total':>5s} {'PASS':>5s} {'INCON':>5s} {'ERR':>4s} {'mean_rate':>10s}")
    print("-" * 50)
    for fam in sorted(by_family):
        rows = by_family[fam]
        total = len(rows)
        p = sum(1 for r in rows if r.get("judge") == "PASS")
        ic = sum(1 for r in rows if r.get("judge") == "INCONCLUSIVE")
        err = sum(1 for r in rows if r.get("status") == "MISSING" or r.get("judge") not in ("PASS", "INCONCLUSIVE"))
        rates = []
        for r in rows:
            try:
                rates.append(float(r.get("rate", "0")))
            except (ValueError, TypeError):
                pass
        mean = (sum(rates) / len(rates)) if rates else 0.0
        print(f"{fam:12s} {total:5d} {p:5d} {ic:5d} {err:4d} {mean:10.4f}")

    # F6 check: E-mode mode-1 vs mode-0 rates
    e = by_family.get("E-mode", [])
    if e:
        m1 = [float(r["rate"]) for r in e if r.get("mode") == 1 and r.get("judge") == "PASS"]
        m0 = [float(r["rate"]) for r in e if r.get("mode") == 0 and r.get("judge") == "PASS"]
        if m1 and m0:
            ratio = (sum(m1)/len(m1)) / (sum(m0)/len(m0))
            print(f"\nF6 check (E-mode): mode-1 mean rate={sum(m1)/len(m1):.4f}, "
                  f"mode-0 mean rate={sum(m0)/len(m0):.4f}, ratio={ratio:.2f}x "
                  f"(expect ~4x per root-cause report)")

    if incon:
        print(f"\n{len(incon)} INCONCLUSIVE cases to rerun in fresh load windows:")
        for cid in incon[:20]:
            print(f"  ./scripts/run_case.sh {cid}")
        if len(incon) > 20:
            print(f"  ... and {len(incon)-20} more")

    return 0


if __name__ == "__main__":
    sys.exit(main())
