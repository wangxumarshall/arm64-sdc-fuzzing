# SDC-Agent：面向 ARM64 架构的 SDC 自动化 Fuzzing 工具集

> **项目代号**：SDC-Agent
> **架构版本**：v2.0 (A/B 双循环 + SQLite Vault 中枢)
> **目标微架构**：TaiShan v110 / Kunpeng 920 (ARMv8.2-A)
> **最后更新**：2026-04-02

---

## 一、项目概述

### 1.1 背景与目标

静默数据破坏（Silent Data Corruption, SDC）是数据中心 ARM 服务器面临的最隐蔽硬件可靠性问题之一——CPU 悄然产生错误结果，却无任何异常信号。本项目旨在构建一套**自动化 SDC 用例生成的 Agent 系统**，通过"生成-校验-覆盖-检测-反馈"闭环，自进化地寻找高风险指令组合，用于：

1. **SDC 问题筛选**：快速识别疑似 SDC 的指令序列
2. **SDC 定界定位**：通过差分测试（QEMU vs gem5）定位触发条件
3. **微架构覆盖率验证**：量化评估 ARM64 CPU 可靠性测试的覆盖完整性

### 1.2 核心方法论

系统摒弃了传统的"单轨在线循环"和笨重的测试框架（如 OpenDCDiag 原始方案），采用**"A/B 异步架构 + 轻量级差分测试"**：

| 方法 | 原理 | 速度 | 精度 |
|------|------|------|------|
| 纯静态降维 | 不运行仿真，通过 ACE/IBR 启发式评分 | 极快（~10⁶/天） | 中等（筛选候选） |
| 零开销差分判定 | QEMU ISA 金标准 vs gem5 微架构故障注入 | 快（~10³/天） | 高（SDC 判定） |

### 1.3 五大子项目

```
sdc-fuzzing/
├── Sub-P0: opendcdiag-arm/     # ARM64 SDC 真实环境压测工具集
├── Sub-P1: microprobe-arm/     # ARM64 指令流生成（离线引擎）
├── Sub-P2-1: qemu/             # QEMU 仿真验证（ISA 金标准）
├── Sub-P2-2: gem5/            # gem5 SDC 故障注入与仿真
├── Sub-P3: mcpat-arm/          # ARM64 指令流功耗计算
└── sdc_discovery/              # 核心调度层（Agent 系统）
```

---

## 二、系统架构

### 2.1 整体架构

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          SDC-Fuzzing Agent System                          │
│                                                                             │
│  ╔═══════════════════════════════════════════════════════════════════════╗  │
│  ║             高频内循环：SDC 用例生成与静态评估（离线）                  ║  │
│  ║  ┌──────────────┐  ┌──────────────┐  ┌────────────────────────────┐  ║  │
│  ║  │  Generator   │──▶│  Validator   │──▶│      Coverage Engine    │  ║  │
│  ║  │   Agent      │   │   Agent      │   │  (ACE · IBR · Memory)   │  ║  │
│  ║  └──────────────┘  └──────────────┘  └────────────────────────────┘  ║  │
│  ║         │                                           │                ║  │
│  ║         ▼                                           ▼                ║  │
│  ║  ╔═══════════════════════════════════════════════════════════════╗  ║  │
│  ║  ║              SQLite Vault (Testcase Pool)                       ║  ║  │
│  ║  ║  字段: testcase_key, asm_content, ace_score, ibr_score,       ║  ║  │
│  ║  ║         memory_pressure_score, risk_score, status             ║  ║  │
│  ║  ╚═══════════════════════════════════════════════════════════════╝  ║  │
│  ╚═══════════════════════════════════════════════════════════════════════╝  │
│                                    │                                         │
│                          批量拉取 Top N                                     │
│                                    ▼                                         │
│  ╔═══════════════════════════════════════════════════════════════════════╗  │
│  ║             低频外循环：SDC 差分检测与进化（在线）                      ║  │
│  ║  ┌──────────────┐  ┌──────────────┐  ┌────────────────────────────┐  ║  │
│  ║  │  Runner      │  │  Power       │  │      Feedback             │  ║  │
│  ║  │  Agent       │  │  Agent       │  │      Agent                │  ║  │
│  ║  └──────────────┘  └──────────────┘  └────────────────────────────┘  ║  │
│  ║        │                   │                    │                     ║  │
│  ║        ▼                   ▼                    ▼                     ║  │
│  ║  ┌──────────────┐  ┌──────────────┐  ┌────────────────────────────┐  ║  │
│  ║  │ SDC Wrapper  │  │   McPAT      │  │   优化 Prompt             │  ║  │
│  ║  │ (materialize)│  │  功耗计算    │  │   注入下一轮生成           │  ║  │
│  ║  └──────────────┘  └──────────────┘  └────────────────────────────┘  ║  │
│  ║        │                                                             ║  │
│  ║        ▼                                                             ║  │
│  ║  ╔═══════════════════════════════════════════════════════════════╗  ║  │
│  ║  ║           差分测试：QEMU(golden) vs gem5(faulted)              ║  ║  │
│  ║  ║           Hash(Golden) == Hash(gem5) ? matched : sdc_found   ║  ║  │
│  ║  ╚═══════════════════════════════════════════════════════════════╝  ║  │
│  ╚═══════════════════════════════════════════════════════════════════════╝  │
│                                                                            │
│  ╔═══════════════════════════════════════════════════════════════════════╗  │
│  ║              输出：SDC 检测用例 → OpenDCDiag-ARM                      ║  │
│  ╚═══════════════════════════════════════════════════════════════════════╝  │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 2.2 高频内循环（High-Frequency Inner Loop）

