# SDC-Agent 代码结构说明

## 1. 这份说明解决什么问题

这个仓库不是单体项目，而是一个以 `sdc_agent/` 为控制面、把 `microprobe`、`qemu`、`gem5`、`mcpat`、`opendcdiag` 组织在一起的 ARM64 SDC 自动化发现 monorepo。

理解代码时，最重要的判断不是“哪个目录最大”，而是“哪个目录在承担项目自己的业务逻辑”。从实现上看：

1. 项目自研控制面主要在 `sdc_agent/`、`tools/`、`tests/`、`scripts/`、`docs/`。
2. `microprobe/`、`gem5/`、`mcpat/`、`opendcdiag/` 中既有上游源码，也有本项目接入点。
3. `qemu/` 在当前架构里主要扮演 golden executor，本仓控制面更多是“调用它”，而不是在 Python 层深度包裹它。

如果你只想快速抓住项目骨架，优先读 root control plane，再回头看各子项目中的定制接缝。

## 2. 一句话架构

项目的核心结构可以概括成一句话：

> `tools/sdc_agent.py` 把命令行请求交给 `sdc_agent/agent.py`，后者以 `sdc_agent/vault.py` 为中心总线，驱动生成、物料化、QEMU/gem5 差分、McPAT 功耗标注、进化反馈和硬件验证闭环。

可以把仓库理解为五层：

1. 入口层：`tools/`
2. 编排层：`sdc_agent/agent.py`
3. 领域模块层：`sdc_agent/*.py`
4. 数据层：`sdc_agent/vault.py` + `artifacts/*.sqlite3`
5. 外部执行引擎层：`microprobe/`、`qemu/`、`gem5/`、`mcpat/`、`opendcdiag/`

## 3. 顶层目录职责

| 路径 | 角色 | 说明 |
| --- | --- | --- |
| `README.md` | 项目总览 | 描述目标、A/B 架构、主要模块映射 |
| `plan.md` | 长期架构合同 | 完成态架构、phase 路线图、验收口径 |
| `findings.md` | 历史状态快照 | 保留 `2026-04-06` 的状态与决策快照 |
| `progress.md` | 实施日志 | 记录最近修复、验证结果和环境限制 |
| `docs/` | 补充文档 | 包含 monorepo 约束、构建说明、ISA 文档等 |
| `sdc_agent/` | 控制面核心代码 | 项目真正的业务逻辑主目录 |
| `tools/` | CLI 入口 | 面向用户的薄包装命令 |
| `tests/` | root control plane 测试 | 以控制面模块为中心的单测/集成测 |
| `scripts/` | 环境与构建脚本 | 安装依赖、构建 QEMU/gem5/McPAT |
| `artifacts/` | 运行产物 | Vault、e2e 报告、物料化文件、活动记录 |
| `microprobe/` | 生成与进化域 | ARM64 fuzzing policy、静态分析 pass、遗传驱动 |
| `qemu/` | golden 执行器 | 用于 ISA 正确结果对照 |
| `gem5/` | fault-side 执行器 | 负责故障语义、统计、注入请求 |
| `mcpat/` | 功耗后处理 | 将 gem5 输出转成功耗标签 |
| `opendcdiag/` | 硬件验证后端 | 将高价值样本推进到真实硬件测试 |

## 4. 哪些代码是“项目骨架”

### 4.1 第一优先级

下面这些文件决定了项目的主行为：

