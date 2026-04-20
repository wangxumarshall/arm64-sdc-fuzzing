# Progress Log

本文件记录当前根目录文档合并、控制面修复与本机验证结果。

## Session: 2026-04-20

### Sim Lane Runthrough on Ubuntu 24.04 ARM

- 修复 `sim` 路线的本机收口问题，完成从 preflight、gem5 构建、phase2/phase4、
  到 cycle 的真实串联。
- `gem5` 侧补齐 ARM KVM 编译缺口，并将本地构建链改为支持
  `gem5.opt -> gem5.debug` fallback；在当前 8G 主机上最终落地使用
  `gem5/build/ARM/gem5.debug`。
- 更新 `resolve_local_tools()` 与 preflight：
  默认 `gem5.opt` 缺失时允许回退到 `gem5.fast/gem5.debug`；
  运行时 Python 依赖检查新增 `numpy`、`h5py`。
- 调整 baremetal 验证配置，显式禁用会在受限环境下触发监听 socket 的
  VNC、terminal、remote-gdb 路径，使 phase2 能稳定进入 `INNER_READY`。
- 修正 phase4/cycle 的 fault 参数传递与配置分流：
  phase2 使用 baremetal smoke，cycle 使用 `sdc_kunpeng920_se.py`；
  phase4 的 `phase4_no_injector` 在本地 smoke 下视作非阻塞状态。

### OpenDCDiag / Eigen 5.0 Integration

- 下载并本地编译安装官方 `Eigen 5.0.0`，安装前缀为
  `third_party/eigen-5.0.0-install`。
- 为 `opendcdiag` 新增 `eigen3_root` Meson 选项，并默认优先探测仓库内
  `../third_party/eigen-5.0.0-install`，从而显式使用本地 Eigen，
  不再依赖系统 `libeigen3-dev`。
- 修复若干 ARM64/OpenDCDiag 本地构建缺口，使 `opendcdiag` 主程序可在
  AArch64 主机上成功编译并链接。

### Eigen Test Validation on ARM64

- 已确认 `opendcdiag --beta --list` 中的 `@math` 组包含 10 个 Eigen 用例：
  `eigen_gemm_*`、`eigen_sparse`、`eigen_svd*`。
- 本机 ARM64 直接运行下，Eigen 用例全部通过。
- `qemu-aarch64 -L /` 用户态仿真入口下，10 个 Eigen 用例全部通过。
- 当前结论限定在“ARM64 用户态仿真入口”；
  并未把 OpenDCDiag 整体接入 full-system gem5 Linux rootfs 场景。

### Verification Results

| Command | Result |
| --- | --- |
| `python3 -m pytest -q tests/test_sdc_preflight.py tests/test_sdc_phase4_validation.py tests/test_sdc_agent_sim_lane.py tests/test_sdc_agent.py` | PASS, `27 passed` |
| `python3 -m sdc_agent.preflight --profile sim --verbose` | PASS，解析到 `gem5/build/ARM/gem5.debug`，运行时模块包含 `numpy`、`h5py` |
| `python3 tools/sdc_agent.py e2e-sim --output-root /tmp/sdc-e2e-sim --timeout 300` | PASS，`ok=true`；`phase2=INNER_READY`；`phase4=INVALID/phase4_no_injector`（非阻塞）；`cycle.executed=2`，`cycle.emitted=2` |
| `meson setup /tmp/opendcdiag-build opendcdiag --buildtype=debugoptimized` | PASS，显式输出 `Using repo-local Eigen .../third_party/eigen-5.0.0-install` |
| `ninja -C /tmp/opendcdiag-build opendcdiag -j4` | PASS |
| `/tmp/opendcdiag-build/opendcdiag --beta -n 1 -e @math -t 50ms --strict-runtime -Y` | PASS |
| `qemu-aarch64 -L / /tmp/opendcdiag-build/opendcdiag --beta -n 1 -e eigen_gemm_double14 -t 10ms --strict-runtime -Y` | PASS |
| `python3 - <<'PY' ... full qemu-aarch64 sweep over 10 Eigen tests ... PY` | PASS，10/10 Eigen 用例通过 |

## Session: 2026-04-17

### Armv9.2 / LS64 / WFxT Extension Completion

- 完成 `microprobe/targets/arm64/isa/armv8-common/instruction_props/armv9_2.yaml`，
  补齐 LS64 / WFxT 指令定义：`LD64B`、`ST64B`、`ST64BV`、`ST64BV0`、
  `WFET`、`WFIT`。
- 扩展 ARM64 ISA schema 与内存建模：
  新增 `LS64_LOAD`、`LS64_STORE`、`LS64_STORE_STATUS`、`WFXT`，
  并补充 `Rn_sp`、`Rt_ls64_*`、`Rs_ls64_status`、`Rd_wfxt` 等字段与操作数。
