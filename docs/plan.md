# SDC-Agent Project Plan

## 1. 计划目标

本计划把 README 的愿景拆成一组与当前源码结构兼容、可逐步交付的工程阶段。核心原则只有三个：

1. 不推倒重来，围绕现有控制平面骨架升级。
2. 先把数据契约和内循环做厚，再扩展 fault campaign 与真机回灌。
3. 所有阶段都必须能明确映射到子项目：
   - `Sub-P0 opendcdiag-arm`
   - `Sub-P1 microprobe-arm`
   - `Sub-P2-1 qemu`
   - `Sub-P2-2 gem5`
   - `Sub-P3 mcpat-arm`
   - `Sub-P4 SDC-Agent control plane`

---

## 2. 计划全景

| Phase | 目标 | 主要子项目 | 当前状态 | 完成度 |
| --- | --- | --- | --- | --- |
| Phase 0 | 架构合同与规划文档重构 | Control plane | 已完成 | 100% |
| Phase 1 | Vault v2 与数据契约升级 | Control plane | 已完成 | 100% |
| Phase 2 | 高频内循环产品化 | Sub-P1 microprobe-arm、Sub-P2-1 qemu、Sub-P3 mcpat-arm、Sub-P4 Control plane | 进行中 | 80% |
| Phase 3 | 功耗驱动的进化闭环 | Sub-P1 microprobe-arm、Sub-P3 mcpat-arm、Sub-P4 Control plane | 部分完成 | 30% |
| Phase 4 | 低频外循环产品化 | Sub-P2-1 qemu、Sub-P2-2 gem5、Sub-P4 Control plane | 部分完成 | 35% |
| Phase 5 | gem5 真实 fault injector | Sub-P2-2 gem5 | 早期 | 10% |
| Phase 6 | opendcdiag-arm promotion 与真机回灌 | Sub-P0 opendcdiag、Sub-P4 Control plane | 早期 | 10% |
| Phase 7 | LLM/PCFG/template 智能生成 | Sub-P1 microprobe-arm、Sub-P4 Control plane | 规划中 | 10% |

### 2.1 关键路径

达到 README 完成态的关键路径必须按这个顺序推进：

1. `Phase 1: Vault v2`
2. `Phase 2: Inner Loop`
3. `Phase 4: Outer Loop`
4. `Phase 5: gem5 Injector`
5. `Phase 6: Hardware Lane`
6. `Phase 7: Intelligent Generation`

原因很简单：

1. 没有数据库 v2，就无法表达 fault campaign 和硬件回灌。
2. 没有正式 inner loop，就没有稳定的 `INNER_READY` 样本池。
3. 没有 outer loop 与 injector，就无法真实判断 SDC 检测能力。
4. 没有硬件验证环，就无法闭合 README 最后的真实环境愿景。

---

## 3. Phase 0：架构合同与规划文档重构

**目标**：把“源码事实、README 愿景、子项目边界、执行顺序”统一成一套稳定叙事。

### 已交付

1. 重写 `docs/spec.md`
2. 重写 `docs/plan.md`
3. 将状态类文档收敛为 `docs/state.md`
4. 将 `doc/` 目录重命名为 `docs/`
5. 删除 root 级重复状态镜像文件
6. 修正 README 与仓库内文档引用

### 验收标准

1. 所有规划文档都以源码事实为依据。
2. 明确区分：
   - 已实现
   - 控制面已实现但执行面未实现
   - 纯规划项
3. 内循环、外循环、硬件验证环边界清晰。

---

## 4. Phase 1：Vault v2 与数据契约升级

**目标**：把当前 `offline_testcases` 单表扩展为能承载完整三层闭环的兼容式多表模型。

### 需要完成的工作

1. 设计并创建以下表：
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
2. 为现有 `offline_testcases` 提供兼容映射层。
3. 将 `risk_score / qemu_golden_hash / gem5_fault_hash / mcpat_power / status` 保持为 summary 字段。
4. 定义统一状态机：
   - inner states
   - outer states
   - hardware states
5. 增加 schema migration 与最小回滚策略。

### 子项目映射

1. `Control plane`
   - 负责迁移、DAO、兼容层、summary 写回
2. `Sub-P1 microprobe-arm`
   - 负责补充 generation metadata contract
3. `Sub-P2-2 gem5`
   - 负责定义 `fault_runs` 需要的最小字段
4. `Sub-P0 opendcdiag-arm`
   - 负责定义 `hardware_runs` 所需元数据

### 交付物

1. `sdc_agent/vault_v2.py` 或对 `vault.py` 的兼容升级
2. 数据迁移脚本
3. 兼容视图或 summary adapter
4. 对应单元测试与迁移测试

### 验收标准

1. 现有 CLI 不因为数据库升级而失效。
2. 一个 testcase 可以关联多次 power run、fault run、hardware run。
3. 现有 `status` 汇总能力仍然可用。

---

## 5. Phase 2：高频内循环产品化

**目标**：将 README 中要求的“生成、覆盖率、wrapper、QEMU 合法性、McPAT 功耗、反馈进化”收敛成正式 `inner_loop`。

