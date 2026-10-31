# CORE179 盲区单元隔离战役（2026-09-09/10）

## 0. 摘要

针对此前标注的**未测微架构盲区**（MMU/TLB、LSQ 隔离、RF 端口、ROB、预取器），以最强触发骨架
`neon_rot_ldr_at_top_rowmajor`（三轮均值 ~223 fail/30min）为基线，构造 6 个单元隔离变体，
7 测试 × 2 轮 × 30min 全核 192（含 179）auto seed 串行执行。

**结果：6 个变体两轮全部 0 fail；基线 rowmajor 两轮 271/216（均值 244，与前日三轮均值 223 量级一致），
fail 全部且仅在 thread 179。** 由于所有 6 个变体都以不同方式扰动了热循环指令布局，
"单元不参与" 与 "布局扰动灭活" 不可区分——归因保留，见 §5。

- 战役脚本: `builddir/campaign_20260910_unit_isolation.sh`
- 日志目录: `builddir/campaign_20260910_unit_isolation/`（14 份日志，19:20 → 次日 02:20 完整落盘）
- 冒烟记录: `builddir/smoke_20260909_units/`（09-09 18:09–18:47，179 hotplug 下线，`-n 191`，6 新测试全 0 fail 准入）

## 1. 公共骨架（所有 7 个测试共享的触发配方）

基线家族 = [[2src-alu-portable-trigger-20260902]] 三要素（≥2 源 load + 轮换 ALU + 紧时序）的
NEON ldr_at_top 最强版。每元素热循环：

```asm
ldr  q?, [scratch+i]        // 顶部第 3 ldr（dead load，制造 L1D 阵列流量）
ldr  a, [srcA+i]            // 源 load 1
ldr  b, [srcB+i]            // 源 load 2
<ALU: add/eor/and/orr 按 i%4 轮换>   // 2 源 + 轮换 ALU
str  res, [temp+i]          // 背靠背 str
str  res, [dst+i]           // 背靠背 str（reload 供 memcmp）
```

- 缓冲区: srcA/srcB/scratch/expected 各 1024 × 16B（uint64x2_t）= 16KiB/缓冲，64B 对齐
- load 一律 `__asm__ volatile ("ldr %q0, [%1]")`（asm 防编译器重排/合并）
- golden 在 init 阶段用同组 NEON 指令算好；run() 每 sweep 后冷路径 `memcmp` 检查
- 扫描顺序: rowmajor = 偶数 sweep 升序、奇数 sweep 降序（交替）
- `TEST_LOOP(test, 1 << 13)`，全核 192 并发（各线程独立缓冲，dst/temp 线程局部）

## 2. 各测试负载详述

### 2.1 rowmajor（基线，轮内参照）
源码: `tests/cpu/misc/neon_rot_ldr_at_top_rowmajor.cpp`

纯骨架（§1）。变体维度 = 扫描顺序交替升降（vs 父测试纯升序），用于区分
"SDC 签名跟随 buffer 槽位" vs "跟随 sweep 前进位置"。
本轮作为轮内参照基线，校验 179 当晚处于活跃态。

### 2.2 tlbstress（MMU/TLB 维度）
源码: `tests/cpu/misc/neon_rot_ldr_at_top_tlbstress.cpp`

- 骨架不变，但 48KiB 工作窗口（srcA+srcB+scratch 各 16KiB）在 1MiB+48KiB
  `mmap(MAP_POPULATE)` 区域内**每外层迭代滑动一页（4KiB）**，循环 256 页
- 效果：同一虚→实翻译不复用，dTLB 持续 miss + 硬件页表遍历常压；
  **cache 层压力不变**（窗口仍 48KiB），唯一新增维度 = 翻译压力
- golden 按"每窗口 × 每线程"重算（`noinline` 防循环融合——首版 inline 被 GCC 12
  融合后删除 dst store，191 健康核全 fail，冒烟抓出后修复，见 [[tlbstress-two-smoke-bugs]]）
- 判据设计：率不变 → 翻译路径不参与；率变 → TLB/页表遍历参与

