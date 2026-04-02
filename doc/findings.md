# SDC-Agent Findings

## 1. 审阅范围

本次审阅覆盖以下真实实现与资产：

1. 控制平面
   - `sdc_agent/agent.py`
   - `sdc_agent/campaign.py`
   - `sdc_agent/differential.py`
   - `sdc_agent/scheduler.py`
   - `sdc_agent/vault.py`
2. 生成与静态分析
   - `sdc_agent/generation.py`
   - `microprobe/targets/arm64/policies/sdc_fuzzing_policy.py`
   - `microprobe/src/microprobe/passes/sdc_analysis/offline_coverage.py`
   - `microprobe/targets/generic/tools/mp_sdc_offline_gen.py`
   - `microprobe/src/microprobe/driver/genetic.py`
3. 外部子项目接点
   - `gem5/configs/example/arm/sdc_kunpeng920_se.py`
   - `gem5/configs/example/arm/sdc_fault_request.py`
   - `sdc_agent/power_backends/mcpat_backend.py`
   - `sdc_agent/power_backends/opendcdiag_backend.py`
   - `opendcdiag/framework/device/cpu/arm64/arm64_sdc_detect.cpp`
   - `opendcdiag/tests/cpu/arm64/sdc_test.cpp`
4. 关键测试
   - `tests/test_sdc_agent.py`
   - `tests/test_sdc_campaign.py`
   - `tests/test_offline_to_campaign_integration.py`

---

## 2. 执行摘要

审阅结论可以压缩成一句话：

> 项目已经具备一条可运行的控制平面骨架，但距离 README 的完整愿景，还缺少正式的内循环 orchestrator、可表达多次 fault run 的数据库模型、真实 gem5 injector，以及 opendcdiag-arm 的 promotion/backfill 链路。

这意味着项目现在最应该做的不是重写，而是重新分层、补齐契约、让已有模块进入正确的位置。

---

## 3. 关键发现

### Finding 1：控制平面已经存在，但目前只是“可运行骨架”

证据：

1. `sdc_agent/agent.py` 已有 `status / generate / evolve / cycle`
2. `tests/test_sdc_agent.py` 已验证 `run_cycle()` 是“生成 + campaign + evolve”的组合器

影响：

1. 项目不是从零开始。
2. 但 `cycle()` 还不能等同于 README 所要求的正式高频内循环。
3. 下一步应当抽出 `inner_loop.py / outer_loop.py / hardware_lane.py`，而不是继续把所有逻辑堆在 `cycle()`。

### Finding 2：`generation -> vault -> campaign -> genetic` 已经是项目真实主干

证据：

1. `sdc_agent/generation.py` 负责生成与入库
2. `sdc_agent/campaign.py` 负责选样、物料化、执行、回写
3. `microprobe/.../genetic.py` 已负责 offspring 生成

影响：

1. 这条主干值得保留。
2. 文档重构必须围绕这条真实数据流，而不是另起一套概念架构。

### Finding 3：Microprobe 侧已经能生成 ARM64 样本并计算静态指标

证据：

1. `sdc_fuzzing_policy.py` 能选择指令、构造合成器、挂接 SDC 分析 pass
2. `offline_coverage.py` 已实现：
   - `StaticACECalculatorPass`
   - `StaticIBRCoveragePass`
   - `Kunpeng920MemoryPressurePass`
   - `CapstoneValidationPass`
3. `mp_sdc_offline_gen.py` 已能批量写入 Vault

影响：

1. `Sub-P1 microprobe-arm` 已经不是瓶颈中的“无实现”部分。
2. 规划重点应该转向 profile、metadata contract、feedback loop，而不是重新发明生成器。

### Finding 4：当前生成策略本质上是 `SIM_SAFE`，和 README 的激进指令愿景存在缺口

证据：

1. `SDCSensitiveAnalyzer` 明确排除了 FMADD/FMLA、LDP/STP、大量 LSE 等指令
2. 注释直接说明这是为了避免 gem5 bare-metal 与工具链兼容问题

影响：

1. 当前生成路径适合高稳定仿真，不适合单独兑现 README 的全部覆盖目标。
2. 文档必须把 `SIM_SAFE` 与 `HW_AGGRESSIVE` 拆开，否则“目标”与“当前实现”会继续混写。

### Finding 5：Memory Pressure 评分器与默认生成器存在显著目标错位

证据：

1. `Kunpeng920MemoryPressurePass` 对 `LDP/STP/LDXR/STXR/CAS/LDADD/PRFM` 赋高权
2. 默认 `SDCSensitiveAnalyzer` 却把其中大部分模式排除

影响：

1. 当前系统会出现“评分想要、生成不给”的长期偏差。
2. 必须引入 profile-aware generation 和 profile-aware scoring。

### Finding 6：QEMU 当前是 golden legality validator，不是仓库里的自定义执行面

证据：

1. `sdc_agent/differential.py` 通过 `qemu-aarch64` 直接执行 ELF
2. `sdc_agent/preflight.py` 只检查 qemu 可执行文件是否在 PATH 中
3. 现阶段未发现控制平面依赖 qemu 仓库内自定义 patch

