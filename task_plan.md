# SDC-Agent Task Plan

## Goal

基于重构后的源码结构，重新定义能够对齐 README 愿景的整体架构，并将其落实到以下文档：

- `doc/spec.md`
- `doc/plan.md`
- `doc/findings.md`
- `doc/progress.md`

同时同步：

- `README.md`
- `doc/CLAUDE.md`
- root 级 `findings.md`
- root 级 `progress.md`

最后完成验证并提交一次 git commit。

## Current Status

| Phase | Status | Notes |
| --- | --- | --- |
| Phase 1: Source audit | completed | 已审阅 `sdc_agent/`、`microprobe`、`gem5`、`mcpat`、`opendcdiag` 与关键测试 |
| Phase 2: Architecture redesign | completed | 已定义整体架构、高频内循环、低频外循环、硬件验证环、数据流 |
| Phase 3: Spec/Plan rewrite | completed | 已重写 `doc/spec.md` 与 `doc/plan.md` |
| Phase 4: Findings/Progress rewrite | completed | 已重写 `doc/findings.md`、`doc/progress.md`、root planning files |
| Phase 5: Consistency sync | completed | 已同步 `README.md` 与 `doc/CLAUDE.md` 的关键架构口径 |
| Phase 6: Verification and commit | completed | 已完成一致性检查；`python3 -m pytest tests -q` 通过（24 passed），本次变更已准备提交 |

## Key Decisions

1. 保留 `sdc_agent/` 作为核心控制平面，不推倒重写。
2. 明确采用三层闭环：
   - high-frequency inner loop
   - low-frequency outer loop
   - hardware validation lane
3. 显式引入双生成 profile：
   - `SIM_SAFE`
   - `HW_AGGRESSIVE`
4. 将 `opendcdiag-arm` 定位为最终硬件验证层，而不是高频仿真执行层。
5. 将数据库从当前单表模型规划为兼容式多表模型。

## Remaining Risks

- 当前源码的真实 gem5 fault injector 仍未实现。
- 当前 Vault 单表模型仍是未来实现的主要约束点。
- `doc/CLAUDE.md` 仍保留部分旧阶段表述，但已经修正了最关键的架构冲突。
