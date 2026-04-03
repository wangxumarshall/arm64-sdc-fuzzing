# SDC-Agent State

本文件是项目唯一的“当前状态”权威文档，用来取代并合并此前分散在 `docs/` 与仓库根目录中的 findings / progress / task 镜像文件。

更新规则：

1. [spec.md](/Users/wangxu/1-project/sdc-fuzzing/docs/spec.md) 只描述完成态架构与长期合同。
2. [plan.md](/Users/wangxu/1-project/sdc-fuzzing/docs/plan.md) 只描述阶段计划、交付物与验收标准。
3. `state.md` 只描述当前阶段、最新发现、当前进展、验证结果、剩余风险与下一步。

---

## 1. Current Phase

日期：`2026-04-03`

当前主阶段：

- `Phase 2: 高频内循环产品化`

当前判断：

1. `Phase 0` 已完成。
2. `Phase 1` 已完成。
3. `Phase 2` 进行中，已完成约 `80%`。

当前阶段的核心目标：

1. 让 inner loop 成为正式 orchestrator，而不是零散脚本拼接。
2. 将生成、静态分析、物料化、QEMU 合法性、McPAT 功耗、反馈进化串成一条标准路径。
3. 为 `Phase 4` 的 outer loop 准备稳定的 `INNER_READY` 样本池。

---

## 2. Latest Findings

本轮收敛和实现后，最重要的发现与结论是：

1. 项目当前真正稳定的主干仍然是：
   - `generation -> vault -> materialize/differential -> scheduler -> genetic`
2. `STATIC_DONE` 应当作为内循环里“已生成、已静态分析、待执行”的明确状态保留下来。
3. `run_differential()` 只要支持：
   - `skip_compile`
   - `skip_qemu`
   - `cached_golden_digest`
   就足以承载 Phase 2 所需的 ELF 与 golden cache 复用。
4. source / ELF / golden 三层 cache 已经能显著减少重复执行时的内循环开销。
5. `fault_model=none` 的过滤必须继续保留，否则 inner loop 会污染 outer loop 的 `fault_runs` 历史。
6. 当前控制平面已经足够支撑继续推进，不需要重写整体骨架。

---

## 3. Completed

### 3.1 文档体系

1. 仓库的正式文档现已收敛为：
   - [spec.md](/Users/wangxu/1-project/sdc-fuzzing/docs/spec.md)
   - [plan.md](/Users/wangxu/1-project/sdc-fuzzing/docs/plan.md)
   - [state.md](/Users/wangxu/1-project/sdc-fuzzing/docs/state.md)
2. `doc/` 已重命名为 `docs/`。
3. 状态类文档已合并，不再保留 root 级镜像。

### 3.2 Phase 1

1. [sdc_agent/vault.py](/Users/wangxu/1-project/sdc-fuzzing/sdc_agent/vault.py) 已升级为兼容式多表实现。
2. 保留了 `offline_testcases` 作为现有控制平面的 summary/兼容层。
3. 已新增：
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

### 3.3 Phase 2

1. [sdc_agent/inner_loop.py](/Users/wangxu/1-project/sdc-fuzzing/sdc_agent/inner_loop.py) 已实现正式 inner loop orchestrator。
2. [tools/sdc_inner_loop.py](/Users/wangxu/1-project/sdc-fuzzing/tools/sdc_inner_loop.py) 已提供 CLI 入口。
3. 内循环状态流已接入：
   - `STATIC_DONE`
   - `GOLDEN_READY`
   - `POWER_READY`
   - `INNER_READY`
4. source / ELF / golden digest cache 已接入 inner loop 主路径。
5. `fault_model=none` 的 inner loop 运行不会污染 `fault_runs`。
6. evolution 继续可作为 inner loop 的尾段使用。

---

## 4. Validation

截至当前，已完成的直接验证包括：

1. `python3 -m py_compile sdc_agent/generation.py sdc_agent/differential.py sdc_agent/inner_loop.py sdc_agent/agent.py`
2. `python3 -m pytest tests/test_sdc_inner_loop.py tests/test_sdc_agent.py tests/test_run_sdc_differential.py -q`
3. `python3 -m pytest tests -q`
4. `python3 tools/sdc_inner_loop.py --help`
5. `python3 tools/sdc_agent.py status --db artifacts/sdc_vault.sqlite3 --limit 1`

当前结果：

1. `32 passed`
2. 新 CLI 正常暴露参数
3. 现有 `status` 汇总仍可用

---

## 5. Open Risks

当前最主要的未完成项和风险如下：

1. `HW_AGGRESSIVE` profile 尚未正式落地。
2. inner loop 已具备基础缓存，但更细粒度的 artifact/index 体系仍可继续增强。
3. outer loop 仍未产品化：
   - 缺少 `fault matrix planner`
   - 缺少正式 `outer_loop.py`
   - 缺少 `outer_value_score`
4. gem5 real fault injector 尚未实现。
5. `opendcdiag-arm` promotion/backfill 尚未接入控制平面。

---

## 6. Next Actions

推荐的后续顺序仍然是：

1. 完成 Phase 2 的尾项
   - 更强的 artifact/index 体系
   - profile contract 继续收口
2. 进入 `Phase 4: 低频外循环产品化`
   - `outer_loop.py`
   - `fault matrix planner`
   - per-fault aggregation
3. 推进 `Phase 5: gem5 真实 fault injector`
4. 推进 `Phase 6: opendcdiag-arm promotion 与真机回灌`

---

## 7. Canonical Pointers

1. 完成态架构见 [spec.md](/Users/wangxu/1-project/sdc-fuzzing/docs/spec.md)
2. 分阶段计划见 [plan.md](/Users/wangxu/1-project/sdc-fuzzing/docs/plan.md)
3. 当前状态见 [state.md](/Users/wangxu/1-project/sdc-fuzzing/docs/state.md)
