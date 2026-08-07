# CLAUDE.md — OpenDCDiag (ARM64 port)

Project-specific guidance for Claude Code working in this repository.
Read this before building or running.

## What this is

Intel's OpenDCDiag CPU/GPU diagnostic tool, here under an ARM64 (AArch64)
port targeting Kunpeng 920 (ARMv8.1-A). Build system is Meson + Ninja.
Output binary: `opendcdiag` (was historically `sandstone`).

## Toolchain (verified on this host)

- openEuler / aarch64, GCC 12.3.1 (`gnu++23` supported), Meson 1.3.1, Ninja 1.11.1
- Deps: boost 1.83 (headers only is fine — `meson.build` falls back from
  header-check), gtest_main 1.14, libzstd 1.5.5, zlib 1.2.13.
- Eigen: system pkg is 3.3.8 (too old; needs >= 5.0) → build uses the
  bundled `third-part/` Eigen 5.0.1 submodule. See "Pitfall" below.

## Build commands

```console
meson setup builddir --buildtype=release
ninja -C builddir
./builddir/opendcdiag --version
```

Cross from x86: `meson setup builddir --cross-file meson-cross-arm64.ini`.
Fuzzing (AFL): `./scripts/build-fuzzing.sh build-fuzzing` (needs `afl-gcc`).

## Pitfall: third-part/ Eigen submodule does not auto-init

**This is the #1 thing that breaks a fresh build.** Root cause, in full:

- `opendcdiag/` is itself a git submodule of `../` (the parent repo).
- `opendcdiag/third-part` (Eigen 5.0.1) is a *nested* submodule.
- There is **no `.gitmodules` inside `opendcdiag/`** — the submodule config
  for `opendcdiag/third-part` lives in the *parent* `.gitmodules`.
- `third-part/` is listed in `opendcdiag/.gitignore` (fetched, not committed).
- Consequence: a plain `git submodule update --init` run from inside
  `opendcdiag/` finds nothing and leaves `third-part/` empty. The next
  `meson setup` hits the `assert(fs.is_dir('../../third-part/Eigen'))` in
  `tests/cpu/meson.build` and fails.

**Fix — always do one of these on a fresh checkout:**

```console
git submodule update --init third-part              # from inside opendcdiag/
# or from the parent repo:
git submodule update --init --recursive opendcdiag/third-part
# or without git: clone Eigen 5.0.1 straight in:
git clone --depth 1 --branch 5.0.1 https://gitlab.com/libeigen/eigen.git third-part
```

If `meson setup` prints `Dependency eigen3 found: NO` followed by
`Using bundled Eigen 5.0 source from third-part/`, the submodule is present
and the fallback is working. If instead you see the `assert` failure, it is
not.

## Full-load / continuous run

`-T forever` = loop indefinitely (the key "nonstop" flag).
`-n <N>` = run with N threads. **Do NOT use `-n 0`** — in this build `0` is
treated as out-of-range and clamped to 1, so only one core runs (the warning
`value out of range for option '-n / --threads': 0` appears in stdout). For
full load pass the explicit CPU count: this Kunpeng 920 host has `nproc` = 128,
so use `-n 128`.
`--ignore-os-error --ignore-timeout` = don't halt on errors/timeouts.

```console
./builddir/opendcdiag -T forever -n 128 --ignore-os-error --ignore-timeout -o builddir/run.log -q
```
(`builddir/` is gitignored; keep a log file instead of `/dev/null` so SDC
errors are captured.)

Timed variant: `-T 24h`. Directed ARM64 tests: `-e arm64_sdc -e neon_add -e arm_crypto`
(note: `--list` does not print the arm64 tests, but `-e <name>` runs them).
Self-tests: `./builddir/opendcdiag --selftests --max-test-loop-count 1`
(exits `invalid` by design — the selftests deliberately fail/crash to verify
the framework's failure detection; count `result: pass` for the positive cases).
Bats suite: `bats bats/sanity-check/` (bats is not installed on this host; the
directed-test + full-load runs are the authoritative ARM64 gate).
Full option reference: `framework/sandstone_opts.cpp` (`usage()`).

## ARM64 port vs upstream sync notes

The `opendcdiag/` subtree is synced from `github.com/opendcdiag/opendcdiag`
main. Upstream is x86-only; the local ARM64 additions are the 27 files under
`framework/device/cpu/arm64/`, `tests/cpu/arm64/`, `docs/ARM64_*`,
`docs/sdc1-01-02-core179-diagnostics/`, `CLAUDE.md`, `meson-cross-arm64.ini`,
plus local edits in 5 shared files (`meson.build` aarch64 flags,
`framework/device/cpu/meson.build` arm64 subdir, `tests/cpu/meson.build`
bundled-Eigen fallback, `.gitignore`, `README.md` ARM64 docs).

Known ARM64/x86 divergences that surface on each upstream sync:
- `cpu_info_t` gained `die_id` (upstream renamed `tile_id`→`die_id`,
  commit 4094e185). `arm64_topology.cpp` must use `device_info[i].die_id`,
  not `tile_id`.
- `framework/mmap_region.c` was deleted upstream (logging refactor merged it
  into `LogMessagesFile`); it is dead code locally and removed on sync.
- `unittests` binary (`meson.build` `executable('unittests', ..., native: true)`)
  hard-codes `-march=haswell` and is x86-only — it does NOT build on aarch64
  and is `build_by_default: false`, so it's not part of the default build.
  `--test-tests` needs it; use `--selftests` instead on ARM64.

## Expected ARM64 warnings (harmless)

- `sysv_abi attribute ignored` — `framework/sandstone_run.cpp:664`, x86-only ABI
  on an ARM64 build. Ignored by design. (Upstream moved `test_end` from
  `sandstone.cpp` to `sandstone_run.cpp`; the line number moves with it.)
- `attributes at the beginning of statement are ignored` — `[[assume(...)]]`
  in `framework/device/cpu/topology.cpp`. GCC 12 limitation, semantics fine.
- `-Wrestrict` note in `framework/logging.cpp` — libstdc++ memcpy folding noise.

These do not affect correctness. If new ARM64 warnings appear (especially in
`framework/device/cpu/arm64/`), treat them as real regressions.

## Reference docs in this repo

- `docs/ARM64_PORTING_PLAN.md`, `docs/ARM64_PORTING_SUMMARY.md` — port design
- `docs/writing_tests.md` — how to author tests
- `README.md` — build/run quickstart (kept in sync with this file)
