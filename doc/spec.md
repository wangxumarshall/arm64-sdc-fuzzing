# SDC-Agent Specification

## 1. Purpose

本规范定义 SDC-Agent 的完整目标形态：在 ARM64 平台上，把 `microprobe-arm`、`qemu`、`gem5`、`mcpat-arm`、`opendcdiag-arm` 组织成一套可以持续演进的 SDC 自动化 Fuzzing 系统。

这里的目标不是“让几个脚本能跑”，而是形成一条完整的发现与验证链路：

1. 高频内循环负责大规模生成、静态筛选、快速合法性验证、功耗标注和种群迭代。
2. 低频外循环负责故障注入差分验证，判断一条指令流是否真的具备 SDC 检测价值。
3. 硬件验证环负责把高价值样本推送到 `opendcdiag-arm`，在真实机器上做最终确认，并把结果回灌数据库。

---

## 2. Source-Backed Baseline

### 2.1 当前代码已经具备的能力

当前源码中已经存在以下可用主干：

- 控制平面
  - [`sdc_agent/agent.py`](/Users/wangxu/1-project/sdc-fuzzing/sdc_agent/agent.py)
- 离线生成与静态分析
  - [`sdc_agent/generation.py`](/Users/wangxu/1-project/sdc-fuzzing/sdc_agent/generation.py)
  - [`microprobe/targets/arm64/policies/sdc_fuzzing_policy.py`](/Users/wangxu/1-project/sdc-fuzzing/microprobe/targets/arm64/policies/sdc_fuzzing_policy.py)
  - [`microprobe/src/microprobe/passes/sdc_analysis/offline_coverage.py`](/Users/wangxu/1-project/sdc-fuzzing/microprobe/src/microprobe/passes/sdc_analysis/offline_coverage.py)
- 持久化与反馈
  - [`sdc_agent/vault.py`](/Users/wangxu/1-project/sdc-fuzzing/sdc_agent/vault.py)
  - [`sdc_agent/scheduler.py`](/Users/wangxu/1-project/sdc-fuzzing/sdc_agent/scheduler.py)
  - [`microprobe/src/microprobe/driver/genetic.py`](/Users/wangxu/1-project/sdc-fuzzing/microprobe/src/microprobe/driver/genetic.py)
- 执行与差分
  - [`sdc_agent/materialize.py`](/Users/wangxu/1-project/sdc-fuzzing/sdc_agent/materialize.py)
  - [`sdc_agent/differential.py`](/Users/wangxu/1-project/sdc-fuzzing/sdc_agent/differential.py)
  - [`sdc_agent/campaign.py`](/Users/wangxu/1-project/sdc-fuzzing/sdc_agent/campaign.py)
- 功耗
  - [`sdc_agent/power_analysis.py`](/Users/wangxu/1-project/sdc-fuzzing/sdc_agent/power_analysis.py)
  - [`sdc_agent/power_backends/mcpat_backend.py`](/Users/wangxu/1-project/sdc-fuzzing/sdc_agent/power_backends/mcpat_backend.py)
- 预检
  - [`sdc_agent/preflight.py`](/Users/wangxu/1-project/sdc-fuzzing/sdc_agent/preflight.py)
- 硬件侧占位接口
  - [`sdc_agent/power_backends/opendcdiag_backend.py`](/Users/wangxu/1-project/sdc-fuzzing/sdc_agent/power_backends/opendcdiag_backend.py)

### 2.2 当前代码尚未闭环的能力

要实现 README 中“100% 的目标和愿景”，还必须补齐以下缺口：

1. 内循环尚未统一编排
   - 当前生成、QEMU、功耗标注、进化仍分散在不同模块
2. 外循环缺少 fault matrix
   - 当前 `campaign` 一次只跑一个 fault 配置，缺少系统化 fault sweep
3. gem5 真实 fault injector 未落地
   - 目前只有 `sdc_fault_request.json` manifest，没有真正注入执行
4. OpenDCDiag 回灌链路未实现
   - 当前只有 placeholder backend，没有“生成测试 → 执行 → 采集 → 回写”的闭环
5. 数据模型过于扁平
   - 现有 `offline_testcases` 单表不能完整表达多次 fault run、功耗版本、硬件回灌结果

---

## 3. Design Principles

### 3.1 三层闭环，而不是单一循环

系统采用三个频率层级：

1. **高频内循环**
   - 高吞吐、低成本
   - 目标是把海量候选筛成“值得仿真”的种子