**目标**：纯静态、无环境依赖、高并发生成 ARM64 指令序列

| 阶段 | 组件 | 输入 | 输出 |
|------|------|------|------|
| 1. 生成 | `Generator Agent` | Microprobe Policy + SDC 敏感指令分析 | ARM64 汇编序列 |
| 2. 校验 | `Validator Agent` | 汇编序列 | 合法性结果 + 错误信息 |
| 3. QEMU 执行 | `Runner Agent` | 指令序列wrapper成的ELF 文件 | 执行结果 |
| 4. 覆盖评估 | `Coverage Agent` | 汇编序列 | ACE/IBR/Memory Pressure 分数 |
| 5. 持久化 | SQLite Vault | 评分后的用例 | PENDING 状态记录 |

**关键文件**：
- 生成器入口：`microprobe/targets/generic/tools/mp_sdc_offline_gen.py`
- Policy 定义：`microprobe/targets/arm64/policies/sdc_fuzzing_policy.py`
- 覆盖率 Pass：`microprobe/src/microprobe/passes/sdc_analysis/offline_coverage.py`
- Vault 接口：`sdc_vault.py`

**性能目标**：单机 ~50,000 条/天（受限于 SQLite 写入和 Capstone 校验）

### 2.3 低频外循环（Low-Frequency Outer Loop）

**目标**：物理级仿真、精准测试、动态进化

| 阶段 | 组件 | 输入 | 输出 |
|------|------|------|------|
| 1. 候选选取 | `Scheduler` | Vault Top N 候选 | 高价值用例列表 |
| 2. 封装 | `Materialize` | Vault 汇编序列 | 可编译 C 源文件 |
| 3. QEMU 执行 | `Runner Agent` | ELF 文件 | Golden Hash |
| 4. gem5 执行 | `Runner Agent` | ELF 文件 + 故障注入 | Faulted Hash |
| 5. McPAT 计算 | `Power Agent` | gem5 统计输出 | 功耗数据 |
| 6. SDC 判定 | `Feedback Agent` | Golden vs Faulted Hash | SDC_FOUND / MATCHED |
| 7. 数据库更新 | `Scheduler.record_result()` | 判定结果 | 更新 status/fitness |

**关键文件**：
- 差分测试：`run_sdc_differential.py`
- Campaign 调度：`sdc_campaign.py`
- 调度器：`sdc_scheduler.py`
- 物料化：`sdc_materialize.py`

**关键文件**：
- 差分测试：`run_sdc_differential.py`
- Campaign 调度：`sdc_campaign.py`
- 调度器：`sdc_scheduler.py`
- 物料化：`sdc_materialize.py`

**性能目标**：单次差分测试 ~2-5 分钟（gem5 SE 模式），每日 ~300 次/机

### 2.4 数据流

```
指令序列生成 ──▶ ISA 合法性校验 ──▶ 微架构覆盖计算 ──▶ 功耗评估 ──▶ 仿真执行 ──▶ 结果反馈 ──▶ 优化 Prompt
     ▲                                                                                                    │
     └──────────────────────────────────────── 反馈闭环 ────────────────────────────────────────────────────┘

Vault 数据流：

┌─────────────┐     ┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   PENDING   │────▶│GOLDEN_READY│────▶│  MATCHED    │     │  SDC_FOUND │
│ (新生成)    │     │(QEMU验证)   │     │(gem5匹配)   │     │(检测到SDC) │
└─────────────┘     └─────────────┘     └─────────────┘     └─────────────┘
      │                   │                   │                   │
      │                   │                   │                   │
      ▼                   ▼                   ▼                   ▼
  继续参与           参与外循环          保留用于          优先保留用于
  内循环生成         gem5测试           统计分析          根因分析
```

