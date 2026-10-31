# CORE179 SDC：ALU 逐指令 / AGU / SIMD(NEON) 三组判别实验——设计与结果

> 日期：2026-09-03 初稿，2026-09-04 补 NEON 矩阵（§5）
> 平台：Kunpeng 920 (ARMv8.1-A, 192 逻辑核)，openEuler / aarch64，OpenDCDiag ARM64 port
> 日志根目录：`movbe_log/trigger_variants/`（ALU 系列）、`movbe_log/agu_stress/`（AGU 系列）、`movbe_log/neon_rot/`（SIMD baseline）、`movbe_log/neon_matrix/`（SIMD 矩阵）
> 源码：`tests/cpu/misc/mrn_nuke_2src_*.cpp`、`tests/cpu/misc/agu_stress_*.cpp`、`tests/cpu/misc/neon_rot_*.cpp`

---

## 0. 三组实验在研究路线中的位置

此前的正向构造与跨骨架移植（2026-09-01 ~ 09-02）已经锁定触发诱因为三要素：

1. **≥2 源 load + ALU 依赖链**（1 源 = 0 fail，梯度实验证实）
2. **ALU 轮换/混合**（候选，待本组实验判别）
3. **紧时序**（store→reload 背靠背，拉开 7 条指令 = 0 fail）

三组实验分别对诱因做逐项判别：

| 实验组 | 判别问题 | 结论一句话 |
|---|---|---|
| ALU 逐指令 | 是"特定 ALU 指令"还是"轮换/混合"在起作用 | **轮换/混合是必要条件**，纯单指令全 0-fail |
| AGU 四变体 | 触发是否依赖源数 / reload 窗口 / 寻址模式 | **2 源最优**；store_only 无 reload 仍触发 1 次（单样本）；改寻址灭活 |
| SIMD (NEON) | 触发配方是否绑定标量数据通路 | **不绑定**——NEON 向量通路同样触发，触发率为标量基准 1.7 倍 |

---

## 1. 统一实验方法（三组共用）

### 1.1 两阶段验证协议

- **阶段 1（用例可靠性）**：`taskset -c 0-178,180-191` 排除 179 核，191 线程跑 60s，**必须 0 fail**——证明测试用例本身在正常核上不误报。
- **阶段 2（SDC 触发）**：全核 192 线程（含 179），auto seed（不固定 `-s`），30~36min，`--ignore-os-error --ignore-timeout` 不停跑。
- 监控脚本 `taskset -c 0` 绑核 0（用户硬性要求：>10min 的跑测必须开监控且监控绑离 179，避免挤占 179 算力污染全核并发压力条件）。

### 1.2 判读口径

- **fail 数 = 唯一 `result: fail` 块数**（python 按 `- test:` 切块，块内含 `result: fail` 才计 1）——不能用 `grep -c miscompare`（每 fail 2 行 miscompare，双计虚高 2 倍）。
- fail 核号 = cpu-mask 从左数下标，**直接等于核号**（勿做 192-1-pos 换算）。
- 阶段 2 的 exit: fail + 唯一 fail 块 + miscompare 三者交叉确认。

### 1.3 统一热循环骨架（mrn_nuke 骨架，asm 保证背靠背）

```c
TEST_LOOP(test, 1 << 13) {
    for (int i = 0; i < COUNT; i++) {        // COUNT=1024, 每缓冲 8KB
        uint64_t a = srcA[i];                 // 源 load A
        uint64_t b = srcB[i];                 // 源 load B
        uint64_t res;
        switch (i % 4) { /* 轮换 ALU */ }     // 数据 ALU 加工
        store_qword(&temp[i], res);           // asm: str x,[addr]
        store_qword(&dst[i], load_qword(&temp[i]));  // asm: 背靠背 ldr→str reload
    }
    if (memcmp(dst, expected, ...) != 0)
        report_fail_msg("... data miscompare");   // 冷分支, 不碰热循环
}
```

`store_qword`/`load_qword` 为 `__asm__ volatile` 内联（objdump 验证 str→ldr 背靠背落进二进制，编译器不可融合/消除）。golden 在 init 阶段一次性算好（逻辑核 0 上跑，天然隔离 179）。

---

## 2. 实验组一：ALU 逐指令判别（2026-09-03）

