# SDC-Agent：面向 ARM64 架构的 SDC 自动化 Fuzzing 工具集

> 项目代号：SDC-Agent
> 架构版本：v2.1
> 目标微架构：TaiShan v110 / Kunpeng 920（ARMv8.2-A）
> 最后更新：2026-04-02

---

## 一、项目概述

### 1.1 背景与目标

静默数据破坏（Silent Data Corruption, SDC）是 ARM64 服务器可靠性验证里最难发现的问题之一：程序没有崩溃，系统没有抛异常，但最终计算结果已经悄悄偏离正确值。

本项目的目标不是构建一个重量级测试框架，而是构建一套围绕 ARM64 指令流的 **低成本、高吞吐、可反馈进化的 SDC 发现流水线**。它解决三个核心问题：

1. 如何高并发地产生足够多的 ARM64 候选指令流。
2. 如何在不运行大规模周期级仿真的前提下，先用静态指标筛出高风险样本。
3. 如何用最轻量的方式，把 “ISA 正确结果” 与 “带微架构/故障语义的执行结果” 做差分，从而高置信度判定 SDC。

### 1.2 核心方法论

系统采用 **A/B 异步架构 + 轻量级差分测试**，并在完整目标形态中追加一条 **真实硬件验证环**：

| 方法 | 原理 | 速度 | 作用 |
| --- | --- | --- | --- |
| 离线静态降维 | 不跑仿真，仅基于 Microprobe 生成结果计算 ACE / IBR / Memory Pressure | 极快 | 大规模筛种 |
| 在线差分验证 | QEMU 作为 ISA golden，gem5 作为微架构执行侧，再接 McPAT 功耗后处理 | 较慢 | 精准判定与反馈 |

这意味着项目把“生成”和“验证”彻底解耦：

- 阶段 A 追求吞吐，负责产出足够多的候选。
- 阶段 B 追求精度，负责把有限仿真预算用在最危险的样本上。

为了 100% 实现 README 的目标，最终系统会稳定收敛为三层：

1. 高频内循环：生成、静态分析、wrapper、QEMU 校验、功耗标注、进化反馈
2. 低频外循环：gem5 fault campaign + QEMU 差分 + SDC 能力评分
3. 硬件验证环：将高价值样本推广到 `opendcdiag-arm` 并把结果回灌数据库

完整目标架构、数据库模型和实施路线见 [spec.md](./doc/spec.md) 与 [plan.md](./doc/plan.md)。

### 1.3 SDC-Agent 的定义

这里的 **Agent** 指的是项目级控制平面，不是仓库内已经实现了一组独立的 LLM 子代理。当前仓库中的 SDC-Agent 由以下可执行模块组成：

- 离线生成器：Microprobe policy + static passes + SQLite Vault
- 在线执行器：materialize + QEMU/gem5 differential + McPAT
- 反馈调度器：根据执行结果更新 fitness、挑选候选、生成进化种子
- 顶层入口：`tools/sdc_agent.py`，控制逻辑位于 `sdc_agent/agent.py`

因此，README 后续章节统一使用“引擎 / 模块 / 控制器”术语，而不是把每个阶段包装成一个独立 AI agent。

---

## 二、系统架构

### 2.1 A/B 异步架构

当前仓库中 A/B 两层已经具备可运行骨架；完整目标形态会在其外再加一条硬件验证闭环，但不会把 OpenDCDiag 直接拖进高频仿真路径。

```text
┌───────────────────────────────────────────────────────────────────────────┐
│                             SDC-Agent Control Plane                      │
│                         status / generate / campaign / evolve            │
└───────────────────────────────────────────────────────────────────────────┘
                    │
        ┌───────────┴───────────┐
        │                       │
        ▼                       ▼
┌───────────────────┐   ┌──────────────────────────────────────────────────┐
│ Phase A           │   │ Phase B                                          │
│ Offline Engine    │   │ Online Precision Campaign                        │
├───────────────────┤   ├──────────────────────────────────────────────────┤
│ Microprobe Policy │   │ sdc_agent/materialize.py / BareMetalDiffWrapper  │
│ Static Passes     │   │ aarch64-linux-gnu-gcc -static                    │
│ ACE / IBR / Mem   │   │ qemu-aarch64  → Golden Digest                    │
│ Capstone Validate │   │ gem5 SE       → Faulted Digest / stats           │
│ SQLite Vault      │   │ McPAT         → power_total / dynamic / leakage   │
└───────────────────┘   └──────────────────────────────────────────────────┘
        │                               │
        └──────────────┬────────────────┘
                       ▼
               ┌────────────────┐
               │ SQLite Vault   │
               │ offline_testcases
               │ status / hashes
               │ power / metadata
               └────────────────┘
                       │
                       ▼
         ┌─────────────────────────────────────┐
         │ FeedbackScheduler + Genetic Driver  │
         │ select / record / evolve / reinject │
         └─────────────────────────────────────┘
```

