# CORE179："2源load+ALU依赖链"跨 mrn 类骨架移植结果

> 日期：2026-09-02
> 任务：把最强触发特征"2源load+ALU依赖链"（mrn_nuke_2src_alu 14fail/36min 强触发）移植到其他 mrn 类骨架，验证是否通用可移植。
> 关联：[[CORE179_TRIGGER_VARIANT_CONSTRUCTION_RESULT]]、[[PLAN_2SRC_ALU_PORT_TO_MRN]]

## 一、候选与改造

mrn 类核心测试：mrn_rmw（已触发基准）、mrn_nuke（已加2src_alu触发）、mrn_pairs（0-fail）、mrn_reloaded（0-fail）、mrn_flags（纯ALU无store→load，不适合）。

选 mrn_pairs、mrn_reloaded 改造，做 3 个变体：

| 变体 | 基础 | 改造 | 时序 |
|---|---|---|---|
| mrn_pairs_2src_alu（5a） | mrn_pairs | 1源→2源+ALU + **8+8展开改回逐元素背靠背** | 紧（背靠背） |
| mrn_pairs_2src_alu_keep8（5b） | mrn_pairs | 1源→2源+ALU，**保持8+8展开** | 松（拉开7条） |
| mrn_reloaded_2src_alu（6） | mrn_reloaded | qword段1源→2源+ALU（byte/dword段去掉） | 紧（背靠背） |

5a vs 5b 唯一差异=时序（紧 vs 松），两者都加了2源+ALU，用来分离"2源+ALU"和"时序"的作用。

## 二、验证结果（两阶段）

### 阶段1：排除179核60s —— 全 0-fail（变体无bug）

| 变体 | exit | fail_blocks |
|---|---|---|
| mrn_pairs_2src_alu | pass | 0 |
| mrn_pairs_2src_alu_keep8 | pass | 0 |
| mrn_reloaded_2src_alu | pass | 0 |

### 阶段2：全核192含179+auto seed+36min（30min×120%）

| 变体 | fail数 | 独立seed数 | 失败线程 | 首失败时间(平均) | 触发率 |
|---|---|---|---|---|---|
| **mrn_pairs_2src_alu（5a，紧时序）** | **46** | 46 | 全179 | 331s | ~1.28/min |
| mrn_pairs_2src_alu_keep8（5b，松时序） | **0** | 0 | — | — | 不触发 |
| **mrn_reloaded_2src_alu（6，紧时序）** | **126** | 126 | 全179 | 15.3s | ~3.5/min |

每个 fail 都是独立 seed（46/46、126/126 全独立），全在 thread 179。

### 确定性核实（排除变体bug）

- mrn_pairs_2src_alu：取首fail seed(LCG:323188435)，排除179+同seed→exit:pass 0fail → 真SDC
- mrn_reloaded_2src_alu：取首fail seed(LCG:625904185)，排除179+同seed→exit:pass 0fail → 真SDC

## 三、关键发现

### 发现1：5a触发(46fail) vs 5b不触发(0fail) —— 时序是灭活开关

两者唯一差异是时序（5a逐元素背靠背 vs 5b 8store+8load拉开7条），都加了2源+ALU。
- 5a（紧）46 fail，5b（松）0 fail
- **"2源load+ALU依赖链"不是充分条件**——5b有它却0fail
- **时序拉开7条是灭活开关**——即使加2源+ALU，时序一拉开就0fail
- 触发需要"2源+ALU"**且**"紧时序背靠背"两者同时满足

这干净回答了之前 22 测试判别里的"紧时序必要非充分"——现在确认：紧时序是必要条件，且单独的紧时序也不够（mrn_nuke原版紧时序但1源无ALU也0fail），需要"紧时序+2源+ALU"组合。

### 发现2：mrn_reloaded_2src_alu 126fail/36min —— "2源+ALU"是最强通用可移植触发特征

- mrn_reloaded 原版（1源原值背靠背）0-fail；加2源+ALU后 126 fail/36min（~3.5/min）
- 这是目前所有变体里**触发率最高**的，接近甚至超过 movbe 原版（1.9/min）
- 首失败平均15.3s（movbe是约30s首失败），说明179的marginal窗口被高频命中

### 发现3：不同骨架加2源+ALU触发率差异大（但都触发）

紧时序骨架加2源+ALU的触发率：
| 骨架 | 触发率 | 说明 |
|---|---|---|
| mrn_reloaded（背靠背，qword） | ~3.5/min | 最高 |
| mrn_pairs（5a，改回背靠背） | ~1.28/min | 中 |
| mrn_nuke（背靠背） | ~0.39/min | 较低（14fail/36min） |

三者都触发，但率差9倍。说明"2源+ALU依赖链"是**通用可移植触发特征**（紧时序骨架加上都能触发），但触发率受骨架具体结构影响（mrn_reloaded的store→load→立即cmp的极紧依赖链比mrn_nuke的store→load→store更易命中窗口）。

## 四、综合结论

**"2源load+ALU依赖链"是通用可移植的 179 SDC 触发特征**——前提是骨架本身时序紧（背靠背）。移植到 mrn_nuke/mrn_pairs/mrn_reloaded 三个不同骨架都能触发（全179），触发率0.39~3.5/min。

触发的**两个必要条件**（缺一不可）：
1. **2源load + 数据ALU依赖链**（store值是两源经ALU加工的结果，非原值）
2. **紧时序背靠背**（store→load forwarding 0间隔；时序拉开7条即灭活）

这推翻了之前"输入方式无判别力"的部分判断——**store值是否经数据ALU加工**（输入方式的子特征）配合紧时序是有判别力的：紧时序+2源+ALU=触发，紧时序+1源原值=0fail（mrn_nuke原版），紧时序+2源+ALU+松时序=0fail（5b）。

## 五、可追溯产物

- 变体源码：`tests/cpu/misc/mrn_pairs_2src_alu.cpp`、`mrn_pairs_2src_alu_keep8.cpp`、`mrn_reloaded_2src_alu.cpp`
- meson 注册：`tests/cpu/meson.build`（misc区3行）
- 阶段1日志：`movbe_log/trigger_variants/*_stage1_no179.log`
- 阶段2日志：`movbe_log/trigger_variants/*_stage2_36min.log`
- 串行脚本：`run_2src_alu_port_serial.sh`
- 编译验证：ninja通过，3变体2s短跑pass
