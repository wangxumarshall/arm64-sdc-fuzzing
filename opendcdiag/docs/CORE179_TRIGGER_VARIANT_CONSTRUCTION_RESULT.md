# CORE179：相似测试变体构造结果（4 变体，3 触发）

> 日期：2026-09-01
> 任务：把 22 测试中与 movbe/mrn_rmw 相似但不触发的候选测试，按三个方向修改输入方式/指令序列，构造变体使其也能检出 SDC。
> 这是"找触发特征"的正向实验，与之前的反向删减探针互补。
> 关联计划：[[PLAN_SDC_TRIGGER_VARIANT_CONSTRUCTION]]，判别依据：[[CORE179_22TESTS_LOAD_INPUT_SEQUENCE]]、[[objdump-7tests-trigger-vs-notrigger]]

## 一、变体设计（4 个，按三个方向）

| 变体 | 基础测试 | 改造方向 | 改了什么 | 骨架是否变 |
|---|---|---|---|---|
| mrn_nuke_2src_alu | mrn_nuke(0-fail) | 方向一：2源load+ALU依赖链 | 1源src→2源srcA/srcB；store原值→store(a op b) | 否（forwarding骨架不变） |
| mem_disambig_alu | mem_disambiguation(0-fail) | 方向一：ALU加工 | store原值values[i]→store(values[i] op offsets[i]) | 否（pattern1 forwarding骨架不变） |
| mrn_nuke_recross | mrn_nuke(0-fail) | 方向二：movbe式同址重读 | forwarding(store temp;load temp)→L1D同址重读(load src;ALU;store dst异址;load src同址;cmp) | 是（forwarding→重读，inline asm固定寻址） |
| mrn_nuke_dense | mrn_nuke(0-fail) | 方向三：提高load密度 | count 1024→16384（16倍，ldr/轮 24576→393216） | 否（仅改count） |

## 二、验证结果（两阶段协议）

### 阶段1：排除179核60s —— 全 0-fail（证明变体本身无 bug）

| 变体 | exit | pass_loops | fail_blocks | miscompare行 |
|---|---|---|---|---|
| mrn_nuke_2src_alu | pass | 108 | 0 | 0 |
| mem_disambig_alu | pass | 155 | 0 | 0 |
| mrn_nuke_recross | pass | 108 | 0 | 0 |
| mrn_nuke_dense | pass | 50 | 0 | 0 |

**4 变体排除 179 核均 0-fail，证明变体逻辑正确（expected 计算自洽，非变体 bug）。**

### 阶段2：全核192含179 + auto seed —— 3/4 触发（坐实）

#### 初筛 5min（3 触发）

| 变体 | fail_blocks | 失败线程 | 首失败时间 | seed |
|---|---|---|---|---|
| mrn_nuke_2src_alu | **2** | 179, 179 | 51.7s, 147.7s | LCG:850477535, LCG:1705962479 |
| mem_disambig_alu | **2** | 179, 179 | 212.4s, 249.9s | LCG:392101390（同seed retry，1独立样本） |
| mrn_nuke_recross | 0 | — | — | — |
| mrn_nuke_dense | **1** | 179 | 22.5s | LCG:1118352743 |

#### 坐实 36min（30min理论×120%，3 触发变体各跑）

| 变体 | 时长 | fail_blocks | 失败线程 | pass_loops | 触发率 |
|---|---|---|---|---|---|
| mrn_nuke_2src_alu | 36m | **14** | 全179 | 3005 | ~0.39/min（强触发） |
| mem_disambig_alu | 36m | **1** | 179 | 5539 | ~0.03/min（弱触发） |
| mrn_nuke_dense | 36m | **1** | 179 | 1775 | ~0.03/min（弱触发） |
| mrn_nuke_recross | 5m | 0 | — | 546 | 不触发 |

**3 个变体坐实触发 179 SDC，全在 thread 179。** mrn_nuke_recross 5min 0-fail（不触发）。

#### mem_disambig_alu 确定性核实（排除变体bug）

fail 消息 `expected 0x790 got 0xbe9e0f1a91086b94`（expected是小值，got是巨大值，可疑）。核实：
- **排除179核 + 同seed(LCG:622154420) → exit:pass，0 fail** → 确认真179特异SDC，非变体bug
- expected自洽：pattern 87 = 87%4=3 = sub，expected=values[87]-offsets[87]=0x790合法
- 每pattern自己store再load（forwarding背靠背），offsets重复不影响（鸽巢512落511 slot，各自store→load独立）

#### 触发率分层

- **强触发**：mrn_nuke_2src_alu（14fail/36min，~0.39/min）——复刻mrn_rmw的"2源load+ALU依赖链"核心特征
- **弱触发**：mem_disambig_alu（1fail/36min）、mrn_nuke_dense（1fail/36min，~0.03/min）——能触发但率低
- 说明"2源load+ALU依赖链"是最强可移植触发特征，"ALU加工+随机地址"和"提高密度"是弱触发改造

## 三、关键发现与对旧结论的修正

### 发现1：mrn_nuke_2src_alu 触发 → "2源load+ALU依赖链"是可移植触发特征

- mrn_nuke 原版（1源+原值forwarding）0-fail；加 2源+ALU 后触发。
- **这回答了 v2 探针的未解 confound**：v2 探针(probe_asm_fwd_v2)在 mrn_nuke 骨架加 eor 仍 1 源 → 0-fail；而本变体是完整 **2源load + ALU** 组合 → 触发。
- 结论：**"2源load + 数据ALU依赖链"是 mrn_rmw 区别于 mrn_nuke 的关键触发特征**，可移植到 mrn_nuke 骨架使其触发。
- 修正 [[probe-asm-fwd-v2-both-0fail-dataalu-refuted]]：该记忆说"数据ALU不是触发开关"——单加 ALU 确实不触发（v2证），但 **2源load+ALU组合**才触发。相关性真，因果性在于"2源load+ALU"组合而非单独ALU。

