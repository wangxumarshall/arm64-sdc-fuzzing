# SDC-Agent Task Plan

## Goal

按照重构后的项目计划，落地当前阶段：

- `Phase 1: Vault v2 与数据契约升级`

要求：

1. 在不破坏现有 `offline_testcases` 兼容接口的前提下，引入 v2 多表模型。
2. 为 inner loop / outer loop / hardware lane 提供基础 DAO 和历史存储面。
3. 补充迁移与兼容测试，确保现有控制平面可继续运行。

## Current Status

| Phase | Status | Notes |
| --- | --- | --- |
| Phase 1: Vault call-site audit | completed | 已梳理 `sdc_agent/`、`tests/`、`microprobe.driver.genetic` 对 `SDCVault` 的调用面 |
| Phase 2: Vault v2 implementation | completed | 已实现兼容式多表 schema、summary 同步、自动回填和基础 DAO |
| Phase 3: Validation | completed | `python3 -m pytest tests/test_sdc_vault_v2.py -q` 通过；`python3 -m pytest tests -q` 通过 |

## Key Decisions

1. 保留 `offline_testcases` 作为现有控制平面的 summary/兼容层。
2. 新增 `testcases / static_metrics / artifacts / inner_runs / power_annotations / fault_campaigns / fault_runs / hardware_promotions / hardware_runs / lineage_events`。
3. `upsert_testcase()` 与 `update_execution_result()` 自动同步 v2 投影，避免调用方一次性大改。
4. metadata-only 更新只刷新投影和 artifacts，不重复写入 inner/power/fault 历史。
5. 在 `differential.py` 和 `scheduler.py` 中补充 `fault_request / execution / mcpat` 元数据，支撑 v2 历史表。

## Remaining Risks

- 当前 `fault_runs` 仍只能记录控制面的 fault request，真实 gem5 injector 仍未落地。
- `inner_runs`/`fault_runs` 当前仍是 summary-sync 风格，下一阶段需要演进为正式 orchestrator 写入。
- `hardware_promotions` 和 `hardware_runs` DAO 已具备，但尚未接入实际 promotion 流程。
