# Findings And Current State

本文件是仓库根目录下的当前状态、源码事实、关键发现与技术决策主文档，吸收了此前 `docs/state.md` 中的当前阶段、最新发现与源码基线内容。

## 1. Current Phase

日期：`2026-04-06`

当前主阶段：

- `Phase 5`: gem5 scripted injector expansion
- `Phase 6`: 硬件 promotion lane bootstrap
- `Phase 7`: template / PCFG / advisor generation bootstrap

当前判断：

1. `Phase 0` 已完成。
2. `Phase 1` 已完成。
3. `Phase 2` 已完成 source-complete 内循环主链，`SIM_SAFE` 现在会生成 compiler-stable ARM64 样本。
4. `Phase 3` 已完成 source-level feedback loop hardening；无效 offspring 不再中止整个进化过程。
5. `Phase 4` 已完成 source-level outer-loop productization；fault matrix、aggregation、promotion signals 与 qemu-only fallback 已接通。
6. `Phase 5` 已具备多种 scripted fault model 与完整控制面 plumbing，但 full gem5 runtime 仍受主机内存和本地构建状态限制。
7. `Phase 6` 已具备 promotion / run / ingest 主链，但仍属于 bootstrap 阶段。

## 2. Source-Backed Baseline

下表只记录仓库中的真实实现，不把规划项混入“已完成”：

| Area | Current Anchor | Current Fact |
| --- | --- | --- |
| Control plane | `sdc_agent/agent.py`, `tools/sdc_agent.py` | 提供 `status / generate / evolve / cycle / e2e-*` 入口 |
| Generation | `sdc_agent/generation.py`, `microprobe/targets/arm64/policies/sdc_fuzzing_policy.py` | 可生成 ARM64 指令流并写回 Vault |
| Static analysis | `microprobe/src/microprobe/passes/sdc_analysis/offline_coverage.py` | 已有 ACE / IBR / Memory Pressure / Capstone pass |
| Persistence | `sdc_agent/vault.py` | 兼容 summary + multi-table persistent model |
| Materialization | `sdc_agent/materialize.py`, `microprobe/targets/arm64/wrappers/baremetaldiff.py` | 可生成 digest-style source artifacts |
| QEMU validation | `sdc_agent/differential.py` | 负责 golden digest 与 paired compare |
| gem5 execution | `gem5/configs/example/arm/sdc_kunpeng920_se.py` | 具备 SE runner 和 scripted fault request 路径 |
| Power labeling | `sdc_agent/power_backends/mcpat_backend.py` | McPAT 主链已接入控制面 |
| Scheduling / evolution | `sdc_agent/scheduler.py`, `microprobe/src/microprobe/driver/genetic.py` | 具备 ranking、lineage、offspring feedback |
| Hardware lane | `sdc_agent/hardware_lane.py`, `sdc_agent/hardware_results.py` | 具备 promotion / run / ingest 主链 |

## 3. Key Findings

### 3.1 Documentation

1. 根目录文档与 `docs/` 文档曾长期重复。
2. 当前 root `plan.md`、`findings.md`、`progress.md` 已成为权威文档。
3. `docs/spec.md`、`docs/state.md` 现在仅保留兼容入口，旧 `docs/plan.md` 已删除。

### 3.2 Control Plane And Tooling

1. `tools/sdc_agent.py` 之前在 CLI 解析前强依赖 Microprobe runtime，导致缺少 Python 包时连 `--help` 都无法使用。
2. `preflight` CLI 之前错误地把 `--skip-build-deps` / `--skip-hardware-tools` 当成默认强制启用，导致 `dev` profile 被误报缺少 sim/hw build deps。
3. 根目录之前缺少统一的 Python 依赖清单，导致默认 `python3` 环境下无法稳定运行 `pytest` 与 Microprobe。

### 3.3 ARM64 Generation

1. ARM64 operand 定义中三条 relative immediate 使用了错误字段，真实离线生成会直接失败。
2. A64 catalog 的 assembler 校验之前对缺少本地 toolchain fail closed，不符合 best-effort validation 目标。
3. `e2e-dev` 之前在 generation 没有产出 testcase 时仍可能返回伪成功，需要 fail closed。
4. `SIM_SAFE` 之前因为策略导入失败而退化到“全 ISA 随机集”，导致 Phase 2/4 频繁出现不可编译样本。
5. materialized wrapper 之前没有恢复被 testcase clobber 的 callee-saved registers，导致 qemu-user golden 运行崩溃。

## 4. Decisions

1. 根目录文档成为唯一权威来源：
   - `plan.md` 承担 architecture + roadmap
   - `findings.md` 承担 current state + decisions + risks
   - `progress.md` 承担 implementation log + verification
2. CLI 入口改成 lazy import，轻量命令不再被 Microprobe 依赖阻塞。
3. preflight 必须显式检查 Python runtime modules，而不是只看二进制工具。
4. catalog asm validation 改成 best effort：
   缺少 clang 或其他 assembler 时记录 `toolchain_limited`，不让 catalog profile 直接失效。
5. `e2e-dev` 必须 fail closed：
   如果 generation 没有插入 testcase 或 materialize 失败，则整条开发 smoke 直接报错。

## 5. Verified Current State

当前主机已经可以用默认 `python3` 跑通：

- `python3 tools/sdc_agent.py --help`
- `python3 -m sdc_agent.preflight --profile dev --verbose`
- `python3 -m pytest -q tests`
- `python3 tools/sdc_agent.py e2e-dev --output-root ...`
- `python3 tools/sdc_agent.py e2e-sim --skip-gem5 --skip-mcpat --output-root ...`

当前主机的 full gem5 sim 路径仍未闭环。当前阻塞已经从系统依赖收敛为两类：

1. gem5 本地构建仍会因源码编译/资源成本失败或被主动跳过
2. repo-local QEMU build 会被当前 worktree 中缺失的 qemu tracked files 阻塞

因此，当前实际可用口径是：

- full `dev` lane
- qemu-only `sim` smoke
- source-complete `Phase 2`
- source-complete `Phase 3`
- source-complete `Phase 4`

## 6. Current Risks

1. 本机是 `Ubuntu 25.10`，不是 README 认可的 `Ubuntu 24.04 ARM` sim baseline，因此 full sim lane 仍是 best-effort。
2. repo-local gem5 仍未产出 `gem5.opt`；当前为内存受限环境提供了 `--skip-gem5 --skip-mcpat` fallback。
3. 当前 worktree 中存在与本轮无关的 qemu tracked-file 缺失，这会阻塞 repo-local QEMU rebuild。
4. qemu-only `cycle` 仍可能选到无法通过当前 ARM64 wrapper/compiler 的样本；top-level smoke 已可运行，但这条生成空间仍需继续收敛。
