# SDC-Agent Architecture And Roadmap

本文件是仓库根目录下的长期架构合同与阶段计划主文档，合并了此前分散在 `docs/spec.md` 与 `docs/plan.md` 中的目标架构、交付阶段与验收口径。

## 1. Canonical Docs

- `plan.md`
  描述完成态架构、阶段路线图、交付物与验收标准。
- `findings.md`
  描述当前源码事实、关键发现、技术决策与当前风险。
- `progress.md`
  描述实施日志、验证结果与本轮变更产出。

`docs/spec.md`、`docs/state.md` 只保留兼容入口，不再承载规范正文；旧 `docs/plan.md` 已移除。

## 2. Objective

`SDC-Agent` 的完成态目标是把 `microprobe`、`qemu`、`gem5`、`mcpat`、`opendcdiag` 组织成一套围绕 ARM64 指令流持续演进的 SDC 自动化发现系统。

这里的“完成”不是宣称仓库已经 100% 完成，而是定义最终应满足的合同：

1. `microprobe` 可以按 profile 大规模生成 ARM64 指令流并写回数据库。
2. 每条样本都具备静态覆盖率、合法性、功耗、血缘与状态轨迹。
3. `qemu` 作为 golden executor 能稳定产出可比对 digest。
4. `gem5` 能承载 fault-side 执行与 fault campaign 记录。
5. `mcpat` 能为内循环或外循环 shortlist 写回功耗标签。
6. `opendcdiag` 能接收 promotion 样本、在真实硬件执行并回灌结果。

## 3. Monorepo Model

当前仓库采用单一 monorepo 模型，核心路径统一由 root 管理：

- `microprobe/`
- `qemu/`
- `gem5/`
- `mcpat/`
- `opendcdiag/`
- `sdc_agent/`
- `tools/`
- `tests/`

变更归属、审阅边界与阶段映射按路径域管理；治理约束见 [docs/monorepo.md](./docs/monorepo.md)。

## 4. System Architecture

### 4.1 Three Loops

系统围绕三条执行环收敛：

1. 高频内循环
   `generate -> static metrics -> materialize -> qemu legality -> power label -> evolve`
2. 低频外循环
   `INNER_READY -> fault planning -> gem5/qemu differential -> sensitivity aggregation`
3. 硬件验证环
   `promotion -> OpenDCDiag staging/run -> ingest -> backfill`

### 4.2 Core Responsibilities

| Subsystem | Responsibility | Current Anchor |
| --- | --- | --- |
| Control plane | 顶层 orchestration、summary、CLI | `sdc_agent/agent.py`, `tools/sdc_agent.py` |
| Generation | ARM64 指令流合成与 profile contract | `sdc_agent/generation.py`, `microprobe/targets/arm64/policies/sdc_fuzzing_policy.py` |
| Static analysis | ACE / IBR / Memory Pressure / Capstone | `microprobe/src/microprobe/passes/sdc_analysis/offline_coverage.py` |
| Persistence | testcase / artifact / run / lineage 存储 | `sdc_agent/vault.py` |
| Materialization | digest-style source / wrapper generation | `sdc_agent/materialize.py`, `microprobe/targets/arm64/wrappers/baremetaldiff.py` |
| Golden validation | QEMU 执行与 digest 抽取 | `sdc_agent/differential.py` |
| Outer loop | fault planning / aggregation / ranking | `sdc_agent/campaign.py`, `sdc_agent/scheduler.py` |
| Evolution | offspring generation / feedback reinjection | `microprobe/src/microprobe/driver/genetic.py` |
| Hardware lane | promotion / build / run / ingest | `sdc_agent/hardware_lane.py`, `sdc_agent/hardware_results.py` |

### 4.3 Architecture Rules

