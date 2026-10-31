# CORE179 AGU 压力测试战役结果（agu_stress 四变体）

> 日期：2026-09-03（战役 12:10–14:14，nohup 脱离会话，SSH 断连未中断）
> 平台：Kunpeng 920 (ARMv8.1-A, AArch64), 192 核, openEuler
> 工具：OpenDCDiag ARM64 移植版 (opendcdiag-837c6948deaa-dirty)
> 目标核：逻辑核 179
> 基准：`mrn_nuke_2src_alu`（{add,sub,eor,and} 轮换）= 14 fail/30min 全 179（~0.47/min）

---

## 摘要

按外部提案构造 4 个 AGU 压力测试（提案代码经 6 处方法论修正后实现），各 30min 全核 192 含 179 + auto seed 两阶段验证：

| 测试 | 指令流（每元素） | fail/30min | fail核 | ~率/min | 预期 → 实际 |
|------|----------------|-----------|--------|---------|------------|
| `agu_stress_2src` | 2源load + {add,eor,and,orr}轮换 + str/reload/str | **19** | **全179** | 0.63 | 触发 → ✅触发（率超基准） |
| `agu_stress_1src` | 1源load + 同轮换 + str/reload/str | 0 | — | 0 | 0-fail → ✅命中预言 |
| `agu_stress_store_only` | 2源load + 同轮换 + **2×str，无reload** | **1** | **179** | 0.03 | 0-fail → **⚠️意外触发** |
| `agu_stress_unaligned` | 2src骨架 + 16B槽位旋转偏移(7/8非对齐) | 0 | — | 0 | 未知 → 0-fail |

三个核心发现：

1. **轮换成分鲁棒性确认**：把 sub 换成 orr（{add,eor,and,orr}）仍触发且率更高（19 vs 14，0.63 vs 0.47/min）→ 触发不依赖特定指令成分，"轮换/混合"这个模式本身才是关键（与 ALU 单指令对比实验结论互证）。
2. **`agu_stress_store_only` 无 reload 也触发 1 次**：该变体只有 ldr,ldr,ALU,str,str（无任何 temp 重读、无 store→load forwarding 窗口），却在 179 上出 1 个真实 memcmp miscompare（ttf=32s，loop-count=1，seed LCG:2093805559，阶段1排除179核0-fail证明非测试bug）→ **forwarding/reload 窗口并非严格必要**，但率相差 ~20 倍（1 vs 19），reload 是强放大器而非绝对开关。
3. **非对齐寻址 0-fail**：unaligned 版保留完整 2src+轮换+reload 骨架，仅地址改为 16B 槽位旋转偏移（7/8 非对齐），30min 0-fail → 与 movbe-l1d-variants 的"寻址模式敏感"雷区一致：改寻址即挪时序窗口，0-fail 更可能是布局灭活而非"非对齐路径免疫"。

---

## 1. 实验设计

### 1.1 来源与修正

测试设计来自外部提案（"最大程度压榨 AGU 吞吐"思路：2源load+1store 塞满 2 个 AGU）。提案原始代码有 6 处会出假数据的问题，实现时全部修正：

| # | 提案问题 | 后果（若不改） | 修正 |
|---|---------|--------------|------|
| 1 | checksum 跨轮累加不清零 | 第2轮 g^g=0≠golden，每核必假失败 | memcmp 逐元素冷校验 |
| 2 | `test_time_condition()` 不存在 | 编译不过 | 框架 `TEST_LOOP` 宏 |
| 3 | 纯 C++ `temp[i]=res; x=temp[i];` | 编译器融合/DCE，背靠背 str→ldr 不落二进制 | 房子 `store_qword/load_qword` 内联汇编 |
| 4 | 固定种子 `mt19937_64(123456789)` | 单一输入模式，fixed-seed 陷阱 | `memset_random`（auto seed） |
| 5 | checksum ALU 塞进热循环 | 扰动 21 条指令的触发窗口 | 校验全部移冷路径 |
| 6 | unaligned 初版元素写重叠（off=7 与下元素 off=0 重叠） | 1/8 元素确定性假失败（smoke 阶段1已抓到） | 16B 独立槽位 + 旋转偏移 0..7 |

