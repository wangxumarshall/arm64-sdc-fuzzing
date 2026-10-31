# MOVBE SDC CORE179 LOCALIZATION REPORT V5 — Addendum 2026-08-26

This addendum supersedes the "V5 direction" sketched at the end of V4
(§V4.4 point 4: "patch the `str` to a `nop`"). That proposed V5 is **not**
pursued because it was found to be logically unworkable (see §V5.1). Instead,
V5 consolidates the full movbe variant spectrum (§V5.2), states the
methodology ceiling that bounds any further intervention experiment
(§V5.3), and records the honest status of cross-test-case checking on the
eigen family (§V5.4) — which remains an open gap.

The empirical base of V3 §§2–8 and V4 (§§V4.0–V4.5) still stands.

---

## §V5.1  Why the V4-proposed "patch str→nop" V5 is NOT done

V4 §V4.4 point 4 proposed: patch the `str w3,[x5,x1,lsl#2]` (offset
`0xbae80`) to `nop`, so the reload reads L1D without a preceding same-domain
store — to separate "store-induced" (store→reload forwarding / L1D-array
interplay) from "load-path-intrinsic".

This is **not a clean experiment**, and was rejected:

- Removing the `str` means `swapped[]` is never written. `input` is 64 KB (the
  whole L1D capacity) and `swapped` adds another 64 KB → 128 KB across a
  4-way 64 KB L1D. Removing one write per iteration perturbs the
  L1D-residency balance of the reload. A resulting 0-fail could mean either
  "the store was genuinely necessary" (store-induced) *or* "the reload
  degraded to an L2 miss and took a clean path" (false-clean). The two are
  inseparable. So the 0-fail cell is **unreadable**; only the "still
  triggers" cell would carry information.

- Symmetrically, patching the reload `ldr` (`0xbae84`) to `nop` destroys the
  checked value itself (the reload *is* the value being compared), so it
  isn't a probe anymore.

The root reason both fail is that **path and latency are physically bound at
the L1D level**: you cannot make a reload "miss L1D" (to change the path)
without also making it slower (changing the timing window). There is no
knob that changes *only* the path. See §V5.3.

---

## §V5.2  Consolidated movbe variant spectrum

All movbe-family probes share the hot-loop skeleton (compiled at `0xbae54`):

```
ldr  w4, [x2, x1, lsl #2]   ; FIRST load  (input[i])
rev  w3, w4                  ; ALU (byte-swap)  — patchable word
str  w3, [x5, x1, lsl #2]   ; store to swapped[]
ldr  w3, [x2, x1, lsl #2]   ; RELOAD     (input[i], hits L1D)  <- checked
cmp  w3, w4                  ; reload vs first-load  <- SDC check
```

### V5.2.1  Establishing triggerability (baseline + dump)

| variant | config | result |
|---------|--------|--------|
| `movbe` (original) | full 192-core + 179, auto seed | triggers (baseline logs 1–9 fails) |
| `movbe_dump` | hot loop byte-identical, dump in cold branch | **same fail count as original** |

Finding: the dump template does not break the trigger → all later probes are
built on the dump base. (See `movbe-dump-compiler-dce-root-cause`.)

### V5.2.2  Early probes A–E (what store→reload conditions trigger)

| probe | change | result | reading |
|-------|--------|--------|---------|
| A | no store | PASS | store is necessary |
| B | 16 nops between the two loads | PASS | back-to-back is necessary |
| C | store-to-load-forwarding on input | multi-core FP (contaminated) | design race, unusable |
| D | store to a fixed unrelated global | PASS | store must be same-domain/address-related |
| E | swapped on remote NUMA node | PASS | store and reload must share LLC domain |

Finding: trigger needs same-domain, address-related, back-to-back store→reload.

### V5.2.3  Footprint probes F/G1/G2/H

