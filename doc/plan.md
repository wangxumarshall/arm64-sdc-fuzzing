# SDC-Agent Project Plan

## 1. Goal

把当前已经存在的 SDC-Agent 骨架扩展为一套完整系统，使其能够完整兑现 README 的目标与愿景：

1. 高频内循环
   - 生成海量指令流
   - 计算覆盖率
   - wrapper 成 SDC 检测用例
   - QEMU 验证
   - McPAT 功耗标注
   - 反馈指导 Microprobe 继续生成更优样本
2. 低频外循环
   - 从数据库中选择高价值样本
   - 执行 gem5 fault campaign 与 QEMU 对照
   - 量化样本的 SDC 检测能力
3. 真实硬件验证环
   - 将高价值样本推广到 OpenDCDiag-ARM
   - 运行真实环境检测
   - 把结果回灌数据库

---

## 2. Planning Assumptions

1. 不重写现有控制平面，而是在 `sdc_agent/` 基础上扩展。
2. 保留现有 `offline_testcases` 兼容入口，同时引入多表模型。
3. OpenDCDiag 只作为最终硬件验证层，而不是仿真执行层。
4. 允许 `SIM_SAFE` 与 `HW_AGGRESSIVE` 双 profile 并存。

---

## 3. Work Packages

## Phase 0: Baseline Freeze

状态：已完成

已具备：

- 代码结构重构完成
- README 与当前代码基线已同步
- `tools/`、`scripts/`、`dev/`、`artifacts/runtime/` 已分层
- 定向 pytest 已通过

主要资产：

- [`sdc_agent/agent.py`](/Users/wangxu/1-project/sdc-fuzzing/sdc_agent/agent.py)
- [`sdc_agent/generation.py`](/Users/wangxu/1-project/sdc-fuzzing/sdc_agent/generation.py)
- [`sdc_agent/differential.py`](/Users/wangxu/1-project/sdc-fuzzing/sdc_agent/differential.py)
- [`sdc_agent/campaign.py`](/Users/wangxu/1-project/sdc-fuzzing/sdc_agent/campaign.py)
- [`sdc_agent/scheduler.py`](/Users/wangxu/1-project/sdc-fuzzing/sdc_agent/scheduler.py)
- [`sdc_agent/vault.py`](/Users/wangxu/1-project/sdc-fuzzing/sdc_agent/vault.py)

---

## Phase 1: Database v2

目标：

让数据库足以支撑内循环、外循环、硬件回灌。

交付物：

1. 在现有 `offline_testcases` 之外增加：
   - `testcase_static_metrics`
   - `testcase_builds`
   - `testcase_qemu_runs`
   - `testcase_power_profiles`
   - `fault_campaigns`
   - `fault_runs`
   - `hardware_promotions`
   - `hardware_runs`
   - `lineage`
2. 在 `sdc_agent/vault.py` 中增加 migration / repository API
3. 兼容旧接口：
   - `fetch_top_k_risky`
   - `record_result`
   - `select_candidates`

建议新增文件：

- `sdc_agent/db_schema.py`
- `sdc_agent/db_models.py`

验收标准：

- 一个 testcase 可挂多次 qemu/gem5/hardware run
- 不破坏现有测试和 CLI 基本能力

---

## Phase 2: High-Frequency Inner Loop Orchestrator

目标：

把当前分散的生成、静态分析、物料化、QEMU 验证、功耗标注、进化收束成正式内循环。

交付物：

1. 新增 `sdc_agent/inner_loop.py`
2. 新增 `tools/sdc_inner_loop.py`
3. 内循环状态机：
   - `NEW`
   - `STATIC_DONE`
   - `QEMU_VALID`
   - `POWER_ANNOTATED`
   - `INNER_READY`
4. 双 profile 支持：
   - `SIM_SAFE`
   - `HW_AGGRESSIVE`

内循环步骤：

1. `microprobe-arm` 生成样本
2. 运行 ACE / IBR / Memory Pressure / Capstone
3. materialize
4. compile + qemu validate
5. tiered power annotate
6. 更新 inner score
7. 调用 genetic driver 调整下一批样本

需要改动的现有模块：

- [`sdc_agent/generation.py`](/Users/wangxu/1-project/sdc-fuzzing/sdc_agent/generation.py)
- [`sdc_agent/materialize.py`](/Users/wangxu/1-project/sdc-fuzzing/sdc_agent/materialize.py)
- [`sdc_agent/power_analysis.py`](/Users/wangxu/1-project/sdc-fuzzing/sdc_agent/power_analysis.py)
- [`microprobe/src/microprobe/driver/genetic.py`](/Users/wangxu/1-project/sdc-fuzzing/microprobe/src/microprobe/driver/genetic.py)

验收标准：

- 单个命令能跑完完整内循环
- 样本在数据库中形成完整 inner-loop 轨迹
- genetic feedback 真正使用 QEMU/功耗信号，不只看静态分

---

## Phase 3: Generation Strategy Upgrade