### 2.3 lsqfill（LSQ 维度）
源码: `tests/cpu/misc/neon_rot_ldr_at_top_lsqfill.cpp`

- 骨架不变，在 scratch load 与两源 load 之间插入 **8 个独立 filler load**
  （filler 缓冲 8 项，每项独占一条 64B cache line）
- 结果折入 dead 累加器（每 sweep 末尾 asm sink 一次防 DCE），**不进入触发依赖链**
- 效果：每元素在飞 load 深度 ~3 → ~11，压 LSQ 分配 / store-to-load 转发检查 / 记忆消歧宽度
- 注意（源码自注）：此变体**有意改变热循环指令数/时序**——不与基线字节可比，
  回答的是 "LSQ 深度压力相对基线骨架升/降/灭活触发率"

### 2.4 rfport（RF 端口维度）
源码: `tests/cpu/misc/neon_rot_ldr_at_top_rfport.cpp`

- 骨架不变，在源 load 与 ALU 之间对 a 操作数插入 **4 级纯寄存器搬运链**
  （inline asm `mov v4→v5→v6→v7→v8`，GCC 不可折叠/消除）
- 效果：只增加寄存器堆读写端口占用 + bypass 网络流量 + 4 深串行重命名依赖，
  **零内存流量**；同样有意改变时序，非字节可比

### 2.5 robfill（ROB/调度维度）
源码: `tests/cpu/misc/neon_rot_ldr_at_top_robfill.cpp`

- 骨架不变，每元素插入 **10 条独立标量 fmul 链**（d8..d17 各自 ×0.375，
  inline asm + fmov 常数，GCC 不可常量折叠/外提）
- 每条链长延迟（FPU pipe）、与触发链及彼此皆独立 → 调度器必须全部保窗，
  ROB 占用 / issue queue 压力大幅上升
- 每 sweep 末冷路径折叠 10 链入栈 sink（防 DCE）
- 配套对照 robfill_np（§2.6）分离 "窗口压力" vs "纯时序拉长"

### 2.6 robfill_np（时序拉长对照）
源码: `tests/cpu/misc/neon_rot_ldr_at_top_robfill_np.cpp`

- 与 robfill **同骨架、同热循环槽位数（10 槽），但全部为 nop**
- 零资源占用（仅解码宽度），无 FPU 工作、无寄存器写
- robfill 与 robfill_np 的触发率差 → 归因于链的资源压力而非 ~10 槽时序拉长。
  此对照是 movbe 家族 nop 梯度教训（0→1→2→64 nop: 18→1→6→0）后的必选项

### 2.7 prefetch（预取器维度）
源码: `tests/cpu/misc/neon_rot_ldr_at_top_prefetch.cpp`

- 缓冲缩为 256 × 16B = **每缓冲恰好一页 4KiB**；`TEST_LOOP(1<<15)` 补偿扫描量
- 元素访问序变为 **j → (j×65) mod 256** 全周期置换（65 与 256 互素），
  相邻访问平均距 ~1KiB 且非常数步长 → 流/步长预取器无法跟踪
- op 轮换按置换后的**访问位置** pos%4（golden 同序计算），非槽位索引
- 效果：破坏预取器步长检测，翻译压力不变（每缓冲仍单页单 dTLB 项）；
  设计用于检验 rowmajor(223) vs sub(109) 差异是否预取器介导

## 3. 实验结果

### 3.1 冒烟准入（09-09 18:09–18:47，179 hotplug 下线，`-n 191`）

6 个新测试全部 0 fail（含 tlbstress 修复后的 r3 复测），准入。
tlbstress 首版冒烟抓出 2 个测试自身 bug（GCC 循环融合删 store + 共享 golden 跨线程竞态，
191 健康核全 fail），修复后复测干净。

### 3.2 正式战役（7 测试 × 2 轮 × 30min，全核 192 含 179，auto seed）