### 2.1 实验设计

**判别问题**：正向构造的触发配方里 ALU 是轮换的 `{+,-,^,&}`。触发依赖的是"某条特定 ALU 指令"，还是"轮换/混合"这个模式本身？

**设计**：把 mrn_nuke 2src 骨架的 switch 轮换乘掉，固定为单条指令，其余（2 源 load、背靠背 reload、缓冲布局、loop 次数）**逐字节不动**。四个单指令变体 + 轮换版对照 + 同日 3src/4src 阳性对照：

| 测试 | ALU 操作 | 时长 |
|---|---|---|
| `mrn_nuke_2src_add` | 仅 `+` | 36min |
| `mrn_nuke_2src_sub` | 仅 `-` | 36min |
| `mrn_nuke_2src_eor` | 仅 `^` | 36min |
| `mrn_nuke_2src_and` | 仅 `&` | 36min |
| `mrn_nuke_2src_alu`（对照） | 轮换 `{+,-,^,&}` | 30min |
| `mrn_nuke_3src_alu`（同日阳性对照） | 轮换，3 源 | 36min |
| `mrn_nuke_4src_alu`（同日阳性对照） | 轮换，4 源 | 36min |

### 2.2 实验结果

| 测试 | 唯一 fail 块 | fail 核 | loops | 触发率 |
|---|---|---|---|---|
| 2src_add（纯加） | **0** | — | — | 0 |
| 2src_sub（纯减） | **0** | — | — | 0 |
| 2src_eor（纯异或） | **0** | — | — | 0 |
| 2src_and（纯与） | **0** | — | — | 0 |
| 2src_alu（轮换乘减） | **14** | 全 179 | 1547 | ~0.47/min |
| 3src_alu（轮换，同日） | **10** | 全 179 | 1940 | ~0.28/min |
| 4src_alu（轮换，同日） | **4** | 全 179 | 1930 | ~0.11/min |

（日志：`movbe_log/trigger_variants/mrn_nuke_2src_{add,sub,eor,and}_stage2_36min.log`、`mrn_nuke_2src_alu_30min.log`、`mrn_nuke_3src/4src_alu_stage2_36min.log`）

### 2.3 结论

1. **"ALU 操作轮换/混合"是触发 179 SDC 的必要条件**：同骨架同布局下，四条纯单指令全部 0-fail，换回轮换版立即触发（14 fail/30min 全 179）。
2. **否定"特定 ALU 指令"假说**：add/sub/eor/and 没有任何一条单独具备触发能力——缺陷不在某条指令的执行通路，而在**混合指令序列形成的数据流/时序模式**。
3. 同日 3src/4src 阳性对照（10/4 fail）确认实验环境当天触发窗口活着，四个 0-fail 不是环境原因。
4. 结合源 load 梯度（09-02：2src=14 > 3src=10 > 4src=4，非单调）：**诱因精化为"≥2 源 load + 轮换混合 ALU 依赖链 + 紧时序，2 源最优"**——源过多会扰动时序窗口、降低触发率。

---

## 3. 实验组二：AGU 四变体（2026-09-03）

### 3.1 实验设计

**判别问题**：触发对 (a) 源 load 数量、(b) store→reload 窗口、(c) 寻址模式各自多敏感？

**设计**：以 `agu_stress_2src` 为基线（mrn_nuke 骨架，轮换乘 `{+,^,&,|}`——orr 换掉 sub，同时验证轮换指令集可替换），三个变体各改一个变量：

| 测试 | 改动的变量 | 其余 |
|---|---|---|
| `agu_stress_2src`（基线） | 无 | 2 源 load + 轮换 ALU + 背靠背 reload |
| `agu_stress_1src` | 源数 2→1（去掉 srcB） | 其余同基线 |
| `agu_stress_store_only` | **去掉 reload**：`store(temp); store(dst, res)` 两次都写 res，无 `load(temp)` | 其余同基线 |
| `agu_stress_unaligned` | 寻址改非对齐 | 其余同基线 |

```c
// store_only 的关键改动（唯一差异）：
store_qword(&temp[i], res);
store_qword(&dst[i], res);      // 原为 load_qword(&temp[i])，reload 被移除
```