| 文件 | 作用 |
| --- | --- |
| `tools/sdc_agent.py` | 顶层 CLI wrapper |
| `sdc_agent/agent.py` | 控制面总入口，负责统一编排 |
| `sdc_agent/vault.py` | SQLite 持久化与多表投影总线 |
| `sdc_agent/generation.py` | 生成任务组织、profile contract、批量落库 |
| `sdc_agent/materialize.py` | 将汇编 testcase 物料化成可执行 C 程序 |
| `sdc_agent/differential.py` | 编译、QEMU、gem5、McPAT 差分执行核心 |
| `sdc_agent/scheduler.py` | 候选排序、反馈吸收、promotion 规划 |
| `sdc_agent/campaign.py` | 经典 campaign 执行器 |
| `sdc_agent/inner_loop.py` | 高频内循环 orchestrator |
| `sdc_agent/outer_loop.py` | 低频外循环 orchestrator |
| `sdc_agent/hardware_lane.py` | promotion bundle 生成 |
| `sdc_agent/hardware_results.py` | 硬件执行与结果回灌 |
| `sdc_agent/preflight.py` | 工具链/环境检查 |
| `sdc_agent/tooling.py` | 本地工具解析和缺失步骤建议 |

### 4.2 第二优先级

下面这些文件是控制面与外部引擎之间的关键接缝：

| 文件 | 作用 |
| --- | --- |
| `microprobe/targets/arm64/policies/sdc_fuzzing_policy.py` | ARM64 SDC 生成策略 |
| `microprobe/src/microprobe/passes/sdc_analysis/offline_coverage.py` | 静态风险分析 pass |
| `microprobe/src/microprobe/driver/genetic.py` | Python 3 版进化驱动 |
| `microprobe/targets/generic/tools/mp_sdc_offline_gen.py` | 兼容 Microprobe 风格的离线生成 CLI |
| `gem5/configs/example/arm/sdc_kunpeng920_se.py` | gem5 SE 模式下的 SDC runner |
| `sdc_agent/power_backends/mcpat_backend.py` | McPAT Python 适配层 |
| `sdc_agent/power_backends/opendcdiag_backend.py` | OpenDCDiag staged workspace 执行后端 |

## 5. 控制面主链

### 5.1 入口层

`tools/` 基本都是薄入口，负责把命令转交给 `sdc_agent` 模块：

| 路径 | 作用 |
| --- | --- |
| `tools/sdc_agent.py` | 总入口，调用 `sdc_agent.agent.main()` |
| `tools/sdc_inner_loop.py` | 内循环入口 |
| `tools/sdc_outer_loop.py` | 外循环入口 |
| `tools/sdc_campaign.py` | campaign 入口 |
| `tools/sdc_materialize.py` | 物料化入口 |
| `tools/sdc_preflight.py` | 环境检查入口 |
| `tools/sdc_promote_hw.py` | 硬件 promotion 入口 |
| `tools/sdc_ingest_hw_results.py` | 硬件结果回灌入口 |

这里的设计意图很直接：CLI 保持很薄，业务逻辑尽量集中在 `sdc_agent/`。

### 5.2 编排层

`sdc_agent/agent.py` 是整个控制面的“总控制器”。

它负责三类工作：

1. 统一暴露子命令：
   - `status`
   - `domains`
   - `diff`
   - `generate`
   - `evolve`
   - `cycle`
   - `promote-hw`
   - `run-hw`
   - `ingest-hw`
   - `e2e-dev`
   - `e2e-sim`
   - `e2e-hw`
   - `e2e-local`
2. 处理 lazy import：
   - `generate`/`phase2`/`phase4`/`evolve` 这类命令只有在真正需要时才加载 Microprobe 依赖。
3. 提供组合执行：
   - `run_cycle()` 组合 `generate -> campaign -> evolve`
   - `run_e2e_dev()` 跑开发 smoke
   - `run_e2e_sim()` 串起 phase2、phase4 和 cycle
   - `run_e2e_hw()` 串起硬件 promotion 与执行链

因此，`agent.py` 不是算法核心，而是控制面编排中心。

## 6. 数据层是整个项目的“总线”

### 6.1 为什么 `vault.py` 这么关键

`sdc_agent/vault.py` 是全项目最重要的基础设施文件之一。这个项目不是靠对象直接互相调用来耦合，而是把 SQLite 当成模块总线。

控制面的大部分模块都遵循这个模式：

1. 从 Vault 选 testcase
2. 执行一段流水线
3. 把新状态、摘要和产物路径写回 Vault
4. 下一个模块继续从 Vault 接着跑