- 扩展 catalog 归一化与 profile 选择逻辑：
  新增 `ARMV82_TO_ARMV92_GENERATABLE` /
  `ARMV82_TO_ARMV92_EXECUTABLE`，
  根据 feature tag 自动推导 `minimum_arch`、`.arch` 和
  `.arch_extension`，并把 `WFET`/`WFIT` 归类为可执行 system 指令。
- 扩展 audit 逻辑以纳入 `instruction_props/*.yaml`，避免 Armv9.2 增量定义
  在仓库审计时被误报缺失。
- 补充真实回归测试：
  校验新 profile 的 catalog 生成链路、目标导入后指令可见性，以及
  LS64 / WFxT 在 catalog 窗口中的覆盖。

### Verification Results

| Command | Result |
| --- | --- |
| `python3 -m pytest -q tests/test_sdc_generation_profiles.py microprobe/targets/arm64/tests/tools/test_a64_isa_catalog.py microprobe/targets/arm64/tests/tools/test_a64_isa_audit.py microprobe/targets/arm64/tests/targets/test_target_contract.py` | PASS |
| `python3 -m pytest -q microprobe/targets/arm64/tests tests/test_sdc_generation_profiles.py` | PASS, `59 passed` |
| `python3 -m sdc_agent.preflight --profile dev --verbose` | PASS |
| `python3 - <<'PY' ... generate_testcase(profile=ARMV82_TO_ARMV92_GENERATABLE/EXECUTABLE) ... PY` | PASS, 两个新 profile 均走 catalog 路径，输出 `.arch armv8.5-a`，clang 校验通过 |

## Session: 2026-04-06

### Documentation Consolidation

- 新增根级 `plan.md`，合并旧 `docs/spec.md` 与 `docs/plan.md` 的长期架构合同和阶段路线图。
- 将根级 `findings.md` 和 `progress.md` 收敛为新的权威状态文档。
- `docs/spec.md`、`docs/plan.md`、`docs/state.md` 已改为兼容入口。
- README 与构建指南已改为引用根级文档。

### Control Plane Fixes

- 将 `sdc_agent/agent.py` 改为 lazy import：
  `--help`、`status` 等轻量命令不再因为 Microprobe Python 依赖缺失而直接失败。
- 修复 `sdc_agent/preflight.py` 的 CLI 参数覆盖错误：
  `dev` profile 不再被误报需要 sim/hw build deps。
- 新增 Python runtime module 检查，preflight 现在会明确报告缺少 `six`、`fasteners`、`cachetools`、`rxjson` 等依赖。
- 新增 sim build dependency 检查与缺失步骤提示：
  `pkg-config`、`python3-config`、`scons`、`swig`、`protoc` 的缺失现在会被显式报告。
- 修复 `run_e2e_dev()`：
  generation 没有插入 testcase 或 materialize 失败时，开发 smoke 不再伪装成功。

### Source Fixes

- 新增根级 `requirements.txt` 与 `requirements-dev.txt`。
- 更新 `scripts/bootstrap_ubuntu_24_04_arm.sh`：
  安装根级 Python 依赖，并补充 QEMU 常见系统依赖。
- 更新 `scripts/setup_environment.sh`：
  改为安装根级依赖清单，并更新后续验证命令。
- 修复 `microprobe/targets/arm64/isa/armv8-common/operand.yaml` 中三条 relative immediate 的 schema 字段。
- 放宽 `microprobe/utils/arm64_isa_catalog.py` 的 assembler 校验：
  缺少 clang 时返回 `toolchain_limited`，不再让 catalog profile 直接失败。

## Verification Results

| Command | Result |
| --- | --- |
| `python3 tools/sdc_agent.py --help` | PASS |
| `python3 -m sdc_agent.preflight --profile dev --verbose` | PASS |
| `python3 -m pytest -q tests/test_sdc_preflight.py tests/test_sdc_agent.py` | PASS |
| `python3 -m pytest -q tests/test_sdc_generation_profiles.py microprobe/targets/arm64/tests/tools/test_mp_sdc_offline_gen.py microprobe/targets/arm64/tests/targets/test_target_contract.py` | PASS |
| `python3 -m pytest -q tests` | PASS, `79 passed, 1 skipped` |
| `python3 -m pytest -q microprobe/targets/arm64/tests` | PASS, `46 passed` |
| `python3 tools/sdc_agent.py e2e-dev --output-root /tmp/sdc-e2e-dev` | PASS |
| `python3 -m sdc_agent.preflight --profile sim --verbose` | FAIL, host missing required sim build deps and binaries |
| `PATH=\"$HOME/.local/bin:$PATH\" ./scripts/build_qemu_headless.sh` | FAIL, missing system QEMU build deps (`pkg-config`, `glib-2.0`) |
| `PATH=\"$HOME/.local/bin:$PATH\" python3 -m SCons -C gem5 -j2 build/ARM/gem5.opt` | FAIL, missing `python3-config` |

## Current Outcome

- `dev` lane is source-complete and runnable with the default `python3` after user-space Python bootstrap.
- `sim` lane now fails honestly and points to the real missing system dependencies instead of collapsing inside import-time or generation-time bugs.