| probe | store footprint | result |
|-------|-----------------|--------|
| F | never crosses a cache line | PASS 0/5 (fixed seed — **methodology-tainted**) |
| G1 | 16 lines, one LLC set (max way pressure) | 0/5 (fixed seed — tainted) |
| G2 | 16 lines, 16 LLC sets (min pressure) | 0/5 (fixed seed — tainted) |
| H | sweep distinct lines (LINES=512) | **100% trigger** (auto seed) |

Finding + correction: F/G1/G2's 0/5 were obtained under a **fixed LCG seed**
(`fixed-lcg-seed-methodology-error`), which is one input pattern for a
seed-sensitive defect — the 0/5 is *seed luck*, not a real suppression.
Only H's 100%-under-auto-seed is reliable. The footprint-shape (way-pressure)
line of evidence is therefore **not usable as a conclusion**.

### V5.2.4  Back-to-back non-monotonicity (probeX / probeXN)

| extra no-op ALU between str and reload | fails |
|----------------------------------------|-------|
| 0 (back-to-back) | ~18 (baseline ~100%) |
| 1 | 1 |
| 2 | 6 |
| 64 (nop64) | 0 |

Finding: **non-monotonic** (0→18, 1→1, 2→6, 64→0). Not "tighter = more" —
a timing-race window of finite width.

### V5.2.5  Single-instruction patch sweep (V4, re-summarized)

Patching the one word at `0xbae7c` (`rev w3,w4`):

| patch | result |
|-------|--------|
| rev → mul | triggers (179) |
| rev → add | triggers (4 miscomp) |
| rev → nop (collapses to ldr→str→ldr→cmp) | triggers (4 miscomp) |

Finding: defect is **not instruction-specific**; lives in the
store→reload→compare path, not the ALU op.

### V5.2.6  Addressing-mode sensitivity (v_rev)

| variant | addressing | result |
|---------|------------|--------|
| original movbe_l1d | `ldr w4,[x2,x1,lsl#2]` | triggers (2–4 miscomp/3min) |
| v_rev (hand-written asm "structurally equivalent") | `add+ldr` | **0-fail** |

Finding: functionally-equivalent rewrite that changes the **compile-time
addressing mode** → AGU timing changes → defect killed. Trigger is sensitive
down to the addressing-mode-selection level.

### V5.2.7  Evict-path L1D-vs-L2 (30-min verified)

| variant | reload path | wall | fails |
|---------|-------------|------|-------|
| `movbe_l1d` | L1D | 3 min | 17 |
| `movbe_l2` (dc civac+dsb evict) | L2/L3 | **30 min** | **0** |
| `mrn_rmw_l1d` (forwarding) | L1D/forwarding | — | triggers |
| `mrn_rmw_l1d` evict | L2/L3 | **30 min** | **0** |

Finding + boundary: evict-path 0-fail over 30 min. **But this 0-fail is not
cleanly attributable** — evict changes *both* the reload path (L1D→L2) *and*
the latency (L2 is slower; `dsb sy` further stalls). Per §V5.3, the 0-fail
cannot separate "bypassed L1D" from "slower path missed the timing window."

---

## §V5.3  Methodology ceiling — intervention experiments can only exclude, not attribute

The repeated failure mode across the whole investigation: every available
intervention knob that changes the **path** also changes the **timing window**,
because at the cache hierarchy path and latency are physically bound (you
cannot make a reload "miss L1D" without also making it slower). Therefore:

| knob | intended variable | also changes | 0-fail readable? |
|------|-------------------|-------------|------------------|
| dc civac evict | path L1D→L2 | latency (+dsb stall) | **no** |
| SCTLR.C=0 (disable L1D) | path | latency (stall_backend ×12.8) | **no** |
| remove str | path (no store) | L1D residency balance | **no** |
| remove reload ldr | — | destroys the checked value | destroys probe |
| insert no-op ALU | timing window | path unchanged ✓ | **yes (only "still triggers")** |
| change addressing mode | addressing | AGU timing | **no** |

Consequences:
- **Exclusion is possible** (the "still triggers" cell): e.g. rev→nop still
  triggering excludes "the rev instruction identity is necessary"; triggering
  across all footprints excludes "L1D capacity pressure is necessary."
