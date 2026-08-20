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
- Eigen: on this host a system `eigen3` is found at `/usr/local/include/eigen3`
  (3.4.0); `tests/cpu/meson.build` prefers a system `eigen3 >= 5.0` when present
  and otherwise falls back to the bundled `third-part/` Eigen 5.0.1 source
  (which is **committed to the repo**, vendored, not a submodule). In practice
  the 3.4.0 system pkg is accepted and used (no Eigen-5.0-only API is
  exercised), so no fetch step is needed. If `meson setup` prints
  `Using bundled Eigen 5.0 source from third-part/`, the vendored tree is
  being used instead.

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

## ARM64 优化库依赖 (arithmetic_arm)

`tests/cpu/arithmetic_arm/` (13 个 SDC 测试: `aor_math`/`aor_string`/
`crt_builtins`/`acl_gemm`/`gmp_bignum`/`gmp_bigadd`/`adcx_arm`/`adcxlong_arm`/
`adcx_adox_interleaved_arm`/`adox_arm`/`bigint_mulx_arm`/`cbw_arm`/`fisttp_arm`)
依赖第三方优化库, 在 `tests/cpu/meson.build` 的 `if host_machine.cpu_family()
== 'aarch64'` 块里挂接. 这些库走**系统包**, 不需要 `third_party/arm-opt-install`:

- `libmathlib` / `libstringlib` (Arm Optimized Routines, math+string) —
  系统包 `/usr/lib/lib{mathlib,stringlib}.a`, 头文件 `/usr/include/{mathlib,stringlib}.h`.
- `libarm_compute` (Arm Compute Library, 动态库) — 系统包 `/usr/lib64/libarm_compute.so.29`,
  头文件 `/usr/include/arm_compute/`. 动态链接, 运行时由 ldconfig 解析, 无需 `LD_LIBRARY_PATH`.
- `libgmp` — 系统包 `/usr/lib64/libgmp.so`, 头文件 `/usr/include/gmp.h`.
- compiler-rt 软浮点 builtins — 系统 compiler-rt 17
  `/usr/lib/clang/17/lib/aarch64-openEuler-linux-gnu/libclang_rt.builtins.a`,
  提供 `__addsf3`/`__subsf3`/`__mulsf3`/`__divsf3` (`crt_builtins.cpp` 用).

**`-lfplib` 已从 `aor_dep` 移除** (提交 4316aa36 曾引用 `third_party/arm-opt-install`
下的 `libfplib`, 但该目录在此主机从不存在, 且 AOR 的 fplib 是 32 位 ARM
软浮点汇编 — Cortex-M `armv6-m` / A32 `at32`, 为无硬件浮点的目标设计 —
无法在 aarch64 上汇编/链接, AOR 也没有 aarch64 fplib 端口. Kunpeng 920
armv8.1-a 有硬件浮点, 不需要软浮点例程; 且无任何测试源码引用 fplib 符号.
软浮点覆盖由 `crt_builtins.cpp` 经系统 compiler-rt 完成.) 若未来有测试
需要真实 fplib, 需先为 aarch64 移植 AOR fplib, 再加回 `-lfplib`.

`crt_builtins_lib` 优先 `third_party/arm-opt-install/lib/libclang_rt.builtins-aarch64.a`,
不存在时回退系统 compiler-rt 路径 (见 `tests/cpu/meson.build` 中的
`fs.exists()` 分支).

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
