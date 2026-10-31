# MOVBE SDC CORE179 LOCALIZATION REPORT V6 — Addendum 2026-08-28

**日期**:2026-08-28
**状态**:统计学误判纠正 + 触发机制重构;V5 多条结论被推翻
**目标机器**:192 核 aarch64(8 NUMA × 24),package 19062,core 179
**触发配置**:全核 192(含 179)+ auto-seed + `--max-test-loop-count=0` + `-T 5m/15m`
**统计口径**(本 addendum 起强制):fail 数 = `result: fail` 块数(每个 SDC 事件 = 1 块),**禁止**用 `grep miscompare` 行数

---

## §V6.1  本 addendum 缘起:V5 的两个统计误判

V5(V5.4 表)的 nop 曲线和"6/10 检测器"判定,建立在两处错误统计上,导致结论系统性偏移:

1. **miscompare 关键词双计/漏计**——先前统计脚本用 `grep miscompare` 数 fail 行。但:
   - `mrn_rmw` 系错误信息含 `miscompare`(`mrn_rmw data miscompare`),且每个 SDC 事件产生 **2 行** miscompare(`E> test:` 数据行 + `E> Failed at ...` 位置行),grep 双计,fail 数翻倍。
   - `movbe` 系错误信息写的是 `MovBE: Round-trip failed at index %u`,**不含 miscompare**,grep 一行都匹配不上,movbe 系 fail **全部漏计为 0**。
   - 后果:movbe/movbe_dump/movbe_l1d 被误报"5min 0 fail"(实为 9~15 fail),mrn_rmw 系被误报为 2x。
2. **SiliFuzz 污染窗口**——8-26 15:44 起 SiliFuzz(reading_runner,`--max_cpus=192` 含 179)占核,8-27 那批 movbe 1/2/3/4/8/64nop 全 0fail 是 179 被占、碰不上触发窗口,**数据作废**。

**纠正动作**:统一口径为 `result: fail` 块;8-28 在 SiliFuzz 已停、179 干净环境下重测。

---

## §V6.2  8-28 干净环境复测结果(正确口径)

环境确认:SiliFuzz 无进程,179 核 100% idle,load ~0.3。全核 192 含 179 + auto-seed + `--max-test-loop-count=0`。

### V6.2.1  10 检测器 5min 复测(主结果)

| # | 测试 | 5min fail | fail/min | seeds(LCG) | 触发 |
|---|------|-----------|----------|------------|------|
| 1 | **movbe** | 15 | 3.0 | 2055646887×3, 236415565×2, ... | ✅ 最高 |
| 2 | **movbe_dump** | 10 | 2.0 | (10 个) | ✅ 高 |
| 3 | **movbe_l1d** | 9 | 1.8 | (9 个) | ✅ 高 |
| 4 | movbe_l1d_v_rev | 0 | — | — | 间歇(真 0,寻址敏感) |
| 5 | **mrn_rmw**(原始版) | 2 | 0.4 | 1735548145@578ms, 1944529265@343ms | ✅ 中 |
| 6 | **mrn_rmw_dump** | 2 | 0.4 | 1100507883@547ms, 53609704@357ms | ✅ 中 |
| 7 | **mrn_rmw_fwd** | 1 | 0.2 | 1946537215@570ms | ✅ 中 |
| 8 | movbe_dump_probe_h | 0 | — | — | 间歇(1/10 seed) |
| 9 | movbe_dump_probe_x | 0 | — | — | 间歇(1/5 seed) |
| 10 | movbe_dump_probe_e | 0 | — | — | 间歇 |
| (另) | movbe_dump_probe_c | 390 | — | — | ⚠️ 非同一缺陷(多核 FP 机制) |

**5min 内确认触发 = 6 个**:movbe、movbe_dump、movbe_l1d、mrn_rmw、mrn_rmw_dump、mrn_rmw_fwd。

### V6.2.2  movbe 15min 复测

movbe 15min = **22 fail**(~1.47 fail/min),全核 179,22 个不同 seed,time-to-fail 从 6.9ms 到 1107ms 不等。

### V6.2.3  nop 时序曲线(正确口径)

干净复测,唯一 fail 块数:

