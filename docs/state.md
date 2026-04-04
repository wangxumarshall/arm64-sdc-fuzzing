# SDC-Agent State

本文件是项目唯一的“当前状态”权威文档，用来取代并合并此前分散在 `docs/` 与仓库根目录中的 findings / progress / task 镜像文件。

更新规则：

1. [spec.md](/Users/wangxu/1-project/sdc-fuzzing/docs/spec.md) 只描述完成态架构与长期合同。
2. [plan.md](/Users/wangxu/1-project/sdc-fuzzing/docs/plan.md) 只描述阶段计划、交付物与验收标准。
3. `state.md` 只描述当前阶段、最新发现、当前进展、验证结果、剩余风险与下一步。

---

## 1. Current Phase

日期：`2026-04-04`

当前主阶段：

- `Phase 3: 功耗驱动的进化闭环 hardening`
- `Phase 4: 低频外循环产品化`
- `Phase 5: gem5 scripted injector expansion`
- `Phase 6: 硬件 promotion lane bootstrap`
- `Phase 7: template/PCFG intelligent generation bootstrap`

当前判断：

1. `Phase 0` 已完成。
2. `Phase 1` 已完成。
3. `Phase 2` 已完成真实端到端验证。
4. `Phase 4` 已开始首版实现，并已把 injector confidence / promotion readiness 接入调度层。
5. `Phase 6` 已从“只有表结构和 placeholder”推进到“有 promotion selector、有 bundle emitter、有 build/run backend、有结果 ingest 写回”的阶段。
6. 仓库治理层面，`root + microprobe + qemu + gem5 + mcpat + opendcdiag` 现已合并到单一 monorepo 管理。
7. `Phase 3` 当前已补上 inner-loop value scoring、diversity-aware mutation planning 与 profile-aware evolution fallback 这条控制面缺口。
8. `Phase 5` 当前已从两类 scripted fault model 扩到第三类：`memory_bit_flip`。
9. `Phase 6` 当前已从“回写原始 hardware payload”推进到“规范化 detectors / detector summary / machine-build-runtime metadata”。
10. `Phase 7` 当前已把 template/PCFG generation 和 heuristic mutation advisor 真正挂进主控制平面路径。

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
6. `HW_AGGRESSIVE` 默认生成路径现在已具备 profile-aware instruction picker，不再默认回退到 `SIM_SAFE`。
7. inner loop 现在会优先从 artifacts 索引恢复 source / ELF，而不是只依赖 metadata 路径。
8. `fault_model=none` 的过滤必须继续保留，否则 inner loop 会污染 outer loop 的 `fault_runs` 历史。
9. 当前控制平面已经足够支撑继续推进，不需要重写整体骨架。
10. 通过 source-built `qemu-system-aarch64`、source-built `mcpat`、`aarch64-conda-linux-gnu-gcc`、`gem5` 的真实链路，`Phase 2` baseline case 已得到端到端通过。
11. gem5 SE 路径下，支持的 register bit flip 请求已经不再只是 manifest 记录；脚本侧可以观测并打印真实注入事件。
12. 当前脚本化 injector 已扩到第二类 fault model：`vector_register_bit_flip`，可对 `v0/q0` 这类 ARM 向量寄存器执行 128-bit 范围内 bit flip。
13. 控制面现在需要区分三类外循环 fault run：
   - `gem5_scripted`
   - `manifest_only`
   - `request_only`
