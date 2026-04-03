# Findings

## Summary

本轮继续推进 `Phase 2` 后，新增的关键结论如下：

1. `STATIC_DONE` 应当作为内循环里“已生成、已静态分析、待执行”的明确状态保留下来。
2. `run_differential()` 只要支持 `skip_compile / skip_qemu / cached_golden_digest`，就足以承载 Phase 2 所需的 ELF 与 golden cache 复用。
3. source / ELF / golden 三层 cache 已经能显著减少重复执行时的开销。
4. `fault_model=none` 的过滤必须继续保留，否则 cache 驱动的 inner loop 会反复污染外循环历史。

## Pointers

- 项目级发现见 [doc/findings.md](/Users/wangxu/1-project/sdc-fuzzing/doc/findings.md)
- 当前阶段实现见 [sdc_agent/inner_loop.py](/Users/wangxu/1-project/sdc-fuzzing/sdc_agent/inner_loop.py)
- 当前任务状态见 [task_plan.md](/Users/wangxu/1-project/sdc-fuzzing/task_plan.md)