2. **低频外循环**
   - 低吞吐、高精度
   - 目标是回答“这条指令流是否真的有 SDC 检测能力”
3. **真实硬件验证环**
   - 最低频、最高价值
   - 目标是把最优候选迁移到 OpenDCDiag-ARM 真实压测环境

### 3.2 仿真层坚持轻量执行层

在仿真阶段，严格坚持：

- 裸汇编或轻量 C wrapper
- digest/hash 驱动的状态对比
- 不把 OpenDCDiag 直接拖入 qemu / gem5 快速循环

OpenDCDiag 只在最终“真实环境验证环”使用。

### 3.3 数据库是系统总线

所有阶段通过数据库解耦，而不是通过临时文件名约定解耦。

数据库必须记录：

- 样本内容
- 覆盖率与风险指标
- 构建/物料化工件
- QEMU 结果
- 功耗标注
- gem5 故障注入结果
- OpenDCDiag 真实运行结果
- 血缘与进化信息

### 3.4 双执行配置文件

为兑现 README 的完整目标，系统必须支持两种指令配置文件：

1. **SIM_SAFE**
   - 面向 qemu/gem5 可稳定运行的指令子集
   - 当前源码已经具备这条路径
2. **HW_AGGRESSIVE**
   - 面向真实硬件，包含更激进的 NEON FMA / LDP-STP / LSE / Cache-thrash 模式
   - 当前仅在愿景层，需要后续补齐

这能解决当前源码中一个关键现实约束：

- README 想覆盖 NEON FMA、LDP/STP、LSE
- 当前 `sdc_fuzzing_policy` 为了保证 gem5 可运行，默认把这些大多排除了

因此要实现 README 全目标，必须采用双 profile，而不是只靠单一 sim-safe 生成器。

---

## 4. Target Architecture

## 4.1 Overall Architecture

```text
                   ┌──────────────────────────────────────┐
                   │        SDC-Agent Control Plane       │
                   │  plan / inner-loop / outer-loop /   │
                   │      hardware-promotion / report    │
                   └──────────────────────────────────────┘
                                      │
         ┌────────────────────────────┼────────────────────────────┐
         │                            │                            │
         ▼                            ▼                            ▼
┌───────────────────┐      ┌────────────────────┐      ┌────────────────────┐
│ High-Freq Inner   │      │ Low-Freq Outer     │      │ Hardware Validation│
│ Loop              │      │ Loop               │      │ Lane               │
├───────────────────┤      ├────────────────────┤      ├────────────────────┤
│ Microprobe gen    │      │ Fault campaign     │      │ Promote to         │
│ Static coverage   │      │ gem5 injection     │      │ opendcdiag-arm     │
│ Wrapper           │      │ QEMU/gem5 diff     │      │ Real machine run   │
│ QEMU validate     │      │ SDC sensitivity    │      │ Result ingest      │
│ Power annotate    │      │ Promotion score    │      │ DB backfill        │
│ Seed evolution    │      │ DB update          │      │                    │
└───────────────────┘      └────────────────────┘      └────────────────────┘
                                      │
                                      ▼
                         ┌──────────────────────────┐
                         │      Testcase Vault      │
                         │ + metrics + runs + hw    │
                         └──────────────────────────┘
```

---

## 5. High-Frequency Inner Loop

## 5.1 Responsibility

内循环负责用最小代价建立一个“高价值候选池”。它不是单纯的静态生成器，而是由两个子阶段组成：

1. **Inner-A: Ultra-fast static screening**
2. **Inner-B: Fast validation and annotation**

## 5.2 Inner-A: Ultra-fast static screening

输入：

- `microprobe-arm` target
- generation profile (`SIM_SAFE` / `HW_AGGRESSIVE`)
- 父代样本或随机种子

步骤：

1. 调用 `microprobe-arm` 生成指令流
2. 运行静态 Pass：
   - `StaticACECalculatorPass`
   - `StaticIBRCoveragePass`
   - `Kunpeng920MemoryPressurePass`
   - `CapstoneValidationPass`
3. 记录：
   - `ace_score`
   - `ibr_score`
   - `memory_pressure_score`
   - `capstone_validated`
   - `instruction_names`
4. 计算 `static_risk_score`
5. 写入数据库

输出：

- `STATIC_DONE` 样本

## 5.3 Inner-B: Fast validation and annotation

对于 `STATIC_DONE` 样本，内循环继续做快验证：

1. `materialize`
   - 生成 digest wrapper C 源