14. 仅有 digest 差异还不足以支撑 promotion；还需要把 injector 是否真正被观测到收敛成独立聚合信号。
15. 重新核对已完成 phases 后，最明显的遗漏并不在 `Phase 0/1/2` 主链，而在 `Phase 6` 控制面完全未起步。
16. `promotion_plan` 只有在真正落地成 `hardware_promotions + artifact bundle` 后，才算进入硬件验证环，而不是仅停留在 scheduler 输出。
17. `hardware_promotions / hardware_runs` 表此前已经存在，但没有对应的 source artifact 与控制面入口；这条缺口现已补上第一段。
18. 对已实现 phase 做对抗性复盘后，确认 `manifest_only / request_only` 这类无实际注入运行如果被当作 `MATCHED/SDC_FOUND`，会直接污染 outer-loop 结论；现在这类运行会 fail closed 为 `no_injection / INVALID`。
19. 先前 `Phase 4` 的 semihost validation 在请求 fault 但没有实际 injector 证据时，存在“同一 workload 跑多次也能绿”的风险；现在这条路径已改为诚实地返回 `INVALID`。
20. `materialize.py` 与 `phase2_validation.py` 之前共享的 digest harness 只初始化了部分寄存器并在 capture 阶段自我污染；现在两条路径都已改成 defined-state harness。
21. `hardware_lane.py` 生成的 promotion source 之前是无条件 `EXIT_SUCCESS` 的占位物；现在会真实执行 promoted asm 并对比 golden digest。
22. 此前 `gem5/mcpat/microprobe/opendcdiag/qemu` 只是 root 外部的 nested repo；现在这些核心子项目源码已被正式导入 root monorepo 历史。
23. `qemu` 内部 submodule 保留不变，但现在作为 root monorepo 内部的 gitlink 路径存在。
24. `OpenDCDiagBackend` 已不再是 placeholder；控制面现已具备 staging build/run 主链。
25. `hardware result ingest` 与 `run-hw / ingest-hw` CLI 已接入，硬件 lane 现在能把运行结果回写到 `hardware_runs`。
26. 调度层现在已经把 `inner_value_score / diversity_bonus / legality_factor / power_gain` 作为独立反馈信号暴露出来，不再只剩单一 `fitness`。
27. Python 3 genetic driver 现在会做 profile-aware fallback instruction recovery、diversity-aware partner selection，并把这些决策写进 lineage metadata。
28. 仓库根目录现在可以直接运行 `pytest` 收集 `tests/` 下的控制面测试，不再依赖隐式解释器入口行为。
29. gem5 Python 层 `physProxy.read/write` 足以支撑第一版真实 `memory_bit_flip`，不必等待更深的 C++ memory injector hook。
30. hardware result ingest 现在不仅保存原始 payload，还会提炼 stage detector 状态和可查询的 detector summary。
31. Phase 7 的智能生成现在不再只停留在文档里；`generate_batch()`、scheduler mutation plan、以及 `tools/sdc_agent.py generate/cycle` 已能消费 template / pcfg / mutation advice。

---

## 3. Completed

### 3.1 文档体系

1. 仓库的正式文档现已收敛为：
   - [spec.md](/Users/wangxu/1-project/sdc-fuzzing/docs/spec.md)
   - [plan.md](/Users/wangxu/1-project/sdc-fuzzing/docs/plan.md)
   - [state.md](/Users/wangxu/1-project/sdc-fuzzing/docs/state.md)
2. `doc/` 已重命名为 `docs/`。
3. 状态类文档已合并，不再保留 root 级镜像。
4. 已新增 [monorepo.md](/Users/wangxu/1-project/sdc-fuzzing/docs/monorepo.md) 作为单仓治理规则文档。

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
10. `HW_AGGRESSIVE` 现在已会保留 `requested/effective = HW_AGGRESSIVE`，并使用独立的激进指令选择集合。

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
8. [validate_phase4_e2e.py](/Users/wangxu/1-project/sdc-fuzzing/tools/validate_phase4_e2e.py) 已提供真实多 fault campaign 端到端验证入口。
9. [differential.py](/Users/wangxu/1-project/sdc-fuzzing/sdc_agent/differential.py) 现在会读取 gem5 侧 `sdc_fault_request.json` 并解析脚本化注入观测日志。
10. [outer_loop.py](/Users/wangxu/1-project/sdc-fuzzing/sdc_agent/outer_loop.py) 现在会记录：
   - `fault_execution_plane`
   - `injector_confidence_score`
   - `promotion_readiness_score`