- **Attribution is not possible**: 0-fail under any path-changing intervention
  is unreadable (true-suppression vs false-clean inseparable).
- The defect's location is pinned to: **the reload (load) return path + the
  timing-race window preceding it, on core 179, activated by full-core
  concurrent pressure, root cause = 179 hardware fault.** L1D-array is the
  *most-suspected* but **not cleanly confirmed** (evict 0-fail unreadable;
  nop64 still goes through L1D yet 0-fail refutes "L1D-fetch is sufficient").
  Which load-path stage (L1D array / store-buffer forwarding / load port /
  register file) — **not separable** with intervention tools.

A "decoupling probe that changes only the path" was proposed and retracted
twice (once as a path probe, once as PMU-based attribution) — both
over-promised. PMU counts defined micro-architectural events; a silent
data-wrong load triggers none of them, and is statistically buried at
~0.24/min; cross-configuration PMU comparison hits the same path↔timing
wall. A truly non-perturbing *and* fault-relevant discriminator would be L1D
ECC/RAS (a silent defect with zero ECC events would exclude "array-side
stored-wrong/read-out-wrong"), but the machine is firmware-first (GHES/APEI),
so dmesg having zero cache events does not prove the array is clean — the
firmware may be absorbing them. This discriminator is therefore also
conditional, not clean.

---

## §V5.4  Cross-test-case check on the eigen family — honest status (open gap)

Question asked: do the *other* effective SDC test cases (eigen) trigger in the
**same region** movbe is pinned to (reload return path + timing window)?

The eigen hot loop (`tests/cpu/eigen_gemm/double14.cpp:55–78`) is
structurally different — it has an FMA computation stage, not just
load→compare-load:

```
_x = lhs; _y = rhs;          // step1: memcpy copy (load inputs)
_prod = _x * _y;              // step2: GEMM (internal load _x[i,j]/_y[i,j] + FMA)
_x.isApprox(lhs); memcmp(_x, lhs);   // step3: check input-copy == golden
_prod.isApprox(prod);                // step4: check result == golden  ← all 10 fails here
```

All eigen fails (30-min stress: 10× `_prod.isApprox failed`; 15-min dump:
"product miscompare") land on **step4 (the computation result)**, never on
step3.

### V5.4.1  First (over-claimed) reading — retracted

I first claimed: step3 = 0 fail ⇒ "eigen's input load is clean ⇒ B-input
(the load path) is excluded ⇒ eigen is NOT in the movbe-pinned region." This
was an **over-claim**, caught on review:

- step3's `memcmp(_x, lhs)` compares `_x`'s *memory content* vs golden. GEMM
  (step2) only reads `_x`, never writes it, so `_x`'s memory is always the
  step1-copy value. step3 passing only proves **the step1 memcpy copy didn't
  write wrong data** — it does *not* cover the GEMM-internal loads of
  `_x[i,j]` (different addressing, different dependency timing).
- The defect is **intermittent** (~0.24/min): "this particular load was fine"
  does not imply "that particular load was fine." step1-copy being clean
  says nothing about step2-internal loads.

So the load path on eigen is **not excluded**. The defect could still be:
- **A** — FMA/SIMD computation error (the multiply mis-computes), or
- **B-gemm-load** — a GEMM-internal load `_x[i,j]` reads wrong and feeds a
  wrong FMA (not covered by step3), or
- **B-compare** — the golden `prod` read wrong at comparison time.

### V5.4.2  Attempted discriminator `eigen_gemm_double_ab_split` — failed

To separate A from B-gemm-load, a probe was built: run the same GEMM twice on
the same `_x`/`_y` (`prod_a`, `prod_b`), add an **internal** check
`memcmp(prod_a, prod_b)` (covers the GEMM-internal load consistency) plus the
external golden check. Theory: external-fail + internal-fail ⇒ B-gemm-load
alive; external-fail + internal-pass ⇒ A alive.

**Result: probe is broken, the 0-fail is unreadable.** Eigen **inlines both
`x*y` calls** into one large hand-written loop (no `bl`), restructuring the
entire hot loop and filling it with `stp`/`ldp`; each iteration slowed from
~5 ms (original) to ~1895 ms (**380× slower**). Since core 179 is sensitive
to hot-loop layout down to the addressing-mode level, the 0-fail (30 min,
both INTERNAL and EXTERNAL = 0) cannot distinguish "slowed, didn't hit the
intermittent defect" from "layout changed, defect suppressed." Same lesson
as `movbe_dump` (changing even a cold branch suppresses the trigger).

Single-instruction patching of an inlined GEMM's `fmadd` (analogous to movbe
V4) is also not clean: the inlined FMA chain has `d0` as both input and
accumulator, so patching one `fmadd` breaks the dependency chain → all-fail,
not a discriminator; and it still changes both computation path and timing
(§V5.3 ceiling).