### 6.2 数据模型分两层

`vault.py` 同时维护两套视图：

1. 兼容摘要表：`offline_testcases`
   - 这是当前控制面最常直接读取的兼容表
2. v2 归一化表：
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

这意味着项目当前处于“兼容旧表 + 持续向归一化模型演进”的状态。

### 6.3 `metadata_json` 的真实角色

代码里大量逻辑依赖 `metadata_json`。它不是随手塞点附加信息，而是当前控制面跨模块传递上下文的事实总线。

典型内容包括：

1. 生成信息：
   - `profile_name`
   - `instruction_names`
   - `preferred_stride_bytes`
   - `lineage`
2. 执行信息：
   - `source_path`
   - `golden_digest`
   - `faulted_digest`
   - `execution`
   - `fault_request`
3. 子流程摘要：
   - `campaign`
   - `inner_loop`
   - `outer_loop`
   - `hardware_lane`

读代码时如果只盯着表字段，不盯 `metadata_json`，会误判很多模块的耦合关系。

## 7. 生成域

### 7.1 `sdc_agent/generation.py`

这是控制面视角下的生成核心，负责：

1. bootstrapping Microprobe Python path
2. 定义 profile contract
3. 选择指令序列
4. 组织 catalog 模式和 synthesizer 模式
5. 生成 `VaultEntry`
6. 批量落库

它把生成分成两种模式：

1. `catalog`
   - 适用于 `ALL_GENERATABLE`、`EXECUTABLE_SAFE`、`KUNPENG920_STRESS`
2. `synthesizer`
   - 适用于 `SIM_SAFE`、`HW_AGGRESSIVE`

这说明 profile 不是简单的标签，而是会切换底层生成路径。

### 7.2 Microprobe 中的项目定制

项目自己的生成逻辑主要落在 Microprobe 的三处扩展点：

1. `microprobe/targets/arm64/policies/sdc_fuzzing_policy.py`
   - 定义 `SDCSensitiveAnalyzer`
   - 根据 `SIM_SAFE` / `HW_AGGRESSIVE` 选择指令族
   - 组装 `InitializeRegistersPass`、结构 pass、寄存器分配 pass 和静态分析 pass
2. `microprobe/src/microprobe/passes/sdc_analysis/offline_coverage.py`
   - `StaticACECalculatorPass`
   - `StaticIBRCoveragePass`
   - `Kunpeng920MemoryPressurePass`
   - `CapstoneValidationPass`
3. `microprobe/targets/generic/tools/mp_sdc_offline_gen.py`
   - 提供兼容传统 Microprobe 风格的离线生成命令

所以生成能力虽然依赖 `microprobe/`，但项目关键增量并不分散，主要集中在 policy、pass 和 driver 三类扩展点上。

## 8. 物料化与差分执行

### 8.1 `materialize.py`

`sdc_agent/materialize.py` 做的不是简单模板替换，而是把 Vault 里的汇编片段包装成一个可重复执行、可输出 digest 的 ARM64 C 程序。

它做了三件关键事：

1. 初始化寄存器、SIMD 状态和一块固定模式的内存
2. 将 testcase 汇编嵌入 `sdc_benchmark_body`
3. 运行后采集 GPR/NZCV/SIMD/内存，折叠成 `SDC_DIGEST`

这一步的意义是把“原始汇编候选”变成“可被 QEMU 和 gem5 同时消费的统一执行物料”。

### 8.2 `differential.py`

`sdc_agent/differential.py` 是线上执行核心，负责：

1. `compile_static_elf()`
2. `run_qemu()`
3. `run_gem5()`
4. `build_fault_request_summary()`
5. `classify()`
6. 可选调用 `McPATBackend`

它输出的 `DifferentialResult` 是后续 `campaign`、`inner_loop`、`outer_loop`、`scheduler` 的共同输入格式。

其核心判定逻辑很清晰：