| 测试 | r1 fail | r2 fail | 备注 |
|---|---|---|---|
| rowmajor（基线） | **271** | **216** | 均值 244；两轮 cpu-mask X 位解码均 = thread 179；ttf r1 6.2–1003s（均值 391），r2 max 1011s（均值 335） |
| tlbstress | 0 | 0 | |
| lsqfill | 0 | 0 | |
| rfport | 0 | 0 | |
| robfill | 0 | 0 | |
| robfill_np | 0 | 0 | 与 robfill 无差别 |
| prefetch | 0 | 0 | |

交叉验证（三法）：`result: fail` 唯一块计数 = 271/216（ttf 行数 542/434 恰为 2 倍，口径一致，
见 [[sdc-fail-count-unique-blocks]]）；6 变体 12 份日志 grep miscompare = 0、exit=0；
rowmajor 两轮 exit=1 且 cpu-mask 唯一 X = 179。

ttf 覆盖整个 30min 窗口（min 6.2s / max 1011s），非开场聚集——与 09-09 稳定性战役
"fails 时间均匀分布" 一致。

## 4. 判读

1. **基线活跃性确认**：rowmajor 271/216 与前日三轮 276/244/149（均值 223）量级一致，
   179 当晚活跃，0-fail 不是 "179 休眠" 假阴性。
2. **6 变体全部灭活**（~244/30min → 0，两轮一致）。逐个判读：
   - tlbstress：连续 dTLB miss + 页表遍历压力下触发消失
   - lsqfill：LSQ 深度压力（在飞 load 3→11）下触发消失
   - rfport：RF 端口/bypass 压力下触发消失
   - robfill + robfill_np：ROB 窗口压力与纯时序拉长**双双**灭活，且二者无差别
   - prefetch：步长破坏 + 页内置换序下触发消失
3. **robfill = robfill_np = 0 是本轮唯一的单变量对照信息**：在 nop 拉长时序已灭活的
   前提下，加真实 fmul 链不恢复也不进一步压低——**本轮对 "ROB 资源压力" 维度
   没有区分度**（对照自身已灭活，对照失效）。

## 5. 归因保留（重要）

所有 6 个变体都以不同方式**扰动了热循环的指令布局/时序**（滑动窗口改寻址模式、
+8 load、+4 mov、+10 fmul/nop、置换序改循环形状）。已知触发配方对布局敏感到
编译期寻址模式级（[[movbe-l1d-variants-schedule-sensitivity]]），故本轮 0-fail
**不能**区分两个假设：

- H1（单元不参与）：所加单元压力与触发机制无关，0 是真阴性
- H2（布局灭活）：任何对 §1 骨架字节布局的扰动都灭活触发（同 dump 变体抑制 30×、
  sub 变体减半的先例），0 是布局 confound

这与 [[neon-u32x4-threshold-and-storeonly-correction]] "源码级唯一差异 ≠ 微架构级
单变量" 和 [[objdump-7tests-trigger-vs-notrigger-20260901]] 的教训同构。
本轮的**硬结论**仅限：

- 6 种单元压力的加入方式（如源码所述的具体形态）**无一是触发的增强/保持因素**——
  没有任何一个变体在保持或提升触发率
- 基线配方（§1 骨架 + 交替扫描）再次两轮复现 ~244/30min，179 唯一

**下一步方向（若继续）**：构造不改变热循环指令布局的单元压力（例：通过 sysfs/固件
关预取器、 neighbouring 核放置翻译压力负载、或 cpulimit 频率扰动），才能拿到
真单变量数据。

## 6. 环境与可追溯性

- 主机: Kunpeng 920, 192 逻辑核（nproc=192，本战役 taskset 0-191 全核含 179）
- 二进制: `builddir/opendcdiag`（09-09 18:46 构建，含 6 新测试）
- 命令模板: `timeout 2100 taskset -c 0-191 ./builddir/opendcdiag -e <test> -n 192 -T 30m --ignore-os-error --ignore-timeout -o <log> -q`
- 逐轮起止时间与 exit code: `builddir/campaign_20260910_unit_isolation/progress.txt`
  （19:20:33 开始，02:20:25 结束，14/14 轮完整，无中断）
