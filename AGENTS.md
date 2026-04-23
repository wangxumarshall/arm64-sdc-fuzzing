# AGENTS.md

本文件定义 `/data/slim/arm64-sdc-fuzzing` 的仓库级 agent 工作约束。
目标是让任何进入本仓的自动化 agent 或协作编码代理，先理解项目骨架、
指令优先级和 monorepo 边界，再开始修改代码。

## Project Overview (YOU MUST READ FIRST)

### 项目一句话

本仓库是 `SDC-Agent` 的 monorepo。顶层 CLI `tools/sdc_agent.py`
将请求交给 `sdc_agent/agent.py`，后者以 `sdc_agent/vault.py`
维护的 SQLite Vault 为总线，编排：

1. `microprobe` testcase 生成与进化
2. `materialize` 物料化
3. `qemu` / `gem5` 差分执行
4. `mcpat` 功耗标注
5. 反馈调度与外循环筛选
6. `opendcdiag` 硬件验证闭环

### 核心目标

本项目服务于 ARM64 场景下的 SDC 自动化发现，重点不是单点仿真，
而是构建一条低成本、高吞吐、可反馈进化的端到端流水线。

### 三条执行环

1. 高频内循环：生成、静态分析、物料化、readiness 回写
2. 低频外循环：fault campaign、差分判定、价值聚合
3. 硬件验证环：promotion、OpenDCDiag 执行、结果回灌

### 推荐先读文件

1. `README.md`：项目目标与总体架构
2. `docs/code-structure.md`：代码骨架与模块职责
3. `docs/monorepo.md`：managed domain 边界
4. `progress.md`：当前实现事实与最近验证结果

## Instruction Hierarchy

当多份说明同时存在时，按以下优先级解释和执行：

1. 系统指令 / 平台运行时约束
2. 开发者指令
3. 用户在当前对话中的明确要求
4. 本文件 `AGENTS.md`
5. 仓库内更细粒度的目录级或局部说明文件
6. `docs/monorepo.md`
7. `docs/code-structure.md`
8. `progress.md` 与 `README.md`
9. 代码、测试和可运行行为本身

### 冲突处理规则

1. 若用户要求与更高优先级指令冲突，必须服从更高优先级。
2. 若文档与代码不一致，以当前代码与测试行为为准，并在提交说明中指出文档漂移。
3. 若 `progress.md` 与旧设计文档冲突，优先按 `progress.md` 理解“当前实现事实”。
4. 若修改跨越多个 domain，必须先按 `docs/monorepo.md` 明确变更归属，再实施修改。

## Repository Structure

### 顶层目录索引

| 路径 | Managed Domain | 角色 |
| --- | --- | --- |
| `sdc_agent/` | `root-control-plane` | 控制面核心实现 |
| `tools/` | `root-control-plane` | CLI 薄入口 |
| `tests/` | `root-control-plane` | 控制面与接缝测试 |
| `scripts/` | `root-control-plane` | 环境、构建、bootstrap 脚本 |
| `docs/` | `root-control-plane` | 补充文档与治理说明 |
| `microprobe/` | `microprobe` | testcase 生成与进化域 |
| `qemu/` | `qemu` | golden executor |
| `gem5/` | `gem5` | fault-side executor |
| `mcpat/` | `mcpat` | 功耗后处理 |
| `opendcdiag/` | `opendcdiag` | 硬件验证后端 |
| `artifacts/` | `root-control-plane` | Vault、运行产物、e2e 输出 |
| `build/` | `root-control-plane` | 本地构建中间物 |
| `dev/` | `root-control-plane` | 调试样例与临时开发资源 |
| `third_party/` | `root-control-plane` | 第三方依赖快照 |
| `README.md` | `root-control-plane` | 项目总览 |
| `plan.md` | `root-control-plane` | 长期架构合同 |
| `findings.md` | `root-control-plane` | 当前源码事实 |
| `progress.md` | `root-control-plane` | 最近修复与验证记录 |

### 控制面分层

1. 入口层：`tools/` 中的命令只做薄包装，实际逻辑应落在 `sdc_agent/`
2. 编排层：`sdc_agent/agent.py` 统一暴露 `status`、`generate`、`cycle`、
   `e2e-dev`、`e2e-sim`、`e2e-hw` 等子命令，并承担 lazy import