1. 编译失败：`compile_failed`
2. golden 失败：`golden_failed`
3. gem5 超时：`gem5_timeout`
4. gem5 失败：`gem5_failed`
5. fault 请求未真正观察到注入：`no_injection`
6. digest 不同：`sdc_found`
7. digest 相同：`matched`

这也是整个项目“轻量级差分测试”方法论在代码里的落点。

## 9. 三条执行环

### 9.1 高频内循环

`sdc_agent/inner_loop.py` 是高频内循环 orchestrator。

它做的事情是：

1. 可选调用 `generate_batch()`
2. 从 Vault 取 `STATIC_DONE`/`PENDING` 候选
3. 解析缓存的 source/ELF/golden digest
4. 调用 `run_differential()` 跑无 fault 的合法性和功耗路径
5. 回写 `GOLDEN_READY` / `POWER_READY` / `INNER_READY` 等状态
6. 可选触发进化

注意这里的 gem5 不是为了 fault campaign，而是为了功耗和 inner-loop readiness。

### 9.2 经典 campaign

`sdc_agent/campaign.py` 是较早、更直接的一层执行器：

1. 通过 `FeedbackScheduler` 选样
2. 若无 source，则现场 materialize
3. 跑一次 `run_differential()`
4. 用 `scheduler.record_result()` 把结果折回 Vault

可以把它理解为控制面里较通用、较薄的一条“执行一批候选”的路径。

### 9.3 低频外循环

`sdc_agent/outer_loop.py` 比 `campaign.py` 更接近 README 中的完成态外循环。

它新增了两个关键概念：

1. `FaultSpec`
   - 描述故障模型、目标、bit、tick
2. `OuterLoopAggregate`
   - 聚合 fault campaign 的统计摘要

主逻辑是：

1. 规划 fault matrix
2. 为每个 candidate 跑多组 differential
3. 记录 `fault_runs`
4. 聚合 `fault_detection_rate`、`repeatability_score`
5. 计算 `outer_value_score`、`injector_confidence_score`
6. 回写 `outer_loop` metadata 和 summary status

外循环真正回答的问题不是“能不能跑”，而是“带 fault 时是否稳定暴露 SDC，值不值得推进硬件验证”。

## 10. 调度、排序与反馈

`sdc_agent/scheduler.py` 是控制面的策略层。

它不直接生成、不直接执行，而是负责把静态分、功耗、合法性、外循环结果组合成排序与决策信号。

核心概念有：

1. `RankedCandidate`
   - 控制面内部的统一候选表示
2. `compute_static_score()`
   - 静态风险
3. `compute_legality_factor()`
   - 状态对价值的影响
4. `compute_power_gain()`
   - 功耗维度增益
5. `compute_diversity_bonus()`
   - 指令族多样性增益
6. `compute_inner_value_score()`
   - 高频内循环价值分
7. `promotion_plan()`
   - 硬件推广候选规划

所以 `scheduler.py` 实际上承担了“项目里的轻量策略引擎”角色。

## 11. 进化闭环

进化逻辑放在 `microprobe/src/microprobe/driver/genetic.py` 的 `SDCFuzzingGeneticDriver` 中。

它和老的 `pyevolve` 时代已经不是一回事；当前可运行的是 Python 3 版反馈驱动实现。

它的行为可以概括为：

1. 从 `FeedbackScheduler` 取高价值父代
2. 按指令族多样性选择 partner
3. 做 one-point crossover
4. 做 memory bias 和 opcode replacement
5. 强化 `preferred_stride_bytes`
6. 重新调用 `generate_testcase()`
7. 写回 lineage 元数据并重新注入 Vault

也就是说，进化不是独立服务，而是直接复用控制面的生成入口和 Vault。

## 12. 硬件验证环

### 12.1 `hardware_lane.py`

`sdc_agent/hardware_lane.py` 负责把候选转成硬件可跑 bundle。

主要动作：

1. 通过 `FeedbackScheduler.select_promotion_candidates()` 选样
2. 计算 promotion score
3. 生成：
   - `.s`
   - `promotion.json`
   - `opendcdiag` 风格的 `.cpp`
   - `meson.build.fragment`