### 2.2 数据契约

Vault 中心表为 `offline_testcases`，承载两类信息：

1. 静态阶段产物
   - `asm_content`
   - `ace_score`
   - `ibr_score`
   - `memory_pressure_score`
   - `risk_score`
2. 在线阶段产物
   - `qemu_golden_hash`
   - `gem5_fault_hash`
   - `mcpat_power`
   - `status`
   - `metadata_json`

当前状态机如下：

```text
PENDING ──▶ GOLDEN_READY ──▶ MATCHED
    │             │
    │             └────────▶ SDC_FOUND
    │
    ├────────────▶ INVALID
    ├────────────▶ TIMEOUT
    └────────────▶ CRASHED
```

### 2.3 真实代码映射

| 组件 | 责任 | 关键文件 |
| --- | --- | --- |
| 离线生成 | 生成 ARM64 指令流并计算静态风险分 | `microprobe/targets/arm64/policies/sdc_fuzzing_policy.py` |
| 静态分析 Pass | 计算 ACE / IBR / Memory Pressure / Capstone 校验 | `microprobe/src/microprobe/passes/sdc_analysis/offline_coverage.py` |
| 离线 CLI | 批量生成并写入 Vault | `microprobe/targets/generic/tools/mp_sdc_offline_gen.py` |
| 共享生成库 | 离线生成与进化共用的合成逻辑 | `sdc_agent/generation.py` |
| Vault | 候选持久化与排序抓取 | `sdc_agent/vault.py` |
| Wrapper / 物料化 | 把指令流变成可执行 SDC digest 程序 | `microprobe/targets/arm64/wrappers/baremetaldiff.py`、`sdc_agent/materialize.py` |
| 差分执行 | 编译、跑 QEMU、跑 gem5、调用 McPAT | `sdc_agent/differential.py` |
| 调度器 | 候选排序、结果回写、fitness 更新 | `sdc_agent/scheduler.py` |
| Campaign | 从 Vault 选样并执行在线外循环 | `sdc_agent/campaign.py` |
| 进化驱动 | 根据高价值样本生成 offspring 并回灌 Vault | `microprobe/src/microprobe/driver/genetic.py` |
| 项目入口 | 统一提供 status / generate / evolve / cycle | `tools/sdc_agent.py` + `sdc_agent/agent.py` |

---

## 三、当前实现

### 3.1 离线引擎

当前离线引擎已经具备以下能力：

1. 基于 `sdc_fuzzing_policy` 生成 ARM64 指令流。
2. 通过 `StaticACECalculatorPass` 计算寄存器 Def-Use 暴露跨度。
3. 通过 `StaticIBRCoveragePass` 估计宽寄存器/宽访存占比。
4. 通过 `Kunpeng920MemoryPressurePass` 对缓存压力与访存倾向做启发式加权。
5. 通过 `CapstoneValidationPass` 做最佳努力反汇编校验。
6. 将结果写入 SQLite Vault，供在线阶段按风险分拉取。

当前静态分数使用 `benchmark.metadata` 挂载，并进一步持久化进 `metadata_json`。这比把分析结果塞进运行态 `Context` 更清晰，也与当前仓库实现保持一致。

### 3.2 在线差分引擎

在线阶段的执行路径如下：

