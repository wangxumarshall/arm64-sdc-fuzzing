# SDC-Agent Findings

## 1. Executive Summary

基于对重构后源码的系统性阅读，可以得出一个明确结论：

> 项目已经具备“可运行的闭环骨架”，但距离 README 中的完整愿景，还缺少统一内循环编排、多 fault 外循环、真实 gem5 fault injector、以及 OpenDCDiag 硬件回灌这四块关键能力。

当前源码不需要推倒重来；真正需要的是把已有模块组织成一个更完整的分层系统。

---

## 2. Source-Backed Findings

## 2.1 控制平面已经存在，但仍偏 orchestration skeleton

[`sdc_agent/agent.py`](/Users/wangxu/1-project/sdc-fuzzing/sdc_agent/agent.py) 已经提供：

- `status`
- `generate`
- `evolve`
- `cycle`

这说明控制平面不是从零开始。

但 `cycle()` 当前的顺序是：

1. generate
2. campaign
3. evolve

它还没有把以下步骤完整纳入一个正式内循环：

- qemu inner validation
- power annotation
- seed weight update after qemu/power

结论：

- 现有 `cycle()` 是可运行骨架
- 不是 README 愿景中的完整“高频内循环”

## 2.2 生成器与静态 Pass 已可用，但策略仍偏 sim-safe

[`microprobe/targets/arm64/policies/sdc_fuzzing_policy.py`](/Users/wangxu/1-project/sdc-fuzzing/microprobe/targets/arm64/policies/sdc_fuzzing_policy.py) 和 [`microprobe/src/microprobe/passes/sdc_analysis/offline_coverage.py`](/Users/wangxu/1-project/sdc-fuzzing/microprobe/src/microprobe/passes/sdc_analysis/offline_coverage.py) 已经实现：

- ARM64 instruction selection
- ACE
- IBR
- Memory Pressure
- Capstone validation

但有一个关键现实约束：

- README 的理想目标强调 NEON FMA、LDP/STP、LSE、复杂访存模式
- 当前 `SDCSensitiveAnalyzer` 为了保证 gem5/qemu 可运行，默认把其中很大一部分排除了

这意味着：

1. 当前生成器适合 `SIM_SAFE` profile
2. 它还不足以单独覆盖 README 的全部“敏感指令愿景”

## 2.3 Memory Pressure Pass 与默认生成策略之间存在目标错位

`Kunpeng920MemoryPressurePass` 会对这些模式给高权重：

- `LDP`
- `STP`
- `LDXR`
- `STXR`
- `CAS`
- `LDADD`

但默认生成策略却把这些模式大多排除在外。

结果是：

- 评分器偏好某些模式
- 默认生成器却很少产出这些模式

结论：

- 必须引入 profile-aware generation
- 否则内循环会长期在“评分想要但生成不出来”的状态里打转

## 2.4 数据模型过于扁平，不足以支撑 fault matrix 与硬件回灌

[`sdc_agent/vault.py`](/Users/wangxu/1-project/sdc-fuzzing/sdc_agent/vault.py) 当前只有一个中心表 `offline_testcases`，关键字段包括：

- `qemu_golden_hash`
- `gem5_fault_hash`
- `mcpat_power`
- `status`
- `metadata_json`

这对单次执行足够，但对完整愿景不够，因为它无法自然表达：

1. 一个 testcase 对多个 fault 配置的多次 gem5 运行
2. 一个 testcase 的多轮功耗测量
3. 一个 testcase 被多次推广到硬件环境
4. 一个 testcase 在不同 profile 下的构建产物

结论：

- 要实现完整目标，必须从单表过渡到兼容式多表模型

## 2.5 Outer loop 已有差分主干，但还不是完整 fault campaign

[`sdc_agent/differential.py`](/Users/wangxu/1-project/sdc-fuzzing/sdc_agent/differential.py) 和 [`sdc_agent/campaign.py`](/Users/wangxu/1-project/sdc-fuzzing/sdc_agent/campaign.py) 已能完成：

- compile
- qemu golden
- gem5 run
- McPAT post-process
- result classify
- scheduler record_result

但当前外循环仍有三个局限：

1. 每次只跑一个 fault 配置
2. 没有 fault matrix planner
3. 没有 per-fault run persistence model

结论：

- 当前外循环适合“点状验证”
- 还不适合“系统化 fault sweep”

## 2.6 真实 fault injector 仍未实现

[`gem5/configs/example/arm/sdc_fault_request.py`](/Users/wangxu/1-project/sdc-fuzzing/gem5/configs/example/arm/sdc_fault_request.py) 定义了：

- `fault_model`
- `fault_target`
- `fault_bit`
- `fault_tick`
- `implemented_in_script=False`

[`gem5/configs/example/arm/sdc_kunpeng920_se.py`](/Users/wangxu/1-project/sdc-fuzzing/gem5/configs/example/arm/sdc_kunpeng920_se.py) 会输出 `sdc_fault_request.json`，但不会真正消费它。

结论：

- fault control plane 已贯通
- fault execution plane 尚未落地

## 2.7 OpenDCDiag-ARM 资产已经存在，但集成层缺位

源码中可以看到：

- `opendcdiag/tests/cpu/arm64/sdc_test.cpp`
- `opendcdiag/tests/cpu/arm64/neon_test.cpp`
- `opendcdiag/tests/cpu/arm64/crypto_test.cpp`
- ARM64 porting docs

这说明 OpenDCDiag-ARM 不是空白项目。

但当前 SDC-Agent 中只有 [`sdc_agent/power_backends/opendcdiag_backend.py`](/Users/wangxu/1-project/sdc-fuzzing/sdc_agent/power_backends/opendcdiag_backend.py) 的 placeholder，没有：

- testcase promotion
- generated test packaging
- result parser
- DB backfill

结论：

- P0 有资产
- 但还没有接入 SDC-Agent 主链路

## 2.8 功耗链路存在，但没有与内循环融合

[`sdc_agent/power_analysis.py`](/Users/wangxu/1-project/sdc-fuzzing/sdc_agent/power_analysis.py) 已经能做：

- materialize
- compile
- gem5 baremetal
- McPAT
- vault update

但它是独立 pipeline，不属于当前 `cycle()` 的一部分。

结论：

- 功耗模块已经存在
- 但还没有成为高频内循环的标准步骤

## 2.9 评分体系需要拆层

当前源码里至少存在两套评分逻辑：

1. 生成阶段的 `risk_score`
2. 调度阶段的 `fitness`

它们用途不同，但现在没有在架构层被正式区分。

结论：

- 需要引入：
  - `static_risk_score`
  - `inner_value_score`
  - `outer_value_score`
  - `promotion_score`

这样系统才能在内外循环和硬件推广之间保持解释性。

---

## 3. Implications for the Redesign

基于以上发现，完整方案必须采用以下结构：

1. `SIM_SAFE` 与 `HW_AGGRESSIVE` 双 profile 生成策略
2. 内循环统一编排：
   - generate
   - static metrics
   - wrapper
   - qemu validate
   - power annotate
   - evolve
3. 外循环 fault matrix 化
4. 数据库从单表扩展为多表兼容模型
5. OpenDCDiag 只在最终硬件验证环使用，不回退到仿真执行层

---

## 4. What Is Already Strong

这次阅读后最值得保留的部分有：

- `sdc_agent/generation.py`
- `sdc_agent/differential.py`
- `sdc_agent/campaign.py`
- `sdc_agent/scheduler.py`
- `microprobe.driver.genetic` 中新增的 Python 3 进化驱动

这些模块已经足够构成新方案的骨架，后续应该围绕它们扩展，而不是重写整条链路。
