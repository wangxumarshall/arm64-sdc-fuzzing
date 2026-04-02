# 1. SDC Agent 方案
- **概述：** SDC-agent Project用于ARM64 SDC (Silent Data Corruption) 检测与功耗分析。通过借助AI模型，通过microprobe生成随机指令流(Sub-P1)、qemu仿真执行(Sub-P2-1)、gem5故障注入差分验证(Sub-P2-2)，McPAT功耗计算(Sub-P3)，筛选高价值的SDC检测用例，最后统一封装到OpenDCDiag-ARM(Sub-P0)真实环境压测，实现全面的CPU可靠性验证。

- **愿景：** 数据中心 ARM 服务器提供可靠的 CPU SDC故障检测能力，保障硬件稳定运行。

- **目标：** 设计一套自动化 SDC 用例生成的 Agent 系统，通过 "生成-校验-覆盖-检测-反馈" 闭环，自进化地寻找高风险指令组合，用于疑似SDC问题筛选和高效辅助SDC定界/定位。

---

## 1.1 系统架构

### 1.1.1 整体架构

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                            SDC Agent System                                 │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │                    高频内循环：SDC用例生成闭环                        │    │
│  │  ┌──────────────┐    ┌──────────────┐    ┌──────────────────────┐   │    │
│  │  │  Generator   │───▶│  Validator   │───▶│      Coverage      │   │    │
│  │  │   Agent      │    │   Agent      │    │       Agent          │   │   │
│  │  └──────────────┘    └──────────────┘    └──────────────────────┘   │   │
│  │         │                                          │                │   │
│  │         ▼                                          ▼                │   │
│  │  ┌──────────────────────────────────────────────────────────────┐   │   │
│  │  │                    合法测试用例池                             │   │   │
│  │  └──────────────────────────────────────────────────────────────┘   │   │
│  │                              │                                      │   │
│  │                              ▼                                      │   │
│  │  ┌──────────────┐    ┌──────────────┐    ┌──────────────────────┐   │   │
│  │  │    Runner    │    │    Power     │    │      Feedback        │   │   │
│  │  │    Agent     │    │    Agent     │    │       Agent          │   │   │
│  │  └──────────────┘    └──────────────┘    └──────────────────────┘   │   │
│  │         │                  │                    │                   │   │
│  │         ▼                  ▼                    ▼                   │   │
│  │  ┌──────────────┐    ┌──────────────┐    ┌──────────────────────┐   │   │
│  │  │ SDC Wrapper  │    │   McPAT      │    │    优化Prompt        │   │   │
│  │  │   qemu仿真   │     │   功耗计算    │    │    注入下一轮         │   │   │
│  │  └──────────────┘    └──────────────┘    └──────────────────────┘   │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                            │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                    低频外循环                                        │   │
│  │  ┌──────────────────────────────────────────────────────────────┐   │   │
│  │  │  Generator + Validator + Coverage → 合法用例池                │   │   │
│  │  │         ▲                                              │     │   │   │
│  │  │         │                                     批量拉取  ▼     │   │   │
│  │  │  ┌──────────────┐    ┌──────────────┐    ┌──────────────────┐ │  │   │
│  │  │  │    Power     │    │   Runner     │    │     Feedback     │ │  │   │
│  │  │  │   Agent      │    │   Agent      │    │      Agent       │ │  │   │
│  │  │  └──────────────┘    └──────────────┘    └──────────────────┘ │  │   │
│  │  │         │                  │                    │             │  │   │
│  │  │         ▼                  ▼                    ▼             │  │   │
│  │  │  ┌──────────────┐    ┌──────────────┐    ┌──────────────────┐ │  │   │
│  │  │  │   McPAT      │    │ OpenDCDiag   │    │ 批量打标签         │ │  │   │
│  │  │  │  功耗评估    │     │   真实环境   │    │  喂给Generator     │ │  │   │
│  │  │  └──────────────┘    └──────────────┘    └──────────────────┘ │  │   │
│  │  └───────────────────────────────────────────────────────────────┘  │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                            │
└────────────────────────────────────────────────────────────────────────────┘
```

### 1.1.2 数据流

```
指令序列生成 → ISA合法性校验 → 微架构覆盖计算 → 功耗评估 → 仿真执行 → 结果反馈 → 优化Prompt
     ↑                                                                     │
     └────────────────────────────────────── 反馈闭环 ──────────────────────┘
