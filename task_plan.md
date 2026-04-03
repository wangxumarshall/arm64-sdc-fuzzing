# SDC-Agent Task Plan

## Goal

按 [doc/plan.md](/Users/wangxu/1-project/sdc-fuzzing/doc/plan.md) 优先完成 `Phase 2: 高频内循环产品化`，并进行充分验证。

同时保持：

1. `doc/spec.md`、`doc/plan.md`、`doc/findings.md`、`doc/progress.md` 作为项目级权威来源。
2. root 级 `task_plan.md`、`findings.md`、`progress.md` 作为当前任务镜像。
3. 两层文档在 Phase 状态变化时同步更新。

## Current Status

| Phase | Status | Notes |
| --- | --- | --- |
| Phase 1: Plan re-check | completed | 已重新核对 `doc/plan.md` 的 Phase 2 目标、交付物、阻塞与验收标准 |
| Phase 2: Inner-loop cache completion | completed | 已补上 `STATIC_DONE` 状态流，以及 source / ELF / golden digest cache |
| Phase 3: Verification | completed | 定向测试、全量测试、CLI smoke、status smoke 均通过 |

## Key Decisions

1. `Phase 2` 继续以 inner loop 为边界，不提前混入 outer loop/fault matrix。
2. 通过扩展 `run_differential()` 支持：
   - `skip_compile`
   - `skip_qemu`
   - `cached_golden_digest`
   实现 artifact cache 复用。
3. 新生成但尚未进入执行阶段的样本，在 inner loop 路径上显式标记为 `STATIC_DONE`。
4. 继续保持 `fault_model=none` 的 inner loop 结果不写入 `fault_runs`。

## Validation

已完成：

1. `python3 -m py_compile sdc_agent/generation.py sdc_agent/differential.py sdc_agent/inner_loop.py sdc_agent/agent.py`
2. `python3 -m pytest tests/test_sdc_inner_loop.py tests/test_sdc_agent.py tests/test_run_sdc_differential.py -q`
3. `python3 -m pytest tests -q`
4. `python3 tools/sdc_inner_loop.py --help`
5. `python3 tools/sdc_agent.py status --db artifacts/sdc_vault.sqlite3 --limit 1`

结果：

- `10 passed`
- `32 passed`

## Remaining Risks

- `HW_AGGRESSIVE` profile 尚未落地。
- cache 已具备基础复用，但更强的 artifact/index 体系仍可继续增强。
- 外循环、fault matrix、real injector 仍是下一关键路径。