4. 记录 `hardware_promotions`
5. 回写 testcase 的 `hardware_lane` metadata

它本质上是“从仿真世界到硬件世界的格式转换器”。

### 12.2 `hardware_results.py`

`sdc_agent/hardware_results.py` 负责：

1. 调 OpenDCDiag 后端执行 promotion
2. 解析结果
3. 归一化 detector 状态
4. 写入 `hardware_runs`
5. 更新 `hardware_promotions`
6. 回灌 testcase metadata

### 12.3 `opendcdiag_backend.py`

这个后端的做法非常务实：

1. 复制一份 `opendcdiag` workspace
2. 把 promotion 生成的测试源拷进去
3. patch `tests/cpu/arm64/meson.build`
4. 执行 `meson setup`
5. 执行 `meson compile`
6. 运行 `sandstone`
7. 把 stdout/stderr/TAP 摘要封成 JSON

因此，硬件 lane 不是只导出代码，而是已经有一条可执行的 staged runtime path。

## 13. 外部引擎如何接入

### 13.1 Microprobe

Microprobe 是生成前端和进化后端，项目在其中做了三类定制：

1. policy
2. static pass
3. genetic driver

### 13.2 QEMU

QEMU 在项目里主要承担 golden side 执行器角色：

1. 输入：物料化后的静态 ELF
2. 输出：golden digest
3. 位置：主要通过 `sdc_agent/differential.py` 被调用

当前 Python 控制面并没有深度包裹 QEMU 源码本身，重点在“构建和调用 repo-local qemu-aarch64”。

### 13.3 gem5

gem5 是 fault-side 执行器。关键接缝在 `gem5/configs/example/arm/sdc_kunpeng920_se.py`。

这个脚本负责：

1. 构造 Kunpeng920-like cache/memory profile
2. 装载 ELF
3. 记录 `sdc_fault_request.json`
4. 支持脚本化寄存器/向量寄存器/内存 bit flip
5. 输出可供 `differential.py` 解析的执行结果

### 13.4 McPAT

McPAT 通过 `sdc_agent/power_backends/mcpat_backend.py` 接入，后者只是一个薄 adapter，把 `mcpat/pypat` 的结果规范化回控制面协议。

### 13.5 OpenDCDiag

OpenDCDiag 只在硬件验证环出现，不进入高频内循环。

这和 README/plan 里的架构规则是对齐的：

1. `qemu` 负责 golden
2. `gem5` 负责 fault-side
3. `opendcdiag` 只做最终硬件验证

## 14. 环境、构建与可执行性

`sdc_agent/preflight.py` 和 `sdc_agent/tooling.py` 共同负责“这台机器能不能跑哪条 lane”。

### 14.1 `tooling.py`

主要职责：

1. 解析 repo-local 工具路径
2. 支持环境变量覆盖
3. 兼容 PATH 中已有工具
4. 为编译器、QEMU、gem5、McPAT、meson、ninja、OpenDCDiag 提供统一解析

### 14.2 `preflight.py`

主要职责：

1. 定义 `dev` / `sim` / `hw` 三种 profile
2. 检查 Python runtime 模块
3. 检查 host 是否匹配 sim profile
4. 检查编译器、QEMU、gem5、McPAT、meson、ninja
5. 生成 `missing_steps`

从代码结构上说，`preflight.py` 让“能不能跑”成为一等概念，而不是把失败留到执行期。

## 15. 文档与治理结构

项目文档已经做了 root 收敛：

1. `plan.md`
   - 长期架构和阶段路线图
2. `progress.md`
   - 最近一次实施与验证
3. `docs/monorepo.md`
   - domain 边界和管理方式

根级 `plan.md` 与 `progress.md` 是当前主文档；`findings.md` 保留为历史快照；`docs/` 下内容用于结构和专题补充。

## 16. 测试结构如何映射源码

`tests/` 基本是“按控制面模块镜像”的结构。