11. outer loop 聚合结果现在可区分“真实脚本注入已观测”与“只有 manifest 记录”的 fault run。
12. [scheduler.py](/Users/wangxu/1-project/sdc-fuzzing/sdc_agent/scheduler.py) 现在已经消费这些外循环聚合信号，并提供独立的 `promotion_plan()` / `promotion-plan` CLI。
13. [hardware_lane.py](/Users/wangxu/1-project/sdc-fuzzing/sdc_agent/hardware_lane.py) 已落地首版硬件 promotion lane orchestrator。
14. [sdc_promote_hw.py](/Users/wangxu/1-project/sdc-fuzzing/tools/sdc_promote_hw.py) 与 [sdc_agent.py](/Users/wangxu/1-project/sdc-fuzzing/tools/sdc_agent.py) `promote-hw` 已提供 CLI 入口。
15. hardware lane 现在会生成 promotion bundle：
   - `promotion.json`
   - 原始 `asm`
   - opendcdiag-shaped `cpp`
   - `meson.build.fragment`
16. Vault artifacts 投影现在已纳入 hardware lane 产物，便于统一查询。
17. `outer_loop` 现在会拒绝把无实际注入证据的运行当作有效 fault campaign 成功。
18. `outer_loop` campaign 现在按执行实例生成唯一 `campaign_key`，重试不会覆盖历史 campaign。
19. `phase4_validation` 现在只有在 fault request 真正带来注入证据时才会报 faulted success；请求 fault 但无 injector 的 semihost 路径会返回 `INVALID`。
20. `materialize.py` 与 `phase2_validation.py` 现在都使用 defined-state digest harness：
   - 初始化 `x0-x30`
   - 绑定到 `sdc_memory`
   - capture 时不再覆盖原始寄存器值
21. `hardware_lane.py` 生成的 promotion source 现在会执行 promoted asm 并对比 `qemu_golden_hash`。
22. gem5 现在已支持第二类脚本化 fault model：`vector_register_bit_flip`。
23. `differential.py` 现在能解析向量寄存器 bit flip 的注入观测日志。

### 3.5 Phase 3

1. [scheduler.py](/Users/wangxu/1-project/sdc-fuzzing/sdc_agent/scheduler.py) 现在已显式区分：
   - `static_score`
   - `inner_value_score`
   - `diversity_bonus`
   - `legality_factor`
   - `power_gain`
2. `mutation_plan()` 现在会把 profile、instruction family 与 inner-loop feedback breakdown 一起暴露给后续进化步骤。
3. [genetic.py](/Users/wangxu/1-project/sdc-fuzzing/microprobe/src/microprobe/driver/genetic.py) 现在会：
   - 按 profile 恢复 fallback instruction set
   - 基于 instruction family diversity 选择 partner
   - 过滤 offspring instruction set，避免 profile contract 漂移
   - 在 `lineage` / `evolution_feedback` 中记录多维反馈理由
4. [agent.py](/Users/wangxu/1-project/sdc-fuzzing/sdc_agent/agent.py) 与 [hardware_lane.py](/Users/wangxu/1-project/sdc-fuzzing/sdc_agent/hardware_lane.py) 现在已经消费这些新增的调度信号。

### 3.6 Phase 5

1. [sdc_fault_request.py](/Users/wangxu/1-project/sdc-fuzzing/gem5/configs/example/arm/sdc_fault_request.py) 现在已支持 `mem:0x...` 与 `cpuN:mem:0x...` fault target 约定。
2. [sdc_kunpeng920_se.py](/Users/wangxu/1-project/sdc-fuzzing/gem5/configs/example/arm/sdc_kunpeng920_se.py) 现在已支持 scripted `memory_bit_flip`，并会输出可解析的 memory injection 观测日志。
3. [differential.py](/Users/wangxu/1-project/sdc-fuzzing/sdc_agent/differential.py) 现在能解析 memory fault observation，并把它收敛到 `fault_request.observation`。