影响：

1. `Sub-P2-1 qemu` 当前更像“被调用的 golden executor”，而不是需要立即修改的内核项目。
2. 规划文档应该把 qemu 的近期职责定义为：
   - 合法性验证
   - golden digest
   - 批量缓存

### Finding 7：外循环控制面已通，但 fault 执行面没有真正落地

证据：

1. `sdc_kunpeng920_se.py` 会接收 `fault_model / fault_target / fault_bit / fault_tick`
2. `sdc_fault_request.py` 只负责生成 `sdc_fault_request.json`
3. `FaultRequest.implemented_in_script=False`

影响：

1. 当前 `Sub-P2-2 gem5` 的 fault 相关能力仍属于“记录请求”而不是“真实注入”。
2. 外循环产品化之前，必须先承认真正的硬缺口在 injector。

### Finding 8：`campaign.py` 能完成单次差分，但还不能表达 fault matrix

证据：

1. `campaign.py` 每次只带一组 `fault_model / target / bit / tick`
2. `scheduler.record_result()` 写回的是 testcase summary，而不是 per-fault 历史
3. 当前 Vault 只有单表 `offline_testcases`

影响：

1. 当前外循环适合点状验证，不适合系统化 sensitivity evaluation。
2. 文档必须把 `fault_campaigns` 与 `fault_runs` 作为完成态的正式对象。

### Finding 9：功耗链路存在，但没有真正并入高频内循环

证据：

1. `power_analysis.py` 已能 materialize、编译、跑 gem5 bare-metal、调用 McPAT、写回 Vault
2. `mcpat_backend.py` 已规范化输出 `power_total / dynamic / leakage`
3. `agent.py` 当前的 `cycle()` 并没有调用 `power_analysis.py`

影响：

1. `mcpat-arm` 当前是可用能力，不是系统默认步骤。
2. 下一步应该把功耗标注拉回 `inner_loop.py` 主路径，而不是继续作为旁路脚本。

### Finding 10：评分体系已经有两层雏形，但还没被明确命名

证据：

1. `generation.py` 在写入时计算 `risk_score`
2. `scheduler.py` 会结合 `status_signal` 与 `power_total` 计算 `fitness`

影响：

1. 当前实际上已经存在“静态筛分”和“调度筛分”两套口径。
2. 需要在架构上明确拆成：
   - `static_risk_score`
   - `inner_value_score`
   - `outer_value_score`
   - `promotion_score`

### Finding 11：OpenDCDiag-ARM 资产真实存在，但主控制平面仍然只留了 placeholder

证据：

1. `opendcdiag/framework/device/cpu/arm64/arm64_sdc_detect.cpp` 已有 CRC32/CRC64/checksum/ECC 逻辑
2. `opendcdiag/tests/cpu/arm64/sdc_test.cpp` 已有 ARM64 SDC 测试
3. `sdc_agent/power_backends/opendcdiag_backend.py` 仍显式抛出 `NotImplementedError`

影响：

1. `Sub-P0 opendcdiag-arm` 不应再被当作空白外部项目。
2. 缺的不是算法资产，而是 promotion、打包、运行、回灌这层控制逻辑。

### Finding 12：现有测试主要证明控制平面骨架，而不是完整 README 愿景

证据：

1. `tests/test_sdc_agent.py` 证明 `cycle()` 编排成立
2. `tests/test_sdc_campaign.py` 和 `tests/test_offline_to_campaign_integration.py` 证明单次差分链路成立
3. 现有测试没有证明：
   - 多 fault campaign
   - 真实 injector
   - opendcdiag backfill

影响：

1. 当前代码“能跑主干”不等于“已完成愿景”。
2. 新计划必须把测试分层写清楚，而不是用少量集成测试代替完成度判断。

---

## 4. 直接导出的设计结论

基于以上发现，完整重构必须遵守以下结论：

1. 保留现有控制平面骨架，不推倒重写。
2. 将系统明确拆成三层：
   - 高频内循环
   - 低频外循环
   - 硬件验证环
3. 引入双 profile：
   - `SIM_SAFE`
   - `HW_AGGRESSIVE`
4. 将数据库从单表升级为兼容式多表模型。
5. 把 `opendcdiag-arm` 放在最终验证环，而不是快速仿真路径里。
6. 把 README 愿景中真正未完成的硬缺口明确归因到：
   - fault matrix
   - gem5 injector
   - promotion/backfill

---

## 5. 最值得保留的实现

如果只保留项目里最有价值的一批基础设施，应保留：

1. `sdc_agent/generation.py`
2. `sdc_agent/materialize.py`
3. `sdc_agent/differential.py`
4. `sdc_agent/campaign.py`
5. `sdc_agent/scheduler.py`
6. `microprobe/src/microprobe/driver/genetic.py`

这几块已经足够支撑新架构的主骨架。

---

## 6. Findings 结论

当前仓库最真实的状态不是“功能残缺的散装脚本”，而是：

1. 已经有一个强骨架。
2. 缺的是分层、数据模型和最后两层执行面。
3. 因此最优策略是架构重构与合同升级，而不是大规模重写已有实现。
