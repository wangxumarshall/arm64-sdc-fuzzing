# SDC-Agent Task Plan

## Goal

按照项目正式计划推进当前阶段：

- `Phase 2: 高频内循环产品化`

并确保：

1. 项目级正式文档仍以 `doc/spec.md`、`doc/plan.md`、`doc/findings.md`、`doc/progress.md` 为权威来源。
2. root 级 `task_plan.md`、`findings.md`、`progress.md` 始终作为当前任务镜像，与 `doc/` 文档保持引用关系。
3. 当前实现不丢失 Phase 1 已完成内容，并能继续向 Phase 4/5/6 递进。

## Current Status

| Phase | Status | Notes |
| --- | --- | --- |
| Phase 1: Phase-2 scope audit | completed | 已审阅 `differential.py`、`power_analysis.py`、`scheduler.py`、`generation.py` 与现有 planning files |
| Phase 2: Tracking contract sync | completed | 已补强项目级正式文档与 root 工作记忆的引用链 |
| Phase 3: Inner-loop implementation | completed | 已实现 `sdc_agent/inner_loop.py` 与 `tools/sdc_inner_loop.py` |
| Phase 4: Validation | completed | `python3 -m pytest tests/test_sdc_inner_loop.py tests/test_sdc_scheduler.py -q` 与 `python3 -m pytest tests -q` 通过 |

## Key Decisions

1. `Phase 2` 以“首版正式 inner loop orchestrator”为目标，不把 Phase 3/4 一次性混进来。
2. 继续复用现有执行器：
   - generation
   - materialize
   - differential
   - genetic
3. inner loop 通过 summary 状态推进：
   - `GOLDEN_READY`
   - `POWER_READY`
   - `INNER_READY`
4. `fault_model=none` 的 inner loop 运行不得污染 `fault_runs`。
5. evolution 继续作为 inner loop 的可选尾段，而不是另起一套 orchestration。

## Pointers

- 项目级方案见 [doc/spec.md](/Users/wangxu/1-project/sdc-fuzzing/doc/spec.md)
- 项目级计划见 [doc/plan.md](/Users/wangxu/1-project/sdc-fuzzing/doc/plan.md)
- 项目级进展见 [doc/progress.md](/Users/wangxu/1-project/sdc-fuzzing/doc/progress.md)
- 当前阶段实现见 [sdc_agent/inner_loop.py](/Users/wangxu/1-project/sdc-fuzzing/sdc_agent/inner_loop.py)

## Remaining Risks

- inner loop 仍缺 profile-aware generation。
- 批处理缓存和更细粒度 artifact 索引仍可继续增强。
- outer loop / fault matrix / real injector 仍是后续关键路径。
