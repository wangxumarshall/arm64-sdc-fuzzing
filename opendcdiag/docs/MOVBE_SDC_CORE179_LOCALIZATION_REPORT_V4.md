# MOVBE_SDC_CORE179_LOCALIZATION_REPORT V4 — Addendum 2026-08-26

## §V4.5  30-minute re-test of the L2/L3 (evict) reload path — observation

Motivation: the earlier claim "SDC disappears when reload is forced to serve
from L2/L3 via `dc civac` eviction" was cited from V3-era memory records
(l1d-read-path-sdc-confirmed / load-port-downstream-sdc-confirmed), but those
records did **not specify the run duration** and their log files are no longer
present. The V4 sweep itself showed `nop`'s first-fail ttf up to 119s (~3 min
to first trigger), so a short-duration 0-fail is not evidence of
disappearance. The evict-path probes were therefore re-run at a verified
30-minute wall-clock duration.

### V4.5.1  Design

Two genuine evict-path probes (both evict the relevant cache line before the
reload via `dc civac, <addr>` + `dsb sy`, forcing the reload to serve from
L2/L3 rather than L1D):

- `movbe_l2` (movbe family): evicts `input[i]` line before the reload.
- `mrn_rmw_l1d` (mrn_rmw family): evicts between the `str` and the `ldr`,
  breaking store-buffer forwarding and forcing the load from L2/L3.

Run config: `--enable=<test> --max-test-loop-count=0 -T forever -n 192
--ignore-timeout`, full 192 cores (incl. 179), auto seed (no `-s`), **no
`--ignore-os-error`** (first fail stops the run cleanly). Each test capped at
a 30-min wall clock by a background killer (which produces the terminal
`result: interrupted` line). Verified both binaries contain the tests and
source is unchanged (`tests/cpu/misc/movbe_l1d_vs_l2.cpp:131` `evict_l1d_line`
uses `dc civac + dsb sy`).

### V4.5.2  Observation

| test | wall clock (verified) | result:fail | result:pass | result:interrupted | xor | cpu-mask | ttf |
|------|----------------------|-------------|-------------|---------------------|-----|----------|-----|
| movbe_l2 | 30 min (15:36:34→16:06:36) | **0** | 128 | 1 (killer) | none | none | none |
| mrn_rmw_l1d | 30 min (16:06:36→16:36:37) | **0** | 847 | 1 (killer) | none | none | none |

Both evict-path probes ran the full 30 min wall clock with **0 fails**. The
retry-count difference (128 vs 847) reflects per-iteration cost: `movbe_l2`
iterations are ~14s (large 64KB buffer sweep + evict per element), `mrn_rmw_l1d`
~2.4s. Neither produced any miscompare data block.

For contrast, the L1D-hit-path V4 variants (§V4.2) each produced 2–3 fails
within a ~3-min window under the same core/seed regime. Thus at the 30-min
scale the L1D path triggers and the evict path does not.

### V4.5.3  Boundary (what this does and does not establish)

This 30-min re-test establishes, more reliably than the earlier
duration-unspecified records, the **observation** that forcing the reload
through L2/L3 (via eviction) yields no SDC over 30 minutes, whereas the
L1D-hit path yields SDC over minutes. It does **not** by itself clean-parse
the cause: `dc civac + dsb sy` both changes the data path (reload no longer
hits L1D) **and** inserts a barrier that lengthens timing, so the evict-path
0-fail remains compatible with both "path change" and "timing lengthened"
explanations (the long-standing unresolved tail noted in l1d-is-sdc-rootcause-
verified / timing-race-final-conclusion). It is also not a mathematical zero
rate — only a rate demonstrably far below the L1D-hit path's at this duration.

---

## §V4.0  Single-instruction binary-patch sweep: defect is NOT instruction-specific

Supersedes/refines §12 (V3.1 addendum). Same empirical base (§§2-8 of the V3
report still stands). This addendum reports a controlled single-instruction
substitution experiment that *decisively refutes* the earlier hypothesis that
the core-179 defect is sensitive to the identity of the pre-`str` ALU
instruction (e.g. `rev` as a "bit-flipping high-current" instruction).

### V4.1  Experimental design

The SDC check in `movbe_l1d_run` (compiled hot loop at `0xbae54`) is a
**round-trip load-vs-reload comparison**, NOT a check on the byte-swapped
value. GCC optimized the second `bswap` out of the loop (because
`bswap(bswap(x))==x`), so the hot loop is:

```
bae78: ldr  w4, [x2, x1, lsl #2]   ; w4 = input[i]         (FIRST load)
bae7c: rev  w3, w4                  ; <-- PATCHED instruction
bae80: str  w3, [x5, x1, lsl #2]   ; swapped[i] = w3        (never read again)
bae84: ldr  w3, [x2, x1, lsl #2]   ; w3 = input[i]          (RELOAD, hits L1D)
bae88: cmp  w3, w4                  ; reload (w3) vs first-load (w4)  <- SDC check
bae8c: b.ne miscompare
bae90: add  x1, x1, #1
bae94: cmp  x1, #0x4000
bae98: b.ne loop
```