---

## 三、核心 Agent 设计

### 3.1 Generator Agent

**职责**：负责生成 AArch64 指令序列

**输入 Skill**：
- `ISA_Constraint_Skill`：ARMv8.2-A 指令约束
- `Microarch_Characteristic_Skill`：TaiShan v110 微架构特性
- `SDC_Sensitive_Unit_Skill`：敏感单元优先级

**生成策略**：

| 策略 | 说明 | 适用场景 |
|------|------|----------|
| 模板化生成 | 基于预定义指令模板（基线） | 已知有效模式 |
| 概率上下文文法 | PCFG 随机变换 | 高效随机探索 |
| LLM-prompt | 高层语义指令生成 | 复杂场景模式 |
| GA 优化 | 种群式搜索优化 | 迭代进化 |

**种群元素定义**（对应代码 `sdc_fuzzing_generator.py`）：

```python
class Individual:
    instructions: List[str]      # 指令序列
    metadata:
        power_estimate: float    # 功耗估计
        coverage_vector: list    # 覆盖向量
        dependency_graph: dict   # 依赖图
        generation_strategy: str # 生成策略
        seed: int               # 随机种子
```

**变异算子**（按概率应用）：
- 插入指令：在随机位置插入指令
- 删除指令：移除冗余指令
- 替换指令：用等价指令替换
- 改变立即数：调整立即数值
- 改变内存偏移/步长：修改访存模式（强制 ≥8KB 步长以触发 Cache 驱逐）
- 改变寄存器分配：寄存器重分配
- 指令重排：保持依赖约束的乱序

**核心实现**（`microprobe/targets/arm64/policies/sdc_fuzzing_policy.py`）：

```python
class SDCSensitiveAnalyzer:
    """Pick ARM64 instructions that are more likely to expose silent faults."""
    _EXCLUDED_MNEMONICS = {
        "FMADD", "FMSUB", "FNMADD", "FNMSUB",  # FP SIMD (gem5 不支持)
        "LDP", "STP",                           # Pair memory
        "CASAL", "CAS", "CASL", "CASA",         # LSE atomics
    }
    _INCLUDED_MNEMONICS = {
        "MOVZ", "MOVK", "MOVN",  # Move
        "ADD", "SUB", "CMP",      # Arithmetic
        "AND", "ORR", "EOR",     # Logical
        "LDUR", "STUR", "LDR", "STR",  # Memory
        "B", "BL", "BEQ", "BNE", # Branch
    }
```

### 3.2 Validator Agent

**职责**：验证指令序列合法性

**两层验证**：

| 层级 | 工具/方法 | 检查内容 |
|------|-----------|----------|
| 语法层 | Capstone/LLVM disassembler | 合法 AArch64 指令、寄存器冲突、Immediate 范围、CPU 模式 |
| 语义层 | QEMU-lite 仿真器 | 短跑执行（3-5 条指令）检测异常/未定义行为/非法地址访问 |
| 运行时 |  `Runner Agent`调用qemu | 执行指令序列wrapper成的ELF 文件，返回执行结果 |

**核心实现**（`microprobe/src/microprobe/passes/sdc_analysis/validation.py`）：

```python
class CapstoneValidationPass(microprobe.passes.Pass):
    """Best-effort disassembly validation for generated instruction streams."""
    def __call__(self, building_block, dummy_target):
        # 使用 Capstone 反汇编校验每条指令的二进制编码
        # 如果解码失败，记录失败指令名
```

### 3.3 Coverage Agent

**职责**：计算微架构覆盖指标，引导迭代

**覆盖维度**：

| 覆盖类型 | 指标 | 说明 |
|----------|------|------|
| 功能覆盖 | 指令类型分布 | ALU、FMA、LDR/STR、BR、SIMD 覆盖率 |
| 微架覆盖 | ACE | 架构崩溃 susceptibility（Def-Use 数据流分析） |
| 微架覆盖 | IBR | 位翻转抗性（虚拟执行） |
| 微架覆盖 | 功能单元占用 | NEON 使用率 |
| 微架覆盖 | Cache 覆盖 | L1/L2 cache line 触达分布 |

**ACE 评分公式**（`StaticACECalculatorPass`）：

