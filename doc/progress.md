# SDC-Agent Progress

## 2026-04-02 Snapshot

### 已完成

- 重写 README，使其与当前代码结构一致。
- 更新 `doc/plan.md` 为真实阶段路线图。
- 新增 `doc/spec.md`、`doc/findings.md`、`doc/progress.md`。
- 新增共享生成模块 `sdc_agent/generation.py`。
- 重构 `mp_sdc_offline_gen.py` 复用共享生成逻辑。
- 在 `microprobe.driver.genetic` 中新增 Python 3 `SDCFuzzingGeneticDriver`。
- 新增顶层编排入口 `tools/sdc_agent.py`。
- 新增测试：
  - `tests/test_sdc_agent.py`
  - `tests/test_sdc_genetic_driver.py`

### 已验证

- `python3 -m py_compile ...` 通过
- 定向 pytest:
  - `tests/test_sdc_genetic_driver.py`
  - `tests/test_sdc_agent.py`
  - `tests/test_sdc_scheduler.py`
  - `tests/test_sdc_campaign.py`
  - `tests/test_offline_to_campaign_integration.py`
  - `microprobe/targets/arm64/tests/tools/test_mp_sdc_offline_gen.py`
  - `microprobe/targets/arm64/tests/targets/test_target_contract.py`

### 阻塞与边界

- 仓库全量 `pytest -q` 会进入第三方 `gem5/ext/pybind11/tests`，不适合作为本项目回归基线。
- `microprobe/targets/arm64/tests/tools/test_a64_isa_audit.py` 依赖额外模块路径，不属于本次改动引入的问题。
- gem5 真实 fault injection 仍是后续重点任务。