### 3.7 Phase 7

1. [generation_strategies.py](/Users/wangxu/1-project/sdc-fuzzing/sdc_agent/generation_strategies.py) 已新增首版智能生成策略层，支持：
   - `baseline`
   - `template`
   - `pcfg`
2. 已新增首版高价值模板库：
   - `cache_thrash`
   - `long_dependency_chain`
   - `neon_fma_heavy`
3. [generation.py](/Users/wangxu/1-project/sdc-fuzzing/sdc_agent/generation.py) 与 [agent.py](/Users/wangxu/1-project/sdc-fuzzing/sdc_agent/agent.py) 现在已经把 `generation_strategy` / `template_name` 接到主生成和 `cycle` 路径。
4. [mutation_advisor.py](/Users/wangxu/1-project/sdc-fuzzing/sdc_agent/mutation_advisor.py) 已提供可被未来 LLM 替换的 mutation-advice 接口；scheduler mutation plan 现在会附带 advice。

### 3.8 Monorepo Governance

1. `microprobe/`、`qemu/`、`gem5/`、`mcpat/`、`opendcdiag/` 的完整历史已通过 subtree 导入 root。
2. root 不再整目录忽略这些核心子项目。
3. 新增 monorepo managed domains：
   - `root-control-plane`
   - `microprobe`
   - `qemu`
   - `gem5`
   - `mcpat`
   - `opendcdiag`
4. `tools/sdc_agent.py status` 现在会输出 `managed_domains_summary`。
5. `tools/sdc_agent.py domains` 与 `tools/sdc_agent.py diff --domain <id>` 已提供单仓域视图。

### 3.9 Phase 6 Runtime

1. [opendcdiag_backend.py](/Users/wangxu/1-project/sdc-fuzzing/sdc_agent/power_backends/opendcdiag_backend.py) 现在已支持 staging workspace build/run。
2. [hardware_results.py](/Users/wangxu/1-project/sdc-fuzzing/sdc_agent/hardware_results.py) 现在已支持：
   - 执行已发出的 promotion
   - ingest `result.json`
   - 写回 `hardware_runs`
