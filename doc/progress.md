# SDC-Agent Progress

## 1. Current Snapshot

本文件描述的是“距离 README 完整愿景还有多远”，而不是简单的代码提交记录。

---

## 2. Progress by Loop

| Loop | Status | Completion | Notes |
| --- | --- | --- | --- |
| High-Frequency Inner Loop | partial | 60% | 生成、静态分析、进化骨架已具备；QEMU/功耗未完全纳入统一内循环 |
| Low-Frequency Outer Loop | partial | 50% | 单 fault differential 可用；fault matrix 与 sensitivity aggregation 未完成 |
| Hardware Validation Lane | early | 20% | OpenDCDiag-ARM 资产存在，自动 promotion/backfill 尚未落地 |

---

## 3. Progress by Subproject

| Subproject | Status | Completion | Current State |
| --- | --- | --- | --- |
| Sub-P0 opendcdiag-arm | partial | 25% | ARM64 测试与文档已存在，但尚未接入 SDC-Agent promotion/backfill |
| Sub-P1 microprobe-arm | strong | 80% | target/policy/static passes/generation CLI/driver 已可用 |
| Sub-P2-1 qemu | partial | 65% | differential runner 已能做 golden digest，但 inner-loop integration/cache 未完成 |
| Sub-P2-2 gem5 | partial | 40% | SE runner 与 fault manifest 已就位，真实 fault injector 未完成 |
| Sub-P3 mcpat-arm | partial | 60% | backend 与 power pipeline 已存在，但尚未成为内循环标配 |
| SDC-Agent Control Plane | strong | 70% | package、CLI、scheduler、campaign、genetic 骨架已成型 |

---

## 4. What Is Done

### Architecture and Repository

- 非第三方目录已完成分层：
  - `sdc_agent/`
  - `tools/`
  - `scripts/`
  - `dev/`
  - `artifacts/runtime/`

### Core Pipeline

- 已实现 ARM64 指令流生成
- 已实现 ACE / IBR / Memory Pressure
- 已实现 Vault 持久化
- 已实现 digest materialization
- 已实现 QEMU / gem5 / McPAT 单次差分链路
- 已实现 scheduler 与 Python 3 genetic driver

### Validation

- `python3 -m py_compile ...` 通过
- `python3 tools/sdc_agent.py status --db /tmp/sdc-agent-arch.sqlite3` 通过
- `python3 tools/sdc_preflight.py --help` 通过
- `python3 microprobe/targets/generic/tools/mp_sdc_offline_gen.py --help` 通过
- 定向 pytest `32 passed`

---

## 5. What Is Not Done

### Inner Loop Gaps

- 缺少正式 `inner_loop.py`
- 功耗标注不在 `cycle()` 主路径中
- QEMU 校验与种群反馈未成为标准内循环步骤

### Outer Loop Gaps

- 缺少 fault matrix
- 缺少多 fault 结果聚合
- 缺少 `sdc_sensitivity_score`

### Hardware Lane Gaps

- OpenDCDiag promotion 未实现
- OpenDCDiag result ingestion 未实现

### Infrastructure Gaps

- 数据库仍是单表兼容模型
- gem5 real fault injector 未完成

---

## 6. Readiness Assessment

### Can the current code run a minimal research workflow?

可以。

它已经能支持：

1. 生成样本
2. 静态打分
3. 持久化
4. 物料化
5. 单样本差分
6. 结果回写
7. offspring 生成

### Can the current code fully realize the README vision?

还不可以。

阻塞点主要是：

1. 内循环未完全编排
2. 外循环没有完整 fault campaign
3. gem5 fault injector 未真实落地
4. OpenDCDiag 硬件验证链路未打通

---

## 7. Immediate Execution Order

下一步最正确的顺序是：

1. 数据库 v2
2. `inner_loop.py`
3. `outer_loop.py`
4. gem5 real fault injector
5. OpenDCDiag promotion

这个顺序的原因是：

- 不先升级数据库，后续 fault campaign 和硬件回灌就没有干净的存储面
- 不先把 inner loop 统一，power/qemu/genetic 就无法形成真正的高频闭环