| str→ldr 间隔 | 测试 | 时长 | 唯一 fail | fail/min |
|---|---|---|---|---|
| 0 nop(紧贴) | mrn_rmw_fwd | 15m | 1 | 0.067 |
| 1 nop(~1cyc) | mrn_rmw_nop1 | 30m | 2 | 0.067 |
| 2 nop(~2cyc) | mrn_rmw_nop | 30m | 2 | 0.067 |
| 4 nop | mrn_rmw_nop4 | 30m | 1 | 0.033 |
| 8 nop | mrn_rmw_nop8 | 30m | 0 | 0 |
| 16 nop | mrn_rmw_nop16 | 1h | 0 | 0 |
| 64 nop | mrn_rmw_nop64 | 5m | 0 | 0 |

**形状**:0/1/2 nop 持平 ~0.067/min,4 nop 减半,≥8 nop 归零。
**推翻 V5**:V5 的"0→18→1→6→0 非单调"曲线是双计 + 15min 短样本涨落假象;正确曲线是**单调**下降——短间隔(0~2cyc)才触发,长间隔灭活。1 nop 不是谷,2 nop 不是峰。

---

## §V6.3  触发机制重构(推翻 V5.4/V5.5 的部分)

### V6.3.1  两个被推翻的候选

| 候选 | V5/先前主张 | 8-28 证据 | 判决 |
|---|---|---|---|
| "存储-加载时延较长"导致 | 长时延暴露缺陷 | nop 曲线:0/1/2cyc 触发,≥8cyc 归零 | ❌ **反**——要的是**短**间隔,不是长 |
| "高频用 L1D"压垮 | 高吞吐/大 footprint 触发 | footprint 64B(fwd)~128KB(movbe)跨 2000× 都触发;evict 走 L2=0 | ❌ 高频不成立;路径必需成立 |

### V6.3.2  正确机制:pattern-dependent 硬件缺陷 × 时序窗口

179 是**硬件故障**(L1D 阵列某物理位置 marginality),不是软件 bug、不是均匀随机错。触发由两个变量叠加决定:

1. **bit pattern 激活潜力**——不同 seed 产生不同 bit pattern,落进 L1D 同一物理位置时 bit 态不同。只有特定 pattern 在缺陷位置处于激活态才有触发可能。
   - **固定 seed**:整个 input buffer 是一个 pattern。若该 pattern 在缺陷位置不处于激活态 → 缺陷这轮物理上碰不上 → load 再多次、跑再久也 0 fail。**这不是采样量不足,是物理上碰不上激活态。**
   - **auto-seed**:每轮 `memset_random` 填新 pattern,缺陷位置 bit 轮换 → 有轮次撞上激活态 → 触发。
   - 证据:probe_h 1/10 seed 触发 = 10 个 pattern 里约 1 个激活,pattern 间方差远大于纯概率二项涨落,pattern 是真变量。
2. **时序窗口激活**——同激活 pattern 下,全核并发微观时序每轮波动,触发与否也波动。
   - 解了"同 seed 重跑不稳定"的张力(h-rate:同 seed 一次 fail、重跑 pass):pattern 决定激活**潜力**,时序决定**该潜力下每轮是否真激活**。两个变量叠加,非单一概率。

### V6.3.3  触发率公式

窗口内(激活 pattern + 时序命中):
```
触发率 ≈ L1D 域 load 次数 × 单次概率(~10⁻⁶)
```

| 测试 | 内层迭代 | ldr/迭代 | 轮率 | ldr/s | fail/min | 推算单次概率 |
|---|---|---|---|---|---|---|
| movbe | 16384 | 2 | 652轮/15min | ~24000 | ~1.5 | ~1.0×10⁻⁶ |
| mrn_rmw | 1024 | 3 | 253轮/5min | ~2600 | ~0.4 | ~2.6×10⁻⁶ |

ldr 次数差 ~9×,fail 率差 ~5×,单次概率同数量级(~10⁻⁶)。**movbe 触发率高只因 load 次数多(采样足),不是单次更易错、也不是路径更脆弱。**

> 注:此公式在前置条件全满足后才成立。pattern 不激活时,load 次数无关。

---

## §V6.4  完整激活条件(四要素,缺一不可)

