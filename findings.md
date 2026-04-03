# Findings

## Summary

进入 `Phase 2` 之后，本轮新增的关键结论如下：

1. 现有 `generation / materialize / differential / genetic` 已足够拼出首版正式 inner loop，不需要重写执行器。
2. inner loop 的 summary 状态推进应明确为 `GOLDEN_READY / POWER_READY / INNER_READY`。
3. `fault_model=none` 的结果必须从 fault history 投影里排除，否则会污染外循环数据。
4. 正式文档与 root 工作记忆必须同时更新，才能避免后续 Phase 4/5/6 执行时丢上下文。

## Pointers

- 项目级发现见 [doc/findings.md](/Users/wangxu/1-project/sdc-fuzzing/doc/findings.md)
- 当前阶段代码见 [sdc_agent/inner_loop.py](/Users/wangxu/1-project/sdc-fuzzing/sdc_agent/inner_loop.py)
- 当前任务执行状态见 [task_plan.md](/Users/wangxu/1-project/sdc-fuzzing/task_plan.md)
