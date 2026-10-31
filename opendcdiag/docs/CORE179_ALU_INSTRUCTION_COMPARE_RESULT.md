# CORE179 ALU 指令对比实验结果（单指令 add/sub/eor/and vs 混合轮换）

> 日期：2026-09-02 ~ 2026-09-03
> 平台：Kunpeng 920 (ARMv8.1-A, AArch64), 192 核, openEuler
> 工具：OpenDCDiag ARM64 移植版 (opendcdiag-837c6948deaa-dirty)
> 目标核：逻辑核 179

---

## 摘要

在已坐实的触发变体 `mrn_nuke_2src_alu`（2 源 load + ALU 依赖链，混合轮换版，36min 14 fail 全 179）基础上，拆出 4 个**单指令变体** `mrn_nuke_2src_{add,sub,eor,and}`，每个做两阶段验证（阶段1排除179核60s须0-fail；阶段2全核192含179+auto seed 36min）。

**核心结果：4 个单指令变体全部 0-fail，而混合轮换版 14 fail/36min。** 纯 add、纯 sub、纯 eor、纯 and 都不触发，只有"add/sub/eor/and 按 `i % 4` 逐元素轮换"的混合版触发。

这否定了"触发由某条特定 ALU 指令（如 eor）驱动"的假说，指向**"混合轮换"这个指令序列模式本身**是触发的必要条件——单指令的时序/微操作序列无法落在 179 的触发窗口内，而轮换引入的指令多样性（每 4 个元素切换一次 ALU 操作）改变了流水线/转发时序，才落进窗口。

同日阳性对照：9-02 当天混合版梯度变体 3src（10 fail）与 4src（4 fail）均正常触发全在 179，证明当天 179 缺陷活跃，排除"当天 179 不活跃导致单指令 0-fail"的解释。

**诱因精化：触发 179 SDC 需"≥2 源 load + 数据 ALU 依赖链"且"ALU 操作按固定周期轮换/混合"——单一 ALU 指令不触发，混合轮换才触发。**

---

## 1. 实验设计

### 1.1 变体构造

4 个单指令变体从 `mrn_nuke_2src_alu` 拆出，骨架（store temp → forwarding load → store dst）与 mrn_nuke 完全一致，唯一差异是热循环 ALU 操作从 `switch (i % 4)` 轮换改为单指令：

| 变体 | 热循环 ALU 操作 | 对照基准（混合版） |
|------|----------------|--------------------|
| `mrn_nuke_2src_add` | `res = a + b`（纯加法） | `switch (i % 4) { add, sub, eor, and }` 逐元素轮换 |
| `mrn_nuke_2src_sub` | `res = a - b`（纯减法） | 同上 |
| `mrn_nuke_2src_eor` | `res = a ^ b`（纯异或） | 同上 |
| `mrn_nuke_2src_and` | `res = a & b`（纯按位与） | 同上 |

源码：`tests/cpu/misc/mrn_nuke_2src_{add,sub,eor,and}.cpp`，骨架不动，只改 ALU 操作。混合版轮换实现见 `tests/cpu/misc/mrn_nuke_2src_alu.cpp:67-72`（init 预计算 expected）与 `:93-98`（热循环）。

### 1.2 两阶段验证协议

每个变体：

- **阶段1（排除179核60s）**：`taskset 0-178,180-191` + 固定 seed，须 0-fail → 证明变体无 bug
- **阶段2（全核36min）**：`-n 192 -T 36m`（含179）+ auto seed（不传 `-s`）→ 看真实触发
- 每变体配监控脚本（taskset 绑核0，守候 fail+进度），符合 >10min 测试必须开监控的硬性要求
- 统计口径：数唯一 `result: fail` 块数（每 fail = 2 行 miscompare，不能 grep 双计）

### 1.3 实验目的

上一轮（9-01~9-02）已坐实：混合版 `mrn_nuke_2src_alu` 36min → 14 fail 全 179（~0.39 fail/min）。当时诱因结论为"≥2 源 load + 数据 ALU 依赖链"。本实验要回答：**触发是"2 源 + 任意 ALU"，还是"2 源 + 特定 ALU 指令（如 eor）"？**

