# CORE179：源 load 数梯度实验结果（1→4 源）

> 日期：2026-09-02
> 任务：补全源 load 数梯度（已有1源0-fail、2源14fail/36min），新增3源、4源变体，验证触发率随源数变化的规律。
> 关联：[[CORE179_2SRC_ALU_PORT_RESULT]]、[[CORE179_SDC_TRIGGER_RESEARCH_REPORT]]

## 一、实验设计

在已验证的 mrn_nuke_2src_alu 基础上，只增加源 load 数（其余完全不变：store→forwarding 背靠背骨架、ALU 轮换、count=1024、两阶段验证协议）：

| 变体 | 源 load 数 | 依赖链深度 | ALU 运算示例 |
|---|---|---|---|
| mrn_nuke（原版） | 1 | 0（无ALU） | 原值搬运 |
| mrn_nuke_2src_alu | 2 | 1 跳 | a ^ b |
| mrn_nuke_3src_alu | 3 | 2 跳 | a ^ b ^ c |
| mrn_nuke_4src_alu | 4 | 3 跳 | a ^ b ^ c ^ d |

单变量：源 load 数。每变体两阶段验证（排除179核60s须0fail + 全核192含179+auto seed+36min）。

## 二、实验数据（36min 坐实）

| 源 load 数 | fail/36min | 独立seed | 线程 | 触发率 | 首失败(平均) |
|---|---|---|---|---|---|
| 1 源 | 0 | 0 | — | 0 | — |
| 2 源 | 14 | 14 | 全179 | ~0.39/min | — |
| 3 源 | 10 | 9 | 全179 | ~0.28/min | 473s |
| 4 源 | 4 | 4 | 全179 | ~0.11/min | 633s |

阶段1（排除179核60s）：3源、4源均 0-fail（变体无bug）。
确定性核实：3源(seed=LCG:294104253)、4源(seed=LCG:2142989040)排除179+同seed→均0fail，确认真179特异SDC。

## 三、关键发现：触发率随源数增加而下降

**触发率非单调上升，而是 2源最高、3源次之、4源最低：**

- 1→2源：0→14fail（跳变，跨阈值，从不触发到触发）
- 2→3→4源：14→10→4fail（逐渐下降）

这说明：
1. **"≥2源"是阈值条件**，不是"源越多越强"——2源刚好跨过触发门槛
2. **更多源 load 反而降低触发率**——依赖链拉长、指令数增多，扰动紧时序窗口（呼应 mrn_pairs keep8 拉开7条灭活的发现：时序窗口对源数也敏感）

## 四、对诱因结论的精化

原结论：触发诱因 = "2源load + 数据ALU依赖链" + "紧时序背靠背"（二者缺一不可）。

精化：
- **"2源load + 数据ALU"是触发诱因的必要组成**——1源不触发，2源即触发
- 但**不是"越多越好"**——"≥2源"是阈值型条件，源数过多反而因时序窗口拉长而降低触发率
- **触发率受源数×时序的交互影响**：2源最易命中179 marginal窗口，3/4源依赖链更深但时序窗口被扰动

完整诱因表述：**触发179 SDC的诱因是"≥2源load + 数据ALU依赖链"配合"紧时序背靠背forwarding"，源数以2源为最优阈值，过多反而降低触发率。**

## 五、可追溯产物

- 变体源码：`tests/cpu/misc/mrn_nuke_3src_alu.cpp`、`mrn_nuke_4src_alu.cpp`
- meson 注册：`tests/cpu/meson.build`
- 阶段1日志：`movbe_log/trigger_variants/mrn_nuke_{3src,4src}_alu_stage1_no179.log`
- 阶段2日志：`movbe_log/trigger_variants/mrn_nuke_{3src,4src}_alu_stage2_36min.log`
- 串行脚本：`run_3src_4src_serial.sh`