```

---

## 1.2 核心 Agent 设计与实现

### 1.2.1 Generator Agent

**职责**：负责生成 AArch64 指令序列

**输入**：
- ISA_Constraint_Skill：ARMv8.2-A 指令约束
- Microarch_Characteristic_Skill：TaiShan v110 微架构特性
- SDC_Sensitive_Unit_Skill：敏感单元优先级

**实现方式**：混合生成器

| 生成策略 | 说明 | 适用场景 |
|----------|------|----------|
| 模板化生成 | 基于预定义指令模板（基线） | 已知有效模式 |
| 概率上下文文法 | PCFG 随机变换 | 高效随机探索 |
| LLM-prompt | 高层语义指令生成 | 复杂场景模式 |
| GA优化 | 种群式搜索优化 | 迭代进化 |

**种群元素定义**：
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
- 改变内存偏移/步长：修改访存模式
- 改变寄存器分配：寄存器重分配
- 指令重排：保持依赖约束的乱序

**交叉算子**：
- 将两个序列的子区段交换
- 重连依赖边
- 运行 Validator 验证合法性

**Prompt 设计**：
- microarch 特性作为可复用模板
- 少量示例 + 禁止清单
- SDC sensitive hints 注入

### 1.2.2 Validator Agent

**职责**：验证指令序列合法性

**输入**：指令序列

**输出**：校验结果（通过/失败 + 错误信息）

**实现方式**：两层验证

| 层级 | 工具/方法 | 检查内容 |
|------|-----------|----------|
| 语法层 | Capstone/LLVM disassembler | 合法 AArch64 指令、寄存器冲突、Immediate 范围、CPU 模式 |
| 语义层 | QEMU-lite 仿真器 | 短跑执行（3-5条指令）检测异常/未定义行为/非法地址访问 |

### 1.2.3 Coverage Agent

**职责**：计算微架构覆盖指标，引导迭代

**输入**：指令序列

**输出**：覆盖指标

**覆盖维度**：

| 覆盖类型 | 指标 | 说明 |
|----------|------|------|
| 功能覆盖 | 指令类型分布 | ALU、FMA、LDR/STR、BR、SIMD 覆盖率 |
| 微架覆盖 | ACE | 架构崩溃 susceptibility（Def-Use 数据流分析） |
| 微架覆盖 | IBR | 位翻转抗性（虚拟执行） |
| 微架覆盖 | 功能单元占用 | NEON 使用率 |
| 微架覆盖 | Cache 覆盖 | L1/L2 cache line 触达分布 |

**ACE 评分公式**：
```
ACE = (live_time_score × 0.6 + fanout_bonus × 0.4) × (1 - WAW_penalty/10)
```
- live_time：变量存活周期（最后使用索引 - 定义索引）
- fanout_bonus：寄存器被引用次数
- WAW penalty：写后写危害比例

**IBR 评分公式**：
```
fault_penetration = flip_rate × 0.6 + entropy × 0.4
```
- flip_rate：popcount(old XOR new) - 寄存器位翻转数
- entropy：受影响寄存器比例

### 1.2.4 Runner Agent

**职责**：封装指令序列，在仿真环境中运行 OpenDCDiag-ARM

**输入**：指令序列 + 测试配置

**输出**：仿真数据 + 缺陷报告

**执行流程**：
1. 生成 C wrapper（init/run/finish）
2. 嵌入 inline 汇编
3. 链接 OpenDCDiag 框架
4. 执行并捕获结果
5. 解析缺陷报告

### 1.2.5 Power Agent

**职责**：计算指令序列功耗

**输入**：指令序列

**输出**：功耗指标

**实现方式**：两层评估

| 模式 | 方法 | 精度 | 速度 |
|------|------|------|------|
| 快速估算 | 统计模型 | 低 | 快 |
| 精准评估 | McPAT 调用 | 高 | 慢 |

**功耗评分指标**：

| 指标 | 计算方式 | 权重 |
|------|----------|------|
| energy_score | 指令能量权重之和（FMADD=10, FDIV=12, ADD=2, MOV=1） | 50% |
| didt_score | 瞬态脉冲检测：能量变化率 > 阈值 | 30% |
| ilp_bonus | 指令级并行度奖励（无 RAW 依赖） | 20% |

**扩展指令支持**：
- 密码学指令：AESE, AESD, SHA1H, SHA256H, SM3SS1, SM4E
- 矩阵指令：MEQ, MADD, MSUB
- SVE 指令：ADDV, ANDV, SMAXV
- 同步指令：LDXP, STXP, DMB, DSB

### 1.2.6 Feedback Agent

**职责**：汇总结果，生成反馈，优化下一轮生成

**输入**：
- 指令序列
- 功耗指标
- 变异策略
- 仿真结果

**输出**：优化后的 Prompt/权重

**分类存档**：
| 类型 | 特征 | 处理方式 |
|------|------|----------|
| SDC/异常 | 触发硬件错误 | 优先保留，分析 root-cause |
| 高覆盖低功耗 | ACE/IBR 高但功耗低 | 调整生成策略增加功耗 |
| 高功耗 | 功耗分数高 | 保留用于 stress 测试 |

**反馈内容**：
- 变异历史链（支持 root-cause 分析）
- 权重分布更新（如增加 NEON-FMA 链生成概率）
- 特定触发路径生成（如 L1D 一致性冲突）

---

## 1.3 核心 Skills

### 1.3.1 ISA_Constraint_Skill

**功能**：RAG 查询 ARMv8.2-A 手册，拒绝违规指令

**实现**：
- 索引 ARMv8 ISA 文档
- 查询指令约束条件
- 检查寄存器依赖、Immediate 范围、CPU 模式兼容性

### 1.3.2 Microarch_Characteristic_Skill

**功能**：匹配 TaiShan v110 微架构特性

**微架构参数**：
- Issue Width：4-wide OoO
- L1 D-Cache：64KB
- L2 Cache：512KB 私有
- L3 Cache：共享 NUMA

**约束**：
- 强制步长 ≥ 8KB 随机访问
- 避免 L1 cache thrash
- 优化 ILP（无 RAW 依赖）

### 1.3.3 SDC_Sensitive_Unit_Skill

**功能**：优先敏感单元

**敏感单元优先级**：
1. NEON FMA 单元
2. L1D 一致性路径
3. L3 写回路径
4. MUL 依赖链
5. PMU 时序路径

### 1.3.4 ISA_validation_Skill

**功能**：验证指令流序列的合法性

**检查项**：
- 指令语法正确性
- 寄存器读写冲突
- 立即数范围
- 内存对齐
- 异常分支目标

### 1.3.5 Coverage_Guided_Skill

**功能**：通过分析 ACE 和 IBR，计算指令序列覆盖率

**引导策略**：
- 优先覆盖低频指令类型
- 增加 ACE/IBR 高风险序列权重
- 动态调整覆盖目标

### 1.3.6 OpenDCDiag_Integration_Skill

**功能**：自动生成 C wrapper，链接 OpenDCDiag 框架

**流程**：
1. 生成 test_init()：初始化测试环境
2. 生成 test_run()：执行指令序列
3. 生成 test_finish()：清理资源
4. 嵌入 inline assembly
5. 编译链接
6. 执行并解析结果

---

## 1.4. 强化学习自进化

### 1.4.1 RL Agent 设计

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
- cache_thrash_prob
- vector_insert_prob
- fp_mix_prob
- load_store_prob
- branch_insert_prob
- register_reuse_prob
- crypto_insert_prob

**探索策略**：ε-greedy，ε 衰减

### 1.4.2 候选池管理

**综合评分公式**：
```
TotalScore = α × Trigger + β × ACE + γ × IBR
```
- 默认权重：α=0.4, β=0.3, γ=0.3

**动态阈值**：
- 计算 Top 5% 百分位数作为动态阈值
- 高于阈值的候选进入下一阶段（gem5 仿真）

---

## 1.5 工作流程

### 1.5.1 主循环

1. **初始化**：创建各组件实例，加载 Skills
2. **生成阶段**：`Generator.generate_batch(count=50)`
3. **校验阶段**：`Validator.validate_batch(candidates)`
4. **评估阶段**：并行运行 Coverage/Power Agent
   ```python
   coverage_result = coverage.analyze(instructions)
   power_result = power.analyze(instructions)
   ```
5. **排序阶段**：加入 CandidatePool，计算 TotalScore
6. **学习阶段**：RL Agent 从 Top 候选中学习，更新变异权重
7. **反馈阶段**：Feedback Agent 生成优化 Prompt
8. **输出**：Top 10 候选用于 gem5 仿真

### 1.5.2 高频内循环

```
while True:
    # 批量生成
    candidates = generator.generate(count=50)

    # 校验 + 覆盖计算（高频）
    valid_candidates = []
    for c in candidates:
        if validator.validate(c):
            c.coverage = coverage.analyze(c)
            valid_candidates.append(c)

    # 存入用例池
    pool.add(valid_candidates)

    # 批量拉取（低频）
    batch = pool.fetch_batch(size=10)

    # 并行功耗评估 + 仿真
    results = parallel_execute(power, runner, batch)

    # 打标签
    for r in results:
        label(r)  # SDC/异常/高覆盖低功耗/高功耗

    # 反馈给 Generator
    feedback.send(results)