目标：

让生成策略真正覆盖 README 想要的指令敏感区。

交付物：

1. 拆分指令 profile：
   - `sim_safe_pool`
   - `hardware_aggressive_pool`
2. 扩展 mutation operators：
   - NEON/FMA 组合
   - 大步长访存
   - LDP/STP 对偶访存
   - cache eviction 访存模板
3. 引入多目标 seed selection：
   - coverage
   - qemu stability
   - power volatility
   - diversity

关键说明：

这个阶段是兑现 README “NEON / FMA / 跨步访存”愿景的必要条件。

验收标准：

- 数据库中可以区分 sim-safe 和 hardware-aggressive 样本
- aggressive 样本可以被正确标记为 `HW_ONLY` 或 `SIM_UNSUPPORTED`

---

## Phase 4: Low-Frequency Outer Loop

目标：

把当前单 fault 执行器升级为完整 fault campaign。

交付物：

1. 新增 `sdc_agent/outer_loop.py`
2. 新增 `tools/sdc_outer_loop.py`
3. 新增 fault matrix planner
4. 新增 per-fault run persistence
5. 新增 `sdc_sensitivity_score`

外循环步骤：

1. 从 `INNER_READY` 样本中选择 top-K
2. 生成 fault matrix
3. 缓存 golden digest
4. 执行多次 gem5 fault run
5. 分类结果
6. 聚合出 testcase 级 sensitivity
7. 更新数据库并产生 promotion candidate

需要改动的现有模块：

- [`sdc_agent/differential.py`](/Users/wangxu/1-project/sdc-fuzzing/sdc_agent/differential.py)
- [`sdc_agent/campaign.py`](/Users/wangxu/1-project/sdc-fuzzing/sdc_agent/campaign.py)
- [`sdc_agent/scheduler.py`](/Users/wangxu/1-project/sdc-fuzzing/sdc_agent/scheduler.py)

验收标准：

- 单个 testcase 可以绑定多组 fault run
- 能输出 testcase 级 `outer_value_score`

---

## Phase 5: gem5 Real Fault Injector

目标：

让 fault manifest 变成真正的 fault execution。

交付物：

1. gem5 fault injector 设计与实现
2. `implemented_in_script` 从 `False` 变成真实路径
3. 至少支持：
   - register bit flip
   - memory bit flip
   - configurable tick injection

建议落点：

- `gem5/src/...` CPU hook 或 SimObject
- `gem5/configs/example/arm/sdc_kunpeng920_se.py` 中接入 injector

验收标准：

- 启用 fault 参数时，gem5 结果可真实变化
- 不再只是记录 `sdc_fault_request.json`

---

## Phase 6: OpenDCDiag Promotion Lane

目标：

把最优样本迁移到真实环境中验证，并将结果回灌。

交付物：

1. 新增 `sdc_agent/hardware_promotion.py`
2. 新增 `tools/sdc_promote_hw.py`
3. 新增 `sdc_agent/hardware_results.py`
4. 自动生成：
   - `opendcdiag/tests/cpu/arm64/generated/*.cpp`
   - 必要的 metadata manifest
5. 结果采集与解析器

验收标准：

- 可从数据库中选取 top candidates
- 可在 OpenDCDiag-ARM 中形成生成测试
- 可将真实环境结果写回数据库

---

## Phase 7: Reporting, Skillization, and Operations

目标：

把系统从“可开发”提升到“可长期运行”。

交付物：

1. 系统级 report：
   - coverage frontier
   - power frontier
   - sdc frontier
   - hardware verified frontier
2. 将核心能力沉淀为 engine skill 文档：
   - generation skill
   - coverage skill
   - validation skill
   - power skill
   - fault campaign skill
   - hardware promotion skill
3. recurring automation / nightly campaign

---

## 4. Milestone-Based Acceptance

### M1: 完整内循环

判定标准：

- 一条命令可完成生成、静态分析、QEMU 校验、功耗标注、反馈生成

### M2: 完整外循环

判定标准：

- 一条命令可对 top-K 候选执行多 fault campaign 并写回 sensitivity

### M3: 真实 fault injection

判定标准：

- gem5 fault 参数触发真实 fault behavior

### M4: OpenDCDiag 真机闭环

判定标准：

- promoted testcase 能进入 OpenDCDiag-ARM 并把结果回灌数据库

### M5: README Vision Complete

判定标准：

- 高频内循环、低频外循环、真实环境验证环三者全部连通
- 子项目 P0 / P1 / P2-1 / P2-2 / P3 全部接入系统

---

## 5. Immediate Next Steps

按执行顺序，下一步应优先做：

1. Database v2
2. Inner loop orchestrator
3. fault matrix outer loop
4. gem5 real fault injector
5. OpenDCDiag promotion lane

原因：

- 数据模型不先扩展，后面 outer loop 和 hardware lane 都会被迫塞进 `metadata_json`
- inner loop 不先统一，power/qemu/genetic 就始终是分裂的