1. `qemu` 只承担 golden side，不承担 fault 语义。
2. `gem5` 负责 fault-side 执行与统计，不直接给出硬件结论。
3. `opendcdiag` 只进入最终硬件验证环，不进入高频仿真路径。
4. 数据库是模块总线；长期模块耦合不能依赖临时文件命名约定。
5. 高频内循环追求吞吐，低频外循环追求精度，硬件验证环追求最终置信度。

## 5. Data Contract

### 5.1 Compatibility Summary

当前兼容中心仍是 `offline_testcases` summary 视图，至少承载：

- `asm_content`
- `ace_score`
- `ibr_score`
- `memory_pressure_score`
- `risk_score`
- `qemu_golden_hash`
- `gem5_fault_hash`
- `mcpat_power`
- `status`
- `metadata_json`

### 5.2 Target Persistent Model

完成态持久化至少覆盖：

- `testcases`
- `static_metrics`
- `artifacts`
- `inner_runs`
- `power_annotations`
- `fault_campaigns`
- `fault_runs`
- `hardware_promotions`
- `hardware_runs`
- `lineage_events`

### 5.3 Status Model

当前控制面兼容状态：

```text
PENDING -> GOLDEN_READY -> MATCHED
PENDING -> INVALID / TIMEOUT / CRASHED
GOLDEN_READY -> SDC_FOUND
```

完成态应显式表达更细粒度阶段：

```text
NEW
  -> STATIC_DONE
  -> MATERIALIZED
  -> GOLDEN_READY
  -> POWER_READY
  -> INNER_READY
  -> OUTER_QUEUED
  -> FAULT_RUNNING
  -> OUTER_COMPLETE
  -> SDC_CONFIRMED
```

## 6. Inner Loop Contract

### 6.1 Goal

高频内循环的目标不是“找到最终答案”，而是用尽可能低的成本把海量候选压缩成一批值得进入 fault campaign 的 `INNER_READY` 样本。

### 6.2 Stages

1. Generate
   调用 `microprobe` 合成 ARM64 指令流。
2. Static coverage
   计算 ACE / IBR / Memory Pressure / legality hints。
3. Persist
   以 testcase key 写回数据库。
4. Materialize
   物料化 digest wrapper / source / ELF。
5. QEMU validate
   校验可执行性并提取 golden digest。
6. Power annotate
   对 shortlist 做 gem5 bare-metal + McPAT。
7. Evolve
   根据 legality / power / diversity 反馈指导 offspring。

### 6.3 Profiles

内循环至少支持两个 profile：

- `SIM_SAFE`
  面向 qemu/gem5 稳定执行的指令子集。
- `HW_AGGRESSIVE`
  面向真实硬件探索的激进指令族。

### 6.4 Scoring

必须区分：

- `static_risk_score`
  来源于静态覆盖率与合法性启发式。
- `inner_value_score`
  来源于 `static_risk_score + legality + power + diversity`。

概念公式：

```text
static_risk_score = f(ace_score, ibr_score, memory_pressure_score, capstone_validated)
inner_value_score = static_risk_score * legality_factor * power_gain * diversity_bonus
```

## 7. Outer Loop Contract

### 7.1 Goal

低频外循环回答的是：

> 某条指令流在带故障的微架构环境下，是否真的能暴露 SDC，且这种暴露是否稳定、可重复、值得进入硬件验证？

### 7.2 Required Behavior

1. 从 `INNER_READY` 池中选取高价值样本。
2. 为同一 testcase 规划 fault matrix。
3. 对同一 source / ELF 进行 paired qemu / gem5 执行。
4. 对比 golden digest 与 fault-side digest。
5. 聚合出 detection rate、repeatability、outer value。
6. 将结果回写数据库并反哺调度与进化。

### 7.3 Aggregates

外循环至少维护：

- `fault_detection_rate`
- `repeatability_score`
- `outer_value_score`
- `injector_confidence_score`
- `promotion_readiness_score`

## 8. Hardware Lane Contract

### 8.1 Goal