### 3.2 实验结果（各 30min，全核 192 含 179 + auto seed）

| 测试 | 阶段1(排除179) | 唯一 fail 块 | fail 核 | loops | 触发率 |
|---|---|---|---|---|---|
| agu_stress_2src | 0 ✅ | **19** | 全 179 | 1546 | ~0.63/min |
| agu_stress_1src | 0 ✅ | **0** | — | — | 0 |
| agu_stress_store_only | 0 ✅ | **1** | 179 | — | 单样本 |
| agu_stress_unaligned | 0 ✅ | **0** | — | — | 0 |

（日志：`movbe_log/agu_stress/agu_stress_{2src,1src,store_only,unaligned}_stage2_30min.log`）

### 3.3 结论

1. **2 源再确认**：1src = 0 fail，与 09-02 梯度实验一致；"≥2 源 load"是硬阈值。
2. **轮换指令集可替换**：orr 换 sub 后基线仍 19 fail/30min——关键是"轮换/混合"模式，不是具体哪几条指令（与实验组一互证）。
3. **reload 必要性被动摇（单样本，待复跑）**：store_only 无任何 reload 仍触发 1 次（全 179）。若复跑坐实，"背靠背 reload"将从必要条件降级为**强放大器**。当前口径：reload 是强放大器、必要性存疑待复跑。
4. **寻址模式改变 = 灭活**：unaligned 0-fail。这不是"对齐才触发"，而是**改动寻址就改变了指令布局/时序，窗口被挪走**（与此前 movbe-l1d-variants、probe v1 指针重读的教训同族）。
5. fail 核号口径：mask 从左数下标直接等于核号。

---

## 4. 实验组三：SIMD / NEON 通路判别（2026-09-03，`neon_rot_2src`）

### 4.1 实验动机

现有研究表示 CPU SDC 中 SIMD 是多发区（用户指示，2026-09-03）。但 179 此前坐实的检测器全是标量（movbe/mrn_rmw/mrn_nuke/agu_stress 系）；唯一走 SIMD/FMA 通路的 eigen 系列触发率低且间歇（3-6 fail/5min 有时、15min 基线 0-fail 证伪过可复现性），且 eigen 布局不可控（编译器内联展开整个热循环，踩过 380 倍减速的坑）。

**判别问题**：触发配方（2 源 load + ALU 轮换 + 背靠背 reload）搬到 NEON 向量通路，还触发吗？
- 触发 → 病灶不限于标量数据通路（重大新信息）；
- 0-fail → 配方绑定标量通路，定位收窄。
- 无论哪个结果都可读——干净的判别实验。

### 4.2 实验设计

**关键设计选择：`uint64x2_t`（2-lane 64-bit）而非 `uint8x16_t`**——`vaddq_u64/veorq_u64/vandq_u64/vorrq_u64` 每条 lane 的语义与标量版完全同构，"执行通路从标量 ALU 换到 NEON 单元"成为**唯一变量**（16-lane 字节运算会同时改语义和通路，变量不干净）。

```c
// neon_rot_2src 热循环（与标量配方逐项对应）：
uint64x2_t a = data->srcA[i];        // 源 vector load A  (ldr q)
uint64x2_t b = data->srcB[i];        // 源 vector load B  (ldr q)
uint64x2_t res;
switch (i % 4) {                     // 轮换 vector ALU:
    case 0: res = vaddq_u64(a, b);   //   vaddq / veorq /
    case 1: res = veorq_u64(a, b);   //   vandq / vorrq
    case 2: res = vandq_u64(a, b);   // (lane 语义与标量版同构)
    case 3: res = vorrq_u64(a, b);
}
store_vec(&temp[i], res);            // vst1q_u64 -> str q
store_vec(&dst[i], load_vec(&temp[i]));  // asm reload -> 背靠背 ldr q
```

**实现坑（对后续所有 NEON SDC 测试都重要）**：`vld1q_u64` intrinsic 的 reload 会被 GCC 直接消除——objdump 实证：`str q0,[x20,x0]` 之后直接 `str q0,[x19,x0]` 复用 q0，**没有 ldr 发出**（intrinsic 无 volatile 语义，GCC 看得见同址 store→load，值直接待在寄存器里）。这是 movbe_dump DCE 坑在 NEON 上的变体。修复：**reload 必须走 asm**：