```
ACE = Σ(spans) / (n_spans × max_span)
其中 span = last_use_index - def_index（归一化到 [0, 1]）
```

**IBR 评分公式**（`StaticIBRCoveragePass`）：

```
IBR = wide_observations / total_observations
wide_observations 包括：
  - 64-bit 及以上寄存器访问（每次 ×1）
  - 128-bit 寄存器访问（每次 ×2）
  - 8-byte 及以上内存操作（每次 ×1）
  - 16-byte 内存操作（每次 ×2）
```

**综合风险评分**（`sdc_scheduler.py`）：

```python
def compute_static_score(ace_score, ibr_score, memory_pressure_score):
    return ace * ibr * (1.0 + mem * 0.25)  # 乘法确保两者都非零
```

### 3.4 Runner Agent

**职责**：封装指令序列，在仿真环境中运行

**执行流程**：
1. `sdc_materialize.py`：将 Vault 汇编序列渲染为 C 源文件（含寄存器打印哈希）
2. `aarch64-linux-gnu-gcc -static`：编译为静态 ELF
3. `qemu-aarch64`：获取 Golden Hash
4. `gem5.opt`（SE 模式）：获取 Faulted Hash
5. 差分判定：`Hash(Golden) == Hash(Faulted) ? MATCHED : SDC_FOUND`

**C 物料化模板**（`sdc_materialize.py`）：

```c
// 寄存器哈希打印逻辑
extern void sdc_benchmark_body(void);
__asm__(".text\nsdc_benchmark_body:\n  /* 注入的汇编序列 */\n  ret\n");

int main(void) {
    uint64_t sdc_digest = 0xcbf29ce484222325ULL;
    sdc_benchmark_body();
    // 遍历 X0-X30 寄存器、NZCV、SIMD 寄存器
    for (int i = 0; i < 31; i++) sdc_digest = sdc_mix_u64(sdc_digest, sdc_gprs[i]);
    sdc_digest = sdc_mix_u64(sdc_digest, sdc_nzcv);
    printf("SDC_DIGEST=%016" PRIx64 "\n", sdc_digest);
}
```

### 3.5 Power Agent

**职责**：计算指令序列功耗

**两层评估**：

| 模式 | 方法 | 精度 | 速度 |
|------|------|------|------|
| 快速估算 | 统计模型（指令能量权重之和） | 低 | 快 |
| 精准评估 | McPAT 调用（`mcpat/pypat/`） | 高 | 慢 |

**功耗评分指标**：

| 指标 | 计算方式 | 权重 |
|------|----------|------|
| energy_score | 指令能量权重之和（FMADD=10, FDIV=12, ADD=2, MOV=1） | 50% |
| didt_score | 瞬态脉冲检测：能量变化率 > 阈值 | 30% |
| ilp_bonus | 指令级并行度奖励（无 RAW 依赖） | 20% |

### 3.6 Feedback Agent

**职责**：汇总结果，生成反馈，优化下一轮生成

**分类存档**：

| 类型 | 特征 | 处理方式 |
|------|------|----------|
| SDC_FOUND | gem5 正常退出但 Hash 不一致 | 优先保留，分析 root-cause |
| GOLDEN_READY | QEMU 通过但未跑 gem5 | 进入外循环 |
| MATCHED | gem5 Hash 一致 | 保留用于统计分析 |
| INVALID | 编译失败/超时/崩溃 | 丢弃 |

**Fitness 函数**：

```python
def compute_fitness(ace_score, ibr_score, mem_score, sdc_signal, power_total):
    static_score = ace * ibr * (1 + mem * 0.25)
    return static_score * sdc_signal / (power_total + 1.0)
    # 最大化 coverage × SDC 信号，最小化功耗
```

---

## 四、核心实现

### 4.1 SQLite Vault 数据模型

**表结构**（`sdc_vault.py`）：

```sql
CREATE TABLE offline_testcases (
    test_id INTEGER PRIMARY KEY AUTOINCREMENT,
    testcase_key TEXT NOT NULL UNIQUE,
    target_name TEXT NOT NULL,
    policy_name TEXT NOT NULL,
    asm_content TEXT NOT NULL,
    ace_score REAL NOT NULL DEFAULT 0.0,
    ibr_score REAL NOT NULL DEFAULT 0.0,
    memory_pressure_score REAL NOT NULL DEFAULT 0.0,
    risk_score REAL NOT NULL DEFAULT 0.0,
    qemu_golden_hash TEXT,
    gem5_fault_hash TEXT,
    mcpat_power REAL,
    status TEXT NOT NULL DEFAULT 'PENDING',
    metadata_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX idx_offline_testcases_status_risk
ON offline_testcases(status, risk_score DESC, ace_score DESC, ibr_score DESC);
```

