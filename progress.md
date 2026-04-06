# Progress Log

本文件记录当前根目录文档合并、控制面修复与本机验证结果。

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
