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

- `Phase 4: 低频外循环产品化`

当前判断：

1. `Phase 0` 已完成。
2. `Phase 1` 已完成。
3. `Phase 2` 已完成真实端到端验证。
4. `Phase 4` 已开始首版实现。

当前阶段的核心目标：

1. 让 inner loop 成为正式 orchestrator，而不是零散脚本拼接。
2. 将生成、静态分析、物料化、QEMU 合法性、McPAT 功耗、反馈进化串成一条标准路径。
3. 将单次差分执行扩展成真正的 fault campaign。

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
5. `SIM_SAFE / HW_AGGRESSIVE` 现在已经是显式 profile contract，而不是隐式约定。
6. 当前 `HW_AGGRESSIVE` 默认生成路径仍会诚实回退到 `SIM_SAFE`，直到激进生成器真正实现。
7. inner loop 现在会优先从 artifacts 索引恢复 source / ELF，而不是只依赖 metadata 路径。
8. `fault_model=none` 的过滤必须继续保留，否则 inner loop 会污染 outer loop 的 `fault_runs` 历史。
9. 当前控制平面已经足够支撑继续推进，不需要重写整体骨架。
10. 通过 source-built `qemu-system-aarch64`、source-built `mcpat`、`aarch64-conda-linux-gnu-gcc`、`gem5` 的真实链路，`Phase 2` baseline case 已得到端到端通过。

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
5. `SIM_SAFE / HW_AGGRESSIVE` profile contract 已进入 generation / inner loop / CLI。
6. `fault_model=none` 的 inner loop 运行不会污染 `fault_runs`。
7. artifacts 索引现在可为 inner loop 提供 source / ELF fallback。
8. evolution 继续可作为 inner loop 的尾段使用。
9. [validate_phase2_e2e.py](/Users/wangxu/1-project/sdc-fuzzing/tools/validate_phase2_e2e.py) 已提供真实端到端验证入口。

### 3.4 Phase 4

1. [outer_loop.py](/Users/wangxu/1-project/sdc-fuzzing/sdc_agent/outer_loop.py) 已实现首版 outer loop orchestrator。
2. [sdc_outer_loop.py](/Users/wangxu/1-project/sdc-fuzzing/tools/sdc_outer_loop.py) 已提供 CLI 入口。
3. 已支持 fault matrix planner。
4. 已支持多 fault run 写入 `fault_runs` 与 `fault_campaigns`。
5. 已支持基础的：
   - `fault_detection_rate`
   - `repeatability_score`
   - `outer_value_score`
6. 已支持 campaign 查询与按 campaign 检索 `fault_runs`。
7. outer loop 现在会直接返回 testcase 级 `aggregates` 和 campaign 摘要。
8. [validate_phase2_e2e.py](/Users/wangxu/1-project/sdc-fuzzing/tools/validate_phase2_e2e.py) 已提供真实端到端验证入口。

---

## 4. Validation

截至当前，已完成的直接验证包括：

1. `python3 -m py_compile sdc_agent/generation.py sdc_agent/differential.py sdc_agent/inner_loop.py sdc_agent/agent.py`
2. `python3 -m pytest tests/test_sdc_inner_loop.py tests/test_sdc_agent.py tests/test_run_sdc_differential.py -q`
3. `python3 -m pytest tests -q`
4. `python3 tools/sdc_inner_loop.py --help`
5. `python3 tools/sdc_agent.py status --db artifacts/sdc_vault.sqlite3 --limit 1`
6. `python3 tools/sdc_agent.py generate --help`
7. `python3 microprobe/targets/generic/tools/mp_sdc_offline_gen.py --help`
8. 最小 `HW_AGGRESSIVE` profile generation smoke
9. `python3 -m pytest microprobe/targets/arm64/tests/tools/test_mp_sdc_offline_gen.py microprobe/targets/arm64/tests/targets/test_target_contract.py -q`
10. `python3 tools/validate_phase2_e2e.py --candidate-kind baseline ...`
11. `python3 -m pytest tests/test_sdc_outer_loop.py tests/test_sdc_campaign.py tests/test_sdc_vault_v2.py -q`
12. `python3 tools/sdc_outer_loop.py --help`

当前结果：

1. 主仓测试：`36 passed`
2. `microprobe` 定向测试：`8 passed`
3. 新 CLI 正常暴露参数
4. 现有 `status` 汇总仍可用
5. `HW_AGGRESSIVE` 请求会被正确记录为“requested=HW_AGGRESSIVE, effective=SIM_SAFE”
6. baseline Phase 2 真实端到端验证已通过：
   - qemu golden digest = `2b85c03077dc5edd`
   - gem5 digest = `2b85c03077dc5edd`
   - mcpat power_total = `43738.51286976`
7. Phase 4 定向测试已通过：
   - `11 passed`
8. `sdc_outer_loop.py --help` 已 smoke 通过
9. outer loop campaign 查询与 aggregate 返回值测试已通过

---

## 5. Open Risks

当前最主要的未完成项和风险如下：

1. `HW_AGGRESSIVE` 默认生成器尚未正式落地。
2. inner loop 已具备基础缓存和 artifact index，但更细粒度的 artifact/index 体系仍可继续增强。
3. outer loop 已有首版骨架，但仍未与真实 injector 联动完成。
4. gem5 real fault injector 尚未实现。
5. `opendcdiag-arm` promotion/backfill 尚未接入控制平面。

---

## 6. Next Actions

推荐的后续顺序仍然是：

1. 继续推进 `Phase 4`
   - outer loop 与真实 injector 的衔接
   - 更丰富的聚合与排序
2. 推进 `Phase 5: gem5 真实 fault injector`
3. 推进 `Phase 6: opendcdiag-arm promotion 与真机回灌`

---

## 7. Canonical Pointers

1. 完成态架构见 [spec.md](/Users/wangxu/1-project/sdc-fuzzing/docs/spec.md)
2. 分阶段计划见 [plan.md](/Users/wangxu/1-project/sdc-fuzzing/docs/plan.md)
3. 当前状态见 [state.md](/Users/wangxu/1-project/sdc-fuzzing/docs/state.md)