可以直接从文件名反推覆盖域：

| 测试文件 | 覆盖重点 |
| --- | --- |
| `tests/test_sdc_agent.py` | 顶层 agent 编排与 e2e 报告 |
| `tests/test_sdc_vault_v2.py` | Vault v2 投影与兼容迁移 |
| `tests/test_sdc_inner_loop.py` | 高频内循环 |
| `tests/test_sdc_outer_loop.py` | 低频外循环 |
| `tests/test_sdc_scheduler.py` | 排序和反馈 |
| `tests/test_sdc_materialize.py` | 汇编物料化 |
| `tests/test_run_sdc_differential.py` | 差分执行 |
| `tests/test_sdc_hardware_lane.py` | promotion bundle |
| `tests/test_hardware_results.py` | 硬件结果回灌 |
| `tests/test_power_backends.py` | McPAT/OpenDCDiag backend |
| `tests/test_offline_to_campaign_integration.py` | 从离线生成到 campaign 的跨模块集成 |

除此之外，`microprobe/targets/arm64/tests/` 还覆盖了 ARM64 目标与离线生成侧的细节。

## 17. 推荐阅读顺序

如果要高效读懂这个仓库，建议按下面顺序走：

1. `README.md`
   - 先建立项目目标和三条执行环的概念
2. `docs/monorepo.md`
   - 建立 domain 边界
3. `tools/sdc_agent.py`
   - 确认顶层入口极薄
4. `sdc_agent/agent.py`
   - 看控制面如何组织子命令和 e2e
5. `sdc_agent/vault.py`
   - 看数据总线与状态模型
6. `sdc_agent/generation.py`
   - 看生成 contract
7. `microprobe/targets/arm64/policies/sdc_fuzzing_policy.py`
   - 看 ARM64 生成策略
8. `microprobe/src/microprobe/passes/sdc_analysis/offline_coverage.py`
   - 看静态评分从哪来
9. `sdc_agent/materialize.py`
   - 看 testcase 如何变成可执行程序
10. `sdc_agent/differential.py`
   - 看执行与分类核心
11. `sdc_agent/scheduler.py`
   - 看价值分和反馈策略
12. `sdc_agent/inner_loop.py`、`sdc_agent/outer_loop.py`
   - 看高频/低频两条环
13. `microprobe/src/microprobe/driver/genetic.py`
   - 看进化闭环
14. `sdc_agent/hardware_lane.py`、`sdc_agent/hardware_results.py`
   - 看硬件环
15. `gem5/configs/example/arm/sdc_kunpeng920_se.py`
   - 看 fault-side 执行接缝

## 18. 读这个仓库时最容易踩的坑

1. 不要把 `qemu/`、`gem5/`、`microprobe/` 的总代码量误判成“项目业务代码的中心”。
2. 不要忽略 `metadata_json`，很多控制面状态都只存在于那里。
3. 不要只看 `offline_testcases`，v2 归一化表同样重要。
4. 不要把 `campaign.py` 和 `outer_loop.py` 当成重复实现；前者更薄，后者更接近完成态 fault campaign。
5. 不要把硬件 lane 理解成一个导出脚本；它已经包含 bundle 生成、运行和结果 ingestion。

## 19. 总结

从代码结构上看，这个项目的真正核心不是某个单独的大型子目录，而是下面这个组合：

1. `sdc_agent/agent.py` 负责编排
2. `sdc_agent/vault.py` 负责数据总线
3. `sdc_agent/generation.py` + Microprobe 扩展负责生成
4. `sdc_agent/materialize.py` + `differential.py` 负责执行与比对
5. `sdc_agent/scheduler.py` + `microprobe/.../genetic.py` 负责反馈与进化
6. `sdc_agent/hardware_lane.py` + `hardware_results.py` 负责硬件闭环

也就是说，这个仓库本质上是一个“以 SQLite 为总线、以 Python 控制面为核心、以多执行引擎为后端”的 ARM64 SDC 自动化发现系统。