```c
static inline uint64x2_t load_vec(const void *addr) {
    uint64x2_t res;
    __asm__ volatile ("ldr %q0, [%1]" : "=w"(res) : "r"(addr) : "memory");
    return res;
}
```

（汇编语法踩坑记录：`str %0.16b` 非法（%0 已含 V 寄存器名，附加 .16b 变 v0.16b.16b）；`str v0,[x2]` 也非法（GAS 要求 SIMD 整存用 q 名）；正确写法 `ldr %q0, [%1]`。）

修复后 objdump 验证骨架落进二进制：

```asm
add  v0.2d, v0.2d, v1.2d     ; 轮换 vector ALU
add  x2, x20, x0             ; &temp[i]
str  q0, [x20, x0]           ; store temp[i]
ldr  q0, [x2]                ; reload 背靠背 (asm 保证, 同址)
str  q0, [x21, x0]           ; store dst[i]
```

### 4.3 实验结果

| 阶段 | 设置 | 结果 |
|---|---|---|
| 阶段 1 | taskset 排除 179，191 核 60s | **0 fail** ✅ 用例可靠 |
| 阶段 2 | 全核 192 含 179 + auto seed 30min（19:15–19:45） | **33 个唯一 fail 块，全 thread 179** |

阶段 2 明细：1545 loop 完成，exit: fail；33 个独立 seed（LCG 各异）；time-to-fail 11.6s ~ 894.6s，**首触发仅 11.6 秒**；触发率 **~1.1 fail/min**。

（日志：`movbe_log/neon_rot/neon_rot_2src_stage2_30min.log`）

### 4.4 与标量版的对比

| 指标 | neon_rot_2src（NEON） | agu_stress_2src（标量基准） |
|---|---|---|
| 唯一 fail 块 / 30min | **33（~1.1/min）** | 19（~0.63/min） |
| fail 核 | 全部 179 | 全部 179 |
| loops | 1545 | 1546 |
| 首触发 | 11.6 s | — |
| **触发率比** | **1.7 倍** | 1.0 |

### 4.5 结论

1. **触发配方不绑定标量数据通路**：同构配方在 NEON 向量通路（vector load→NEON ALU 轮换→背靠背 str q/ldr q reload）同样触发，且触发率是标量基准的 **1.7 倍**。
2. **"SIMD 是 SDC 多发区"在 179 上获得首个受控实证**：NEON 版成为当前**触发率最高的受控检测器**（布局完全手工掌控，1.1 fail/min）。
3. **关键在数据流模式而非执行单元**：多源 load→轮换 ALU→紧邻 reload 这个模式是跨骨架（mrn_nuke/mem_disambig/mrn_pairs/mrn_reloaded，09-01~09-02）且**跨数据通路（标量 + NEON）**可移植的。
4. NEON 测试的工程红线：reload 必须走 `__asm__ volatile`，intrinsic 会被 DCE。

### 4.6 环境事件备忘（未决）

首次启动（18:23）阶段 1（191 核 NEON 满载）开跑 **<1 分钟后机器硬挂**，18:43 重启；journal 只剩当前 boot、pstore 为空，死因无落盘证据。19:13 重启战役后同规格正常跑完。标量系同规格（192 线程 30min）跑过几十次从未挂机。全核 NEON 满载与挂机的相关性为**单样本、未决**；若复发，需当独立故障模式（比 SDC 更严重）立案。

---

## 5. 实验组四：NEON 矩阵四变体（2026-09-03 22:34 ~ 09-04 00:38）

### 5.1 实验设计

baseline `neon_rot_2src` 触发（33 fail/30min）后自然跟进：把"SIMD 通路里哪个成分放大了触发率"拆出来。三个判别问题各对一个变体，外加 baseline 复跑固化：

| 变体 | 改动的变量 | 判别问题 |
|---|---|---|
| `neon_rot_store_only` | **去掉 reload**：`store(temp,res); store(dst,res)` 两次 store 都直接写 ALU 结果，无 load | reload 是必要条件还是放大器？（与标量 store_only 单样本对上） |
| `neon_rot_u8x16` | lane 组织 2×64b → 16×8b（**每操作同为 16B，宽度不变**） | NEON 放大是"数据量计费"（H1）还是 lane 结构（H2）？ |
| `neon_rot_1src` | 源数 2→1（第二源换编译期常量 `vdupq_n_u64`） | "≥2 源"阈值是否跨通路成立？（阴性对照） |
| `neon_rot_2src`（复跑） | 无 | 固化 33 fail/30min、排除涨落 |