```

---

## 1.6 目标与应用

### 1.6.1 SDC 触发场景

| 场景 | 描述 | 检测指标 |
|------|------|----------|
| 电压 droop | 高功耗指令瞬态导致供电不足 | didt_score |
| 架构状态错误传播 | 位翻转通过数据流传播 | IBR |
| 长生命周期脆弱性 | 寄存器长时间存活增加出错概率 | ACE |

### 1.6.2 输出

- Top 候选指令序列用于 gem5 全系统仿真验证
- SDC 触发路径分析报告
- 微架构覆盖率报告

---

## 1.7 文件结构

- **结构**：

```
[Project] sdc-agent/
├── [Sub-P1] microprobe-arm/      # 增加支持arm64指令流生成，并wrapper成SDC检测用例
├── [Sub-P2-1] qemu/              # qemu仿真执行
├── [Sub-P2-2] gem5/              # 增加SDC故障注入能力，通过qemu和gem5的差分测试进行SDC检测
├── [Sub-P3] mcpat/               # 增加支持 arm64架构，通过gem5输出和arm64微架构/工艺配置，计算指令流功耗
├── [Sub-P0] opendcdiag-arm/      # 增加21个arm64 SDC测试用例，继承x86架构的31个eigen/压缩/加解密方面用例
├── sdc_discovery/
|   ├── main.py                      # 主入口程序
|   ├── generation_layer.py          # PCFG + GA 指令生成 (Generator Agent)
|   ├── trigger_engine.py            # 功耗触发引擎 (Power Agent)
|   ├── ace_engine.py                # 架构崩溃评估引擎 (Coverage Agent)
|   ├── ibr_engine.py                # 位翻转抗性引擎 (Coverage Agent)
|   ├── candidate_pool.py            # 候选池管理
|   ├── rl_agent.py                  # Q-learning 强化学习代理 (Feedback Agent)
|   ├── validator.py                 # ISA 合法性验证 (Validator Agent)
|   └── skills/
|       ├── isa_constraint_skill.py  # ISA_Constraint_Skill
|       ├── microarch_skill.py       # Microarch_Characteristic_Skill
|       ├── sdc_sensitive_skill.py   # SDC_Sensitive_Unit_Skill
|       └── opendcdiag_skill.py      # OpenDCDiag_Integration_Skill
└── doc/                          # 文档
    └── armv8-isa/                # ARMv8 ISA 指令文档
