# Progress

## Snapshot

当前任务继续围绕 `Phase 2` 推进，并已把内循环从“首版能跑”推进到“带基础缓存的可复用版本”：

1. `STATIC_DONE` 已进入正式状态流。
2. source cache 已复用已有 `source_path`。
3. ELF cache 已通过 `skip_compile` 接入。
4. golden digest cache 已通过 `skip_qemu + cached_golden_digest` 接入。
5. `tools/sdc_inner_loop.py` 与 `tools/sdc_agent.py status` 均已 smoke 通过。

## Validation

已完成验证：

1. `python3 -m py_compile sdc_agent/generation.py sdc_agent/differential.py sdc_agent/inner_loop.py sdc_agent/agent.py`
2. `python3 -m pytest tests/test_sdc_inner_loop.py tests/test_sdc_agent.py tests/test_run_sdc_differential.py -q`
3. `python3 -m pytest tests -q`
4. `python3 tools/sdc_inner_loop.py --help`
5. `python3 tools/sdc_agent.py status --db artifacts/sdc_vault.sqlite3 --limit 1`

结果：

- `10 passed`
- `32 passed`

## Pointers

- 项目级进展见 [doc/progress.md](/Users/wangxu/1-project/sdc-fuzzing/doc/progress.md)
- 当前阶段实现见 [sdc_agent/inner_loop.py](/Users/wangxu/1-project/sdc-fuzzing/sdc_agent/inner_loop.py)
- 当前任务计划见 [task_plan.md](/Users/wangxu/1-project/sdc-fuzzing/task_plan.md)
