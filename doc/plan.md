# SDC-Agent Project Plan

## 1. Planning Goal

将整个项目拆解成逻辑独立、边界清晰、与当前源码事实一致的大 Phase，使项目可以在庞大代码基座和较高技术债之上，按阶段逐步兑现 README 与 spec 中的完整愿景。

本计划采用五个大 Phase：

1. `Phase 1: Microprobe-arm`
2. `Phase 2: 高功耗波动引导 SDC Fuzzing`
3. `Phase 3: LLM 增强的智能变异生成`
4. `Phase 4: QEMU vs gem5 + 故障注入差分验证`
5. `Phase 5: OpenDCDiag-ARM 真实环境验证与数据库回灌`

其中 Phase 1-4 与你给出的方向一一对应；Phase 5 是为了与 README/spec 中“真实硬件验证环”保持一致而补出的必要阶段。

---

## 2. Phase Overview

| Phase | Goal | Current Status | Completion |
| --- | --- | --- | --- |
| Phase 1: Microprobe-arm | ARM64 指令流生成与静态覆盖分析底座 | 已完成主干 | 80% |
| Phase 2: 高功耗波动引导 SDC Fuzzing | 建立高频内循环：生成、QEMU、功耗、反馈 | 部分完成 | 60% |
| Phase 3: LLM 增强的智能变异生成 | 让生成策略从规则/GA 扩展到 LLM/PCFG/模板协同 | 规划中 | 15% |
| Phase 4: QEMU vs gem5 + 故障注入差分验证 | 建立低频外循环与 fault campaign | 部分完成 | 50% |
| Phase 5: OpenDCDiag-ARM 真实环境验证与数据库回灌 | 将高价值样本推广到真实硬件环境并回灌 | 早期 | 20% |

---

## 3. Phase 1: Microprobe-arm

**目标**: Microprobe 移植支持 arm64 指令流生成。

### 当前事实

当前源码中，这个阶段已经具备主要基础设施：

- ARM64 target/env/wrapper 已接通
- `sdc_fuzzing_policy` 已能生成 ARM64 指令流
- ACE / IBR / Memory Pressure / Capstone 分析 pass 已存在
- Offline CLI 已可将样本写入 Vault

对应源码：

- [`microprobe/targets/arm64/policies/sdc_fuzzing_policy.py`](/Users/wangxu/1-project/sdc-fuzzing/microprobe/targets/arm64/policies/sdc_fuzzing_policy.py)
- [`microprobe/src/microprobe/passes/sdc_analysis/offline_coverage.py`](/Users/wangxu/1-project/sdc-fuzzing/microprobe/src/microprobe/passes/sdc_analysis/offline_coverage.py)
- [`microprobe/targets/generic/tools/mp_sdc_offline_gen.py`](/Users/wangxu/1-project/sdc-fuzzing/microprobe/targets/generic/tools/mp_sdc_offline_gen.py)
- [`sdc_agent/generation.py`](/Users/wangxu/1-project/sdc-fuzzing/sdc_agent/generation.py)

### 阶段边界

Phase 1 只解决“能生成什么、能分析什么、能否入库”，不负责：

- gem5 fault campaign
- OpenDCDiag 真机回灌
- LLM 驱动的高级变异

### 剩余工作

1. 将当前默认 `SIM_SAFE` 生成 profile 与未来 `HW_AGGRESSIVE` profile 正式区分。
2. 修复当前评分器与生成器的偏好错位：
   - `Kunpeng920MemoryPressurePass` 偏好某些访存模式
   - 默认生成器却大量过滤它们
3. 为后续 Phase 2/3 输出更稳定的 generation metadata。

### 验收标准

1. ARM64 目标可稳定生成指令流。
2. 每个 testcase 都具备基本 static metrics。
3. testcase 可稳定写入数据库。

---

## 4. Phase 2: 高功耗波动引导 SDC Fuzzing

**目标**: 使用 gem5 仿真执行测试用例 + McPAT 计算功耗，利用功耗反馈引导 Microprobe 生成高功耗波动指令流。

### 对应系统层

这是 README/spec 中的 **高频内循环**。