**状态机**：

```
PENDING ──▶ GOLDEN_READY ──▶ MATCHED
    │           │
    │           └──▶ SDC_FOUND
    │
    └──▶ INVALID (编译失败/超时)
```

### 4.2 差分测试核心逻辑

**判定逻辑**（`run_sdc_differential.py`）：

```python
def classify(compile_result, qemu_result, gem5_result,
             golden_digest, faulted_digest) -> str:
    if compile_result.returncode != 0:      return "compile_failed"
    if qemu_result.returncode != 0:          return "golden_failed"
    if gem5_result is None:                  return "golden_only"
    if gem5_result.timed_out:               return "gem5_timeout"
    if gem5_result.returncode != 0:         return "gem5_failed"
    if golden_digest is None or faulted_digest is None:
                                            return "digest_missing"
    if golden_digest != faulted_digest:     return "sdc_found"
    return "matched"
```

### 4.3 FeedbackScheduler 调度逻辑

**候选选择优先级**：

```python
status_priority = {
    "SDC_FOUND": 4,   # 最高优先级
    "GOLDEN_READY": 3,
    "PENDING": 2,
    "MATCHED": 1,     # 已验证无 SDC，但保留用于分析
}
```

**排序键**：

```python
ranked.sort(key=lambda item: (
    status_priority[item.status],  # 状态优先级
    item.fitness,                  # 综合 fitness
    item.row["risk_score"],        # 静态风险分
    -item.row["test_id"],          # 优先选新生成（test_id 大）
), reverse=True)
```

### 4.4 gem5 SDC 故障注入配置

**SE 模式配置**（`gem5/configs/example/arm/sdc_kunpeng920_se.py`）：

```python
cache_hierarchy = PrivateL1PrivateL2CacheHierarchy(
    l1d_size="64KiB",   # Kunpeng920 L1D
    l1i_size="64KiB",
    l2_size="512KiB",   # Kunpeng920 L2
)
processor = SimpleProcessor(
    cpu_type=get_cpu_type_from_str("o3"),  # O3 CPU
    isa=ISA.ARM,
    num_cores=1,
)
board = SimpleBoard(
    clk_freq="2.6GHz",  # Kunpeng920 频率
    ...
)
```

**故障请求记录**（`gem5/configs/example/arm/sdc_fault_request.py`）：

```python
@dataclass(frozen=True)
class FaultRequest:
    fault_model: str = "none"     # bit-flip, stuck-at, none
    fault_target: str = ""        # register, memory
    fault_bit: Optional[int] = None
    fault_tick: Optional[int] = None
```

---

## 五、核心 Skills

### 5.1 ISA_Constraint_Skill

**功能**：RAG 查询 ARMv8.2-A 手册，拒绝违规指令

**实现**：
- 索引 ARMv8 ISA 文档（`doc/armv8-isa/`）
- 查询指令约束条件
- 检查寄存器依赖、Immediate 范围、CPU 模式兼容性

### 5.2 Microarch_Characteristic_Skill

**功能**：匹配 TaiShan v110 微架构特性

**微架构参数**：

| 参数 | 值 |
|------|------|
| Issue Width | 4-wide OoO |
| L1 D-Cache | 64KB |
| L2 Cache | 512KB 私有 |
| L3 Cache | 共享 NUMA |
| 时钟频率 | 2.6GHz |

**约束**：
- 强制步长 ≥ 8KB 随机访问（触发 Cache 驱逐）
- 避免 L1 cache thrash
- 优化 ILP（无 RAW 依赖）

### 5.3 SDC_Sensitive_Unit_Skill

**功能**：优先敏感单元

**敏感单元优先级**：

1. NEON FMA 单元
2. L1D 一致性路径
3. L3 写回路径
4. MUL 依赖链
5. PMU 时序路径

### 5.4 Coverage_Guided_Skill

**功能**：通过分析 ACE 和 IBR，计算指令序列覆盖率

**引导策略**：
- 优先覆盖低频指令类型
- 增加 ACE/IBR 高风险序列权重
- 动态调整覆盖目标

### 5.5 OpenDCDiag_Integration_Skill

**功能**：自动生成 C wrapper，链接 OpenDCDiag 框架

