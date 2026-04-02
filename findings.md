# Findings

## 2026-04-02

### 文档与实现对齐结论

- `README.md` 第 1、2 章核心方向是对的：A/B 异步架构、离线静态筛选、在线差分验证，这与代码主流程一致。
- 从第 3 章开始，README 大量使用“Generator Agent / Validator Agent / Power Agent / Feedback Agent / RL Agent / Skills”叙事，但代码实现主要是函数/CLI/模块级流水线，不是 multi-agent 系统。
- README 描述了很多未落地结构：
  - `sdc_discovery/`
  - `generation_layer.py`
  - `rl_agent.py`
  - `trigger_engine.py`
  - `candidate_pool.py`
- README 同时把 OpenDCDiag 写成执行层核心依赖，但当前差分与功耗主路径已经绕开 OpenDCDiag，转向 `BareMetalDiffWrapper` + `qemu` + `gem5` + `McPAT`。

### 当前代码真实能力

- 离线生成：
  - `microprobe/targets/arm64/policies/sdc_fuzzing_policy.py`
  - `microprobe/src/microprobe/passes/sdc_analysis/offline_coverage.py`
  - `microprobe/targets/generic/tools/mp_sdc_offline_gen.py`
- 中间存储：
  - `sdc_agent/vault.py`
- 物料化与 wrapper：
  - `microprobe/targets/arm64/wrappers/baremetaldiff.py`
  - `sdc_agent/materialize.py`
- 在线差分与调度：
  - `sdc_agent/differential.py`
  - `sdc_agent/scheduler.py`
  - `sdc_agent/campaign.py`
- 功耗与环境检查：
  - `sdc_agent/power_backends/mcpat_backend.py`
  - `sdc_agent/power_analysis.py`
  - `sdc_agent/preflight.py`

### 当前代码缺口

- 真正的故障注入尚未落地：
  - `gem5/configs/example/arm/sdc_fault_request.py` 只写 manifest
  - `sdc_kunpeng920_se.py` 只记录请求，不执行 fault injection
- 真实 gem5 fault injector 仍未实现：
  - 控制面已经有 `fault_model / fault_target / fault_bit / fault_tick`
  - 但 gem5 核心侧暂未消费 manifest
- `mp_sdc_offline_gen.py` 提到了 `InstructionPool`，但仓库中没有 `sdc_fuzzing_generator.py`，该分支目前永远走 fallback

### 设计建议

- README 前两章应把“Agent System”表述收束为“分阶段流水线 + 反馈闭环”，避免误导为已实现的智能代理系统。
- 后续章节应分成：
  - 已实现的核心流水线
  - 计划实现的闭环演化层
  - 外部依赖与能力边界
- Phase 5 最合理的实现方向不是 RL，而是：
  - 新增 Python 3 可用的 `SDCFuzzingGeneticDriver`
  - 读取 Vault top-k 种子
  - 基于 metadata/mutation plan 生成 offspring
  - 重新写回 Vault 形成闭环

### 已完成收敛

- 已新增 `sdc_agent/generation.py`，统一离线生成和进化生成逻辑。
- 已为 `microprobe.driver.genetic` 增加 Python 3 版本 `SDCFuzzingGeneticDriver`。
- 已新增 `tools/sdc_agent.py` 顶层入口。
- 已重写 README 和 `doc/` 下的 spec/plan/findings/progress。

### 仓库结构整理结论

- 非第三方代码已经从“根目录脚本堆叠”收敛为：
  - `sdc_agent/`：核心实现包
  - `tools/`：CLI wrapper
  - `scripts/`：运维/构建脚本
  - `dev/`：调试脚本与样例
  - `artifacts/runtime/`：运行产物
- 这种分层减少了根目录噪声，同时保留了所有原主流程能力。
