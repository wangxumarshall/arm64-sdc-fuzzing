# SDC-Agent Project Plan

## 1. 项目目标

在现有仓库基础上，交付一套面向 ARM64 的 SDC 自动化 Fuzzing 主流程，形成以下闭环：

1. 使用 `microprobe-arm` 生成 ARM64 指令流。
2. 计算 ACE / IBR / Memory Pressure 等静态覆盖指标。
3. 将候选持久化到 SQLite Vault。
4. 物料化为带 digest 的 SDC 检测用例。
5. 用 QEMU 获取 ISA golden。
6. 用 gem5 执行候选并采集统计信息。
7. 用 McPAT 计算功耗。
8. 用反馈调度器和进化驱动把高价值样本重新注入 Vault。

---

## 2. 当前阶段判断

| 阶段 | 状态 | 说明 |
| --- | --- | --- |
| Phase 1：离线生成与静态评分 | 已完成 | Policy、Pass、Offline CLI、Vault 已打通 |
| Phase 2：wrapper、materialize、差分执行 | 已完成 | `sdc_agent/materialize.py`、`sdc_agent/differential.py`、`sdc_agent/campaign.py` 可执行 |
| Phase 3：功耗反馈 | 已完成主干 | `McPATBackend` 和 `sdc_agent/power_analysis.py` 已接通 |
| Phase 4：反馈调度 | 已完成 | `FeedbackScheduler` 已实现状态回写和 fitness 计算 |
| Phase 5：进化闭环 | 已完成首版 | `SDCFuzzingGeneticDriver` 与 `tools/sdc_agent.py` 已落地 |
| Phase 6：gem5 真实故障注入器 | 待实现 | 当前仍为 manifest/hook 形态，未进入 gem5 C++ 核心执行路径 |

---

## 3. 详细计划

### Phase 1：离线静态扫街引擎

目标：

- 稳定生成 ARM64 候选样本。
- 在不运行仿真的情况下评估静态风险。

已完成项：

- `microprobe/targets/arm64/policies/sdc_fuzzing_policy.py`
- `microprobe/src/microprobe/passes/sdc_analysis/offline_coverage.py`
- `microprobe/targets/generic/tools/mp_sdc_offline_gen.py`
- `sdc_agent/generation.py`
- `sdc_agent/vault.py`

验收标准：

- 能批量生成样本并写入 `offline_testcases`
- 样本包含 `ace_score / ibr_score / memory_pressure_score / risk_score`

### Phase 2：执行与差分引擎

目标：

- 将静态候选变成可运行的 SDC 检测程序。
- 用 QEMU 与 gem5 做最小差分判定。

已完成项：

- `microprobe/targets/arm64/wrappers/baremetaldiff.py`
- `sdc_agent/materialize.py`
- `sdc_agent/differential.py`
- `sdc_agent/campaign.py`

验收标准：

- 能编译静态 ELF
- 能提取 `SDC_DIGEST`
- 能把结果归一化为 `matched / sdc_found / invalid / timeout / crashed`

### Phase 3：功耗建模

目标：

- 基于 gem5 输出做 McPAT 后处理。

已完成项：

- `sdc_agent/power_backends/mcpat_backend.py`
- `sdc_agent/power_analysis.py`

验收标准：

- 能返回 `power_total / power_dynamic / power_leakage`
- 能回写 Vault 的 `mcpat_power`

### Phase 4：反馈排序

目标：

- 用执行结果和功耗结果更新样本优先级。

已完成项：

- `sdc_agent/scheduler.py`

验收标准：

- 支持 `normalize_runner_status()`
- 支持 `compute_fitness()`
- 支持 `select_candidates()` 和 `record_result()`

### Phase 5：进化闭环

目标：

- 根据高价值父代自动生成 offspring 并回灌 Vault。

已完成项：

- `microprobe/src/microprobe/driver/genetic.py` 中新增 Python 3 `SDCFuzzingGeneticDriver`
- `tools/sdc_agent.py` 顶层入口

当前策略：

1. 从 Vault 中选取高价值父代。
2. 读取 `instruction_names`。
3. 做一位点交叉。
4. 强制注入偏向访存的变异，并保持 `preferred_stride_bytes >= 8192`。
5. 重新调用 Microprobe 合成 offspring。
6. 将 offspring 写回 Vault，状态默认为 `PENDING`。

验收标准：

- 能自动产生 offspring
- offspring 带 lineage metadata
- offspring 能重新进入 campaign

### Phase 6：真实 gem5 故障注入

目标：

- 让 `fault_model / fault_target / fault_bit / fault_tick` 不只是 manifest，而是真正驱动 gem5 内核注入故障。

当前状态：

- `sdc_fault_request.py` 已定义 manifest
- `sdc_kunpeng920_se.py` 已输出 `sdc_fault_request.json`
- 但尚未在 gem5 C++ 执行路径中消费该请求

后续任务：

1. 明确故障注入粒度：寄存器、ROB、LSQ、cache line、内存位翻转。
2. 设计 gem5 SimObject 或 CPU hook。
3. 让 differential runner 在启用 fault 时拿到真实 faulted digest。

---

## 4. 验证命令

### 离线生成

```bash
python3 microprobe/targets/generic/tools/mp_sdc_offline_gen.py \
  --db artifacts/sdc_vault.sqlite3 \
  --count 10 \
  --output-dir artifacts/generated
```

### Vault 状态

```bash
python3 tools/sdc_agent.py status --db artifacts/sdc_vault.sqlite3
```

### 进化回灌

```bash
python3 tools/sdc_agent.py evolve \
  --db artifacts/sdc_vault.sqlite3 \
  --parent-limit 4 \
  --max-offspring 8
```

### 单样本差分

```bash
python3 tools/run_sdc_differential.py artifacts/materialized/example.c \
  --gem5-config gem5/configs/example/arm/sdc_kunpeng920_se.py
```

### 一次完整循环

```bash
python3 tools/sdc_agent.py cycle \
  --db artifacts/sdc_vault.sqlite3 \
  --generate-count 10 \
  --campaign-limit 3 \
  --max-offspring 6 \
  --skip-preflight
```

---

## 5. 风险与剩余工作

1. `gem5/ext/pybind11/tests` 属于第三方测试目录，不能作为本项目回归基线。
2. 真实 fault injector 尚未落地前，`fault_model != none` 的生产级 SDC 判定仍依赖后续 gem5 侧实现。
3. 当前进化层是可执行首版，后续仍可继续增强：
   - 更强的 crossover
   - 基于父代功耗和状态的多目标选择
   - 针对 TaiShan/Kunpeng 微架构单元的定向变异