### 当前事实状态

你给出的步骤与当前源码的契合度如下：

1. Microprobe 移植支持 arm64 指令流生成
   - 已完成主干
2. 生成 SDC 测试用例到 Vault
   - 已完成主干
3. 用例物化 (Materialize)
   - 已完成主干
4. gem5 SE 执行 + McPAT 功耗计算
   - 已有主干，但仍受两类问题约束：
     - 指令编码/兼容性问题
     - 功耗链路尚未成为统一内循环标准步骤
5. 反馈引导的下一代生成
   - 已有 Python 3 genetic baseline
   - 但还没有真正把 QEMU/功耗反馈编织进统一 inner loop
6. Phase 2 联调验证 (3000+ 用例)
   - 尚未完成

### 详细步骤

#### Step 1: 生成

- 调用 `microprobe-arm`
- 生成 testcase
- 写入数据库

#### Step 2: 覆盖率评估

- ACE
- IBR
- Memory Pressure
- Capstone legality

#### Step 3: Wrapper / Materialize

- 生成 digest wrapper
- 生成可编译 C 源与 ELF

#### Step 4: QEMU 快速验证

- 提取 golden digest
- 快速判定样本是否合法、可执行

#### Step 5: gem5 + McPAT 功耗标注

- 对 shortlist 样本跑 gem5
- 使用 McPAT 打功耗标签
- 计算 `inner_value_score`

#### Step 6: 反馈引导下一代

- 用 genetic driver、功耗信号、覆盖率信号调整下一批样本

#### Step 7: 大规模联调

- 以 3000+ 样本为目标验证吞吐、稳定性、评分有效性

### 当前主要阻塞

1. 当前 `cycle()` 还不是正式 `inner_loop.py`
2. 功耗链路独立存在，但还没有被标准纳入高频内循环
3. 当前生成策略仍主要偏 sim-safe，不足以充分覆盖高功耗/高波动模式

### 本阶段交付物

- `sdc_agent/inner_loop.py`
- `tools/sdc_inner_loop.py`
- 数据库中的 `STATIC_DONE / QEMU_VALID / POWER_ANNOTATED / INNER_READY` 轨迹

### 验收标准

1. 可以批量跑完整 inner loop。
2. 可以稳定得到功耗标签。
3. genetic 迭代开始使用功耗反馈，而不仅是静态分。

---

## 5. Phase 3: LLM 增强的智能变异生成

**目标**: 借助 LLM 推理能力实现更精准的 SDC 检测指令流生成和覆盖率评估。

### 当前事实状态

这个阶段目前还处于规划中，但并非从零开始，因为已有：

- 规则生成器
- genetic baseline
- static coverage metrics
- Vault 数据积累

因此，Phase 3 的定位是“在已有规则/GA 之上叠加智能生成层”，而不是替代现有生成器。

### 步骤

#### Step A: LLM 变异生成器

- 读取父代 lineage / static metrics / power labels
- 生成更具针对性的变异建议

#### Step B: 概率上下文文法 (PCFG) 生成器

- 把 ARM64 指令族、依赖链、访存模板表达为概率文法

#### Step C: 模板生成器

- 沉淀高价值模式模板：
  - cache-thrash
  - long-lifetime register chain
  - vector-heavy compute pattern

#### Step D: 遗传算法 (GA) 优化器

- 当前 Python 3 `SDCFuzzingGeneticDriver` 作为 baseline
- 后续将其升级为与 LLM/PCFG/template 协同的多策略优化器

#### Step E: LLM 覆盖率评估器

- 只能作为补充评估器
- 不能替代 source-of-truth 的 static passes

#### Step F: LLM Prompt 生成

- 自动根据外循环/hardware 反馈调整 prompt、模板和 profile 权重

### 阶段边界

本阶段不负责真实 fault injection；它负责的是更聪明的候选生成。

### 当前主要阻塞

1. 缺少数据库 v2 与更完整 metadata
2. 缺少正式内循环 orchestrator
3. 缺少 aggressive profile 的显式建模

### 验收标准