1. 读取 Vault top-k 候选。
2. 若候选只有汇编，则用 `sdc_agent/materialize.py` 生成带 digest 逻辑的 C 源。
3. 用 `aarch64-linux-gnu-gcc -static` 编译 ELF。
4. 用 `qemu-aarch64` 执行，提取 `Golden Digest`。
5. 用 gem5 SE 配置执行，提取 `Faulted Digest` 与统计文件。
6. 若 gem5 正常退出且 digest 不一致，则标记 `SDC_FOUND`。
7. 若 gem5 成功且配置允许，则调用 McPAT 后处理，回写功耗。

判定逻辑以 `sdc_agent/differential.py` 中的 `classify()` 为准，不依赖额外的重量级测试夹具。

### 3.3 反馈与进化

当前反馈闭环分成两层：

1. `FeedbackScheduler`
   - 负责把 `matched / sdc_found / golden_only / timeout / failed` 映射回 Vault 状态
   - 计算静态分与 `power_total`、`sdc_signal` 组合后的 fitness
2. `SDCFuzzingGeneticDriver`
   - 读取高价值父代
   - 基于父代指令名做一位点交叉和偏向访存的变异
   - 强制继承或提升 `preferred_stride_bytes >= 8192`
   - 重新调用 Microprobe 合成 offspring
   - 将新样本重新注入 Vault，形成真正的内外循环闭环

这一步是当前 README 旧版中最缺失的能力；现在仓库里已经有可执行的 Python 3 版本实现，不再依赖已失效的 `pyevolve`。

### 3.4 顶层控制入口

`tools/sdc_agent.py` 提供四个常用子命令：

- `status`
- `generate`
- `evolve`
- `cycle`

其中 `cycle` 会串联：

1. 离线生成
2. 在线 campaign
3. offspring 进化
4. Vault 状态汇总

它是对现有脚本的轻量编排，不替代底层脚本本身。

### 3.5 外部依赖边界

下面这些能力是当前已经接好接口、但仍依赖外部运行环境或后续 C++/gem5 扩展的部分：

| 能力 | 当前状态 | 说明 |
| --- | --- | --- |
| QEMU golden execution | 已实现 | `tools/run_sdc_differential.py` 可直接调用 |
| gem5 SE execution | 已实现 | `sdc_kunpeng920_se.py` 可执行静态 ELF |
| McPAT post-processing | 已实现 | 通过 `McPATBackend` 调用本地 `pypat` |
| gem5 fault request recording | 已实现 | 输出 `sdc_fault_request.json` |
| 真正的 gem5 位翻转/寄存器注入 | 待补齐 | 当前仍是 manifest/hook 形式，而非 gem5 C++ 内核中已激活的 fault injector |

这意味着项目的 **差分控制平面已经完整**，但 **真正的 gem5 微架构故障注入器** 仍是后续重点工程项。

---

## 四、阶段路线图

### Phase 1：ARM64 静态离线引擎

状态：已完成主干

- ARM64 target / env / wrapper 已接通
- `sdc_fuzzing_policy` 已可生成指令流
- ACE / IBR / Memory Pressure / Capstone Pass 已可运行
- Offline CLI 已可批量写入 Vault

### Phase 2：差分执行与功耗闭环

状态：已完成主干

- `BareMetalDiffWrapper` 与 `sdc_agent/materialize.py` 可生成 digest 程序
- `sdc_agent/differential.py` 已实现 compile → qemu → gem5 → McPAT
- `sdc_agent/campaign.py` 已实现批量外循环
- `sdc_agent/scheduler.py` 已实现状态归一化与 fitness 计算

### Phase 3：反馈进化层

状态：已完成首个可用版本

- Python 3 `SDCFuzzingGeneticDriver` 已落地
- 支持 parent selection / crossover / memory-biased mutation / vault reinjection
- `tools/sdc_agent.py` 已能编排生成、执行、进化与状态汇总

### Phase 4：真实 gem5 故障注入器

状态：待完成

- 当前 `fault_model / fault_target / fault_bit / fault_tick` 已贯通到控制面
- gem5 配置脚本已写出 fault request manifest
- 下一步需要在 gem5 侧增加真正消费 manifest 的 fault injector 实现

---

## 五、代码结构