源码：`tests/cpu/misc/agu_stress_{2src,1src,store_only,unaligned}.cpp`（骨架与 mrn_nuke 系列字节同构）。

### 1.2 变体矩阵

- **2src**（主测试/阳性对照）：`ldr A; ldr B; 轮换ALU{add,eor,and,orr}; str temp; ldr temp(背靠背); str dst` — 3 ldr + 2 str/元素，最大 AGU 压力；轮换成分换掉 sub 测鲁棒性
- **1src**（阴性对照）：去掉 srcB load，操作数换常量 0x5A5A...5A5A — 检验"第2源load必要"（源load梯度实验预言 1src=0-fail）
- **store_only**（预测探针）：`ldr A; ldr B; 轮换ALU; str temp; str dst` — 保留 2 源+轮换+store 压力，**去掉 reload**，检验"reload/forwarding 必要"预测
- **unaligned**（未知探针）：2src 完整骨架 + 每元素 16B 槽位内旋转偏移 0..7（7/8 非对齐访问），golden 从同偏移读取冷重算

### 1.3 两阶段验证协议

每变体：阶段1 `taskset 0-178,180-191` 60s 须 0-fail（证无bug）→ 阶段2 `-n 192 -T 30m` 含179 + auto seed。监控脚本 taskset 绑核0（硬性要求）。统计口径 = 唯一 `result: fail` 块数。

---

## 2. 实验数据

### 2.1 两阶段结果

| 变体 | 阶段1(排除179,60s) | 阶段2 fail块 | miscompare行 | exit | pass行 |
|------|--------------------|--------------|--------------|------|--------|
| 2src | 0-fail ✅ | **19** | 19（无双计） | fail | 3007 |
| 1src | 0-fail ✅ | 0 | 0 | pass | 3169 |
| store_only | 0-fail ✅ | **1** | 1 | fail | 3106 |
| unaligned | 0-fail ✅ | 0 | 0 | pass | 1386 |

### 2.2 2src 的 19 fail 分布

- **核位置：19/19 全在 179**（框架 `thread:` 字段验证，mask 从左数下标 19/19 与 thread 一致）
- ttf（秒）排序：22.2, 29.5, 38.8, 46.4, 67.1, 93.5, 126.7, 219.0, 341.9, 356.9, 367.5, 497.4, 516.3, 517.5, 608.0, 642.2, 693.7, 744.9, 752.4 —— 首失败 22s，末失败 752s，全程持续，非一次性爆发
- ~0.63 fail/min（基准 mrn_nuke_2src_alu ~0.47/min，同量级偏高）

### 2.3 store_only 的 fail 详情

```
thread: 179, time-to-fail: 32.468s, loop-count: 1, seed: LCG:2093805559
E> Failed at ../tests/cpu/misc/agu_stress_store_only.cpp:88: agu_stress_store_only data miscompare
```

第 1 个 loop iteration 即失败；阶段1排除179核 0-fail；memcmp 的是 dst vs golden → 错误在 src load / ALU / store 三者之一（此变体无 reload，无法进一步区分，与 mrn-rmw-recompute 的已知局限同类）。

### 2.4 同战役环境有效性

四变体串行同环境跑（12:10–14:14），2src 在 13:14 前触发 19 次、store_only 在 13:44 触发 1 次，同期 179 缺陷活跃；1src/unaligned 的 0-fail 不是"179 当天不活跃"。

---

## 3. 分析

### 3.1 轮换成分鲁棒性（2src 触发，率更高）

{add,eor,and,orr} vs 基准 {add,sub,eor,and}：换掉一个成分（sub→orr）触发率 0.63 vs 0.47/min，同量级。结合单指令实验（纯 add/sub/eor/and 全 0-fail），**触发驱动是"多条不同 ALU 轮换/混合"这个模式，不挑具体成分**。orr 替换后率略升，符合"率对指令布局敏感、模式不变则量级不变"的既往规律。

### 3.2 store_only 单样本触发——reload 必要性被击穿（重要，需复跑确认）

**事实**：无任何 reload/forwarding 窗口的纯 `2源load+轮换ALU+2×store` 在 179 出了 1 个真实 miscompare。