**流程**：
1. 生成 `test_init()`：初始化测试环境
2. 生成 `test_run()`：执行指令序列
3. 生成 `test_finish()`：清理资源
4. 嵌入 inline assembly
5. 编译链接
6. 执行并解析结果

---

## 六、子项目详细设计

### Sub-P0: opendcdiag-arm

**目标**：增加 21 个 ARM64 SDC 测试用例，继承 x86 架构的 31 个 eigen/压缩/加解密方面用例

**新增文件**：

| 文件路径 | 功能描述 |
|---------|---------|
| `tests/cpu/arm64/sdc_test.cpp` | SDC 检测主测试（CRC32/CRC64/Checksum） |
| `tests/cpu/arm64/neon_test.cpp` | NEON 向量指令测试 |
| `tests/cpu/arm64/crypto_test.cpp` | AES/SHA 加密指令测试 |
| `framework/device/cpu/arm64/arm64_sdc_detect.cpp` | SDC 检测核心模块（CRC32/CRC64/ECC） |
| `framework/device/cpu/arm64/kunpeng920_ecc.cpp` | Kunpeng 920 ECC 内存错误检测 |
| `framework/device/cpu/arm64/arm64_cpuid.h` | ARM64 CPU ID 和特性检测 |
| `framework/device/cpu/arm64/arm64_ras.h` | ARM64 RAS（可靠性可用性可服务性） |

**SDC 检测方法**：

```cpp
enum {
    SDC_METHOD_HW_ECC = 0,
    SDC_METHOD_CRC32 = 1,
    SDC_METHOD_CRC64 = 2,
    SDC_METHOD_CHECKSUM = 3
};
// 使用 ARM64 CRC32/CRC64 指令进行数据完整性检测
// 初始化时计算 golden CRC，运行后比对
```

### Sub-P1: microprobe-arm

**目标**：增加支持 ARM64 指令流生成，并 wrapper 成 SDC 检测用例

**核心文件**：

| 文件路径 | 功能描述 |
|---------|---------|
| `targets/arm64/policies/sdc_fuzzing_policy.py` | SDC 敏感指令分析器 + Policy 入口 |
| `targets/arm64/policies/sdc_detect.py` | SDC 检测专用 Policy |
| `src/microprobe/passes/sdc_analysis/offline_coverage.py` | ACE/IBR/Memory Pressure 计算 |

**SDCSensitiveAnalyzer 过滤规则**：

```python
_EXCLUDED_MNEMONICS = {
    "FMADD", "FMSUB", "FNMADD", "FNMSUB",  # gem5 不支持
    "LDP", "STP",                            # Pair memory
    "CASAL", "CAS", "CASL", "CASA",         # LSE atomics
    "LDAPR", "STLR", "LDAR", "STLAR",
}
_INCLUDED_MNEMONICS = {
    "MOVZ", "MOVK", "MOVN", "ADD", "SUB", "CMP", "CMN",
    "AND", "ORR", "EOR", "TST", "LSL", "LSR", "ASR", "ROR",
    "LDUR", "STUR", "LDR", "STR", "B", "BL", "BEQ", "BNE", "BGT", "BLT", "NOP",
}
```

### Sub-P2-1: qemu 仿真验证

**目标**：在内循环中，负责验证最终生成指令流的wrapper的正确性。在外循环中，QEMU 作为 ISA 金标准，验证指令序列的语义正确性

**执行方式**：

```bash
qemu-aarch64 -L /usr/aarch64-linux-gnu \
    -E LD_LIBRARY_PATH=./third_party/lib \
    ./build-arm64/opendcdiag --cpu=on --total-time 60s
```

**用途**：
1. 快速验证生成的汇编是否可执行
2. 生成 Golden Hash（无故障注入的基准执行结果）

### Sub-P2-2: gem5 SDC 故障注入与仿真

**目标**：通过 gem5 SE 模式执行带故障注入的指令流，与 QEMU 结果进行差分

**核心配置**（`gem5/configs/example/arm/sdc_kunpeng920_se.py`）：

```python
# Kunpeng920-like cache hierarchy
cache_hierarchy = PrivateL1PrivateL2CacheHierarchy(
    l1d_size="64KiB",
    l1i_size="64KiB",
    l2_size="512KiB",
)
# O3 CPU for detailed timing simulation
processor = SimpleProcessor(
    cpu_type="o3",  # 乱序执行引擎
    isa=ISA.ARM,
    num_cores=1,
)
```

**故障注入接口**（`gem5/configs/example/arm/sdc_fault_request.py`）：