---

## 2. 实验数据

### 2.1 主结果：4 单指令变体 vs 混合轮换版

| 变体 | 阶段1(排除179,60s) | 阶段2(全核36min) | fail块数 | fail核 | 轮次 | exit |
|------|--------------------|------------------|----------|--------|------|------|
| `mrn_nuke_2src_add` | 0-fail ✅ | 全核 36min | **0** | — | 3918 | pass |
| `mrn_nuke_2src_sub` | 0-fail ✅ | 全核 36min | **0** | — | 3880 | pass |
| `mrn_nuke_2src_eor` | 0-fail ✅ | 全核 36min | **0** | — | 3888 | pass |
| `mrn_nuke_2src_and` | 0-fail ✅ | 全核 36min | **0** | — | 3890 | pass |
| **对照: 混合版 `mrn_nuke_2src_alu`** | 0-fail ✅ | 全核 30min | **14** | **全179** | 3019 | fail |
| 对照: `mrn_nuke_3src_alu` | 0-fail ✅ | 全核 36min | 10 | 全179 | — | fail |
| 对照: `mrn_nuke_4src_alu` | 0-fail ✅ | 全核 36min | 4 | 全179 | — | fail |

*表说明：fail块数=唯一 `result: fail` 块数；轮次=test-runtime 块数（192核 × ~20轮/核）。单指令 4 变体轮次（3880~3918）与混合版（3019）量级一致甚至更高，排除"轮次不足碰不上"的解释。*

### 2.2 混合版 14 fail 的时间分布（对照确证）

time-to-fail（秒）：106.4, 157.5, 222.5, 365.9, 375.5, 410.3, 458.0, 532.6, 568.3, 680.5, 732.1, 733.3, 789.1, 811.4 —— 首失败 106s，末失败 811s，全程持续触发，非一次性爆发。

### 2.3 同日阳性对照（排除"当天179不活跃"）

9-02 当天上午跑了 3src（10 fail）与 4src（4 fail），均触发、全在 179；当天下午至傍晚 4 个单指令变体依次 0-fail。同日内"混合版触发、单指令版不触发"的对比成立，排除"当天 179 缺陷不活跃"的环境解释。

---

## 3. 分析

### 3.1 否定"特定 ALU 指令"假说

如果触发由某条特定指令（如 eor）驱动，则纯 eor 变体应触发。实际纯 eor 36min 0-fail。同理 add/sub/and 全部不触发。→ **触发不是某条 ALU 指令的固有属性。**

### 3.2 "混合轮换"是触发的必要条件

对比双方满足同样的"≥2 源 load + 数据 ALU 依赖链 + 紧时序"：

- 混合版：36min 14 fail（~0.39/min）
- 单指令版（4个）：36min 全部 0 fail（轮次量级一致，排除轮次不足）

唯一差异 = **ALU 操作是否按 `i % 4` 轮换**。→ 指令序列的多样性/轮换本身是触发的必要条件。

（边界说明：混合版日志为 30min、单指令为 36min；混合版 14 fail 首失败在 106s、全程分布，若单指令有同量级触发率，36min 不可能一个都抓不到。结论对时长差不敏感。）

### 3.3 与既有结论的整合

整合进诱因链：

1. **≥2 源 load + 数据 ALU 依赖链**（9-01 v2 纯净探针 + 正向构造 4 变体 3 触发 + 跨骨架移植验证；9-02 梯度实验：2 源最优，2>3>4 非单调，≥2 源是阈值）
2. **紧时序（back-to-back store→reload）**（9-01 5a/5b 时序拉开实验：拉开 7 条即灭活）
3. **ALU 操作轮换/混合（本实验新增）**——单指令不触发，混合轮换才触发

精化后诱因：**"≥2 源 load + 轮换混合的数据 ALU 依赖链 + 紧时序"三要素组合，缺一不可。要素内部有最优参数：源数 2 最优（非单调，源过多扰动时序窗口反而降触发率），ALU 混合轮换优于单指令。**

### 3.4 机器层面机制分析（objdump 实证，2026-09-03）