骨架全部与 baseline 同构（objdump 逐一验证：store_only 无任何 reload 指令、其余三变体 `str q→ldr q 同址→str q` 背靠背俱在）。战役脚本 `run_neon_matrix.sh`，串行四轮，每轮两阶段。

### 5.2 实验结果

| 变体 | 阶段1(排除179) | fail 块 | fail 核 | loops | 首触发 | 触发率 |
|---|---|---|---|---|---|---|
| store_only（无reload） | 0 ✅ | **14** | 全 179 | 1552 | 13.2s | ~0.47/min |
| u8x16（16×8b lane） | 0 ✅ | **2** | 全 179 | 1591 | 57.6s | ~0.067/min |
| 1src（单源） | 0 ✅ | **0** | — | 1649 | — | 0 |
| 2src（baseline 复跑） | 0 ✅ | **26** | 全 179 | 1538 | 15.4s | ~0.87/min |
| **u32x4（4×32b lane，2026-09-04 补）** | 0 ✅ | **0** | — | 1651 | — | 0 |

（日志：`movbe_log/neon_matrix/neon_rot_*_stage2_30min.log`；阶段 1 全 0 核验在 `*_stage1_no179.log`）

### 5.3 结论

1. **"reload 非必要"的精确表述（2026-09-04 二次修正，朋友评审后）**：store_only 相对 baseline 的差异是**四变量复合**——① 依赖链 4 步→2 步；② AGU 形态 str+ldr 混合→纯双 str（1 个 AGU）；③ 指令条数 -1；④ **`str temp` 的数据流性质改变**：baseline 中它被同址 ldr 消费（store-to-load forwarding），store_only 中成为数据流死 store（SB 中无 forwarding 消费者，排空/提交形态不同；从 CPU 视角 store 照常分配 SB 表项并写 L1D，"死"仅指数据流）。因此 14 fail **只证明存在性命题**："存在一种不含热循环 reload 的触发配置"（2 源+轮换 ALU+连续 store，14 fail 全 179、阶段 1 双 0）——即**存在另一条触发路径**。它**不证明机制同一性**：无法建立"baseline 的同一触发机制在去掉 reload 后仍活着"；此前"根本触发条件比 reload 更底层"的暗示机制统一的表述**作废**。26↔14 的任何精确归因（含"2 倍"）同样作废。
2. **宽度假说（H1）否定，lane 结构（H2）胜出**：u8x16 与 baseline 每操作同为 16B，仅 lane 组织不同（16×8b vs 2×64b），触发率塌缩 **~15 倍**（26-33 → 2）。NEON 放大不在"数据量计费"，而在 **64-bit lane 数据通路**——与标量 64b 语义同构的 per-lane 通路才触发。
3. **≥2 源阈值跨通路成立**：NEON 1src 双阶段全 0，与标量梯度一致。
4. **baseline 可复现**：26 vs 33 fail/30min——NEON 通路稳定高于标量（0.87-1.1 vs 0.63/min，1.4-1.7 倍），首跑 1.7× 非涨落。
5. **64b lane 绑定是阈值，不是梯度（u32x4 中间点，2026-09-04 补）**：uint32x4（4×32b）双阶段全 0（1651 loop，exit: pass），objdump 确认热循环 ALU 为 `add v0.4s` 等 32b lane 指令、reload 骨架完整——塌缩是真实的 32b lane 现象。lane 曲线：**2×64b=26-33 → 4×32b=0 → 16×8b=2**。4×32b 比 16×8b 塌得更彻底，说明绑定不在"lane 越宽越触发"的连续梯度，而在 **64-bit lane 数据通路本身**（低于 64b 的 lane 组织即使语义高效也不触发）。u8x16 的 2 fail 相对 u32x4 的 0 或是布局涨落、或与 16-lane 的时序扰动有关——单样本量级，不参与主结论。
6. 18:24 挂机未复发：本次 8 小时连续 NEON 满载（22:34~00:38）无恙，维持单样本悬置。

