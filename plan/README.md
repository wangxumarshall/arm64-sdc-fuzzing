# SDC Sentinel 项目计划

## 项目概述

面向 ARM64 架构的静默数据破坏 (SDC) 自动化 Fuzzing 工具集，基于 Microprobe 深度定制，结合 gem5 仿真与 McPAT 功耗分析。

---

## 四阶段路线

### Phase 0: opendcdiag-arm

**目标**: 把x86架构的opendcdiag所有SDC测试用例都移植到arm64架构。

### Phase 1: 高功耗波动引导 SDC Fuzzing (当前)

**目标**: 使用 gem5 仿真执行测试用例 + McPAT 计算功耗，利用功耗反馈引导 Microprobe 生成高功耗波动指令流。

**步骤**:
1. ✅ Microprobe 移植支持 arm64 指令流生成
2. ✅ 生成 SDC 测试用例到 Vault
3. ✅ 用例物化 (Materialize)
4. 🔄 gem5 SE 执行 + McPAT 功耗计算 (**阻塞: 指令编码问题**)
5. ⏳ 反馈引导的下一代生成
6. ⏳ Phase 1 联调验证 (3000+ 用例)

**关键文件**:
- `microprobe/targets/arm64/policies/sdc_fuzzing_policy.py`
- `sdc_vault.py`
- `sdc_materialize.py`
- `run_power_analysis.py`
- `gem5/src/arch/arm/bare_metal/workload.cc`
- `gem5/src/arch/arm/bare_metal/process.cc`
- `gem5/configs/example/arm/sdc_baremetal_se.py`

---

### Phase 2: LLM 增强的智能变异生成

**目标**: 借助 LLM 推理能力实现更精准的 SDC 检测指令流生成和覆盖率评估。

**步骤**:
- Step A: LLM 变异生成器
- Step B: 概率上下文文法 (PCFG) 生成器
- Step C: 模板生成器
- Step D: 遗传算法 (GA) 优化器
- Step E: LLM 覆盖率评估器
- Step F: LLM Prompt 生成

---

### Phase 3: QEMU vs gem5+故障注入 差分验证

**目标**: 增加 SDC 检测能力。

**步骤**:
- Step A: 构建 QEMU aarch64-linux-user
- Step B: gem5 SDC 故障注入引擎
- Step C: 差分验证流水线

---

## 当前状态

### Phase 0 进度

| 任务 | 状态 | 说明 |
|------|------|------|
| opendcdiag移植到arm64架构 | ✅ 完成 | 支持 arm64测试 |

### Phase 1 进度

| 任务 | 状态 | 说明 |
|------|------|------|
| Microprobe 环境 | ✅ 完成 | 支持 arm64 指令流生成 |
| 用例生成 | ✅ 完成 | 8 个测试用例写入 Vault |
| 用例物化 | ✅ 完成 | 编译为静态 ELF |
| gem5 ARM 构建 | ✅ 完成 | 含 BareMetalWorkload 支持 |
| gem5 SE 执行 | ❌ 阻塞 | 未知指令错误 (0xf9000fe0) |

### 问题诊断

**问题**: gem5 SE 执行时 panic "unknown instruction (inst 0xf9000fe0)"

**根因**: 生成的测试用例包含无效的 ARM64 机器码指令

**分析**:
- 简单测试 ELF (MOV 指令) 在 gem5 中正常运行
- 复杂 SDC 测试 ELF 包含无效指令编码
- `0xf9000fe0` 不是有效的 ARM64 指令

**解决方案**:
1. 调试 Microprobe SDCFuzzingPolicy 确保生成有效指令
2. 或修复 sdc_materialize.py C 模板确保正确汇编
3. 重新生成验证有效的测试用例

---

## 文件清单

### 新建文件

| 文件 | 说明 |
|------|------|
| `plan/README.md` | 项目计划文档 |
| `microprobe/sdc_offline_gen.py` | 批量生成 ARM64 汇编用例 |
| `run_power_analysis.py` | gem5 + McPAT 功耗流水线 |
| `gem5/src/arch/arm/bare_metal/workload.cc` | BareMetalWorkload |
| `gem5/src/arch/arm/bare_metal/process.cc` | ArmBareMetalProcess64 |
| `gem5/src/arch/arm/bare_metal/workload.hh` | 头文件 |
| `gem5/src/arch/arm/bare_metal/process.hh` | 头文件 |
| `gem5/configs/example/arm/sdc_baremetal_se.py` | ARM64 SE 配置 |

### 修改文件

| 文件 | 修改内容 |
|------|----------|
| `gem5/src/arch/arm/SConscript` | 添加 bare_metal 源码 |
| `gem5/src/arch/arm/ArmSeWorkload.py` | 添加 ArmBareMetalWorkload |

---

## 验证计划

### Phase 1 验证

- [ ] `source microprobe/.venv/bin/activate && python -c "import microprobe"` 成功
- [ ] `python microprobe/sdc_offline_gen.py --db artifacts/sdc_vault.sqlite3 --count 10` 生成用例
- [ ] `python sdc_materialize.py --db artifacts/sdc_vault.sqlite3 --limit 5` 物化用例
- [ ] `python run_power_analysis.py --db artifacts/sdc_vault.sqlite3 --limit 3` 执行并计算功耗
- [ ] Vault 中用例的 `mcpat_power` 字段非空，`status` 为 `GOLDEN_READY`
- [ ] 数据库中有功耗排序，可用于引导下一轮生成
- [ ] **核心**: 修复指令编码问题，确保所有用例可执行
- [ ] 生成 3000+ 满足高覆盖(>80%)和高功耗变化要求的 SDC 检测用例

### Phase 2 验证 (后续)

- [ ] LLM 生成测试用例
- [ ] GA 优化验证 - fitness 收敛曲线
- [ ] PCFG 生成验证 - 多样性对比
- [ ] 覆盖率提升验证

### Phase 3 验证 (后续)

- [ ] QEMU 金标准验证
- [ ] gem5 故障注入验证
- [ ] SDC 检测率验证

---

## 技术栈

- **指令生成**: Microprobe + SDCFuzzingPolicy
- **用例管理**: SQLite (sdc_vault.sqlite3)
- **仿真器**: gem5 SE (ARM64)
- **功耗分析**: McPAT
- **差分验证**: QEMU aarch64-linux-user

---

## 相关路径

- Microprobe: `/Users/wangxu/1-project/sdc-fuzzing/microprobe`
- gem5: `/Users/wangxu/1-project/sdc-fuzzing/gem5`
- 用例池: `/Users/wangxu/1-project/sdc-fuzzing/artifacts/sdc_vault.sqlite3`
- 物化目录: `/Users/wangxu/1-project/sdc-fuzzing/artifacts/materialized/`
- gem5 ARM 构建: `/Users/wangxu/1-project/sdc-fuzzing/gem5/build/ARM/gem5.opt`