### V5.4.3  Honest status

- **eigen's A vs B-gemm-load is not separable with intervention tools.** Two
  successive over-claims (step3-implies-exclusion, ab_split-implies-
  different-path) were both retracted. This is recorded as a **known open
  gap**, not a conclusion.
- What *is* established: eigen's fail is on the **computation result**
  (step4), not on an input-copy memcmp (step3). It involves the GEMM stage,
  which is a load+FMA mix; which sub-path is unknown.
- The cross-family commonalities therefore reduce to the two that are
  cleanly common to all three families (movbe, mrn_rmw, eigen): **(1) only on
  core 179, (2) requires full-core concurrent pressure.** "L1D as the common
  lesion" is **not** established across all families — it is the
  most-suspected lesion for movbe/mrn_rmw only; eigen's location is open.

---

## §V5.5  Consolidated localization (state as of this addendum)

| claim | status | basis |
|-------|--------|-------|
| SDC on the reload (load) return path | ✅ clean | patch sweep: any ALU/nop still triggers; reload is the checked value |
| reload has a preceding timing-race window | ✅ clean | back-to-back non-monotonic (0→18→1→6→0); addressing-mode timing; nop rate drop |
| timing race is the **root cause** | ❌ no | root cause = 179 hardware fault; timing is an activation mechanism |
| store is a necessary condition | ✅ clean | probe A (no store) → PASS |
| full-core concurrent pressure required | ✅ clean | single-core 179 doesn't trigger; 192-core does |
| only on core 179 | ✅ clean | all families |
| "data must be fetched from L1D to be wrong" | ❌ refuted | nop64 still goes through L1D yet 0-fail (not sufficient); necessity unprovable (path↔latency bound) |
| pinned to L1D array | ❌ not clean | evict 0-fail unreadable (path+latency) |
| L1D is the **cross-family** common lesion | ❌ not established | eigen's location is an open gap; movbe/mrn_rmw only |
| specific load-path stage (L1D/fwd/load port/regfile) | ❌ not separable | intervention ceiling |

**Net:** the defect is pinned to the **reload return path + its preceding
timing-race window on core 179**, hardware-rooted, concurrency-activated.
Finer attribution (L1D vs forwarding vs load port vs register file) is beyond
intervention tools; eigen's A-vs-B-gemm-load is an open gap.

---

## §V5.6  Open directions (not executed — require non-intervention means)

1. **EINJ read-only check** — `modprobe einj`; read `available_error_type` to
   confirm whether the firmware surfaces cache-class errors at all (the
   debugfs node was absent pre-`modprobe`). Even if it works, it only
   confirms the channel reports *stored-wrong* class errors; a *read-path*
   fault (correct array, wrong delivery) is ECC-invisible by construction.
2. **Single-instruction binary patch of an inlined GEMM fmadd** — analogous
   to movbe V4, but high-risk (breaks FMA dependency chain) and still
   path+timing coupled. Not recommended without a cleaner plan.
3. **Accept the gap** — document that eigen's A vs B-gemm-load is not
   separable with available tools, and that the cross-family common lesion
   is "179 hardware fault itself (affects both load and FP-compute paths),"
   *not* a specific microarchitectural unit.