2. `compile`
   - 产出静态 ELF
3. `qemu validate`
   - 快速判定可执行性
   - 提取 `golden_digest`
4. `power annotate`
   - Tier-1：静态功耗估算
   - Tier-2：对 shortlist 批量跑 gem5 bare-metal + McPAT
5. 将结果回写数据库

输出：

- `INNER_READY` 样本

## 5.4 Inner Loop Scoring

内循环维护两个分数，而不是混成一个：

1. `static_risk_score`
   - 由 ACE / IBR / Memory Pressure 得出
2. `inner_value_score`
   - 由 `static_risk_score`、QEMU 可执行性、功耗标签、多样性奖励共同得出

这是因为当前源码里已经出现两个不同评分口径：

- 生成侧是线性加权
- 调度侧是乘法 fitness

要 100% 落地 README 目标，需要把这两个概念明确拆开。

## 5.5 Inner Loop Iteration Logic

内循环对 `microprobe-arm` 的迭代指导来自三类信号：

1. 覆盖率信号
   - ACE / IBR / Memory Pressure
2. 可执行性信号
   - Capstone / QEMU
3. 能量信号
   - 静态功耗估计 / McPAT 结果

反馈动作包括：

- instruction family reweighting
- dependency distance tuning
- stride tuning
- mutation operator reweighting
- execution profile switching（SIM_SAFE vs HW_AGGRESSIVE）

---

## 6. Low-Frequency Outer Loop

## 6.1 Responsibility

外循环负责从内循环形成的海量候选中挑出最有价值的样本，执行带 fault injection 的高成本仿真，回答：

> 这条指令流在带故障的微架构环境下，是否真的能暴露 SDC？

## 6.2 Outer Loop Steps

1. 从数据库中拉取 `INNER_READY` 高价值候选
2. 为每个候选构建 fault matrix：
   - `fault_model`
   - `fault_target`
   - `fault_bit`
   - `fault_tick`
3. 对每个 testcase：
   - QEMU golden 执行一次并缓存
   - gem5 fault run 执行多次
4. 做差分判定：
   - `matched`
   - `sdc_found`
   - `timeout`
   - `crashed`
5. 计算 `sdc_sensitivity_score`
6. 更新数据库
7. 将 top candidates 放入 hardware promotion queue

## 6.3 Outer Loop Scoring

外循环最终价值分由以下因素组成：

- `inner_value_score`
- `sdc_found` 频率
- fault diversity 覆盖
- qemu/gem5 结果稳定性
- `mcpat_power`
- lineage diversity

建议目标函数：

```text
outer_value =
  (coverage_score * sdc_sensitivity * diversity_bonus)
  / (normalized_power + 1)
```

## 6.4 Source-Derived Constraints

当前外循环代码存在两个必须在计划中正视的现实约束：

1. `campaign.py` 目前是一条样本一次 fault 配置的执行器，不是完整 fault matrix runner。
2. `gem5/configs/example/arm/sdc_fault_request.py` 只是 manifest writer，真实注入器还没落地。

因此“外循环完整落地”的定义必须包含：

- fault matrix orchestration
- fault result persistence
- gem5 injector implementation

---

## 7. Hardware Validation Lane

## 7.1 Responsibility

最终目标不是止步于仿真，而是把高价值样本推送到真实 ARM64 平台，通过 `opendcdiag-arm` 进行真实环境验证。

## 7.2 Promotion Flow

1. 从数据库中选择 `PROMOTABLE` 样本
2. 生成 OpenDCDiag-ARM test package：
   - `tests/cpu/arm64/generated/*.cpp`
   - 必要时生成 supporting framework hooks
3. 将 testcase 元数据注入测试描述：
   - testcase_key
   - expected digest mode
   - static metrics
   - outer-loop score
4. 在真实设备上运行
5. 收集结果：
   - pass/fail
   - digest mismatch
   - runtime crash / timeout
   - platform info
6. 写回数据库

## 7.3 Why OpenDCDiag Is Final-Lane Only

源码和现阶段架构已经表明：

- 仿真阶段需要极简 wrapper 才能高吞吐
- OpenDCDiag 更适合作为真实机器验证与回归框架

因此 OpenDCDiag 的定位应当是：

- **不是仿真执行层**
- **而是最终硬件验证层**

---

## 8. Core Skills / Capabilities

这里的 “Skill” 指系统能力，而不是 LLM 插件。