```

---

# [Sub-P0] opendc-diag-arm：增加21个arm64 SDC测试用例，继承x86架构的31个eigen/压缩/加解密方面用例

## [opendcdiag-arm完成适配] 2026-3-28 12:30

### 1. 兼容x86版本原有功能模块

#### 1.1 测试模块 (tests/cpu/)

| 类别 | 测试 | x86 | ARM64|
|------|------|------|------|
| eigen_gemm | 矩阵乘法 (float/double/complex) | 支持 | 支持 |
| eigen_sparse | 稀疏矩阵 | 支持 | 支持 |
| eigen_svd | 奇异值分解 (svd, svd_double, svd_cdouble, svd_fvectors) | 支持 | 支持 |
| eigen_svd_jacobi | 高精度奇异值分解 | 支持 | 支持 |
| ifs | 频率扫描 (Intel专用) | 支持 | 不支持 |
| openssl | SHA加密 | 支持 | 支持 |
| zlib / zstd | 压缩测试 | 支持 | 支持 |

#### 1.2 框架模块 (framework/)
| 模块 | x86 | ARM64 |
|------|------|------|
| **CPU** | 使用 cpuid 进行 CPU 功能检测 | arm64_cpuid.h (使用getauxval|
| **SIMD** | AVX, AVX2, AVX-512, AMX (高级矩阵扩展) | NEON/SVE | 
| **GPU** | Intel Level Zero | N/A |
| **拓扑** | x86 特定的 CPU 拓扑结构 | arm64_topology.cp |

### 2. ARM64新增功能

#### 2.1 SDC检测测试套件 (tests/cpu/arm64_sdc/)

ARM64 版本新增 **SDC (Silent Data Corruption) 检测测试**，包含 20+ 个独立测试:

| 测试文件 | 功能描述 |
|---------|---------|
| `sdc_matmul_test.cpp` | 矩阵乘法 SDC 检测 |
| `sdc_neon_test.cpp` | NEON 向量指令 SDC 检测 |
| `sdc_neon2_test.cpp` | 扩展 NEON 测试 |
| `sdc_sve_test.cpp` | SVE (Scalable Vector Extension) 测试 |
| `sdc_fp16_test.cpp` | 半精度浮点 (FP16) SDC 检测 |
| `sdc_float_test.cpp` | 单精度浮点 SDC 检测 |
| `sdc_crypto_test.cpp` | AES/SHA 加密指令 SDC 检测 |
| `sdc_crypto2_test.cpp` | 扩展加密指令测试 |
| `sdc_sha_test.cpp` | SHA 哈希指令测试 |
| `sdc_crc32_test.cpp` | CRC32 校验测试 |
| `sdc_crc64_test.cpp` | CRC64 校验测试 |
| `sdc_bitop_test.cpp` | 位操作指令测试 |
| `sdc_branch_test.cpp` | 分支指令测试 |
| `sdc_loadstore_test.cpp` | 加载/存储指令测试 |
| `sdc_memory_test.cpp` | 内存操作测试 |
| `sdc_reduction_test.cpp` | 归约操作测试 (求和/最大/最小) |
| `sdc_sysreg_test.cpp` | 系统寄存器访问测试 |
| `sdc_atomic_test.cpp` | 原子操作测试 |
| `sdc_dpe_test.cpp` | 数据处理引擎 (DPE) 测试 |
| `sdc_stress_test.cpp` | 综合压力测试 |

#### 2.2 新增框架代码 (framework/device/cpu/arm64/)

| 文件 | 功能描述 |
|-----|---------|
| `arm64_cpuid.h` | ARM64 CPU ID 和特性检测 (HWCAP/HWCAP2) |
| `arm64_cpu_device.h` | ARM64 CPU 设备信息结构体 |
| `arm64_sdc_detect.cpp` | **SDC 检测核心模块** - CRC32/CRC64/ECC 检测 |
| `arm64_topology.cpp` | ARM64 CPU 拓扑结构 |
| `arm64_ras.h` | ARM64 RAS (Reliability Availability Serviceability) |
| `arm64_privilege.h` | 特权模式相关定义 |
| `kunpeng920_ecc.cpp` | **华为 Kunpeng 920 ECC 内存错误检测** |

### 3. 构建系统差异

#### 3.1 交叉编译配置

**x86 版本**:
- `meson-cross-win32.ini`
- `meson-darwin.ini`
- `meson-freebsd.ini`

**ARM64 版本新增**:
- `cross-file-aarch64.txt` - ARM64 Linux 交叉编译配置

```ini
[binaries]
c = 'aarch64-linux-gnu-gcc'
cpp = 'aarch64-linux-gnu-g++'
cpu_family = 'aarch64'
```

- `meson-cross-arm64.ini` - ARM64 构建配置

#### 3.2 构建选项差异

**ARM64 版本新增选项** (`meson_options.txt`):

```python
option('kunpeng_optimize', type : 'boolean', value : false,
    description : 'Enable Kunpeng 920 specific optimizations')

