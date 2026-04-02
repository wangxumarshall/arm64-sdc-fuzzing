# SDC-Agent Task Plan

## Goal

基于重构后的源码结构，重新定义能够 100% 落地 README 愿景的总方案，并将其写入：

- `doc/spec.md`
- `doc/plan.md`
- `doc/findings.md`
- `doc/progress.md`

同时同步 root 级 `findings.md` / `progress.md`。

## Current Status

| Phase | Status | Notes |
| --- | --- | --- |
| Phase 1: Source audit | completed | 已重新审阅 `sdc_agent/`、`microprobe` pass/policy、gem5 fault manifest、OpenDCDiag 资产 |
| Phase 2: Architecture redesign | completed | 已定义高频内循环、低频外循环、硬件验证环三层架构 |
| Phase 3: Spec/Plan rewrite | completed | 已重写 `doc/spec.md` 与 `doc/plan.md` |
| Phase 4: Findings/Progress rewrite | completed | 已重写 `doc/findings.md` 与 `doc/progress.md` |
| Phase 5: Consistency sync | completed | README 与 root planning files 已同步到新方案口径 |

## Key Decisions

1. 保留 `sdc_agent/` 作为核心控制平面。
2. 采用三层闭环：
   - high-frequency inner loop
   - low-frequency outer loop
   - hardware validation lane
3. 采用双生成 profile：
   - `SIM_SAFE`
   - `HW_AGGRESSIVE`
4. 将 OpenDCDiag 定位为最终硬件验证层，而非仿真执行层。
5. 将数据库从当前单表模型规划为兼容式多表模型。

## Remaining Risks

- README 仍偏高层，需要与新 spec/plan 做轻量同步。
- 当前源码的真实 fault injector 仍未实现。
- 当前 Vault 单表模型仍是未来实现的主要约束点。