| Skill | Responsibility | Current Mapping |
| --- | --- | --- |
| Generation Skill | 生成与变异 ARM64 指令流 | `sdc_agent/generation.py` + `sdc_fuzzing_policy.py` |
| Coverage Skill | 计算 ACE / IBR / Memory Pressure | `offline_coverage.py` |
| Legality Skill | Capstone + QEMU 合法性校验 | `offline_coverage.py` + `sdc_agent/differential.py` |
| Wrapper Skill | 生成 digest wrapper 与构建工件 | `sdc_agent/materialize.py` + `baremetaldiff.py` |
| Power Skill | 功耗估算与 McPAT 标注 | `sdc_agent/power_analysis.py` + `mcpat_backend.py` |
| Differential Fault Skill | QEMU/gem5 差分与 fault campaign | `sdc_agent/differential.py` + `sdc_agent/campaign.py` |
| Evolution Skill | 反馈驱动 offspring 生成 | `microprobe.driver.genetic` |
| Hardware Promotion Skill | 推送 OpenDCDiag 并回灌结果 | 当前待实现 |

---

## 9. Subproject Contracts

### Sub-P0: opendcdiag-arm

角色：

- 真实硬件最终验证层

输入：

- promoted testcase package
- digest or correctness oracle
- metadata tags

输出：

- hardware verdict
- runtime logs
- machine/platform metadata

### Sub-P1: microprobe-arm

角色：

- 指令流生成与静态覆盖分析

输入：

- target
- policy
- mutation profile
- parent seeds

输出：

- asm / c source
- static metrics
- lineage metadata

### Sub-P2-1: qemu

角色：

- ISA-level golden executor
- 内循环 legality / 语义确认器

输入：

- compiled ELF

输出：

- return code
- golden digest

### Sub-P2-2: gem5

角色：

- 外循环微架构 fault campaign executor

输入：

- ELF
- fault matrix

输出：

- faulted digest
- crash / timeout / stats
- raw artifacts for McPAT

### Sub-P3: mcpat-arm

角色：

- 功耗估计与能量标签

输入：

- gem5 stats/config
- platform profile

输出：

- total/dynamic/leakage power

---

## 10. Target Database Model

为 100% 实现 README 愿景，建议从当前单表模型升级为兼容式多表模型。

### 10.1 Compatibility Rule

- 保留现有 `offline_testcases` 作为 seed catalog / backward-compatible surface
- 新增运行明细表，不破坏现有调用

### 10.2 Target Tables

1. `testcase_catalog`
   - 样本主表
   - `testcase_key`, `profile`, `asm_content`, `target_name`, `policy_name`
2. `testcase_static_metrics`
   - `ace_score`, `ibr_score`, `memory_pressure_score`, `capstone_validated`
3. `testcase_builds`
   - source/elf/wrapper/artifact paths
4. `testcase_qemu_runs`
   - qemu return code, digest, stdout/stderr
5. `testcase_power_profiles`
   - static estimate + mcpat result
6. `fault_campaigns`
   - campaign config, fault matrix metadata
7. `fault_runs`
   - per-fault execution result, faulted digest, classification
8. `hardware_promotions`
   - testcase → opendcdiag package mapping
9. `hardware_runs`
   - real machine verdicts
10. `lineage`
   - parent-child relations and mutation operators

### 10.3 Target States

```text
NEW
  -> STATIC_DONE
  -> QEMU_VALID
  -> POWER_ANNOTATED
  -> INNER_READY
  -> OUTER_SELECTED
  -> OUTER_VERIFIED
  -> PROMOTED_TO_HW
  -> HW_VERIFIED

ERROR TERMINALS:
  INVALID / QEMU_FAILED / GEM5_TIMEOUT / GEM5_CRASHED / HW_FAILED
```

---

## 11. Acceptance Criteria

项目达到 README 愿景的“完成态”时，应满足：

1. 内循环
   - 能持续生成海量样本
   - 能对样本完成静态评分、QEMU 校验、功耗标注、种群反馈
2. 外循环
   - 能对高价值样本做成体系的 gem5 fault campaign
   - 能输出稳定的 SDC sensitivity 结论
3. 硬件验证
   - 能把候选自动封装为 OpenDCDiag-ARM 测试
   - 能把真实机器结果写回数据库
4. 数据闭环
   - 一个 testcase 的静态信息、仿真信息、硬件信息和 lineage 全可追溯
5. README 愿景兑现
   - 同时覆盖静态筛选、差分验证、功耗反馈、真实环境验证四个层面