| 条件 | 满足 → 触发 | 不满足 → 0 |
|---|---|---|
| **全核并发压力** | 全核 192 | 单核 taskset / 切片 24/170 |
| **auto-seed** | 随机 seed | 固定 `-s` |
| **reload 走 L1D 域** | 阵列读 / forwarding | evict 走 L2(movbe_l2 / mrn_rmw_l1d) |
| **str→ldr ≤2 cycle** | 0/1/2 nop | ≥8 nop |

四要素是"门",门全开后才有"每次 ~10⁻⁶"的概率窗口。其中条件 1、2(全核压力、auto-seed)最易被破坏,破坏了得**假 0**——SiliFuzz 污染、固定 seed、taskset 单核,都是栽在这两条上。

### V6.4.1  固定 seed 的本质(纠正 V5/旧记忆措辞)

- 旧措辞:"SDC is seed-sensitive"(暗示 bit pattern 是变量但归因模糊)
- 修正:固定 seed = 该 bit pattern 在缺陷物理位置不处于激活态(主因)+ 1 pattern × 时序波动仍碰不上(辅)。
- 字面:固定 seed 锁死**输入值 + 黄金值**(地址序列不变,bit pattern 固定);唯一不固定的是**实际值(actual,来自硬件)**。actual 出错 = 与 golden 不符 = SDC 证据。

---

## §V6.5  对 V5.5 的逐条修正

| V5.5 claim | V5 判 | V6 修正 |
|---|---|---|
| SDC on reload return path | ✅ | ✅ 维持 |
| reload 前有 timing-race window | ✅ | ✅ 维持,但**窗口是窄的(≤2cyc),长间隔灭活**,非 V5 暗示的宽窗 |
| timing race 是 root cause | ❌ no | ❌ 维持(硬件故障是 root cause);但 V6 进一步:bit pattern 激活潜力是**第二变量**,非纯时序 |
| "data must be fetched from L1D" | ❌ refuted(nop64 仍过 L1D 却 0) | ✅ **推翻 V5 的 refutation**:nop64 的 0 是 str→ldr 间隔超窗口(64cyc)导致,不是"不需要 L1D"。reload 走 L1D 域是**必要条件**(evict 走 L2 也 0)。nop64 同时满足"走 L1D"但不满足"≤2cyc",故 0 |
| pinned to L1D array | ❌ not clean | ⚠️ 维持"不可清晰分离",但 evict→0 + pattern 激活指向**L1D 域是必要路径**,是否就是阵列本体仍不可分(forwarding vs 阵列读 vs load port) |
| cross-family common lesion | ❌ not established | ❌ 维持(movbe/mrn_rmw 走 L1D 域;eigen 走 FP-compute,定位仍 open) |

---

## §V6.6  检测器选型结论(给日常 SDC 门)

| 用途 | 推荐 | 理由 |
|---|---|---|
| 日常 SDC 门(高频) | **movbe** | 5min 15 fail(~3/min),15min 22 fail;load 次数多采样足 |
| 备选高频 | movbe_dump / movbe_l1d | ~2/min、~1.8/min |
| 中频验证 | mrn_rmw / mrn_rmw_dump / mrn_rmw_fwd | ~0.2~0.4/min,路径互补 |
| 间歇探测(需长时/多seed) | movbe_l1d_v_rev / probe_h / probe_x / probe_e | seed 敏感,5min 常漏,需 30min+ 或多轮 |

**不推荐作检测器**:probe_c(390 fail 但是多核 FP 机制,非 179 同一缺陷,会误导)。

---

## §V6.7  未决 / 仍 open

1. **eigen 定位**——movbe/mrn_rmw 走 L1D 域,eigen 走 FP-compute,两者是否同一物理缺陷仍是 open gap(V5.6 沿袭)。
2. **L1D 域内进一步分离**——forwarding vs 阵列读 vs load port vs register file,介入工具天花板(V5.6 沿袭)。
3. **bit pattern 调制概率的量化**——V6 判 pattern 是真变量,但"1/10 seed 触发"是 pattern 调制 vs 纯时序概率,数据仍分不清。需设计固定激活 pattern vs 固定非激活 pattern 的对照实验(当前无干净手段)。

---

*本 addendum 基于 8-28 干净环境复测。所有 fail 数为 `result: fail` 块数口径。SiliFuzz 污染期(8-26 15:44 起)数据全部作废,不引用。*