### 需要完成的工作

1. 抽出正式 orchestrator：
   - `sdc_agent/inner_loop.py`
   - `tools/sdc_inner_loop.py`
2. 将生成阶段标准化为：
   - profile 选择
   - batch generation
   - static metrics writeback
3. 将物料化与 QEMU 校验纳入主路径。
4. 引入 artifact caching：
   - source cache
   - ELF cache
   - golden digest cache
5. 将 shortlist 的功耗标注纳入主路径，而不是独立脚本。
6. 输出标准状态：
   - `STATIC_DONE`
   - `GOLDEN_READY`
   - `POWER_READY`
   - `INNER_READY`

### 子项目映射

1. `Sub-P1 microprobe-arm`
   - 生成 testcase、计算静态指标
2. `Sub-P2-1 qemu`
   - 快速合法性验证与 golden digest
3. `Sub-P3 mcpat-arm`
   - 对 shortlist 样本打功耗标签
4. `Sub-P4 Control plane`
   - orchestrator、缓存、状态迁移、批处理

### 当前阻塞

1. source / ELF / golden digest cache 已接入，但更细粒度 artifact/index 仍可继续增强。
2. 功耗链路已进入标准步骤，但仍缺更大规模批处理复用。
3. 当前 profile 仍然以 `SIM_SAFE` 为主，`HW_AGGRESSIVE` 尚未正式落地。

### 交付物

1. `sdc_agent/inner_loop.py`
2. `tools/sdc_inner_loop.py`
3. Inner loop integration tests
4. 批量运行报告与状态汇总

### 当前已完成

1. `sdc_agent/inner_loop.py` 已实现正式 inner loop orchestrator。
2. `tools/sdc_inner_loop.py` 已提供 CLI 入口。
3. `STATIC_DONE / GOLDEN_READY / POWER_READY / INNER_READY` 状态流已接入。
4. source / ELF / golden digest cache 已接入 inner loop 主路径。
5. `fault_model=none` 的 inner loop 运行不会污染 `fault_runs`。
6. 已新增 inner-loop 定向测试与 cache 复用测试。

### 验收标准

1. 单条命令可以把样本从生成推进到 `INNER_READY`。
2. QEMU 可执行性结果被稳定回写数据库。
3. shortlist 样本具备可查询的功耗标签。

---

## 6. Phase 3：功耗驱动的进化闭环

**目标**：让 `microprobe-arm` 的后续样本生成不再只依赖静态分，而是显式使用功耗与合法性反馈。

### 需要完成的工作

1. 把 `static_risk_score` 与 `inner_value_score` 分离。
2. 将 `McPAT` 输出引入 `FeedbackScheduler`。
3. 为 `genetic.py` 增加 profile-aware 变异和 reweighting。
4. 引入 diversity constraint，避免 offspring 全部坍缩到同类样本。
5. 把 memory bias、dependency distance、stride tuning 显式记录到 `lineage_events`。

### 子项目映射

1. `Sub-P1 microprobe-arm`
   - profile-aware instruction family weighting
2. `Sub-P3 mcpat-arm`
   - 稳定的功耗字段与模板版本
3. `Sub-P4 Control plane`
   - scheduler scoring、offspring ranking、feedback log

### 交付物

1. 升级后的 `FeedbackScheduler`
2. 升级后的 `SDCFuzzingGeneticDriver`
3. 功耗与 lineage 联动测试

### 验收标准

1. offspring 的选择能显式使用功耗信息。
2. 能解释“为什么这个 parent 被优先繁殖”。
3. 3000+ 样本级批处理不会让 lineage 失真。

---

## 7. Phase 4：低频外循环产品化

**目标**：把当前单次差分执行扩展成真正的 `fault campaign`。

### 需要完成的工作

1. 抽出：
   - `sdc_agent/outer_loop.py`
   - `tools/sdc_outer_loop.py`
2. 引入 `fault matrix planner`。
3. 确保同一 testcase 的：
   - QEMU golden
   - gem5 fault-side
   - digest compare
   以同一逻辑 run 单元记录。
4. 支持多次 fault run 的聚合：
   - detection rate
   - repeatability
   - outer value score
5. 支持 campaign 级报告与回放。

### 子项目映射

1. `Sub-P2-1 qemu`
   - paired golden execution
2. `Sub-P2-2 gem5`
   - fault-side execution
3. `Control plane`
   - planner、aggregator、campaign ledger

### 当前阻塞

1. `campaign.py` 当前只适合单次或少量点状执行。
2. 没有 `fault_runs` 数据模型。
3. 没有 `outer_value_score` 聚合逻辑。

### 交付物

1. `outer_loop.py`
2. `fault planner`
3. campaign aggregation tests
4. per-fault result schema

### 验收标准

1. 一个 testcase 能关联多个 fault run。
2. 系统能自动判断“该样本是否值得 promotion”。
3. 外循环结果能稳定回写到数据库 summary。

---

## 8. Phase 5：gem5 真实 fault injector

**目标**：把当前的 `fault request manifest` 升级为真正生效的 fault injection 执行面。

### 需要完成的工作

