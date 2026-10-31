# CORE179 单元隔离战役总整理（2026-09-09 ~ 09-11）

整合三轮战役的全部有效数据，回答两个问题：**哪些测试用例测出了 SDC，哪个触发频率最高**。

统一条件：全核 `-n 192`（含 179）、auto seed、无 taskset 绑核、每轮 30min。
fail 计数口径 = 唯一 `result: fail` 块（非 miscompare grep，后者 2 倍双计）。

---

## 1. 总表：所有测试用例的 SDC 触发结果（仅有效数据）

| 测试用例 | 有效轮次 fail 数 | 均值/30min | 频率 | 全部落在 179？ |
|---|---|---|---|---|
| **neon_rot_ldr_at_top_rowmajor** | 276, 244, 149（09-09）；271, 216（09-10）；**320**（09-11 基线复跑） | **≈246**（6 轮，范围 149–320） | **≈8.2/min** | ✅ 每轮 cpu-mask 解码唯一 X = 179 |
| neon_rot_ldr_at_top_sub | 122, 90, 116（09-09） | 109.3 | 3.6/min | ✅ |
| neon_rot_ldr_at_top_rowmajor_dump | 7, 12, 3（09-09） | 7.3 | 0.24/min | ✅ |
| tlbstress | 0, 0 | 0 | — | — |
| lsqfill | 0, 0 | 0 | — | — |
| rfport | 0, 0 | 0 | — | — |
| robfill | 0, 0 | 0 | — | — |
| robfill_np | 0, 0 | 0 | — | — |
| prefetch | 0, 0 | 0 | — | — |

**结论 1：测出 SDC 的测试用例只有 `neon_rot_ldr_at_top` 家族的 3 个变体
（rowmajor / sub / rowmajor_dump），6 个单元隔离变体全部 0-fail。**

**结论 2：触发频率最高 = `neon_rot_ldr_at_top_rowmajor`**，
6 轮均值 ≈246 fail/30min（≈8.2/min），为 sub 的 2.2 倍、dump 变体的 34 倍。
最新一轮（09-11 干净基线）320 fail/30min ≈ **10.7/min**，为历轮最高，
ttf 覆盖全窗口（min 6.3s / max 999.1s / 均值 384s），非开场聚集。

---

## 2. 三轮战役经过与数据来源

### 2.1 09-09 稳定性战役（3 变体 × 3 轮 × 30min）
来源：`docs/CORE179_NEON_ROT_LDR_AT_TOP_STABILITY_CAMPAIGN_20260909.md`
- rowmajor 276/244/149，sub 122/90/116，dump 7/12/3；三轮方向一致。
- rowmajor 逐轮走低但 sub 平稳——单变体趋势，未归因。
- fails 全窗口均匀分布（rowmajor r1 每 5min 桶：48/38/51/42/50/47）。

### 2.2 09-10 单元隔离战役（7 测试 × 2 轮 × 30min）
来源：`docs/CORE179_UNIT_ISOLATION_CAMPAIGN_20260910.md`
- rowmajor 基线 271/216（当晚 179 活跃性确认）。
- tlbstress / lsqfill / rfport / robfill / robfill_np / prefetch 六变体两轮全 0。
- 归因保留：所有变体都扰动了热循环指令布局，0-fail 无法区分
  "单元不参与"（H1）vs "布局灭活"（H2）。硬结论仅：6 种压力加入方式
  无一是触发的保持/增强因素。

### 2.3 09-10 晚饱和修复 v2 战役（4 × 30min）——**整体无效（亲和性掩码事故）**
设计：lsqfill_v2（64% load 管线）、rfport_v2（机器极限 vmov 辫）、
rowmajor+邻核页遍历风暴、rowmajor 基线对照。

**事故：4 项全部假阴性。** 战役 shell 创建于 179 hotplug 离线期间，
亲和性掩码为 `0-178,180-191`，经 nohup 继承给 opendcdiag——
**179 在线但从未运行任何测试线程**。证据：rowmajor_ctl.log 中
`logical: 179` 出现 0 次（176/177/178 各 1 次），
而同条件昨日基线为 271/216。

- lsqfill_v2 = 0、rfport_v2 = 0、rowmajor+storm = 0、rowmajor_ctl = 0
  → **四项数据全部作废**，不进入结论。
- 教训（已入记忆）：从 179 离线期 shell 启动的任何全核测试，
  必须先 `taskset -pc 0-191 $$` 或用 `taskset -c 0-191` 包一层启动，
  并以日志中出现 `logical: 179` 为在场判据。

### 2.4 09-11 基线复跑（干净掩码，30min）
`taskset -c 0-191 ./builddir/opendcdiag -e neon_rot_ldr_at_top_rowmajor
-n 192 -T 30m --ignore-os-error --ignore-timeout -o .../rowmajor_ctl2.log`

- **320 fail 块**（miscompare 320，`exit: fail`）。
- cpu-mask 解码：**320/320 的 X 位全部 = thread 179**（无任何其他核）。
- `logical: 179` 在场 321 次（1 次线程枚举 + 320 次 fail）。
- ttf：min 6.273s / max 999.101s / 均值 384s（n=640 ttf 行，2 行/块）。
- 开跑 90s 即 23 fail——触发形态与历史完全一致。
- 三法交叉验证：唯一 fail 块计数 = 320 = miscompare 计数；exit: fail。✅

---

## 3. 触发频率排序与量级

```
rowmajor        ████████████████████████████████  ~246/30min (8.2/min)   ← 最高
sub             █████████████▌                    ~109/30min (3.6/min)   2.2× 低
rowmajor_dump   █▏                                ~7/30min  (0.24/min)   34× 低（dump 抑制）
六单元隔离变体   —                                 0/30min  (0)
```

- rowmajor vs sub：扫描顺序（交替 vs 顺序）稳定影响触发强度，三轮方向一致，
  但非干净单变量（数据地址流亦不同），不能归因预取器。
- dump 抑制 ~30×：与 movbe/mrn_rmw 系列"加冷分支 dump 即抑制"同构。

## 4. 单元压力维度的有效结论（结合饱和度审计）

来源：`docs/CORE179_UNIT_SATURATION_AUDIT_20260910.md`

- **压力确凿生效仍 0-fail**（真阴性概率高，但仍受 H2 布局 confound 限制）：
  - tlbstress：dTLB refill 13× 基线、页表 walk 3× —— TLB/页遍历压力下触发消失
  - prefetch：L1D miss 塌缩 1900×（最干净的否定证据）—— 预取器介导假说的最强反证
- **压力未饱和的 0-fail**（归因力打折）：
  - lsqfill（load 管线 ~40–60%）、rfport（RF 端口远未饱和）、
    robfill（IPC 2.90 仍高），且 nop 对照自身灭活，本轮对 ROB 维度无区分度。
- v2 修复变体（lsqfill_v2 64% load 管线、rfport_v2 机器极限）因掩码事故
  **未取得有效数据**，如需闭环需重跑。

## 5. 待办 / 开口

1. v2 饱和修复变体（lsqfill_v2 / rfport_v2 / rowmajor+storm）用干净掩码重跑——
   本轮无效，盲区（LSQ 隔离、RF 端口）仍未关闭。
2. rowmajor 逐轮走低（276→244→149，但 09-10 回升 271/216、09-11 达 320）——
   趋势不再单调，"衰减"假说弱化，记录待查。
3. 归因 H1/H2 之争仍开放：需要"不扰动字节布局的前提下加单元压力"的
   实验设计（当前不存在此类手段）。
