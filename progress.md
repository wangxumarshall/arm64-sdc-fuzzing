# Progress

## Session 2026-04-02

- 阅读 `README.md`、`doc/plan.md`、仓库根目录结构和 SDC 相关源码。
- 确认当前主流程已经覆盖：
  - ARM64 指令生成
  - 静态评分
  - SQLite Vault
  - C wrapper / materialize
  - QEMU vs gem5 差分执行
  - McPAT 后处理
  - Scheduler / Campaign 回写
- 确认当前最主要缺口是：
  - README 后半段与实现失配
  - `doc/plan.md` 过旧
  - 缺少正式 spec/findings/progress 文档
  - 缺少 Python 3 可用的反馈进化驱动

- 新增 `sdc_agent/generation.py` 作为共享生成层。
- 重构 `microprobe/targets/generic/tools/mp_sdc_offline_gen.py` 复用共享生成逻辑。
- 在 `microprobe/src/microprobe/driver/genetic.py` 中新增 `SDCFuzzingGeneticDriver`。
- 新增 `tools/sdc_agent.py` 顶层控制入口。
- 重写 `README.md`。
- 新增：
  - `doc/spec.md`
  - `doc/findings.md`
  - `doc/progress.md`
- 更新 `doc/plan.md`。
- 新增测试：
  - `tests/test_sdc_agent.py`
  - `tests/test_sdc_genetic_driver.py`
- 验证结果：
  - `python3 -m py_compile ...` 通过
  - 定向 pytest 20 项通过
  - `pytest -q` 因第三方 `gem5/ext/pybind11/tests` 缺外部构建产物失败

## Session 2026-04-02 Repository Cleanup

- 将核心 Python 实现迁移到 `sdc_agent/` 包：
  - `agent.py`
  - `campaign.py`
  - `differential.py`
  - `generation.py`
  - `materialize.py`
  - `power_analysis.py`
  - `preflight.py`
  - `scheduler.py`
  - `vault.py`
  - `power_backends/`
- 新增 `tools/` 目录承载 CLI wrapper。
- 新增 `scripts/` 目录承载构建和环境脚本。
- 新增 `dev/debug/` 和 `dev/samples/` 收纳调试脚本与样例资产。
- 将 `config-temp/`、`m5out/`、`out.area`、`out.ptrace`、`test_cases/` 收纳到 `artifacts/runtime/`。
- 将 `GEM5_BUILD_GUIDE.md` 移动到 `doc/guides/gem5_build_guide.md`。
- 更新 README、plan/spec/findings/progress、CLAUDE、脚本提示和测试引用到新路径。
- 验证结果：
  - `python3 -m py_compile ...` 通过
  - `python3 tools/sdc_agent.py status --db /tmp/sdc-agent-arch.sqlite3` 通过
  - `python3 tools/sdc_preflight.py --help` 通过
  - `python3 microprobe/targets/generic/tools/mp_sdc_offline_gen.py --help` 通过
  - 定向 pytest 32 项通过

## Next

- 继续推进 gem5 真实 fault injector，实现对 `sdc_fault_request.json` 的消费。
- 视需要增强进化层的 crossover / mutation / multi-objective fitness。
