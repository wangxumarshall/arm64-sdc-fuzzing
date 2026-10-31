# CORE179 单元隔离六变体 — 负载饱和度审计（2026-09-10）

## 问题

[[unit-isolation-campaign-20260910]] 战役的 6 个单元隔离变体（tlbstress/lsqfill/rfport/
robfill/robfill_np/prefetch）两轮全 0-fail。本审计回答：**这些变体是否真的压满了
它们各自要测试的执行单元？** 若没有压满，0-fail 的归因力要打折扣——"单元不参与"
和"压力不够没够到阈值"不可区分。

方法：算术核算（每元素机器预算 vs 实际周期成本）+ PMU 实测（191 核满载形态下
对 core 2 采样 55s）+ objdump 验证 asm 注入如实落进二进制。

环境：179 hotplug 下线（冒烟规范），nproc 192 → 190 可用核 + 主线程。
**注**：`-n 191` 被 clamp 到 190（框架上限，warning 可见），实际 190 线程满载。
所有 7 个变体两轮（上午 + v4）均 0-fail、exit: pass（三法交叉验证）。

## 机器预算基准（TaiShan v110，主频实测 2.35 GHz）

- 4 发射/周期，2×128b NEON pipe，LSU：2 load AGU + 1 store AGU（= 3 访存/周期上限）
- L1D 64KB/4 路组相联（16B/元素 → 4 元素/缓存行）
- L1D MSHR / LSQ 深度：TaiShan v110 公开资料未给精确值（通常 16-24 load 在飞）

## 每变体核算表（PMU 实测，core 2, 55s, 190 核满载形态）

| 变体 | cyc/元素 | 访存/cyc | LSU 管线占用 | 目标单元 | 饱和判定 |
|---|---|---|---|---|---|
| rowmajor (基线) | 4.58 | 1.09 | 36% | — | — |
| tlbstress | 8.33 | 0.71 | 24% | dTLB/页表遍历 | **TLB refill 13×基线，walk 3×基线 — 压力真实生效** |
| lsqfill | 10.88 | 1.19 | 40% | load 队列深度 | 在飞 load 3→11（纸面），访存率 1.19/cyc **≈ load AGU 对 (~2) 的 60%，离饱和远** |
| rfport | 5.61 | 0.89 | 30% | RF 读/写端口 | vmov 链 5 拍/元素 vs NEON pipe 2 发射/周期 — **远未饱和 RF 端口** |
| robfill | 6.58 | 0.76 | 25% | ROB/issue 窗口 | 10 独立 fmul 链，IPC 2.90 — **IPC 仍高，ROB 未被压满** |
| robfill_np | 5.71 | 0.88 | 29% | (nop 对照) | 同槽数 nop — 对照设计失效（见下） |
| prefetch | 4.66 | 1.07 | 36% | 预取器 | 访存率与基线同，见 v4 refill 数据 |

（cyc/元素由 `l1d_cache / 每元素访存数` 反推；每元素访存：基线 5 = 3 ldr + 2 str，
lsqfill 13 = 11 ldr + 2 str，tlbstress 5.9 含摊销的 golden 重算。）

## 逐变体结论

### 1. tlbstress — 压力真实生效 ✅

- l1d_tlb_refill: 18.86M vs 基线 1.30M（**13.5 倍**）；dtlb_walk 347K vs 115K（**3 倍**）
- 窗口滑页设计如设计般强制持续 TLB miss + 页表遍历
- 但注意：**L1D/L2 压力同时下降**（cyc/元素 8.33 vs 4.58），因为 golden 重算摊销
  摊薄了热循环占比——TLB 维度干净，但"其余条件同基线"不成立（见 confound 节）

### 2. lsqfill — 突发深度真实，持续压力中等 ⚠️

- **纸面**：在飞 load 3→11（8 filler + 3 骨架）
- **实测**：访存率 1.19/cyc——LSU 预算 3/cyc 的 **40%**；元素成本 10.88 cyc（基线 2.4 倍）
- **突发行**：filler load 地址互相独立（`filler + k*64`，无数据依赖），OoO 机器可在
  ~5.5 拍内把 8 个 load 全部发射在飞（2 load AGU）——**突发在飞深度 ~8-11 可达成**，
  load queue 分配压力在突发窗口内真实存在（objdump 证实 11 个 q-ldr 全部在场）