3. [sdc_ingest_hw_results.py](/Users/wangxu/1-project/sdc-fuzzing/tools/sdc_ingest_hw_results.py) 与 [sdc_agent.py](/Users/wangxu/1-project/sdc-fuzzing/tools/sdc_agent.py) 已提供：
   - `run-hw`
   - `ingest-hw`

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
13. `python3 tools/validate_phase4_e2e.py ...`
14. `python3 -m pytest tests/test_run_sdc_differential.py tests/test_sdc_outer_loop.py tests/test_sdc_phase4_validation.py tests/test_sdc_campaign.py tests/test_sdc_vault_v2.py -q`
15. `python3 -m pytest tests/test_run_sdc_differential.py tests/test_sdc_outer_loop.py tests/test_sdc_phase4_validation.py tests/test_sdc_campaign.py tests/test_sdc_vault_v2.py tests/test_sdc_scheduler.py tests/test_sdc_agent.py -q`
16. `python3 tools/sdc_scheduler.py promotion-plan --help`
17. `python3 -m pytest tests/test_sdc_hardware_lane.py tests/test_sdc_scheduler.py tests/test_sdc_agent.py tests/test_sdc_vault_v2.py -q`
18. `python3 tools/sdc_promote_hw.py --help`
19. `python3 tools/sdc_agent.py promote-hw --help`
20. `python3 -m pytest tests/test_run_sdc_differential.py tests/test_sdc_outer_loop.py tests/test_sdc_phase4_validation.py tests/test_sdc_campaign.py tests/test_sdc_vault_v2.py tests/test_sdc_scheduler.py tests/test_sdc_agent.py tests/test_sdc_hardware_lane.py -q`
21. `python3 -m pytest tests/test_sdc_phase2_validation.py tests/test_sdc_phase4_validation.py tests/test_sdc_materialize.py -q`
22. `python3 -m pytest tests -q`
23. `python3 tools/sdc_agent.py domains`
24. `python3 tools/sdc_agent.py diff --domain microprobe`
25. `python3 tools/sdc_ingest_hw_results.py --help`
26. `python3 tools/sdc_agent.py run-hw --help`
27. `python3 tools/sdc_agent.py ingest-hw --help`
28. `/Users/wangxu/anaconda3/bin/python -m pytest -q tests/test_sdc_scheduler.py tests/test_sdc_genetic_driver.py tests/test_sdc_agent.py tests/test_sdc_inner_loop.py tests/test_sdc_outer_loop.py tests/test_sdc_hardware_lane.py tests/test_sdc_phase4_validation.py tests/test_sdc_phase2_validation.py`
29. `/Users/wangxu/anaconda3/bin/pytest -q tests`
30. `/Users/wangxu/anaconda3/bin/pytest -q microprobe/targets/arm64/tests/tools/test_mp_sdc_offline_gen.py microprobe/targets/arm64/tests/targets/test_target_contract.py`
31. `/Users/wangxu/anaconda3/bin/python -m pytest -q tests/test_sdc_generation_profiles.py tests/test_sdc_vault_v2.py tests/test_hardware_results.py tests/test_power_backends.py`
32. `/Users/wangxu/anaconda3/bin/python -m pytest -q tests/test_run_sdc_differential.py gem5/tests/test_sdc_fault_request.py`
33. `/Users/wangxu/anaconda3/bin/python -m pytest -q tests/test_hardware_results.py tests/test_power_backends.py`
34. `/Users/wangxu/anaconda3/bin/python -m pytest -q tests/test_sdc_generation_strategies.py tests/test_sdc_generation_profiles.py tests/test_sdc_scheduler.py tests/test_sdc_agent.py tests/test_sdc_genetic_driver.py`
35. `/Users/wangxu/anaconda3/bin/pytest -q tests`
36. `/Users/wangxu/anaconda3/bin/pytest -q microprobe/targets/arm64/tests/tools/test_mp_sdc_offline_gen.py microprobe/targets/arm64/tests/targets/test_target_contract.py gem5/tests/test_sdc_fault_request.py`

当前结果：

1. 主仓测试：`65 passed`
2. `microprobe` 定向测试：`8 passed`
3. 新 CLI 正常暴露参数
4. 现有 `status` 汇总仍可用
5. `HW_AGGRESSIVE` 请求会被正确记录为“requested=HW_AGGRESSIVE, effective=HW_AGGRESSIVE”
6. baseline Phase 2 真实端到端验证已通过：
   - qemu golden digest = `2b85c03077dc5edd`
   - gem5 digest = `2b85c03077dc5edd`
   - mcpat power_total = `43738.51286976`
7. Phase 4 定向测试已通过：
   - `11 passed`
8. `sdc_outer_loop.py --help` 已 smoke 通过
9. outer loop campaign 查询与 aggregate 返回值测试已通过
10. `Phase 4` semihost validation 现在会对“请求 fault 但无 injector 证据”的情况诚实返回 `INVALID`，不再把这类运行记为 `MATCHED`。
11. 新增 fault execution plane 定向回归已通过：
   - `tests/test_run_sdc_differential.py`
   - `tests/test_sdc_outer_loop.py`
12. 相邻回归仍通过：
   - `tests/test_sdc_phase4_validation.py`
   - `tests/test_sdc_campaign.py`
   - `tests/test_sdc_vault_v2.py`
13. 调度层与 agent 汇总现在也已接通 promotion 信号：
   - `tests/test_sdc_scheduler.py`
   - `tests/test_sdc_agent.py`
14. 硬件 promotion lane bootstrap 已通过：
   - `tests/test_sdc_hardware_lane.py`
