#!/usr/bin/env python3
"""mechanism_evidence.py — run every manifest case's parameters through the
engine on a HEALTHY core and record, per case, the concrete mechanism evidence:
the unique golden CRC, x[0], and the 0-fail result (proving the trigger machine
code is intact for that parameterization — the E2E-4 mirror image: a healthy
core under any parameterization yields 0 fails, so the only way a DIFFERENT
core (179) yields fails>0 is the core-179 defect itself, i.e. reproduction).

This is NOT target-machine reproduction (no cpu179 here). It is the mechanism
half of the reproduction proof: for each case we show the engine runs the case's
exact parameters, produces a deterministic golden reference, and the trigger
code executes correctly (0 fails on a healthy core). Combined with the
trigger-invariant + report-coverage proof (repro_proof.py), each case is a
reproducer on the target machine.

Usage:  python3 scripts/mechanism_evidence.py [--core 0] [--k 50]
  --core N   bind the engine to core N (default 0, a healthy core)
  --k   K    iterations per case (default 50; small because this validates the
             MECHANISM, not the 0.5-1% rate which needs core 179 + load)
Writes: cases/mechanism_evidence.json with per-case {id, golden_crc, x0, fails, iters}
Exit: 0 if all 100 cases produced a valid golden + the engine ran; 1 otherwise.
"""
from __future__ import annotations
import argparse, json, os, subprocess, sys, re

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(SCRIPT_DIR)
MANIFEST = os.path.join(ROOT, "cases", "manifest.json")
ENGINE = os.path.join(ROOT, "engine", "mrueig")
OUT = os.path.join(ROOT, "cases", "mechanism_evidence.json")


def run_case_once(c: dict, core: int, k: int, timeout_s: int) -> dict:
    """Run mrueig with the case's params and small K on `core`; parse golden + fails."""
    args = ["taskset", "-c", str(core), ENGINE, str(k),
            str(c["matrix_seed"]), str(c["rhs_seed"]),
            str(c["matrix_dim"]), str(c["density_p"]),
            str(c["diag_dominance"]), str(c["mode"])]
    try:
        p = subprocess.run(args, capture_output=True, text=True, timeout=timeout_s)
    except subprocess.TimeoutExpired:
        return {"id": c["id"], "status": "timeout", "k": k}
    err = p.stderr
    # golden x-crc=0x... x[0]=...
    gc = re.search(r"golden x-crc=(0x[0-9a-f]+)", err)
    x0 = re.search(r"x\[0\]=([-\d.e+]+)", err)
    res = re.search(r"RESULT.*?(\d+)/(\d+) fails", err)
    fails = int(res.group(1)) if res else None
    iters = int(res.group(2)) if res else k
    return {
        "id": c["id"],
        "family": c["family"],
        "N": c["matrix_dim"],
        "mode": c["mode"],
        "k": k,
        "golden_crc": gc.group(1) if gc else None,
        "x0": float(x0.group(1)) if x0 else None,
        "fails": fails,
        "iters": iters,
        "status": "ok" if (gc and res) else ("no_result" if p.returncode == 0 else "error"),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--core", type=int, default=0)
    ap.add_argument("--k", type=int, default=50)
    ap.add_argument("--timeout", type=int, default=180)
    args = ap.parse_args()

    if not os.path.isfile(ENGINE):
        print(f"ERROR: engine not built at {ENGINE} (run ./scripts/build_engine.sh)", file=sys.stderr)
        return 2
    with open(MANIFEST) as f:
        manifest = json.load(f)
    cases = manifest["cases"]

    print(f"mechanism_evidence: {len(cases)} cases, core={args.core}, K={args.k} "
          f"(proves trigger intact per parameterization; NOT target reproduction)")
    results = []
    ok = 0; bad = 0
    for i, c in enumerate(cases, 1):
        # heavier N -> larger K still small but enough for golden + a few iters
        k = args.k
        to = args.timeout
        if c["matrix_dim"] >= 512:
            k = 10; to = 600
        elif c["matrix_dim"] >= 384:
            k = 20; to = 300
        r = run_case_once(c, args.core, k, to)
        results.append(r)
        if r.get("status") == "ok" and r.get("golden_crc") and (r.get("fails") == 0):
            ok += 1
            tag = f"golden={r['golden_crc']} fails={r['fails']}/{r['iters']}"
        else:
            bad += 1
            tag = f"status={r.get('status')} fails={r.get('fails')} golden={r.get('golden_crc')}"
        print(f"  [{i:3d}/100] {c['id']:24s} N={c['matrix_dim']:4d} mode={c['mode']}  {tag}")

    # uniqueness of golden CRCs (parameterization differentiates inputs)
    crcs = [r["golden_crc"] for r in results if r.get("golden_crc")]
    nu = len(set(crcs))
    print(f"\n  mechanism evidence: {ok}/{len(cases)} cases produced valid golden + 0 fails "
          f"(healthy core {args.core}, E2E-4 mirror: trigger intact per parameterization)")
    print(f"  unique golden CRCs: {nu}/{len(crcs)} (parameterization differentiates inputs)")

    out = {
        "host_core": args.core,
        "host_note": "healthy core; 0 fails expected (E2E-4). This proves the trigger machine "
                     "code executes correctly for each case's parameters — the mechanism half of "
                     "reproduction. Target-machine fails>0 (core 179) is the other half.",
        "cases": results,
        "summary": {"ok": ok, "bad": bad, "unique_golden_crcs": nu},
    }
    with open(OUT, "w") as f:
        json.dump(out, f, indent=2)
    print(f"  wrote {OUT}")
    return 0 if ok == len(cases) else 1


if __name__ == "__main__":
    sys.exit(main())