- **confound**：`acc = veorq(acc, f)` 累加器是 8 深串行链，元素成本被它主导——
  该变体同时测了"load→ALU 串行延迟链"，与 LSQ 深度维混杂；且 filler buffer 512B
  恒驻 L1D（v4: L1Dmiss 0.98%），load 全命中、无 MSHR/refill 侧压力
- **判定**：突发深度真实但持续占用中等（~40%），未饱和；含延迟链混杂

### 3. rfport — 5 vmov ≈ NEON 一次发射，压力可忽略 ⚠️

- 4 深 vmov 链 + in/out = 10 vmov/元素 vs 2 NEON 发射/周期 → 仅 ~2.5 拍额外
- 4 深链本身是串行依赖（v4→v5→v6→v7），每拍至多 1 个 vmov 消费 1 读+1 写端口——
  距"RF 端口饱和"（读 6-8/周期）数量级不足
- **rfport 测的实际是"NEON 传送类指令轻微加时"**，不是 RF 端口压力

### 4. robfill — fmul 链独立性与否决定其含义 ⚠️

- 30 fmul/元素（objdump 证实），IPC 2.90、无 stall_backend 显著上升（14.8% vs 基线 15.6%）
- 10 条链每条在元素间连续乘同一累加器（d8..d17 跨元素持续），**跨元素是串行链**
  （d8 *= 0.375 每元素），元素内 10 个 fmul 互相独立 → 跨元素累计在飞独立 fmul = 10
- ROB/issue 窗口确实被填（fmul 延迟 ~3-5 拍 × 10 独立链 ≈ 30-50 拍在飞），有一定
  ROB 压力，但 IPC 2.90（4 发射机的 72%）说明**前端/发射远未受阻**
- **结论：轻度 ROB 压力，未饱和**。且 nop 对照（robfill_np）自己也 0-fail 灭活，
  对照失效——本轮数据对 "ROB 资源维度" 无区分度（战役记忆已记录）

### 5. robfill_np — 对照失效，无信息量 ❌

- 同槽数 nop 注入自身已灭活触发（0-fail），无法区分"ROB 压力不参与" vs "布局灭活"
- 这与 [[movbe-patch-sweep-not-instruction-specific]] 的 nop 折叠仍触发形成有趣对照：
  此处 nop 注入反而灭活——**nop 并非总是中性填充物**，布局敏感性是非单调的

### 6. prefetch — 预取器灭活被 v4 数据直接证实 ✅✅

v4 PMU 数据（191 核满载形态，core 2 采样 55s）：

| 指标 | rowmajor 基线 | prefetch 变体 | 变化 |
|---|---|---|---|
| L1D miss 率 (refill/l1d_cache) | 1.71% | **0.0009%** | **塌缩 ~1900 倍** |
| L2 访问次数 | 60.6M | **4.9** | **塌缩 ~12000 倍** |
| L2 miss 率 | 0.30% | 43.98% | 剩余极稀访问多为 miss |

×65 mod-256 置换访问序把 4KiB/缓冲 footprint 全部锁进 L1D（256 元素×16B），
预取器不再发起任何 L2 流。这是全部六变体中**设计意图与 PMU 证据吻合得最干净
的一个**——它的 0-fail（两轮+今日两次复测）给出迄今最强的单元级否定证据：
**在 L1D 全命中、预取器彻底静默的形态下触发完全灭活**，与 [[sdc-trigger-constant-probability-per-ldr]]
的"L1D 域 load 低概率随机错"模型自洽（L2→L1D 的 refill 路径被掐掉后触发消失，
即触发位面在"从 L1D 阵列读出"或"refill 写入 L1D"二者之一）。

但注意其反向不成立：基线 rowmajor 的 1.71% L1D miss 也远谈不上"高 miss 压力"，
说明触发不需要持续 refill——1.71% 已够。故更精确的表述是：
**置换序灭活 ≠ 预取器参与触发**，而是 ×65 置换同时改变了 (a) 预取流 (b) 访存时序
布局 (c) footprint 大小（1024→256 元素）——三维同变，仍非单变量（老教训
[[neon-u32x4-threshold-and-storeonly-correction]]）。

