# Findings

## Summary

本阶段新增的关键发现与结论：

1. `offline_testcases` 可以继续作为 summary 层保留，而不必在 Phase 1 直接废弃。
2. 只要在 `upsert_testcase()` 和 `update_execution_result()` 中做自动投影，同步成本就能保持很低。
3. `fault_request / execution / mcpat` 这三类元数据必须尽早进入结果合同，否则 v2 历史表会长期失真。
4. metadata-only 更新必须避免重复写历史，否则 campaign 后处理会制造伪运行记录。
5. 现在已经具备继续推进 `Phase 2: 高频内循环产品化` 的数据库基础。

## Pointers

- 当前阶段实现见 [sdc_agent/vault.py](/Users/wangxu/1-project/sdc-fuzzing/sdc_agent/vault.py)
- 当前阶段进度见 [progress.md](/Users/wangxu/1-project/sdc-fuzzing/progress.md)
