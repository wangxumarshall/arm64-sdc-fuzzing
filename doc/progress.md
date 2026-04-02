# SDC-Agent Progress

## 1. 当前快照

日期：`2026-04-02`

本文件回答两个问题：

1. 当前仓库距离 README 完整愿景还有多远？
2. 哪些部分已经具备真实实现，哪些部分仍停留在控制面或规划层？

本次重构后，项目的进度口径被统一为：

1. 高频内循环
2. 低频外循环
3. 硬件验证环
4. 子项目完成度

---

## 2. 按系统环路统计

| 环路 | 状态 | 完成度 | 说明 |
| --- | --- | --- | --- |
| 高频内循环 | partial | 55% | 生成、静态分析、物料化、QEMU、功耗、进化能力都已存在，但尚未作为正式 `inner_loop` 收敛 |
| 低频外循环 | partial | 40% | 单次差分和 summary writeback 已有；fault matrix 与 injector 仍未完成 |
| 硬件验证环 | early | 15% | opendcdiag-arm 资产存在，但 promotion/backfill 尚未接入 |

### 2.1 高频内循环已具备

1. ARM64 指令流生成
2. ACE / IBR / Memory Pressure / Capstone
3. testcase 入库
4. digest materialization
5. QEMU golden digest
6. McPAT backend
7. genetic offspring 生成

### 2.2 高频内循环仍缺

1. 正式 `inner_loop.py`
2. profile-aware generation
3. 将功耗标注变成标准步骤
4. `INNER_READY` 级状态与批处理缓存

### 2.3 低频外循环已具备

1. 单 testcase 的 qemu/gem5 差分执行
2. digest compare 与状态归类
3. McPAT 结果回写
4. Scheduler summary ranking

### 2.4 低频外循环仍缺

1. `fault matrix planner`
2. `fault_runs` 级持久化
3. `outer_value_score`
4. 真实 gem5 fault injector

### 2.5 硬件验证环已具备

1. `opendcdiag-arm` 中已有 ARM64 SDC 检测资产
2. CRC32 / CRC64 / checksum / ECC 的基础实现存在

### 2.6 硬件验证环仍缺

1. promotion contract
2. 自动生成 `opendcdiag` 测试
3. 真机运行 orchestration
4. result ingest / DB backfill

---

## 3. 按子项目统计

| 子项目 | 状态 | 完成度 | 当前判断 |
| --- | --- | --- | --- |
| `Sub-P1 microprobe-arm` | strong | 75% | 生成、静态 pass、CLI、genetic 基线都已到位，缺双 profile 与更智能反馈 |
| `Sub-P2-1 qemu` | partial | 60% | golden runner 已接入；后续重点是批量化、缓存、非法指令分类 |
| `Sub-P2-2 gem5` | partial | 35% | SE runner、fault manifest、stats 链路存在；真实 injector 缺失 |
| `mcpat-arm` | partial | 55% | backend 与 pypat 链路可用；尚未成为 inner loop 标配 |
| `Sub-P0 opendcdiag-arm` | partial | 25% | ARM64 SDC 资产成熟度高于控制面接入度 |
| `SDC-Agent Control Plane` | strong | 65% | package、CLI、campaign、scheduler、genetic 主干已成型 |

---

## 4. 按能力统计

| 能力 | 状态 | 完成度 | 备注 |
| --- | --- | --- | --- |
| testcase generation | done-ish | 80% | 当前已能稳定生成和入库 |
| static coverage scoring | done-ish | 80% | ACE / IBR / Memory Pressure / Capstone 已就位 |
| wrapper/materialization | done-ish | 75% | 用户态 digest wrapper 可用；硬件版 emitter 尚缺 |
| qemu legality validation | partial | 65% | 单次执行稳定，缺 batch caching |
| power annotation | partial | 55% | McPAT 可用，但未纳入内循环标准状态机 |
| outer differential | partial | 45% | 单 fault skeleton 已通 |
| fault injection | early | 10% | 仍是 manifest 级别 |
| lineage/evolution | partial | 60% | Python 3 offspring 已可用，缺更丰富反馈源 |
| hardware promotion | early | 10% | 仍未接入控制平面 |

---

## 5. 本次文档重构已经完成的事情

1. 重新定义了整体架构、内循环、外循环、硬件验证环。
2. 明确了 `Sub-P0 / Sub-P1 / Sub-P2-1 / Sub-P2-2 / mcpat-arm / control plane` 的职责。
3. 将“当前实现”与“完成态规划”做了严格分离。
4. 统一了 `spec / plan / findings / progress` 的口径。
5. 将 root 级 planning files 与 `doc/` 下规划文档同步。

---

## 6. 当前仍未完成的关键阻塞

### 阻塞 1：数据库仍是单表中心

影响：

1. 无法优雅表达多次 fault run
2. 无法表达多次 hardware run
3. 无法追踪 artifact 历史

### 阻塞 2：正式 inner loop 尚未抽出

影响：

1. 功耗链路没有进入标准状态机
2. `cycle()` 仍然过于粗粒度

### 阻塞 3：gem5 fault injector 尚未实现

影响：

1. 当前 `SDC_FOUND` 的外循环价值仍受占位 fault 语义限制
2. README 愿景中的“故障注入差分验证”尚未闭环

### 阻塞 4：opendcdiag-arm promotion/backfill 缺失

影响：

1. 真实硬件验证环尚未打通
2. 项目还无法把仿真价值沉淀为真机可执行资产

---

## 7. 下一阶段推荐顺序

1. `Vault v2`
2. `inner_loop.py`
3. `outer_loop.py`
4. gem5 real injector
5. opendcdiag-arm promotion/backfill
6. LLM/PCFG/template 增益层

这个顺序不只是“方便实现”，而是当前唯一能稳定走向 README 完成态的顺序。

---

## 8. 风险评估

| 风险 | 等级 | 说明 |
| --- | --- | --- |
| 数据模型升级影响现有工具 | medium | 必须保留兼容 summary 层 |
| `SIM_SAFE` 与 `HW_AGGRESSIVE` profile 分叉 | medium | 如果 contract 不清晰，后续会继续混写 |
| gem5 injector 落地难度高 | high | 这是整个项目最硬的技术风险 |
| opendcdiag promotion 工程量大 | medium | 但资产本身已存在，不是从零开始 |

---

## 9. 进度结论

当前项目的真实完成度不应被表述为“还在早期”，更准确的说法是：

1. 控制平面骨架已经成型。
2. 内循环的零件已经齐备但还未正式编排。
3. 外循环差分主干已存在，但 fault execution 仍不完整。
4. 硬件验证环资产已在仓库中，只缺控制平面接入。

因此，项目现在最需要的是结构化推进，而不是方向性重启。

---

## 10. 本次重构验证

本次文档与规划重构后，已完成的直接验证：

1. `python3 -m pytest tests -q`
2. 结果：`24 passed`

这说明本次重构没有破坏顶层控制平面现有的单元与集成测试基线。