1. LLM/PCFG/template 不是单点实验，而是能接入内循环。
2. 新生成策略在覆盖率、多样性或功耗波动上优于纯 baseline。

---

## 6. Phase 4: QEMU vs gem5 + 故障注入差分验证

**目标**: 增加 SDC 检测能力。

### 对应系统层

这是 README/spec 中的 **低频外循环**。

### 当前事实状态

你给出的步骤与当前源码的契合度如下：

#### Step A: 构建 QEMU aarch64-linux-user

- 已具备基本依赖与 runner 支持
- 当前 `tools/run_sdc_differential.py` 已可使用 qemu 作为 golden executor

#### Step B: gem5 SDC 故障注入引擎

- 当前只完成了 fault control plane：
  - `fault_model`
  - `fault_target`
  - `fault_bit`
  - `fault_tick`
  - `sdc_fault_request.json`
- 真实 injector 尚未实现

#### Step C: 差分验证流水线

- 已完成单 fault configuration 的 skeleton
- 尚未升级为完整 fault matrix campaign

### 本阶段应有的完整流程

1. 从数据库中选取高价值 `INNER_READY` 样本
2. 构建 fault matrix
3. 缓存 QEMU golden
4. 多次执行 gem5 fault run
5. 聚合 fault run 结果
6. 计算 `sdc_sensitivity_score`
7. 更新数据库并进入 promotion queue

### 本阶段交付物

- `sdc_agent/outer_loop.py`
- `tools/sdc_outer_loop.py`
- per-fault run persistence
- sensitivity aggregation
- gem5 real injector

### 当前主要阻塞

1. 数据库仍是单表
2. `campaign.py` 还是单 fault 执行器
3. gem5 real injector 未实现

### 验收标准

1. 一个 testcase 能挂多组 fault run。
2. 能输出 testcase 级 SDC 检测能力分。
3. 启用 fault 时，gem5 结果是真实 fault behavior，而不是 manifest 记录。

---

## 7. Phase 5: OpenDCDiag-ARM 真实环境验证与数据库回灌

**目标**: 将数据库中已被证明具有价值的指令流封装成真实环境 SDC 检测用例，追加到 `opendcdiag-arm`，执行后将结果回灌数据库。

### 为什么必须独立成 Phase 5

虽然你给出的参考阶段只写到 Phase 4，但按照 README/spec 的完整愿景，项目最终不能止步于仿真。

所以必须补出一个独立硬件验证阶段。

### 当前事实状态

- `opendcdiag-arm` 中已经有 ARM64 测试与文档资产
- 但 `sdc_agent` 侧只有 placeholder backend
- promotion / packaging / result parser / backfill 还不存在

### 详细步骤

1. 从数据库中选择 `PROMOTABLE` 样本
2. 生成 OpenDCDiag-ARM test package
3. 在真实 ARM64 机器上执行
4. 采集：
   - pass/fail
   - digest mismatch
   - timeout/crash
   - 平台信息
5. 将结果写回数据库

### 本阶段交付物

- `sdc_agent/hardware_promotion.py`
- `sdc_agent/hardware_results.py`
- `tools/sdc_promote_hw.py`
- `opendcdiag/tests/cpu/arm64/generated/`

### 验收标准

1. 可以自动从数据库选择高价值样本。
2. 可以自动生成 OpenDCDiag-ARM 测试。
3. 可以将真实环境结果回灌数据库。

---

## 8. Recommended Execution Order

虽然 Phase 1-5 是项目级大阶段，但真正执行时建议顺序如下：

1. Phase 1 收尾
   - 明确双 profile
2. Phase 2 完整化
   - `inner_loop.py`
   - 功耗正式并入内循环
3. Phase 4 基础化
   - 先补数据库 v2 和 fault matrix，再做 real injector
4. Phase 3 接入
   - 在稳定的 inner loop / outer loop 之上接入 LLM/PCFG/template
5. Phase 5 收尾
   - OpenDCDiag hardware promotion

原因：

- Phase 3 依赖 Phase 2/4 的稳定 metadata 和反馈数据
- Phase 5 依赖 Phase 4 已经能稳定筛出高价值样本