option('arm64_sdc_tests', type : 'boolean', value : true,
    description : 'Enable ARM64 SDC detection tests')

option('eigen_tests', type : 'boolean', value : false,
    description : 'Enable Eigen-based tests (disabled by default on ARM64)')
```

#### 3.3 测试编译标志

**ARM64 版本** (`tests/cpu/arm64_sdc/meson.build`):

```python
arm64_sdc_cpp_flags = [
    '-march=armv8.2-a+crc+crypto+dotprod+fp16',
]
```

### 4. CPU 特性检测差异

#### 4.1 x86 版本

- 使用 `cpuid` 指令
- 检测 Intel/AMD 特定功能
- 支持: AVX, AVX2, AVX-512, AMX, AES-NI, SHA-NI 等

#### 4.2 ARM64 版本

- 使用 `getauxval(AT_HWCAP)` 系统调用
- 读取系统寄存器 (MIDR, ID_AA64PFR0, ID_AA64ISAR0 等)

**支持的 ARM64 特性**:

| 特性 | 描述 |
|------|------|
| CRC32 | CRC32 扩展 |
| AES | ARM Crypto Extension - AES |
| SHA1/SHA2 | ARM Crypto Extension - SHA |
| SHA512 | SHA-512 扩展 |
| SM3/SM4 | 国密算法 |
| SVE/SVE2 | 可扩展矢量扩展 |
| PAuth | 指针认证 |
| MTE | 内存标签扩展 |
| I8MM | 整数矩阵乘 |
| DotProd | 点积指令 |
| FP16 | 半精度浮点 |

#### 4.3 新增第三方依赖

ARM64 版本在 `third-part/` 目录下新增:
- `eigen-5.0.0/` - Eigen 库 (解决 GCC 12+ 兼容性问题)
- `eigen_arm64_build_guide.md` - Eigen ARM64 构建指南

### 5. 结论

ARM64 版本是 x86 版本的重大扩展，主要新增了:

1. **完整的 SDC (Silent Data Corruption) 检测框架**
   - 这是一个独立的测试模块，专门用于检测 ARM64 CPU 上的静默数据损坏
   - 包含 20+ 个针对不同指令类型的 SDC 检测测试

2. **ARM64 架构特定功能**
   - SVE (Scalable Vector Extension) 完整测试
   - MTE (Memory Tagging Extension) 测试
   - PAuth (指针认证) 支持
   - I8MM (整数矩阵乘) 支持
   - ARM Crypto Extension 完整测试

3. **构建系统适配**
   - 交叉编译配置 (aarch64-linux-gnu)
   - ARM64 特定的编译器选项
   - 新增构建选项

### 6. Test Results (2026-03-28)

All 52 tests passed with quality=-1:

#### SDC Tests (21 tests) ✓

| Test | Status |
|------|--------|
| arm64_sdc | ✓ pass |
| arm64_sdc_crc32 | ✓ pass |
| arm64_sdc_memory | ✓ pass |
| arm64_sdc_neon | ✓ pass |
| arm64_sdc_neon2 | ✓ pass |
| arm64_sdc_crypto | ✓ pass |
| arm64_sdc_stress | ✓ pass |
| arm64_sdc_sha | ✓ pass |
| arm64_sdc_float | ✓ pass |
| arm64_sdc_crypto2 | ✓ pass |
| arm64_sdc_atomic | ✓ pass |
| arm64_sdc_matmul | ✓ pass |
| arm64_sdc_sve | ✓ pass |
| arm64_sdc_sysreg | ✓ pass |
| arm64_sdc_fp16 | ✓ pass |
| arm64_sdc_loadstore | ✓ pass |
| arm64_sdc_branch | ✓ pass |
| arm64_sdc_bitop | ✓ pass |
| arm64_sdc_reduction | ✓ pass |
| arm64_sdc_dpe | ✓ pass |
| arm64_sdc_crc64 | ✓ pass |

#### ARM Tests (9 tests) ✓

| Test | Status |
|------|--------|
| neon_add | ✓ pass |
| arm_crypto | ✓ pass |
| neon_perf | ✓ pass |
| arm64_stress | ✓ pass |
| arm64_rng_test | ✓ pass |
| bf16_gemm_test | ✓ pass |
| mte_test | ✓ pass |
| sve_width_test | ✓ pass |

#### Eigen Tests (14 tests) ✓

| Test | Status |
|------|--------|
| eigen_gemm_double14 | ✓ pass |
| eigen_gemm_cdouble_dynamic_square | ✓ pass |
| eigen_gemm_double_dynamic_square | ✓ pass |
| eigen_gemm_float_dynamic_square | ✓ pass |
| eigen_sparse | ✓ pass |
| eigen_svd | ✓ pass |
| eigen_svd_cdouble_noavx512 | ✓ pass |
| eigen_svd_double2 | ✓ pass |
| eigen_svd_double | ✓ pass |
| eigen_svd_fvectors | ✓ pass |
| eigen_svd_jacobi | ✓ pass |
| eigen_svd_jacobi_cdouble | ✓ pass |
| eigen_svd_jacobi_double | ✓ pass |
| eigen_svd_jacobi_fvectors | ✓ pass |

#### Compression Tests (8 tests) ✓

| Test | Status |
|------|--------|
| zstd19 | ✓ pass |
| zstd | ✓ pass |
| zstd1 | ✓ pass |
| zstd_aaa | ✓ pass |
| zfuzz | ✓ pass |
| zlib9 | ✓ pass |
| zlib | ✓ pass |
| zlib1 | ✓ pass |
| zlib_aaa | ✓ pass |


### 7. Test Results (2026-03-26)


#### 测试质量等级

OpenDCDiag测试按质量等级分类：

| 等级 | 名称 | 说明 | 运行条件 |
|------|------|------|----------|
| -1 | SKIP | 跳过级别 | `quality >= -1` |
| 0 | BETA | Beta测试 | `quality >= 0` |
| 1 | (无) | 内部使用 | `quality >= 1` |
| 2 | PROD | 生产就绪 (默认) | `quality >= 2` |

**注意**: 默认质量等级为2 (PROD)。低于2级的测试需要显式指定质量参数。

#### Quality=1 测试 (19个)

| 测试 | 类别 | 描述 |
|------|------|------|
| eigen_gemm_double14 | Eigen GEMM | 双精度矩阵乘法 (14x14) |
| eigen_gemm_cdouble_dynamic_square | Eigen GEMM | 复数双精度动态矩阵乘法 |
| eigen_gemm_double_dynamic_square | Eigen GEMM | 双精度动态矩阵乘法 |
| eigen_gemm_float_dynamic_square | Eigen GEMM | 单精度动态矩阵乘法 |
| eigen_sparse | Eigen Sparse | 稀疏矩阵运算 |
| eigen_svd | Eigen SVD | 奇异值分解 |
| eigen_svd_cdouble_noavx512 | Eigen SVD | 复数双精度SVD (无AVX512) |
| eigen_svd_double2 | Eigen SVD | 双精度SVD (变体2) |
| eigen_svd_double | Eigen SVD | 双精度SVD |
| eigen_svd_fvectors | Eigen SVD | 单精度向量SVD |
| zstd19 | 压缩 | Zstd压缩 (v1.9) |
| zstd | 压缩 | Zstd压缩 (最新) |
| zstd1 | 压缩 | Zstd压缩 (v1.0) |
| zstd_aaa | 压缩 | Zstd压缩AAA模式 |
| zfuzz | 压缩 | Zstd模糊测试 |
| zlib9 | 压缩 | Zlib压缩 (v1.9) |
| zlib | 压缩 | Zlib压缩 (最新) |
| zlib1 | 压缩 | Zlib压缩 (v1.0) |
| zlib_aaa | 压缩 | Zlib压缩AAA模式 |

#### Quality=0 新测试 (5个，ARM64专用)

| 测试 | 类别 | 描述 |
|------|------|------|
| neon_add | NEON SIMD | NEON向量加法运算 |
| neon_perf | NEON SIMD | NEON性能基准测试 |
| arm_crypto | 加密 | ARM加密指令 (AES/SHA) |
| arm64_sdc | SDC检测 | 通过CRC32/CRC64检测静默数据损坏 |
| arm64_stress | 压力测试 | ARM64压力测试 |

#### Quality=-1 新测试 (4个，Jacobi SVD变体)

| 测试 | 类别 | 描述 |
|------|------|------|
| eigen_svd_jacobi | Eigen SVD | 通用Jacobi SVD |
| eigen_svd_jacobi_cdouble | Eigen SVD | 复数双精度Jacobi SVD |
| eigen_svd_jacobi_double | Eigen SVD | 双精度Jacobi SVD |
| eigen_svd_jacobi_fvectors | Eigen SVD | 单精度向量Jacobi SVD |

#### 按质量等级运行测试

```bash
# 仅运行PROD测试 (默认，quality=2)
./builddir/opendcdiag --list-tests

