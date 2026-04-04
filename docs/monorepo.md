# SDC-Agent Monorepo

## 1. 目标

本仓库现在作为 `SDC-Agent` 的唯一 git monorepo，统一承载以下核心子项目源码：

1. `microprobe/`
2. `qemu/`
3. `gem5/`
4. `mcpat/`
5. `opendcdiag/`
6. root control plane：
   - `sdc_agent/`
   - `tools/`
   - `tests/`
   - `docs/`
   - `scripts/`

迁移策略：

1. 保留子项目完整历史，通过 subtree 导入到 root。
2. root 与原 upstream 彻底脱钩。
3. `qemu` 内部 submodule 保留不变，作为 monorepo 内部 gitlink 管理。

## 2. Managed Domains

| Domain | 路径前缀 | 角色 |
| --- | --- | --- |
| `root-control-plane` | `sdc_agent/` `tools/` `tests/` `docs/` `scripts/` `README.md` `.gitignore` `.gitmodules` | `Sub-P4 Control plane` |
| `microprobe` | `microprobe/` | `Sub-P1 microprobe-arm` |
| `qemu` | `qemu/` | `Sub-P2-1 qemu` |
| `gem5` | `gem5/` | `Sub-P2-2 gem5` |
| `mcpat` | `mcpat/` | `Sub-P3 mcpat-arm` |
| `opendcdiag` | `opendcdiag/` | `Sub-P0 opendcdiag-arm` |

所有 phase、审阅、变更归属都必须映射到上述 domain，而不是再按独立 nested repo 处理。

## 3. 日常工作方式

1. 所有代码修改只在 root 仓提交。
2. 不再进入子目录单独执行 `git commit`。
3. 查看整体状态用：
   - `python3 tools/sdc_agent.py status`
   - `python3 tools/sdc_agent.py domains`
4. 查看某个 domain 的差异用：
   - `python3 tools/sdc_agent.py diff --domain microprobe`
   - `python3 tools/sdc_agent.py diff --domain qemu`

## 4. 审阅与跟踪规则

1. 任何实现任务都必须说明涉及哪些 managed domains。
2. phase/state 文档更新时，必须能落到具体 domain。
3. `qemu` 的内部 submodule 不在第一阶段扁平化，但在 root 中仍按 `qemu` domain 管理。