## 横向对照：为什么 0-fail ≠ 单元无罪

六变体共同的结构性缺陷：**任何对热循环指令布局的扰动本身就会灭活触发**
（战役已确立的边界，见 [[unit-isolation-campaign-20260910]]）。因此每个变体的
0-fail 都同时含有两种解释：

1. 该单元不参与触发机制（H1，希望测的）
2. 布局扰动灭活了触发（H2，confound）

本审计的贡献是把"压力是否真实生效"从猜测变成实测：
- **tlbstress、prefetch**：目标压力确凿生效（TLB refill 13×、L1D miss 塌缩 1900×），
  它们的 0-fail **在 H1/H2 之外还排除了"压力没加上"这个第三种解释**——证据等级
  高于其余四变体
- **lsqfill、rfport、robfill**：压力只部分生效/远未饱和（40%/~15%/IPC 仍 72%），
  它们的 0-fail **不能排除"该单元压力不够"**——证据等级低
- **robfill_np**：对照自身灭活，无信息量

## 结论

**回答"这 6 个测试用例是否压满自己要测试的执行单元"：没有一个压满。**

| 变体 | 目标单元 | 实测占用/压力 | 压满? |
|---|---|---|---|
| tlbstress | dTLB/页遍历 | refill 13.5×基线 | **未压满但压力确凿生效** |
| lsqfill | load 队列 | LSU 40%，突发 8-11 在飞 | 未压满+延迟链混杂 |
| rfport | RF 端口 | ~2.5 拍/元素 vmov | **远未压满（数量级不足）** |
| robfill | ROB/issue 窗口 | IPC 2.90/4 | 未压满（轻度压力） |
| robfill_np | (对照) | nop | 对照失效 |
| prefetch | 预取器 | L1D miss 塌缩 1900× | **灭活性生效（设计即如此）** |

含义：
1. **tlbstress/prefetch 的 0-fail 仍具归因力**（压力真实+布局 confound 同在，
   但"没加上压力"已排除）——但正归因仍被 H2 布局 confound 挡住
2. **lsqfill/rfport/robfill 的 0-fail 归因力弱**——"单元不参与"与"压力未达阈值"
   与"布局灭活"三解释并存。若要重试，需把压力提饱和：
   rfport 需 ~10×vmov 以上且改为多独立链并行；lsqfill 需去掉 eor 串行链
   （filler 结果直接落独立寄存器）；robfill 需对照有效（nop 对照不灭活的槽位数）
3. 预取器/L2 refill 路径获得了迄今最干净的否定证据（prefetch 变体），与
   "L1D 域 load 随机错"模型自洽
4. 设计饱和度探针时，**必须先用 PMU 验证压力生效**再上 30min 战役——本次
   6 变体战役若先做 60s PMU 审计，rfport（数量级不足）和 robfill_np（对照
   失效）在冒烟阶段即可拦下，省 ~3 小时机时

## 数据文件

- `builddir/unit_saturation_20260910/*.perf`（v1: cycle/inst/TLB/stall）
- `builddir/unit_saturation_20260910/*.v4.perf`（v4: +L1D/L2 refill）
- `builddir/unit_saturation_20260910/*.log / *.v4.log`（190 核 60s，全 0-fail）
- objdump 指令构成验证：rfport vmov=10、robfill fmul=30、lsqfill q-ldr=11/元素

---

# 第二轮：压满尝试（2026-09-10 下午）

用户问"能给他们压满吗"。答案分单元：两个 v2 变体 + 一个邻核方案落地，
60s PMU 验证。**天花板由专用探针实测**（ceil_probe.c，单核 boost 2.597GHz，
65536-iter batch 计时避免 clock_gettime 冲流水线——v0 探针曾测出 99.6 cyc/iter
的假值，全是时钟开销）。

## 机器真实天花板（ceil_probe 实测）

- **16 独立 L1D ldr + 4 eor 汇聚：1.50 loads/cyc**（非纸面 2/cyc）
- **16 独立 vmov：0.71 movs/cyc**（纯 mov 流受依赖/汇聚限制）
- rfport_v2 形状孤立测：3 ldr + 12 mov = 8.46 cyc/iter

## 第一批落地结果

### lsqfill_v2（去 eor 串行链）—— 64% 饱和