# 运行BETA + PROD测试 (quality=0)
./builddir/opendcdiag --quality=0 --list-tests

# 运行所有测试包括SKIP (quality=-1)
./builddir/opendcdiag --quality=-1 --list-tests

# 运行ARM64 SDC测试
./builddir/opendcdiag --quality=0 -e arm64_sdc -t 5000
```

### 8. 编译构建opendcdiag-arm
```bash
cd opendcdiag

# ARM64原生构建
meson setup build-arm64 --cross-file=cross-file-aarch64.txt --buildtype=release
ninja -C build-arm64

# x86_64构建
meson setup builddir --buildtype=release
ninja -C builddir
```


------------------------

# [Sub-P1] microprobe-arm：增加支持arm64指令流生成，并wrapper成SDC检测用例
1. ARM64指令流生成 (scripts/arm64_power_fuzzing.py)
   - 68条真实ARM64指令 (ADD, SUB, MUL, LDR, STR, B, etc.)
   - 31个64位寄存器 (X0-X30, SP)
   - 随机寄存器分配
2. Wrapper封装
   - .arch armv8-a 指令
   - 标准ARM64汇编格式

脚本包含68条真实ARM64指令：
- **数据处理 (寄存器)**: ADD, SUB, MUL, SDIV, UDIV, AND, ORR, EOR, LSL, LSR, ASR, ROR
- **加载/存储**: LDR, LDRB, LDRH, STR, STRB, STRH, LDP, STP, LDXR, STXR
- **分支**: B, BL, BR, BLR, RET, CBZ, CBNZ, BEQ, BNE, BGT, BLT
- **扩展**: UXTB, UXTH, UXTW, SXTB, SXTH, SXTW

寄存器：31个64位通用寄存器 (X0-X30)

输出文件保存在 `scripts/arm64_output/`:
- `arm64_program_*.s` - 汇编文件
- `arm64_program_*` - ELF可执行文件
- `arm64_stats_*.txt` - 统计信息
- `arm64_power_results.json` - 功耗结果

--------------------------------
# [Sub-P2-1] qemu：仿真执行

```bash
# QEMU模拟环境运行
qemu-aarch64 -L /usr/aarch64-linux-gnu \
    -E LD_LIBRARY_PATH=$(pwd)/third_party/lib \
    ./build-arm64/opendcdiag --cpu=on --total-time 60s

# 真实ARM64硬件运行
./build-arm64/opendcdiag --cpu=on --total-time 300s
```

--------------------------------
# [Sub-P2-2] gem5：增加SDC故障注入能力，通过qemu和gem5的差分测试进行SDC检测

使用gem5 SE模式执行指令流：

```bash
cd gem5
./build/ARM/gem5.opt --outdir /tmp/gem5_output \
    configs/example/se.py -c /path/to/program \
    --cpu-type AtomicSimpleCPU --caches
```
--------------------------------

# [Sub-P3] mcpat-arm:增加支持 arm64架构，通过gem5输出和arm64微架构/工艺配置，计算指令流功耗

📊 1000次ARM64测试结果

| 指标   | 值                 |
|--------|--------------------|
| 架构   | ARM64 (armv8-a)    |
| 指令流数 | 1000              |
| 功耗范围 | 0.1030 ~ 1.9994 W |
| 平均功耗 | 1.0679 W          |

📁 输出文件

- 脚本: scripts/arm64_power_fuzzing.py
- 结果: scripts/arm64_output/arm64_power_results.json
- 报告: scripts/arm64_output/arm64_power_fuzzing_report.md

--------------------------------