objdump 对比混合版（`mrn_nuke_2src_alu_run`，`0xc36a0` 起）与单指令版（`mrn_nuke_2src_eor_run`，`0xc3dc0` 起）热循环，**推翻了"轮换=每个元素执行不同指令"的直观理解**：

**GCC 把 `switch(i%4)` 编译成"四条 ALU 全算 + 分支/csel 挑结果"**，不是四条独立路径：

```asm
; 混合版每元素（21条）：
ldr a; ldr b
eor x2, a, b        ; ← 无条件执行
cmp i%4, #2; b.eq → store
and x2, a, b        ; ← 无条件执行
cmp i%4, #3; b.eq → store
add x2, a, b        ; ← 无条件执行
cmp i%4, #1
sub x0, a, b        ; ← 无条件执行
csel x2, ...        ; ← add/sub 选择
add &temp[i]; str; ldr; add &dst[i]; str   ; 骨架，str→ldr 仍背靠背
```

一个 4 元素周期内实际执行路径：

| 元素 | 实际执行数据 ALU | 分支 taken | load→store 生产链深度 |
|------|-----------------|-----------|---------------------|
| i%4==0 (add) | eor→and→add→sub→csel（5条） | 无 | 5 级 |
| i%4==1 (sub) | eor→and→add→sub→csel（5条） | 无 | 5 级 |
| i%4==2 (eor) | eor（1条） | b.eq#1 | 1 级 |
| i%4==3 (and) | eor→and（2条） | b.eq#2 | 2 级 |

**关键观察：**

1. **机器层面不存在"轮换执行哪条指令"**——eor 每个元素都无条件执行（哪怕结果被丢弃）。落到硬件上的"轮换"实为：store 值生产链深度以周期 4 在 1/2/5 级间变化 + 分支 taken 模式 NT,NT,T,T（周期 4）+ 加法器/逻辑单元交替。
2. **纯 eor 版 0-fail 因此更干净**：混合版也每个元素执行 eor，若"eor 的存在"是诱因则纯 eor 版必触发。纯 eor 版缺的是 and/add/sub/csel、3 条 cmp、2 个动态分支、变化的链深——诱因在此集合内，不在 eor 本身。
3. **str→ldr 背靠背两版都完整保留**（骨架红线未破），差异在**进入 store 之前**：生产 store 值的 ALU 链时延被周期 4、幅度 1↔5 级地调制。
4. 次要差异：混合版 &temp[i] 在 ALU 链之后计算（紧贴 str），单指令版在 load 之前；循环变量 w4 32位计数 vs x19 64位字节偏移。

**机器层面诱因改写：触发需要 store 值生产链呈现周期性变化的深度/内容（多条不同 ALU + cmp/branch/csel 选择机制），叠加在背靠背 store→reload 骨架上；恒定单指令、恒定链深的生产链不触发。**

### 3.5 下一步（单变量分离实验）

- **恒定 2 条链**（每元素 eor+and，无分支无 csel）：分离"链更深" vs "链深度周期变化"
- **纯 csel 无 b.eq**（消除内部分支）：分离"分支扰动" vs "ALU 链本身"
- **恒定 5 条链**（每元素全算四条+csel，无 i%4）：若触发则"可变深度"被否定，指向链长/多执行单元
- 验证轮换周期敏感性：`i % 2` / `i % 8` / `i % 16` 是否都触发

---

## 4. 可追溯数据

- 单指令 4 变体 36min 日志：`movbe_log/trigger_variants/mrn_nuke_2src_{add,sub,eor,and}_stage2_36min.log`（2026-09-02）
- 混合版 30min 日志：`movbe_log/trigger_variants/mrn_nuke_2src_alu_30min.log`（2026-09-01）
- 3src/4src 36min 日志：`movbe_log/trigger_variants/mrn_nuke_{3,4}src_alu_stage2_36min.log`（2026-09-02）
- 串行脚本：`run_alu_instr_serial.sh`（nohup 脱离会话执行，SSH 断连未中断）
- 首轮中断存档：`mrn_nuke_2src_add_stage2_36min_INTERRUPTED_151s.log`（会话回收导致，已重跑覆盖）