### 发现2：mem_disambig_alu 触发 → "ALU+随机地址forwarding"也触发

- mem_disambiguation 原版（2源offsets/values，store原值，随机地址forwarding）0-fail；store 值改 ALU 加工后触发。
- 说明触发**不限于线性地址（temp+i）**，随机地址（buffer+off）的 forwarding + ALU 也触发。
- 关键fail细节：`pattern 291 offset 1144: expected 0x90 got 0xe3c04e15e8b0fd7a`
- **确定性核实**：排除179核+同seed(LCG:392101390) → exit:pass 0-fail → 确认真179特异SDC，非变体bug。
- expected自洽核实：每个pattern自己store再load（forwarding背靠背），必读到自己刚存的值，offsets重复也不影响（鸽巢512 pattern落511 slot，但同slot的pattern各自store→load独立）。0x90是values[291]-offsets[291]的合法值。

### 发现3：mrn_nuke_dense 触发 → 推翻"load计数非驱动"假说

- mrn_nuke 原版 24576 ldr/轮 0-fail；曾记 [[objdump-7tests-trigger-vs-notrigger]] 据此认为"触发非load绝对次数驱动"。
- 但 mrn_nuke_dense 把 count 1024→16384（ldr/轮 24576→393216，16倍），**5min 触发**（22.5s首失败）。
- **修正**：load 绝对次数**确实有影响**——原版0-fail可能是密度低于触发阈值，16倍后跨过阈值。之前的"非load计数驱动"结论是基于"24576 vs 32768"的小跨度对比下的判断，跨度不够；16倍跨度显现了密度效应。
- 这不矛盾"紧时序必要"：密度提升 = 单位时间load次数多 = 命中179 marginal窗口概率高。

### 发现4：mrn_nuke_recross 不触发 → L1D同址重读不可简单移植

- mrn_nuke_recross 复刻 movbe 的"两次ldr同址重读"（inline asm固定[base,idx,lsl#3]寻址），5min 0-fail（546 pass）。
- movbe 原版同模式 1.9/min 高触发，移植到 mrn_nuke 骨架（uint64粒度 + per-thread buffer）却不触发。
- 可能原因：movbe 触发还依赖 64KB 共享 buffer / 32位w寄存器粒度 / 特定rev指令，不只"同址重读"这一条。
- 或 5min 样本不足（但 movbe 5min 能拿~9 fail，同模式移植0-fail倾向真不触发）。

## 四、综合判别：哪些方向能移植触发

| 改造方向 | 触发? | 含义 |
|---|---|---|
| 2源load+ALU依赖链（mrn_nuke_2src_alu） | ✅ | mrn_rmw 触发特征可移植到 mrn_nuke 骨架 |
| ALU加工+随机地址forwarding（mem_disambig_alu） | ✅ | 不限线性地址，随机地址forwarding+ALU也触发 |
| 提高load密度16倍（mrn_nuke_dense） | ✅ | load绝对次数有影响，密度跨阈值触发 |
| movbe式L1D同址重读（mrn_nuke_recross） | ❌ | 不可简单移植，movbe触发还依赖别的 |

**核心结论**：触发 SDC 不是单一特征决定，而是多因素。能让 0-fail 的相似测试触发 SDC 的有效改造是：
1. **加 2源load + 数据ALU依赖链**（最干净，回答了v2探针confound）
2. **store值经ALU加工**（即使随机地址forwarding也触发）
3. **提高load密度**（跨过触发阈值）

而"movbe式L1D同址重读"这一条**不能**简单从 movbe 移植到 mrn_nuke 骨架——说明 movbe 族的触发有其自身不可移植的特征（可能依赖共享buffer/32位粒度/rev指令）。

## 五、可追溯产物

- 变体源码：`tests/cpu/misc/mrn_nuke_{2src_alu,recross,dense}.cpp`、`tests/cpu/memory/mem_disambig_alu.cpp`
- meson 注册：`tests/cpu/meson.build`（misc区3行 + memory区1行）
- 阶段1日志：`movbe_log/trigger_variants/*_stage1_no179.log`
- 阶段2日志：`movbe_log/trigger_variants/*_stage2_5min.log`
- 编译验证：`ninja -C builddir` 通过，4变体 -e 识别 + 2s短跑pass

## 六、方法论与口径

- **fail 口径**：数唯一 `- test:` 块内含 `result: fail` 的事件（[[sdc-fail-count-unique-blocks]]）。注意 mem_disambig_alu 的 fail 消息用 "mismatch"（report_fail_msg）而非框架标准的 "miscompare"，解析时不能要求同时含 miscompare，否则漏计。
- **确定性核实**：低率变体（1fail/36min）必须做"排除179+同seed→0fail"核实，区分真SDC vs 变体bug。mem_disambig_alu 经此核实确认真SDC。
- **时间设置**：opendcdiag 用 `-T` 设总时间，按理论时间×120%设（30min→`-T 36m`）。
- **串行跑**：多变体用脚本串行（run_variants_30min_serial.sh），避免并发抢179核污染触发窗口（[[silifuzz-contamination-window]] 教训）。
- **样本量**：mrn_nuke_2src_alu 14fail 充分坐实；mem_disambig_alu/mrn_nuke_dense 各1fail虽经确定性核实为真SDC，但样本少，率低（~0.03/min），可重复性需更长跑测确认。