```python
@dataclass
class FaultRequest:
    fault_model: str  # "bit-flip", "stuck-at", "none"
    fault_target: str # "register", "memory"
    fault_bit: Optional[int]  # 0-63 for registers
    fault_tick: Optional[int] # injection tick
```

### Sub-P3: mcpat-arm

**目标**：通过 gem5 输出和 ARM64 微架构/工艺配置，计算指令流功耗

**核心模块**（`mcpat/pypat/`）：

| 文件 | 功能 |
|------|------|
| `conversion/arm64_kunpeng920.py` | Kunpeng920 功耗模型定义 |
| `conversion/gem5_to_mcpat.py` | gem5 统计到 McPAT 输入格式转换 |
| `conversion/profiles.py` | 微架构参数模板（issue width, cache size 等） |

**McPATBackend 适配器**（`power_backends/mcpat_backend.py`）：

```python
class McPATBackend:
    template_profile: str = "arm64-kunpeng920"
    def run(self, target_dir: Path) -> Dict[str, Any]:
        # 调用 pypat/conversion/convert.py 进行功耗计算
        # 返回 power_total, power_dynamic, power_leakage 等
```

**功耗范围**：基于 1000 次 ARM64 测试，功耗区间为 **0.1030 ~ 1.9994 W**（平均 1.0679 W）

---

## 七、工作流程

### 7.1 主循环

```
1. 初始化：创建各组件实例，加载 Skills
2. 生成阶段：Generator.generate_batch(count=50)
3. 校验阶段：Validator.validate_batch(candidates)
4. 评估阶段：Coverage.analyze() + Power.analyze() 并行
5. 排序阶段：加入 CandidatePool，计算 TotalScore
6. 学习阶段：RL Agent 从 Top 候选中学习，更新变异权重
7. 反馈阶段：Feedback Agent 生成优化 Prompt
8. 输出：Top 10 候选用于 gem5 仿真
```

### 7.2 高频内循环

```python
while True:
    # 批量生成（高频）
    candidates = generator.generate(count=50)

    # 校验 + 覆盖计算
    valid_candidates = []
    for c in candidates:
        if validator.validate(c):
            c.coverage = coverage.analyze(c)
            valid_candidates.append(c)

    # 存入 Vault
    pool.add(valid_candidates)

    # 批量拉取（低频）
    batch = pool.fetch_top_k_risky(size=10)

    # 并行功耗评估 + 仿真
    results = parallel_execute(power, runner, batch)

    # 打标签
    for r in results:
        label(r)  # SDC/异常/高覆盖低功耗/高功耗

    # 反馈给 Generator
    feedback.send(results)
```

### 7.3 SDC 触发场景

| 场景 | 描述 | 检测指标 |
|------|------|----------|
| 电压 droop | 高功耗指令瞬态导致供电不足 | didt_score |
| 架构状态错误传播 | 位翻转通过数据流传播 | IBR |
| 长生命周期脆弱性 | 寄存器长时间存活增加出错概率 | ACE |

---

## 八、文件结构

```
sdc-fuzzing/
├── Sub-P0: opendcdiag-arm/
│   ├── tests/cpu/arm64/
│   │   ├── sdc_test.cpp       # SDC 检测主测试
│   │   ├── neon_test.cpp       # NEON 指令测试
│   │   └── crypto_test.cpp     # 加密指令测试
│   └── framework/device/cpu/arm64/
│       ├── arm64_sdc_detect.cpp # SDC 检测核心
│       └── kunpeng920_ecc.cpp   # ECC 检测
│
├── Sub-P1: microprobe/
│   ├── targets/arm64/policies/
│   │   ├── sdc_fuzzing_policy.py  # SDC 敏感指令 Policy
│   │   └── sdc_detect.py           # SDC 检测 Policy
│   ├── src/microprobe/passes/sdc_analysis/
│   │   └── offline_coverage.py      # ACE/IBR 计算 Pass
│   ├── targets/generic/tools/
│   │   └── mp_sdc_offline_gen.py    # 离线生成 CLI
│   └── sdc_fuzzing_generator.py     # 批量生成引擎
│
├── Sub-P2-1: qemu/
│   └── (标准 QEMU，ARM64 支持)
│
├── Sub-P2-2: gem5/
│   ├── configs/example/arm/
│   │   ├── sdc_kunpeng920_se.py    # Kunpeng920 SE 配置
│   │   └── sdc_fault_request.py    # 故障注入请求
│   └── build/ARM/
│       └── gem5.opt                # 编译后 gem5
│
├── Sub-P3: mcpat/
│   ├── pypat/
│   │   ├── conversion/
│   │   │   ├── arm64_kunpeng920.py # Kunpeng920 功耗模型
│   │   │   └── gem5_to_mcpat.py    # gem5→McPAT 转换
│   │   └── conversion/profiles.py    # 微架构参数模板
│   └── mcpat/                       # McPAT 主程序
│
├── sdc_discovery/                    # 核心 Agent 系统
│   ├── main.py                      # 主入口
│   ├── generation_layer.py           # PCFG + GA 指令生成
│   ├── trigger_engine.py             # 功耗触发引擎
│   ├── ace_engine.py                 # ACE 评估引擎
│   ├── ibr_engine.py                 # IBR 评估引擎
│   ├── candidate_pool.py             # 候选池管理
│   ├── rl_agent.py                  # Q-learning 强化学习代理
│   ├── validator.py                  # ISA 合法性验证
│   └── skills/
│       ├── isa_constraint_skill.py
│       ├── microarch_skill.py
│       ├── sdc_sensitive_skill.py
│       └── opendcdiag_skill.py
│
├── sdc_vault.py                      # SQLite Vault 接口
├── sdc_scheduler.py                  # 反馈调度器
├── sdc_campaign.py                   # 外循环 Campaign
├── sdc_materialize.py                # C 物料化
├── run_sdc_differential.py            # 差分测试执行器
├── sdc_preflight.py                   # 环境检查
└── power_backends/
    ├── mcpat_backend.py              # McPAT 后端
    └── opendcdiag_backend.py          # OpenDCDiag 后端
```

