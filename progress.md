# Progress Log

本文件记录当前根目录文档合并、控制面修复与本机验证结果。

## Session: 2026-04-06

### Documentation Consolidation

- 新增根级 `plan.md`，合并旧 `docs/spec.md` 与 `docs/plan.md` 的长期架构合同和阶段路线图。
- 将根级 `findings.md` 和 `progress.md` 收敛为新的权威状态文档。
- `docs/spec.md`、`docs/plan.md`、`docs/state.md` 已改为兼容入口。
- README 与构建指南已改为引用根级文档。

### Documentation Cleanup

- 删除根级 `task_plan.md` 兼容别名。
- 删除 `docs/plan.md` 兼容 stub。
- 当前仅保留根级 `plan.md`、`findings.md`、`progress.md` 作为权威文档；`docs/spec.md` 与 `docs/state.md` 继续作为兼容入口。

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
- 新增 `e2e-sim --skip-gem5 --skip-mcpat` qemu-only fallback：
  在内存受限主机上可跳过 gem5 / McPAT，继续跑控制面、QEMU golden 与 qemu-only `cycle`。
- 修复 `SIM_SAFE` 退化为全 ISA 选择的问题：
  ARM64 policy 现在会被直接加载，且 `SIM_SAFE` 只保留 compiler-stable 指令名子集。
- 修复 ARM64 生成 asm 的 GNU 语法归一化：
  `MOVZ/MOVK/MOVN` 与 shifted-register 指令现在会输出 GAS-friendly 形式。
- 修复 materialized wrapper 对 callee-saved registers 的恢复：
  qemu-user golden 运行不再因为 clobbered `x19-x30` 直接崩溃。
- 修复 Phase 3 evolution 的 fail-soft 行为：
  单个无效 offspring 不再中止整个 genetic driver。
- 修复 outer-loop Phase 3/4 评分基线：
  `outer_value_score` 现在以 `inner_value_score` 为优先输入，而不是旧的 raw `fitness`。
- 为 `campaign` / `outer_loop` 加入 `skip_gem5` 语义：
  reduced-memory 路径现在会自动降级为 `fault_model=none`，不再伪造 `no_injection`。

### Source Fixes

- 新增根级 `requirements.txt` 与 `requirements-dev.txt`。
- 更新 `scripts/bootstrap_ubuntu_24_04_arm.sh`：
  安装根级 Python 依赖，并补充 QEMU 常见系统依赖。
- 更新 `scripts/setup_environment.sh`：
  改为安装根级依赖清单，并更新后续验证命令。
- 修复 `microprobe/targets/arm64/isa/armv8-common/operand.yaml` 中三条 relative immediate 的 schema 字段。
- 放宽 `microprobe/utils/arm64_isa_catalog.py` 的 assembler 校验：
  缺少 clang 时返回 `toolchain_limited`，不再让 catalog profile 直接失败。
- 修复 `phase4_validation` 的 gem5 fault-request plumbing：
  fault model / target / bit / tick 现在会真正传入 semihost gem5 runner，并回收 `fault_request` 摘要。
- 修复 `gem5/src/arch/arm/kvm/armv8_cpu.cc` 缺失 `misc_info.hh` include 的构建错误。
- 修复 shared semihost linker script 的 `virt` RAM 基址，和 QEMU AArch64 system test layout 对齐到 `1 << 30`。

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
| `printf 'ubuntu\n' \| sudo -S bash scripts/bootstrap_ubuntu_24_04_arm.sh` | PASS |
| `python3 -m sdc_agent.preflight --profile sim --verbose` | PARTIAL, only `gem5_binary` remains required |
| `python3 -m pytest -q tests/test_run_sdc_differential.py tests/test_sdc_phase4_validation.py gem5/tests/test_sdc_fault_request.py` | PASS, `18 passed` |
| `python3 -m pytest -q tests/test_sdc_phase2_validation.py tests/test_sdc_phase4_validation.py tests/test_sdc_preflight.py tests/test_sdc_agent.py` | PASS, `25 passed` |
| `python3 tools/sdc_agent.py e2e-sim --skip-gem5 --skip-mcpat --output-root /tmp/sdc-e2e-sim-skip` | PASS |
| `python3 -m pytest -q tests/test_sdc_materialize.py tests/test_sdc_campaign.py tests/test_sdc_scheduler.py tests/test_sdc_genetic_driver.py tests/test_sdc_outer_loop.py tests/test_sdc_phase2_validation.py tests/test_sdc_phase4_validation.py tests/test_sdc_preflight.py tests/test_sdc_agent.py tests/test_run_sdc_differential.py gem5/tests/test_sdc_fault_request.py` | PASS, `67 passed` |
| `python3 tools/sdc_agent.py e2e-sim --skip-gem5 --skip-mcpat --output-root /tmp/sdc-e2e-sim-skip4` | PASS |
| `bash scripts/build_gem5_linux_arm.sh` | FAIL, still too heavy / still blocked for full host closure |
| `bash scripts/build_qemu_headless.sh` | FAIL, blocked by unrelated missing tracked files under `qemu/subprojects` |

## Current Outcome

- `Phase 2` is source-complete and compile-stable for the `SIM_SAFE` lane.
- `Phase 3` is source-complete for the feedback/evolution loop.
- `Phase 4` is source-complete for the outer-loop orchestration and reduced-memory fallback.
- `dev` lane is runnable with the default `python3`.
- 当前主机现在有一个可运行的 qemu-only `sim` smoke：
  `e2e-sim --skip-gem5 --skip-mcpat`
- full gem5-based `sim` lane 仍未闭环；Phase 5 remains partially blocked by host memory limits and unrelated local qemu subtree damage.