1. 选择注入实现位置：
   - CPU pipeline hook
   - register file hook
   - memory/cache hook
2. 让 `sdc_fault_request.json` 被 gem5 执行面真正消费。
3. 支持至少一类可验证的注入：
   - register bit flip
   - memory bit flip
4. 增加 injector 自测与金丝雀用例。
5. 把 `implemented_in_script=False` 升级为真实实现状态。

### 子项目映射

1. `Sub-P2-2 gem5`
   - injector 主实现
2. `Control plane`
   - campaign request schema、fault planner 适配

### 交付物

1. gem5 C++/Python 注入扩展
2. 注入正确性测试
3. 与 outer loop 的联调报告

### 验收标准

1. fault request 不再只是记录文件。
2. 系统能证明 fault 已在预期位置、预期时间生效。
3. outer loop 的 `SDC_FOUND` 结果来自真实 injector，而不是占位流程。

---

## 9. Phase 6：opendcdiag-arm promotion 与真机回灌

**目标**：把高价值 testcase 推广为 `opendcdiag-arm` 测试，并把真机结果回灌数据库。

### 需要完成的工作

1. 设计 promotion contract：
   - testcase -> opendcdiag test source
   - metadata -> test knobs / detectors
2. 生成 `tests/cpu/arm64` 风格测试文件。
3. 接入 `meson.build` 或等价构建入口。
4. 提供运行与结果解析脚本。
5. 把 pass/fail、检测器输出、机器元数据、日志路径写回数据库。

### 子项目映射

1. `Sub-P0 opendcdiag-arm`
   - 测试模板、运行环境、结果格式
2. `Control plane`
   - promotion selector、backfill importer

### 当前阻塞

1. 当前只有 `OpenDCDiagBackend` placeholder。
2. 没有 test emitter。
3. 没有 hardware result parser。

### 交付物

1. `sdc_agent/hardware_lane.py`
2. `tools/sdc_promote_hw.py`
3. `tools/sdc_ingest_hw_results.py`
4. opendcdiag-arm 集成样例

### 验收标准

1. 可以从数据库自动生成一个 opendcdiag ARM64 SDC 测试。
2. 可以在真实机器执行并回写结果。
3. 结果能与 outer loop 形成闭环对照。

---

## 10. Phase 7：LLM / PCFG / Template 智能生成

**目标**：在规则生成器和 GA baseline 之上叠加更智能的生成策略，而不是替代当前 Microprobe 主干。

### 需要完成的工作

1. LLM mutation advisor：
   - 读取 lineage、inner/outer/hardware 反馈
   - 输出变异建议
2. PCFG instruction family generator
3. 高价值模板库：
   - cache-thrash
   - long dependency chain
   - NEON/FMA heavy pattern
4. profile reweighting service
5. prompt 与模板版本管理

### 子项目映射

1. `Sub-P1 microprobe-arm`
   - instruction family/模板承载
2. `Control plane`
   - LLM orchestration、版本化、反馈接入

### 验收标准

1. 新生成策略能挂接到 inner loop，而不是独立实验。
2. 新策略在覆盖率、功耗波动或 outer sensitivity 上优于纯 baseline。

---

## 11. 子项目工作包矩阵

| 子项目 | 近期必须完成 | 中期必须完成 | 完成态职责 |
| --- | --- | --- | --- |
| `Sub-P1 microprobe-arm` | 双 profile、metadata contract | template/PCFG/LLM 接入 | 持续生成高价值 ARM64 样本 |
| `Sub-P2-1 qemu` | golden digest 缓存、非法指令分类 | batch executor | 高频 legality/golden 验证 |
| `Sub-P2-2 gem5` | fault matrix runner 对接 | 真实 injector | 外循环主执行面 |
| `Sub-P3 mcpat-arm` | 稳定模板与字段 | batch backfill | 功耗主标签器 |
| `Sub-P0 opendcdiag-arm` | promotion contract | 结果回灌 | 真机验证终端 |
| `Sub-P4 Control plane` | Vault v2、inner/outer orchestrator | hardware lane、reporting | 全局编排总线 |

---

## 12. 测试与验收策略

达到 README 完成态时，测试必须覆盖四层：

1. 单元测试
   - score、status、DAO、artifact contract
2. 集成测试
   - generation -> vault -> materialize -> qemu
   - campaign -> gem5 -> mcpat -> writeback
3. 研究级批处理验证
   - 3000+ 样本吞吐
   - lineage 稳定性
   - score 分布合理性
4. 硬件验收
   - promotion 成功
   - 真机结果可回灌
   - 数据库与报告一致

---

## 13. 计划结论

正确的执行顺序不是“先把所有子项目都改一遍”，而是：

1. 先稳数据库和架构合同。
2. 再把高频内循环正式化。
3. 再把低频外循环升级成真正的 fault campaign。
4. 随后补齐 gem5 injector。
5. 最后接入 `opendcdiag-arm` 真机验证。
6. 在系统闭环之后，再把 LLM/PCFG/template 作为增益层叠加。

按这个顺序推进，才能在不破坏现有骨架的前提下，逐步把项目推到 README 的完整目标形态。