3. 领域模块层：`generation.py`、`materialize.py`、`differential.py`、
   `scheduler.py`、`inner_loop.py`、`outer_loop.py`、`hardware_lane.py`
4. 数据层：`sdc_agent/vault.py` + `artifacts/*.sqlite3`
5. 外部执行引擎层：`microprobe/`、`qemu/`、`gem5/`、`mcpat/`、`opendcdiag/`

### 修改时的结构约束

1. 不要把控制面业务逻辑堆回 `tools/`；CLI 必须保持薄。
2. 不要绕开 Vault 自造跨阶段状态通道；跨模块上下文优先进入数据库与 `metadata_json`。
3. `OpenDCDiag` 只应出现在硬件验证环相关实现中，不应混入高频仿真路径。
4. 若只是 root control plane 变更，尽量不要无关修改 `microprobe/`、`qemu/`、`gem5/` 等外部域。

## Skill Reference

本仓目前没有单独维护一组 repo-local skill 文件；agent 应把下面这些文档与路径
视作默认技能入口，并按任务类型选读。

### 代码骨架理解

- `docs/code-structure.md`
- `README.md`

适用场景：

1. 需要快速判断控制面主链
2. 需要识别某个功能应落在哪一层
3. 需要区分“项目业务逻辑”和“外部执行引擎”

### Monorepo / Domain 治理

- `docs/monorepo.md`

适用场景：

1. 变更跨越多个顶层目录
2. 需要确认 managed domain 归属
3. 需要说明提交影响面与审阅边界

### 当前实现事实与验证状态

- `progress.md`
- `findings.md`

适用场景：

1. 判断某条 lane 是否已经可运行
2. 判断某个失败是环境缺失还是源码缺口
3. 避免重复修复已解决问题

### 调试与验证入口

- `python3 tools/sdc_agent.py status`
- `python3 tools/sdc_agent.py domains`
- `python3 -m pytest -q tests`

适用场景：

1. 快速确认仓库状态
2. 观察 domain 差异边界
3. 对 root control plane 变更做回归验证

## Agent Behavior Guidelines

### 总体行为

1. 修改前先识别受影响的 managed domains。
2. 优先做最小闭环修改，避免跨域“顺手重构”。
3. 默认把 `sdc_agent/` 视为项目主业务逻辑中心。
4. 若文档、测试、代码不一致，先确认真实运行行为，再决定修复代码还是修文档。

### 控制面修改规则

1. CLI 入口保持薄；新增逻辑优先进入 `sdc_agent/`。
2. 新增状态、摘要或跨阶段上下文时，优先考虑 Vault schema 与 `metadata_json` 兼容性。
3. 修改执行链时，明确区分：
   - 生成 / materialize
   - QEMU golden
   - gem5 fault-side
   - McPAT 功耗
   - OpenDCDiag 硬件闭环
4. 不要把硬件 lane 特有依赖泄漏到 `dev` 或 `sim` 常规路径。

### 文档与测试规则

1. 结构性变更后，同步更新相关文档，至少覆盖 `README.md`、`progress.md`
   或对应设计说明中的一处权威来源。
2. 若修改控制面行为，优先补或改 `tests/` 中对应测试。
3. 若无法在当前环境完成完整验证，必须明确写出未验证项与阻塞条件。
4. 保持该文件简洁，详细细节更新到对应的子文档中。

### Monorepo 协作规则

1. 所有提交都在 root 仓完成，不把子目录当成独立仓库操作。
2. `qemu/` 的内部 submodule 仍按 `qemu` domain 管理，但不作为单独提交流。
3. 跨 domain 修改时，说明每个目录为什么必须被改。

### 禁止事项

1. 不要在没有明确需要时修改大型第三方目录中的无关文件。
2. 不要把一次任务扩展成全仓格式化或大规模重命名。
3. 不要忽视 `progress.md` 中已经记录的环境限制和已知风险。

### 回答
- 凡回复，惜字如金，不赘不饰。先行后言，先果后因。如无必要，无增实体。