**含义**：如果复跑坐实，"触发需背靠背 store→reload"要从必要条件降级为**强放大器**（~20×：19 vs 1）。最小诱因配方向"2 源 load + 轮换 ALU 依赖链"收敛——reload 不是开关，是把率放大一个量级的放大器。

**边界与谨慎**：
- 单样本（1 fail/30min），且 ttf=32s/loop-count=1。按 no-premature-conclusions 纪律，先不下结论，需 1–2h 复跑或多样本确认
- 该 fail 无法区分错在 src load / ALU / store（无 reload 意味着没有 recompute 分离手段在手；可考虑后续加冷分支 recompute 增强版）
- 与既有结论的关系：sdc-trigger-constant-probability-per-ldr（"str→ldr 须 ≤2cyc 短窗口"）若被坐实需再收窄——那批实验的 0-fail 对照组里可能没有"2源+轮换ALU"这个当时未知的必要成分，0-fail 可能是缺成分而非缺窗口

### 3.3 unaligned 0-fail 的解读（保守）

unaligned 保留了 2src 的全部触发成分（2源+轮换+背靠背 reload），唯一差异是寻址（`base + i*16 + (i&7)` 替代 `base + i*8`）。0-fail 最可能的解释是**寻址模式改变 → AGU/调度时序挪动 → 布局灭活**（movbe-l1d-variants-schedule-sensitivity 同型雷区），而非"非对齐路径免疫缺陷"。不能作为"AGU 非对齐路径干净"的证据。pass 行数 1386 vs 2src 3007（每轮慢 ~2.2×，槽位 16B 摊薄访存密度），轮次差异也是混淆项。

### 3.4 诱因结论更新

本次实验后诱因配方各成分的证据状态：

| 成分 | 必要性证据 | 状态 |
|------|-----------|------|
| ≥2 源 load | 1src 0-fail（本战役）+ 梯度实验 1源0-fail | **必要，坐实** |
| ALU 轮换/混合 | 4 单指令全 0-fail（9-03）+ 2src 换成分仍触发（本战役） | **必要，坐实** |
| 背靠背 store→reload | store_only 1 fail（本战役，单样本待复跑） | **降级候选：强放大器 (~20×) 而非必要条件** |
| 全核并发压力 | 既往实验（单核179孤立不触发） | 必要，坐实 |

---

## 4. 下一步

1. **复跑 store_only**（优先级最高）：1–2h 全核 + auto seed，确认 1 fail/30min 是真实低率还是孤例；若复现 ≥1 fail，"reload 必要"正式降级为"放大器"
2. **store_only 增强版**：冷分支加 recompute（用 srcA/srcB 重算 golden），下次触发时区分 src load 错 / ALU 错 / store 写错
3. （可选）unaligned 换"仅 src 非对齐、temp/dst 对齐"的半非对齐版，把寻址扰动和 AGU 非对齐路径解耦——但预期同样撞布局敏感雷区，优先级低
4. 同窗口跑一次 mrn_nuke_2src_alu 作日内基准（本战役 2src 本身可视作等效基准，暂不必须）

---

## 5. 可追溯数据

- 阶段1日志：`movbe_log/agu_stress/{variant}_stage1_no179.log`（2026-09-03）
- 阶段2日志：`movbe_log/agu_stress/{variant}_stage2_30min.log`（2026-09-03）
- 战役总日志：`movbe_log/agu_stress/campaign_nohup.log`（nohup，12:10–14:14）
- 战役脚本：`run_agu_stress_serial.sh`
- 监控日志：`movbe_log/agu_stress/{variant}_stage2_monitor.log`（绑核0）
- 源码：`tests/cpu/misc/agu_stress_{2src,1src,store_only,unaligned}.cpp` + `tests/cpu/meson.build` 注册

## 6. 口径备忘（坑）

**fail 核号换算**：`cpu-mask` 里 `X` **从左数的下标直接等于逻辑核号**（本战役 19/19 与框架 `thread:` 字段一致验证）。不要做 192-1-pos 换算——那是把方向搞反的错误口径（本报告初稿曾犯，已纠正；此前文档若引用"从右数第N位"的说法需按此口径复核）。