```text
sdc-fuzzing/
├── README.md
├── sdc_agent/
│   ├── __init__.py
│   ├── agent.py
│   ├── campaign.py
│   ├── differential.py
│   ├── generation.py
│   ├── materialize.py
│   ├── power_analysis.py
│   ├── preflight.py
│   ├── scheduler.py
│   ├── vault.py
│   └── power_backends/
│       ├── mcpat_backend.py
│       └── opendcdiag_backend.py
├── tools/
│   ├── sdc_agent.py
│   ├── sdc_campaign.py
│   ├── sdc_materialize.py
│   ├── sdc_preflight.py
│   ├── sdc_scheduler.py
│   ├── run_power_analysis.py
│   └── run_sdc_differential.py
├── scripts/
│   ├── build_gem5.sh
│   ├── build_gem5_noninteractive.sh
│   └── setup_environment.sh
├── dev/
│   ├── debug/
│   └── samples/
├── microprobe/
│   ├── targets/arm64/policies/
│   │   ├── sdc_fuzzing_policy.py
│   │   └── sdc_detect.py
│   ├── targets/arm64/wrappers/
│   │   ├── arm64asm.py
│   │   └── baremetaldiff.py
│   ├── targets/generic/tools/
│   │   └── mp_sdc_offline_gen.py
│   └── src/microprobe/
│       ├── driver/genetic.py
│       └── passes/sdc_analysis/offline_coverage.py
├── gem5/
│   └── configs/example/arm/
│       ├── sdc_kunpeng920_se.py
│       ├── sdc_baremetal_se.py
│       └── sdc_fault_request.py
├── mcpat/
└── doc/
    ├── spec.md
```

---

## 六、快速开始

### 6.1 预检

```bash
python3 tools/sdc_preflight.py --verbose
```

### 6.2 批量生成候选

```bash
python3 microprobe/targets/generic/tools/mp_sdc_offline_gen.py \
  --db artifacts/sdc_vault.sqlite3 \
  --count 10 \
  --sequence-length 8 \
  --benchmark-size 64 \
  --output-dir artifacts/generated
```

### 6.3 查看 Vault 状态

```bash
python3 tools/sdc_agent.py status --db artifacts/sdc_vault.sqlite3 --limit 5
```

### 6.4 运行一次完整循环

```bash
python3 tools/sdc_agent.py cycle \
  --db artifacts/sdc_vault.sqlite3 \
  --generate-count 10 \
  --campaign-limit 3 \
  --parent-limit 4 \
  --max-offspring 6 \
  --skip-preflight
```

### 6.5 直接跑单个差分样本

```bash
python3 tools/run_sdc_differential.py \
  artifacts/materialized/example.c \
  --compiler aarch64-linux-gnu-gcc \
  --qemu-binary qemu-aarch64 \
  --gem5-binary gem5/build/ARM/gem5.opt \
  --gem5-config gem5/configs/example/arm/sdc_kunpeng920_se.py \
  --fault-model none \
  --timeout 120
```

### 6.6 只做进化回灌

```bash
python3 tools/sdc_agent.py evolve \
  --db artifacts/sdc_vault.sqlite3 \
  --parent-limit 4 \
  --offspring-per-parent 2 \
  --max-offspring 8 \
  --output-dir artifacts/evolved
```

---

## 七、验证现状

本次主干验证覆盖了以下路径：

- `tests/test_sdc_agent.py`
- `tests/test_sdc_genetic_driver.py`
- `tests/test_sdc_scheduler.py`
- `tests/test_sdc_campaign.py`
- `tests/test_offline_to_campaign_integration.py`
- `microprobe/targets/arm64/tests/tools/test_mp_sdc_offline_gen.py`
- `microprobe/targets/arm64/tests/targets/test_target_contract.py`

这些测试验证了：

1. 离线生成可以产出 ARM64 样本并写入 Vault。
2. materialize / campaign / scheduler 的主流程仍然成立。
3. 新增的 `SDCFuzzingGeneticDriver` 能把 offspring 重新注入 Vault。
4. 新增的 `tools/sdc_agent.py` 可以编排主流程并汇总状态。

注意：

- 仓库中的 `gem5/ext/pybind11/tests` 属于第三方测试目录，直接运行 `pytest -q` 会因该目录缺少外部构建产物而失败。
- `gem5` 真实 fault injection 目前仍是后续工程项；当前已验证的是控制面、manifest 和差分流程，不是最终版 fault injector。