15. `Phase 2` semihost harness defined-state 回归已通过：
   - `tests/test_sdc_phase2_validation.py`
16. 当前相关回归总计：`49 passed`
17. monorepo domain 管理回归已补齐：
   - `tests/test_managed_domains.py`
18. `Phase 6 build/run + ingest` 回归已通过：
   - `tests/test_power_backends.py`
   - `tests/test_hardware_results.py`
19. 当前相关回归总计：`53 passed`
20. `Phase 5 vector fault model` 控制面回归已通过：
   - `tests/test_run_sdc_differential.py`
21. `Phase 3 feedback-loop` 与 direct `pytest` 回归已通过：
   - `tests/test_sdc_scheduler.py`
   - `tests/test_sdc_genetic_driver.py`
   - `tests/test_sdc_agent.py`
   - `tests/conftest.py` 引导下的 root `pytest`
22. 当前相关回归总计：`54 passed`
23. `HW_AGGRESSIVE` profile 回归已通过：
   - `tests/test_sdc_generation_profiles.py`
24. `Phase 5 memory fault model` 控制面与 gem5 helper 回归已通过：
   - `tests/test_run_sdc_differential.py`
   - `gem5/tests/test_sdc_fault_request.py`
25. `Phase 6 richer ingest` 回归已通过：
   - `tests/test_hardware_results.py`
   - `tests/test_power_backends.py`
26. `Phase 7 template/pcfg/mutation-advice` 回归已通过：
   - `tests/test_sdc_generation_strategies.py`
   - `tests/test_sdc_scheduler.py`
   - `tests/test_sdc_agent.py`

---

## 5. Open Risks

当前最主要的未完成项和风险如下：

1. inner loop 已具备基础缓存和 artifact index，但更细粒度的 artifact/index 体系仍可继续增强。
3. outer loop 已能识别脚本化 fault execution plane，但更大范围的 injector 联动仍未完成。
4. gem5 real fault injector 目前已支持 `register_bit_flip`、`vector_register_bit_flip` 与 `memory_bit_flip` 三类脚本化路径；更多 fault model 仍未实现。
5. `opendcdiag-arm` promotion 已接入控制面的 build/run + ingest 版，但仍缺真实硬件环境下的稳定性验证。
6. 当前 opendcdiag runtime 仍依赖 staging workspace build，而不是目标机器上的长期部署流程。
7. `qemu` 内部 submodule 仍保留，不属于本轮单仓扁平化范围。
8. 当前 mutation advisor 还是 heuristic/rule-based，真正的外部 LLM-backed mutation advisor 仍需独立接入和环境配置。

---

## 6. Next Actions

推荐的后续顺序仍然是：

1. 继续推进 `Phase 4`
   - outer loop 与真实 injector 的更深衔接
   - 已将新的 injector confidence / promotion readiness 接入排序与 promotion 逻辑
2. 推进 `Phase 5: gem5 真实 fault injector`
   - 扩展 fault model，超出当前 `register/vector/memory bit flip`
3. 推进 `Phase 6: opendcdiag-arm promotion 与真机回灌`
   - 将 staging build/run 升级为真实机器部署流程
   - 将已增强的 detector 解析与机器元数据回灌带到真实机器闭环
4. 持续推进 `Monorepo Governance`
   - 用 domain 级视图承接后续所有跨子项目开发和审阅
5. 推进 `Phase 7`
   - 在当前 template/pcfg/mutation-advice 基础上接入真正的外部 LLM advisor

---

## 7. Canonical Pointers

1. 完成态架构见 [spec.md](/Users/wangxu/1-project/sdc-fuzzing/docs/spec.md)
2. 分阶段计划见 [plan.md](/Users/wangxu/1-project/sdc-fuzzing/docs/plan.md)
3. 当前状态见 [state.md](/Users/wangxu/1-project/sdc-fuzzing/docs/state.md)
