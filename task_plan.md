# SDC-Agent Task Plan

## Goal

统一 `README.md`、`doc/plan.md` 与当前代码实现，产出完整的 SDC-Agent 方案文档（spec/plan/findings/progress），并补齐当前代码中最关键的闭环缺口，使项目形成从离线生成到在线差分验证再到反馈进化的可执行骨架。

## Current Status

| Phase | Status | Notes |
| --- | --- | --- |
| Phase 1: Readme/code audit | complete | 已完成 README、代码、测试与 gem5/McPAT 集成现状核对 |
| Phase 2: Planning files & project spec | complete | 已产出 root planning files 和 `doc/spec.md` |
| Phase 3: README restructuring | complete | 已移除虚构 Agent/RL/目录叙事，改成真实流水线架构 |
| Phase 4: `doc/plan.md` rewrite | complete | 已基于真实实现更新阶段划分与验证命令 |
| Phase 5: SDC-Agent implementation | complete | 已补齐共享生成层、Python 3 进化驱动和 `tools/sdc_agent.py` |
| Phase 6: Verification & progress sync | complete | 已完成定向测试并回填进度 |
| Phase 7: Repository architecture cleanup | complete | 已把非第三方目录重构为 package / tools / scripts / dev / artifacts 分层 |

## Implementation Strategy

1. 先完成文档与代码的现状映射，避免 README 把不存在的模块写成已实现能力。
2. 用项目 spec/plan 明确“当前已实现能力”“待实现闭环能力”“外部依赖能力边界”。
3. 在代码层优先补齐 Phase 5 缺失的 GA/feedback driver 与 Vault/Campaign 的衔接，而不是扩散到不存在的 RL/Agent 框架。
4. 用测试覆盖离线生成 → Vault → 物料化 → 差分执行/记录 → 进化建议 的闭环骨架。

## Known Gaps

- README 后半段包含大量未实现或与仓库结构不符的内容：
  - 已通过重写 README 解决
- gem5 故障注入目前仅实现 fault request manifest 记录，尚无真正的注入执行逻辑
- 仓库第三方测试目录不能直接作为项目回归基线

## Errors Encountered

| Error | Attempt | Resolution |
| --- | --- | --- |
| `README.md` 与代码结构明显失配 | 1 | 记录差异，准备先重写叙事再补代码 |
| `pytest -q` 进入 `gem5/ext/pybind11/tests` 失败 | 1 | 改为只跑项目自有测试与相关 Microprobe ARM64 测试 |
| `test_a64_isa_audit.py` 缺少额外模块路径 | 1 | 识别为现有测试环境问题，不属于本次改动回归 |
