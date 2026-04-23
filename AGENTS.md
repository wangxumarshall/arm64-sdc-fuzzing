# AGENTS.md

本文件定义 `/data/slim/arm64-sdc-fuzzing` 的仓库级协作约束。进入本仓后，先确认项目主链、指令优先级和 managed domain 边界，再修改代码。

## Project Overview (YOU MUST READ FIRST)

本仓库是 `SDC-Agent` 的 monorepo。主链是 `tools/sdc_agent.py -> sdc_agent/agent.py -> sdc_agent/vault.py`，其上编排 `microprobe` 生成与进化、`materialize`、`qemu` / `gem5` 差分、`mcpat` 功耗标注和 `opendcdiag` 硬件验证。

### 三条执行环

1. 高频内循环：生成、静态分析、物料化、readiness 回写
2. 低频外循环：fault campaign、差分判定、价值聚合
3. 硬件验证环：promotion、OpenDCDiag 执行、结果回灌

### 推荐先读

- [README.md](README.md)：目标与总体架构
- [plan.md](plan.md)：长期架构合同与路线图
- [code-structure.md](docs/code-structure.md)：代码骨架与模块职责
- [monorepo.md](docs/monorepo.md)：managed domain 边界
- [progress.md](progress.md)：当前实现状态、风险与最近验证

## Instruction Hierarchy

冲突解释顺序如下：

1. 系统与平台约束
2. 开发者指令
3. 用户在当前对话中的明确要求
4. 本文件 `AGENTS.md`
5. 根级主文档：`plan.md`、`progress.md`
6. `docs/` 下的结构与专题文档
7. 作用域更小的局部说明文件
8. 代码、测试和实际运行行为

规则：

1. 用户要求与更高优先级冲突时，服从更高优先级。
2. 文档与代码、测试不一致时，以代码、测试和实际行为为准，并同步修正文档。
3. 跨 domain 修改前，先按 `docs/monorepo.md` 明确归属。
4. 当前只有根级 `AGENTS.md`；若后续新增子目录 `AGENTS.md`，仅覆盖对应子树。

## Repository Structure

### 顶层目录索引

| 路径 | Managed Domain | 角色 |
| --- | --- | --- |
| `sdc_agent/` | `root-control-plane` | 控制面核心 |
| `tools/` | `root-control-plane` | CLI 入口 |
| `tests/` | `root-control-plane` | 控制面测试 |
| `scripts/` | `root-control-plane` | 环境与构建脚本 |
| `docs/` | `root-control-plane` | 结构与专题文档 |
| `microprobe/` | `microprobe` | 生成与进化域 |
| `qemu/` | `qemu` | golden executor |
| `gem5/` | `gem5` | fault-side executor |
| `mcpat/` | `mcpat` | 功耗后处理 |
| `opendcdiag/` | `opendcdiag` | 硬件验证后端 |
| `artifacts/` | `root-control-plane` | Vault 与运行产物 |
| `build/` | `root-control-plane` | 本地构建中间物 |
| `dev/` | `root-control-plane` | 调试样例 |
| `third_party/` | `root-control-plane` | 第三方依赖快照 |
| `README.md` | `root-control-plane` | 项目总览 |
| `plan.md` | `root-control-plane` | 长期架构合同 |
| `findings.md` | `root-control-plane` | 历史状态快照 |
| `progress.md` | `root-control-plane` | 最近实现与验证 |

### 关键文档

| 路径 | 定位 |
| --- | --- |
| `README.md` | 项目总览 |
| `plan.md` | 长期架构合同 |
| `progress.md` | 最近实现与验证 |
| `docs/code-structure.md` | 结构说明 |
| `docs/monorepo.md` | domain 治理 |
| `docs/CLAUDE.md` | 历史方案参考 |
| `docs/kunpeng920.md` | 微架构背景参考 |

### 控制面分层

1. `tools/`：薄 CLI wrapper
2. `sdc_agent/agent.py`：总入口、编排与 lazy import
3. `sdc_agent/*.py`：领域逻辑
4. `sdc_agent/vault.py` + `artifacts/*.sqlite3`：数据总线
5. `microprobe/`、`qemu/`、`gem5/`、`mcpat/`、`opendcdiag/`：外部执行引擎

### 结构约束

1. CLI 保持薄；控制面业务逻辑进入 `sdc_agent/`。
2. 跨阶段状态优先经 Vault 和 `metadata_json` 传递。
3. `OpenDCDiag` 仅出现在硬件验证环。
4. 仅改 root control plane 时，避免无关触碰 `microprobe/`、`qemu/`、`gem5/` 等外部域。

## Skill Reference

本仓没有 repo-local skill 文件；默认把下列文档和命令视作技能入口。

| 任务 | 优先入口 |
| --- | --- |
| 项目总览与入口链路 | `README.md`、`docs/code-structure.md` |
| 长期架构与阶段目标 | `plan.md` |
| Domain 边界与审阅范围 | `docs/monorepo.md` |
| 当前实现状态、风险、验证结果 | `progress.md`、`docs/code-structure.md` |
| 仓库状态与回归验证 | `python3 tools/sdc_agent.py status`、`python3 tools/sdc_agent.py domains`、`python3 -m pytest -q tests` |

## Agent Behavior Guidelines

### 工作原则

1. 修改前先识别受影响的 managed domains。
2. 优先做最小闭环修改，避免跨域顺手重构。
3. `sdc_agent/` 是控制面主业务逻辑中心。
4. 文档、代码、测试不一致时，先确认真实运行行为，再决定修代码还是修文档。

### 控制面规则

1. CLI 保持薄；不要把业务逻辑堆回 `tools/`。
2. 状态、摘要和跨阶段上下文优先保持 Vault 兼容；`metadata_json` 视为事实总线。
3. 修改执行链时，明确区分生成 / materialize、QEMU golden、gem5 fault-side、McPAT 功耗和 OpenDCDiag 硬件环。
4. 不要把硬件 lane 依赖泄漏到 `dev` 或 `sim` 常规路径。

### 文档与测试

1. 结构性变更后，更新至少一份根级权威文档；必要时同步 `README.md` 或专题文档。
2. 控制面行为变更优先补或改 `tests/`。
3. 若无法完成完整验证，明确写出未验证项和阻塞条件。
4. 保持本文件简洁，细节放到对应子文档。

### 协作约束

1. 所有提交在 root 仓完成；不要把子目录当独立仓库。
2. `qemu` 内部 submodule 仍按 `qemu` domain 管理。
3. 跨 domain 修改时，说明每个目录为何必须被改。

### 禁止事项

1. 不改大型第三方目录中的无关文件。
2. 不把任务扩展成全仓格式化或大规模重命名。
3. 不忽视 `progress.md` 记录的环境限制和已知风险。

### 回答

结果先行，表述简洁；无必要不展开。