---

## 九、强化学习自进化

### 9.1 RL Agent 设计

**算法**：Q-learning

**状态空间**：

```python
state = {
    trigger_score: discretized to bins (0-4),
    ace_score: discretized to bins (0-4),
    ibr_score: discretized to bins (0-4)
}
```

**动作空间**（调整变异权重）：

| 动作 | 说明 |
|------|------|
| cache_thrash_prob | Cache 抖动概率 |
| vector_insert_prob | 向量插入概率 |
| fp_mix_prob | 浮点混合概率 |
| load_store_prob | 访存概率 |
| branch_insert_prob | 分支插入概率 |
| register_reuse_prob | 寄存器重用概率 |
| crypto_insert_prob | 加密指令插入概率 |

**探索策略**：ε-greedy，ε 衰减

### 9.2 候选池管理

**综合评分公式**：

```
TotalScore = α × Trigger + β × ACE + γ × IBR
```
- 默认权重：α=0.4, β=0.3, γ=0.3

**动态阈值**：
- 计算 Top 5% 百分位数作为动态阈值
- 高于阈值的候选进入下一阶段（gem5 仿真）

---

## 十、测试结果

### 10.1 opendcdiag-arm 测试结果（2026-03-28）

All 52 tests passed with quality=-1：

| 类别 | 测试数 | 状态 |
|------|--------|------|
| SDC Tests | 21 | ✓ 全部通过 |
| ARM Tests | 9 | ✓ 全部通过 |
| Eigen Tests | 14 | ✓ 全部通过 |
| Compression Tests | 8 | ✓ 全部通过 |

### 10.2 功耗测试结果（1000 次 ARM64 测试）

| 指标 | 值 |
|------|------|
| 架构 | ARM64 (armv8-a) |
| 功耗范围 | 0.1030 ~ 1.9994 W |
| 平均功耗 | 1.0679 W |

---

## 十一、快速开始

```bash
# 1. 环境检查
python3 sdc_preflight.py --verbose

# 2. 安装依赖
./setup_environment.sh

# 3. 编译 gem5
./build_gem5.sh ARM opt 8

# 4. 生成测试用例
export PYTHONPATH="${PYTHONPATH}:$(pwd)/microprobe/src"
python3 microprobe/targets/generic/tools/mp_sdc_offline_gen.py \
    --target armv8-common-cortex-a53-aarch64_linux_gcc \
    --policy sdc_fuzzing \
    --output-dir ./artifacts/testcases \
    --num-testcases 10

# 5. 运行差分测试
python3 run_sdc_differential.py \
    artifacts/testcases/test_001.c \
    --compiler aarch64-linux-gnu-gcc \
    --qemu-binary qemu-aarch64 \
    --gem5-binary gem5/build/ARM/gem5.opt \
    --fault-model bit-flip \
    --fault-target register \
    --timeout 300

# 6. 运行 Campaign
python3 sdc_campaign.py run \
    --vault-path artifacts/sdc_vault.sqlite3 \
    --batch-size 10
```