硬件验证环负责把数据库中的高价值样本转成 `opendcdiag` 可运行测试，并把真实机器上的执行结果回灌数据库。

### 8.2 Required Steps

1. 选择 `promotion_ready` 样本。
2. 生成 promotion bundle：
   - manifest
   - asm
   - opendcdiag-shaped source
   - build fragment
3. 调用 `opendcdiag` 构建与运行。
4. 采集 detector / machine / runtime metadata。
5. 写回 `hardware_runs`。

## 9. Phase Roadmap

| Phase | Goal | Status | Notes |
| --- | --- | --- | --- |
| Phase 0 | 文档合同与 monorepo 叙事收敛 | complete | root docs are canonical |
| Phase 1 | Vault v2 / 兼容持久化模型 | complete | multi-table model is wired through `vault.py` |
| Phase 2 | 高频内循环产品化 | complete | compile-stable `SIM_SAFE`, materialize hardening, qemu-only sim smoke |
| Phase 3 | 功耗驱动的进化闭环 | complete | scheduler/genetic feedback loop and fail-soft evolution are wired |
| Phase 4 | 低频外循环产品化 | complete | fault matrix, aggregation, promotion signals, qemu-only fallback are wired |
| Phase 5 | gem5 injector 扩展 | in progress | scripted models and control-plane plumbing exist, full host runtime still depends on gem5 capacity |
| Phase 6 | promotion / hardware ingest | in progress | promotion/run/ingest path exists, hardware breadth still grows |
| Phase 7 | template / PCFG / advisor 生成 | in progress | baseline strategy layer exists, sophistication can grow |

### 9.1 Critical Path

README 完成态的关键路径保持不变：

1. Vault v2
2. Inner loop
3. Outer loop
4. gem5 injector
5. Hardware lane
6. Intelligent generation

## 10. Lane Acceptance

### 10.1 `e2e-dev`

必须满足：

- `python3 tools/sdc_agent.py --help`
- `python3 -m sdc_agent.preflight --profile dev --verbose`
- `python3 -m pytest -q tests`
- `python3 tools/sdc_agent.py e2e-dev --output-root <dir>`

### 10.2 `e2e-sim`

必须满足：

- `python3 -m sdc_agent.preflight --profile sim --verbose`
- `./scripts/build_qemu_headless.sh`
- `./scripts/build_gem5_linux_arm.sh`
- `./scripts/build_mcpat.sh`
- `python3 tools/sdc_agent.py e2e-sim --output-root <dir>`

### 10.3 `e2e-hw`

必须满足：

- `python3 -m sdc_agent.preflight --profile hw --verbose`
- `python3 tools/sdc_agent.py e2e-hw --output-root <dir>`
- 至少一条 promotion / run / ingest 记录回写成功

## 11. Bootstrap Contract

Ubuntu 24.04 ARM 的标准 bootstrap 入口：

```bash
./scripts/bootstrap_ubuntu_24_04_arm.sh
```

该脚本负责：

- 安装 repo-local QEMU/gem5/McPAT 常用系统依赖
- 安装 `pkg-config`、`python3-dev`、`libglib2.0-dev`、`libpixman-1-dev`
- 安装根目录 `requirements-dev.txt` 中声明的 Python 依赖

macOS 或其他开发主机只承诺 `dev` lane smoke，不承诺完整 sim 闭环。

## 12. Defaults And Assumptions

1. 默认解释器为当前 shell 的 `python3`，不再依赖用户私有 Conda 路径。
2. 根目录 `requirements.txt` / `requirements-dev.txt` 是控制面的 Python 依赖清单。
3. `docs/spec.md`、`docs/state.md` 仅为兼容入口；旧 `docs/plan.md` 已删除。
4. 专题文档如 [docs/monorepo.md](./docs/monorepo.md) 与 [docs/kunpeng920.md](./docs/kunpeng920.md) 继续保留在 `docs/`。
