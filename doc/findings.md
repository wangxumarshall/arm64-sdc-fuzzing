# SDC-Agent Findings

## 1. README 与代码的主要偏差

原 README 第 3 章以后把系统描述成一组独立 Agent、Skills 和 RL 模块，但仓库中的真实实现是：

- 模块化脚本与库
- SQLite 中心状态
- Microprobe / QEMU / gem5 / McPAT 组合流水线

因此，本次文档收敛的核心原则是：

1. 前两章继续保留 A/B 异步架构。
2. 后续章节只保留仓库真实存在的模块与明确的未来计划。

## 2. 真实已实现能力

- ARM64 目标与 wrapper
- 静态风险分析 Pass
- Offline CLI
- Vault
- materialize / differential runner / campaign
- McPAT backend
- FeedbackScheduler
- Python 3 进化驱动
- 顶层 `tools/sdc_agent.py`

## 3. 真实未完成能力

- gem5 真实 fault injector
- 大规模分布式 campaign
- RL/LLM 驱动的策略优化

## 4. 关键结论

当前项目已经具备一条完整的“控制平面级” SDC 闭环，但离“物理上真实 fault injected gem5”还有最后一段核心实现距离。