### 5.4 方案 A 补充实验：`neon_rot_fwd_probe`（2026-09-04 07:29~08:00，已完成）

用户评审指出 store_only 的对照缺陷（§5.3 结论 1 的三个混淆变量）后设计的干净判别变体：

```
baseline:   ALU → str temp[i] → ldr temp[i] → str dst[i]   (有 forwarding)
fwd_probe:  ALU → str temp[i] → ldr dst[i]  → str dst[i]   (无 forwarding)
```

单 asm 块实现（objdump 验证三条内存指令背靠背：`str q0,[x2] / ldr q1,[x3] / str q0,[x3]`）。**⚠️ 二次修正（朋友评审后）：此前声称"同 4 步依赖链形状，唯一差异 = ldr 地址"是错的。** loaded 值（q1）被丢弃，`str dst` 的数据直接来自 res——baseline 的 4 步串行链 `ALU→str temp→ldr→str dst` 在此**断裂**，ldr 游离链外。鲲鹏 920 是乱序核，链外 ldr 可被自由调度（baseline 中 ldr 被同址内存序约束钉死在 str temp 之后）。因此 fwd_probe 对 baseline 的差异 = 地址 + 依赖链结构**双变量**。

**结果（落入预注册矩阵的 ≈0 分支，但该分支判定已撤回）**：阶段 1 排除 179 = 0 fail ✅；阶段 2 全核 30min = **0 fail**（1645 loop，exit: pass）。

**判定（二次修正后）**：

1. **撤回**"混合压力本身是必要成分"——其前提"4 步依赖链形状全保留"不成立（见上）。
2. **撤回**"触发核心收敛到 store→load 同址窗口"——26↔0（baseline vs fwd_probe）含地址+链结构双变量；14↔0（store_only vs fwd_probe）含位置+存在性+混合 AGU 多变量。三对比较无一单变量，归因全部不干净。
3. **干净保留的**：fwd_probe 是又一例"功能等价改写即灭活"（0 fail，灭活最彻底的一例），加入标量布局敏感性家族（nop/指针重读/unaligned/异址 ldr）。它作为**存在性证据**成立：此具体配置不触发；作为**机制归因证据**不成立。
4. 三点数字 26/14/0 保留为**现象记录**，机制解读待拆分实验（§5.5）。

---

## 6. 三组实验综合结论（2026-09-04 矩阵后更新）

```
触发 179 SDC 的诱因（截至 2026-09-04）：

  ≥2 源 load ──→ 轮换/混合 ALU ──→ store        (核心三要素)
  (硬阈值,1源=0)  (必要,纯单指令=0)
                │ 64-bit lane 数据通路为最强形态, 且为阈值绑定
                │   (u32x4=0, u8x16=2 vs 2x64b=26-33: 非"数据量计费"亦非梯度)
                └ reload = "同址reload触发(26)" vs "无ldr也触发(14)" vs
                    "异址ldr不触发(0)" 三点现象成立, 但三对比较均非
                    单变量(链结构/AGU/条数/死store混杂), 机制归因待§5.5拆分

  前提条件：全核 192 并发压力（单核孤立/切片 = 0）
  布局敏感性：改寻址/拉开时序/增删指令即灭活（贯穿所有实验）
```

- **ALU 逐指令组**证明"轮换/混合"是必要条件，否定特定指令假说；
- **AGU 组**再确认 2 源阈值、验证轮换指令集可替换、暴露 reload 必要性疑点、再证布局敏感性；
- **SIMD baseline**把配方从标量通路解放出来，确立 NEON 为最高触发率受控检测器；
- **SIMD 矩阵**判死宽度假说（lane 阈值绑定 64b）、确认 ≥2 源阈值跨通路；reload 相关三点（26/14/0）为现象记录，机制归因经两轮评审修正后悬置待 §5.5 拆分实验。

**§5.5 拆分实验（2026-09-04 设计，待执行）**：朋友评审指出 fwd_probe 的 0 不能区分"窗口关闭"与"AGU 压力模式改变"。两个干净探针：

