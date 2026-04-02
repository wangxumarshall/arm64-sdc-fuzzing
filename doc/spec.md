# SDC-Agent Specification

## 1. Scope

SDC-Agent 是一个面向 ARM64 的 SDC 自动化 Fuzzing 控制平面，负责把 Microprobe、SQLite Vault、QEMU、gem5 和 McPAT 组织成一条可以持续迭代的发现流水线。

## 2. In Scope

- ARM64 指令流生成
- 静态覆盖率评估（ACE / IBR / Memory Pressure）
- Vault 持久化与排序
- wrapper / materialize
- QEMU vs gem5 differential execution
- McPAT 功耗回写
- feedback scheduling
- offspring generation / reinjection

## 3. Out of Scope

- 分布式调度
- LLM/RL 多智能体框架
- 完整的 gem5 C++ fault injector 实现
- OpenDCDiag 作为当前主执行路径的硬依赖

## 4. Core Contracts

### 4.1 Vault Row

最小字段契约：

- `testcase_key`
- `asm_content`
- `target_name`
- `policy_name`
- `ace_score`
- `ibr_score`
- `memory_pressure_score`
- `risk_score`
- `qemu_golden_hash`
- `gem5_fault_hash`
- `mcpat_power`
- `status`
- `metadata_json`

### 4.2 Status Contract

- `PENDING`
- `GOLDEN_READY`
- `MATCHED`
- `SDC_FOUND`
- `INVALID`
- `TIMEOUT`
- `CRASHED`

### 4.3 Differential Classification Contract

输入：

- compile result
- qemu result
- gem5 result
- golden digest
- faulted digest

输出：

- `compile_failed`
- `golden_failed`
- `golden_only`
- `gem5_timeout`
- `gem5_failed`
- `digest_missing`
- `matched`
- `sdc_found`

### 4.4 Evolution Contract

输入：

- parent rows selected from Vault
- parent metadata instruction names
- target / policy / sequence_length

输出：

- offspring rows written back to Vault
- lineage metadata:
  - generation
  - parent testcase keys
  - operators
  - preferred stride

## 5. Architecture Decisions

1. 静态评分与在线差分完全解耦。
2. 结构化分析结果优先写入 `benchmark.metadata`，再进 Vault。
3. 执行层坚持极简 wrapper + digest，不引入重量级 C++ 测试夹具。
4. `tools/sdc_agent.py` 只做编排，不重复实现底层执行逻辑；核心实现位于 `sdc_agent/agent.py`。
5. 真正的 fault injection 与控制平面分离，先走 manifest/hook。

## 6. Acceptance Criteria

1. 能离线生成样本并写入 Vault。
2. 能在线编译和差分至少一个样本。
3. 能回写 digest、status、power。
4. 能从已有父代生成 offspring 并重新注入 Vault。
5. 能通过统一入口查看状态和运行一轮 cycle。
