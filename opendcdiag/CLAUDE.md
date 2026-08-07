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
  bundled `third-part/` Eigen 5.0.1 source, which is **committed to the repo**
  (vendored, not a submodule). No fetch step needed.

## Build commands

```console
meson setup builddir --buildtype=release
ninja -C builddir
./builddir/opendcdiag --version
```

Cross from x86: `meson setup builddir --cross-file meson-cross-arm64.ini`.
Fuzzing (AFL): `./scripts/build-fuzzing.sh build-fuzzing` (needs `afl-gcc`).

## Bundled Eigen 5.0.1 source (third-part/)

The Eigen 5.0.1 source tree is **vendored directly under `third-part/`** as
ordinary committed files — it is no longer a git submodule, so **no
`git submodule update --init` step is needed** on a fresh checkout. This was
previously the #1 fresh-build breaker (a nested submodule whose config lived
in the parent repo, invisible to a plain `git submodule update --init` run
from inside `opendcdiag/`); vendoring eliminates that footgun.

`tests/cpu/meson.build` prefers a system `eigen3 >= 5.0` when present and
otherwise falls back to the bundled tree via
`assert(fs.is_dir('../../third-part/Eigen'))`. If `meson setup` prints
`Using bundled Eigen 5.0 source from third-part/`, the vendored tree is
being used. To switch Eigen versions, replace the contents of `third-part/`
(keep the flat layout: `third-part/Eigen/Core` must exist).

## Full-load / continuous run

`-T forever` = loop indefinitely (the key "nonstop" flag).
`-n 0` = one thread per logical CPU (full load).
`--ignore-os-error --ignore-timeout` = don't halt on errors/timeouts.

```console
./builddir/opendcdiag -T forever -n 0 --ignore-os-error --ignore-timeout -o /dev/null -q
```

Timed variant: `-T 24h`. Directed ARM64 tests: `-e arm64_neon -e arm64_sdc`.
Self-tests: `./builcdiag/opendcdiag --test-tests`. Bats suite: `bats bats/sanity-check/`.
Full option reference: `framework/sandstone_opts.cpp` (`usage()`).

## Expected ARM64 warnings (harmless)

- `sysv_abi attribute ignored` — `framework/sandstone.cpp:868`, x86-only ABI
  on an ARM64 build. Ignored by design.
- `attributes at the beginning of statement are ignored` — `[[assume(...)]]`
  in `framework/device/cpu/topology.cpp`. GCC 12 limitation, semantics fine.
- `-Wrestrict` note in `framework/logging.cpp` — libstdc++ memcpy folding noise.

These do not affect correctness. If new ARM64 warnings appear (especially in
`framework/device/cpu/arm64/`), treat them as real regressions.

## Reference docs in this repo

- `docs/ARM64_PORTING_PLAN.md`, `docs/ARM64_PORTING_SUMMARY.md` — port design
- `docs/writing_tests.md` — how to author tests
- `README.md` — build/run quickstart (kept in sync with this file)