```
① neon_rot_stale_reloading (baseline 侧, 全形态保持, 唯一变量=窗口时间距离):
     str temp[i] ← res
     ldr temp[i-1]           ← 读上一元素(同缓冲, 常同一条cache line)
     str dst[i] ← loaded        链保持(str dst 依赖 ldr), 条数/混合AGU/地址集全同baseline
                               golden: dst[i]=expected[i-1](轮转一格), init时 memcpy(temp,expected)
   → 触发: 同址性非关键, 时间距离才是 | 0: 背靠背紧度是关键

② neon_rot_ldr_at_top (store_only 侧, 位置 vs 存在性):
     ldr scratch[i]           ← 第三条ldr挪到迭代顶部(源load之前)
     a=srcA[i]; b=srcB[i]; res=ALU(a,b)
     str temp[i]; str dst[i]
   与fwd_probe同条数同混合(3ldr+2str), 唯一差异=第三条ldr的位置(两str之间 vs 迭代顶部)
   → ≈14: 位置是灭活源(插在两str之间才致命) | ≈0: ldr存在/AGU混合本身即灭活源

③ NOP对照(朋友建议, 测"插入本身"):
     str temp[i]; NOP; str dst[i]   (store_only + 1条nop)
   → ≈14: 插入无影响, 灭活特异于ldr | 降: 任何插入都扰动, 时序紧度主导
```

①②③ 串行各 30min，把 26/14/0 三点的机制拆干净。

---

## 附录：文件与日志索引

| 实验组 | 源码 | 日志 |
|---|---|---|
| ALU 单指令 | `tests/cpu/misc/mrn_nuke_2src_{add,sub,eor,and}.cpp` | `movbe_log/trigger_variants/mrn_nuke_2src_*_stage2_36min.log` |
| ALU 轮换对照 | `tests/cpu/misc/mrn_nuke_2src_alu.cpp` | `movbe_log/trigger_variants/mrn_nuke_2src_alu_30min.log` |
| 3src/4src 对照 | `tests/cpu/misc/mrn_nuke_{3,4}src_alu.cpp` | `movbe_log/trigger_variants/mrn_nuke_{3,4}src_alu_stage2_36min.log` |
| AGU 基线 | `tests/cpu/misc/agu_stress_2src.cpp` | `movbe_log/agu_stress/agu_stress_2src_stage2_30min.log` |
| AGU 1src | `tests/cpu/misc/agu_stress_1src.cpp` | `movbe_log/agu_stress/agu_stress_1src_stage2_30min.log` |
| AGU store_only | `tests/cpu/misc/agu_stress_store_only.cpp` | `movbe_log/agu_stress/agu_stress_store_only_stage2_30min.log` |
| AGU unaligned | `tests/cpu/misc/agu_stress_unaligned.cpp` | `movbe_log/agu_stress/agu_stress_unaligned_stage2_30min.log` |
| SIMD | `tests/cpu/misc/neon_rot_2src.cpp` | `movbe_log/neon_rot/neon_rot_2src_stage2_30min.log` |
| SIMD 矩阵 store_only | `tests/cpu/misc/neon_rot_store_only.cpp` | `movbe_log/neon_matrix/neon_rot_store_only_stage2_30min.log` |
| SIMD 矩阵 u8x16 | `tests/cpu/misc/neon_rot_u8x16.cpp` | `movbe_log/neon_matrix/neon_rot_u8x16_stage2_30min.log` |
| SIMD 矩阵 1src | `tests/cpu/misc/neon_rot_1src.cpp` | `movbe_log/neon_matrix/neon_rot_1src_stage2_30min.log` |
| SIMD 矩阵 baseline 复跑 | （同 neon_rot_2src） | `movbe_log/neon_matrix/neon_rot_2src_stage2_30min.log` |
| SIMD 矩阵 u32x4 | `tests/cpu/misc/neon_rot_u32x4.cpp` | `movbe_log/neon_matrix/neon_rot_u32x4_stage2_30min.log` |
| SIMD 方案A fwd_probe | `tests/cpu/misc/neon_rot_fwd_probe.cpp` | `movbe_log/neon_matrix/neon_rot_fwd_probe_stage2_30min.log` |
| 挂机残档 | — | `movbe_log/neon_rot/neon_rot_2src_stage1_no179.log.crash20260903` |