Key property: the patched instruction at `0xbae7c` (`rev w3,w4`) writes **only
`w3`**, whose sole live consumer is the store at `bae80`. The store value
(`swapped[i]`) is never read. The compare at `bae88` uses the RELOAD (`w3` at
`bae84`) vs the FIRST load (`w4` at `bae78`) — both `input[i]` reads, neither
derived from the patched instruction's *value*. Therefore substituting the
instruction at `0xbae7c` changes **only**:
  (a) the pre-`str` ALU op identity,
  (b) its transient current,
  (c) the timing of `str` relative to the first `ldr`,
and **not** the checked value.

Four binaries were produced by patching the single 4-byte instruction word at
file offset `0xbae7c`. The rest of the hot loop is byte-identical across all
four (verified by `objdump`, §V4.3).

| variant | instr @0xbae7c | encoding   |
|---------|---------------|------------|
| rev     | `rev  w3,w4`  | `5ac00883` |
| mul     | `mul  w3,w4,w4` | `1b047c83` |
| add     | `add  w3,w4,w4` | `0b040083` |
| nop     | `nop`         | `d503201f` |

Each run: `--enable=movbe_l1d --max-test-loop-count=0 -t 3m -n 192
--ignore-timeout` (full 192-core load, auto seed). `rev`/`mul` under the
earlier `--ignore-os-error` config (per-retry retry; 3 fails collected), `add`/
`nop` under first-fail-stops config.

### V4.2  Result — all four trigger on core 179

| variant | result:fail | cores in mask | X position (char idx) | xor values (sample)          | ttf (ms, first) |
|---------|-------------|---------------|------------------------|------------------------------|-----------------|
| rev     | 3           | 1             | **179**                | E0D5801A, C192C47E, 31E3EA28, 31D56A92 | 918             |
| mul     | 3           | 1             | **179**                | F6F2C99B, 3500501B, 12DF5978 | 28982           |
| add     | 2           | 1             | **179**                | 7D7987E7, 104DB030           | 288             |
| nop     | 2           | 1             | **179**                | AF4852FB, 3768935A           | 101206          |

**Every** patched variant triggers on core 179 (identical cpu-mask `X` position
across all four), at comparable rate (2–3 fails per ~3 min). The xor values are
random per run (data-dependent, seed-dependent), not instruction-identifying.

### V4.3  Byte-identical hot loop (objdump verification)

`objdump -d` of the hot loop `0xbae78`–`0xbae98` for all four binaries confirms
that **the only differing word is `0xbae7c`**; the load/store/reload/cmp/
branch/index-update are identical instruction-for-instruction, including
register allocation (`w4`=first load, `w3`=patched/store/reload target,
`x1`=index, `x2`=input base, `x5`=swapped base). Therefore any divergence in
trigger behavior is attributable to that one instruction word — and there is
**no** divergence: all four trigger on 179.

### V4.4  Conclusion

1. **The core-179 defect is NOT instruction-specific.** Substituting `rev` with
   `mul` (a very different ALU op), `add` (another), or a `nop` (removing the
   ALU op entirely — so `str` directly follows the first `ldr`) does **not**
   suppress, reduce, or relocate the defect. All four trigger on core 179 at
   the same rate.

2. **This refutes the "rev as high-current bit-flipping trigger" hypothesis.**
   `nop` in particular collapses the loop to `ldr → str → ldr(reload) → cmp`:
   no intervening ALU op at all, `str` back-to-back with the first `ldr`, reload
   back-to-back with the `str`. The defect still fires. The defect therefore
   lives in the **store→reload→compare path**, i.e. the interaction of:
   - the first `ldr w4, [x2,x1,lsl#2]` (load of `input[i]`),
   - the `str w3, [x5,x1,lsl#2]` (store to the `swapped[]` array, a *different*
     base address — this is a same-LLC-domain store, see V3 §12 addendum), and
   - the reload `ldr w3, [x2,x1,lsl#2]` (re-read of `input[i]`, hits L1D) and
     the `cmp w3,w4`.

3. **Reinforces, does not contradict, the timing-race characterization**
   (V3 §12 / timing-race-final-conclusion memory): the defect is a timing race
   on the load/store/reload sequence on core 179, whose root cause is a
   core-179-specific hardware marginality. Removing the `rev` ALU op
   *tightens* the str→reload spacing (nop variant: `str` immediately after
   first `ldr`, reload immediately after `str`) yet the rate is unchanged,
   consistent with a race that is already saturated at these spacings — i.e.
   the defect is not finely tuned to one ALU-op latency.

4. **Open question (direction for V5):** now that the pre-`str` ALU op is ruled
   out, the discriminating instruction is the **store** itself (or the
   store→reload adjacency). A clean next experiment: patch the `str` to a `nop`
   (so reload reads L1D without a preceding store in this domain) — if that
   suppresses the defect, it pins the trigger to the store→reload forwarding/
   L1D-array path; if it still triggers, the defect is in the raw reload-read
   path independent of the store. This separates "store-induced" from
   "load-path-intrinsic."