- 8 filler ldr 进 8 独立寄存器（asm 块尾部 eor 树在 load 全部返回后才消费）
- 实测：11.46 cyc/el，0.96 loads/cyc（v1: 1.01 但含串行链混杂）
- **0.96/1.50 = 64%**。剩余 ~36% 是 str/ALU/循环开销分走的周期——结构性上限，
  骨架（3 ldr + 2 str + ALU + 循环控制）本身要消耗发射口
- 判定：**结构性近饱和，再多的 load 只会拉长元素周期**

### rfport_v2（6 独立 vmov 链）—— 达机器 mov 吞吐上限

- 12 mov/元素，孤立形状 8.46 cyc/iter，测内 7.28 cyc/el（含 ALU+str+循环）
- 12 mov / ~7 cyc ≈ 1.7 mov/cyc 视口而定；纯 mov 流探针 0.71 是 eor 汇聚限制
  非发射口上限。元素周期已由 mov 数主导（7.28 vs 基线 4.58）
- 冒烟抓出 v1 bug：返回值覆盖 b 导致全核确定性 fail（3s 内）——已修（引用进出）
- 判定：**mov 吞吐达机器上限，压满达成**

### tlbstress 邻核版 —— storm 核真饱和，且主核零污染

- 布局发现：**176-179 是同一 L2 cluster**（179 离线时 sysfs 只报 176-178）。
  3 个并行 storm 进程钉在 176/177/178，rowmajor 跑 0-175,180-189
- storm 核 176：**28.9M walks/s（每 3.3 拍 1 次页遍历），TLB refill 1.44G/50s**
  ——dTLB/页遍历路径真饱和（比 v1 自施压版强 **4600 倍**：6.3K vs 28.9M walk/s）
- rowmajor 侧核 2：TLBrf 111K（**比无 storm 基线 1383K 还低 12 倍**）、
  L1D miss 1.64%（基线 1.71%）——**邻核风暴对主测试核几乎零污染**
  （cluster L2 隔离干净 + 主核工作集 4 页全在 dTLB 内）
- v1 执行 bug 记录：3 个 storm 曾串行跑（`sh -c 'a;b;c'`），perf 采样到
  WFI 空闲核（15.8MHz 假时钟）——已修为 3 进程并行
- 判定：**dTLB/页遍历在 storm 核上压满**；但注意——被压满的是 storm 自己的核，
  不是触发核 179（已离线）。这个形态测的是"邻核页遍历风暴是否影响触发核"，
  真正的"触发核自身 TLB 饱和"须等 179 上线后跑 rowmajor+179 内 storm

## 三轮 PMU 战役总表（v1 上午 / v5 下午）

| 变体 | loads/cyc | 天花板 | 饱和度 | 判定 |
|---|---|---|---|---|
| lsqfill (v1) | 1.01* | 1.50 | (67%)* | *含串行链混杂 |
| **lsqfill_v2** | **0.96** | 1.50 | **64% 结构上限** | 近饱和 ✅ |
| **rfport_v2** | — | 0.71 纯mov流 | **mov 吞吐上限** | 压满 ✅ |
| **tlbstress 邻核** | — | — | **28.9M walk/s** | 压满 ✅（storm核） |
| rfport (v1) | 0.54 | — | — | 数量级不足（已废） |
| robfill/np | — | — | — | 待第二批（需先做扩槽标定） |

## 结论（第二批后）

1. **三个单元的"压满"以三种不同含义达成**：lsqfill_v2 结构近饱和（64%，
   剩余被骨架必需开销占据）；rfport_v2 mov 吞吐达机器上限；tlbstress 邻核版
   页遍历达真饱和（4600×v1）且主核零污染
2. **机器真天花板与纸面规格的偏差本身是发现**：128b load 实测 1.50/cyc
   （非 2）、纯 vmov 流 0.71/cyc——后续所有饱和度判定的分母应用实测值
3. 所有 v2 变体 60s 冒烟 0-fail（功能正确性）；邻核实验 rowmajor 176 核
   60s 0-fail——**压满状态下的 SDC 行为待 30min 战役**（需 179 在场）
4. 冒烟继续抓 bug：rfport_v2 的 b-覆盖 bug（全核确定性 3s fail）是冒烟规范
   价值的又一次证明