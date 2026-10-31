# CORE179 SDC 触发用例全量排序与优先级分级（2026-10-22）

> 本文将全部 57 个有效 SDC 触发用例按触发率（fail/min）排成五个梯队，并据此建立
> **P0–P4 优先级分级**，作为后续实验选择负载的统一依据。
> 上位文档（用例判定标准与逐用例出处）：`CORE179_ALL_VALID_SDC_TESTCASES_20260923.md`。
> 数据截至 2026-10-22；排序口径与不可比性注意事项见 §7，务必先读再比较梯队边界附近的次序。

---

## 1. 梯队 × 优先级总览

| 梯队 | 触发率区间 | 用例数 | 优先级 | 定位 |
|---|---|---|---|---|
| 第一梯队 | ≥3 fail/min | 6 | **P0** | 主力触发器（默认负载） |
| 第二梯队 | 2–3 fail/min | 5 | **P1** | 高优先级（替代/取证主力） |
| 第三梯队 | 1–2 fail/min | 11 | **P2** | 中优先级（K-cells 主战场） |
| 第四梯队 | 0.1–1 fail/min | 15 | **P3** | 低优先级（机制对照/梯度位置） |
| 第五梯队 | <0.1 / 间歇 / 特殊条件 | 20 | **P4** | 条件级（仅特定机制验证） |

合计 57 个。**梯队与优先级一一对应**：优先级完全由本排序的梯队决定，不另行引入其它判据。

---

## 2. 第一梯队（≥3 fail/min，6 个）→ P0

| # | 测试用例 | 触发率(fail/min) | 备注 |
|---|---|---|---|
| 1 | `neon_rot_ldr_at_top_rowmajor` | ~8.5（09-08~11 七轮 149–320/30min，均值 255） | 全史最高率稳态；1019/1019 fail 全在 179；⚠️ 09-13 后同用例降至 0.6–1.9/min（跨夜波动，未归因） |
| 2 | `neon_rot_ldr_at_top_sub` | ~3.9（四轮 138/122/116/90） | 纯升序扫描 |
| 3 | `mrn_reloaded_2src_alu` | ~3.5（126/36min） | 标量最高率触发器，首失败均值 15.3s |
| 4 | `neon_rot_ldr_at_top_str3` | ~3.3（四轮 133/164/51/49，跨 6 天） | 第 3 条 store |
| 5 | `movbe` | ~3.0 短窗（15/5min，V6）；30min 口径 1.9（57 唯一块） | 日常 SDC 门首选 |
| 6 | `neon_rot_ldr_at_top_mla` | ~3.0（89/30min，单轮） | 乘加变体 |

## 3. 第二梯队（2–3 fail/min，5 个）→ P1

| # | 测试用例 | 触发率(fail/min) | 备注 |
|---|---|---|---|
| 7 | `neon_rot_ldr_at_top_rowmajor_gps` | 2.9（87/30min） | 取证主力（数据带来源标签） |
| 8 | `mrn_rmw_diff_64k` | ~2.4（19/~8min，截断轮） | 瞬时率，单轮 |
| 9 | `k7p_rand` | 2.6 / 1.1（两晚 78/34） | K-cells 首晚全场最高 |
| 10 | `k5inter_rand` | 2.4 / 1.7（72/50） | 第二晚反超 k7p_rand，两者次序不稳 |
| 11 | `movbe_dump` | ~2（10/5min V6；8-25 短窗峰值 6.4） | |

## 4. 第三梯队（1–2 fail/min，11 个）→ P2

| # | 测试用例 | 触发率(fail/min) | 备注 |
|---|---|---|---|
| 12 | `k3res` | 1.9 / 1.4（58/41） | 114/15min 为 panic 截断突发期，不计 |
| 13 | `movbe_l1d` | ~1.8（9/5min） | |
| 14 | `mrn_rmw_fwd` | 1.8（8-25）↔ 0.067（V6.2.3 干净复测） | 两口径差 27×，取哪个未决 |
| 15 | `movbe_dump_golden` | 1.5（45/30min） | |
| 16 | `k7p_hiham` | 1.5 / 0.3（44/9） | |
| 17 | `k7p_one` | 1.4 / 0.3（42/8） | |
| 18 | `arm0102_kreg_select` | 1.3（40/30min） | ⚠️ 当前未注册 meson，复跑须先挂接 |
| 19 | `mrn_pairs_2src_alu` | ~1.3（46/36min） | |
| 20 | `k5far` | 1.2 / 0.5（37/16） | |
| 21 | `neon_rot_ldr_at_top_ldr4` | ~1.2（29/24.9min，panic 截断） | 父版率的 1/4–1/8 |
| 22 | `neon_rot_2src` | ~1.1（33/30min + 复跑 26） | NEON 移植版 |

## 5. 第四梯队（0.1–1 fail/min，15 个）→ P3

| # | 测试用例 | 触发率(fail/min) | 备注 |
|---|---|---|---|
| 23 | `neon_rot_ldr_at_top_offdiag` | 0.9（27/30min） | |
| 24 | `mrn_rmw_diff` | 0.27–1.0（8/30、10/10min、4/5min） | |
| 25 | `agu_stress_2src` | 0.63（19/30min） | 19/19 逐条核验 |
| 26 | `mrn_nuke_2src_alu` | ~0.47（14/30min） | |
| 27 | `neon_rot_store_only` | 0.47（14/30min） | 无 reload 仍触发 |
| 28 | `mrn_rmw` | 0.2–0.4（6/30min、2/5min） | |
| 29 | `neon_rot_ldr_at_top_rowmajor_dualcmp` | 0.4（12+12 两轮） | 签名采集专用 |
| 30 | `mrn_rmw_dump` | 0.03–0.4（2/60min、2/5min） | |
| 31 | `mrn_nuke_3src_alu` | 0.28（10/36min） | |
| 32 | `eigen_gemm_float_dynamic_square` | ~0.37（11 样本/30min） | 12.7.1 短窗曾 1.2 |
| 33 | `eigen_gemm_double_dynamic_square` | ~0.37（11 样本/30min） | 尾数 93% 最密 |
| 34 | `eigen_svd` | ~0.37（11/30min） | 单位翻转签名 |
| 35 | `neon_rot_ldr_at_top_rowmajor_dump` | ~0.24（7/12/3 三轮） | dump 冷分支抑制 ~30× |
| 36 | `arm0102_kreg_not` | 0.2（6/30min） | ⚠️ 未注册 meson |
| 37 | `mrn_nuke_4src_alu` | 0.11（4/36min） | |

## 6. 第五梯队（<0.1 fail/min / 间歇 / 特殊条件，20 个）→ P4

| # | 测试用例 | 触发率(fail/min) | 备注 |
|---|---|---|---|
| 38 | `mrn_rmw_nop` | 0.067（8-28 干净复测；8-25 曾 0.6） | nop 曲线：0/1/2 持平→≥8 归零 |
| 39 | `neon_rot_u8x16` | 0.067（2/30min） | 16×8b lane 塌缩 15× |
| 40 | `mrn_rmw_nop1` | 0.067（2/30min） | |
| 41 | `eigen_gemm_float_dynamic_square_dump` | 0.067（1/15min） | |
| 42 | `eigen_gemm_double_dynamic_square_dump` | 0.067（1/15min） | |
| 43 | `eigen_gemm_cdouble_dynamic_square` | 0.067（1/15min） | |
| 44 | `eigen_svd_double2` | 0.067（1/15min） | |
| 45 | `movbe_dump_probe_xn` | 0.033（1/30min） | |
| 46 | `mrn_rmw_nop4` | 0.033（1/30min） | |
| 47 | `agu_stress_store_only` | 0.033（1/30min，单样本） | |
| 48 | `neon_rot_ldr_at_top_str3_checkall` | 0.033（1/30min） | 待复跑 |
| 49 | `arm0102_fma_f32` | 0.033（1/30min） | ⚠️ 未注册 meson |
| 50 | `arm0102_kreg_logic` | 0.033（1/30min） | ⚠️ 未注册 meson |
| 51 | `mem_disambig_alu` | 0.028（1/36min） | |
| 52 | `mrn_nuke_dense` | 0.028（1/36min） | |
| 53 | `eigen_svd_cdouble_noavx512` | 最低（历史 1；re-test 0/15min） | |
| 54 | `movbe_dump_probe_h` | 间歇（1/10 seed 触发） | |
| 55 | `movbe_dump_probe_x` | 间歇（1/5 seed 触发） | |
| 56 | `memcpy1` | 无单测率（6 fail 仅全套件并发；单测复测 0） | 判别变量=并发 |
| 57 | `eigen_gemm_double14` | 未定（44 fail，8-12；5min 窗常漏，isApprox 先触发） | |

---

## 7. 优先级分级定义与使用建议

### 7.1 分级定义

优先级与梯队一一对应（见 §1 总览），含义如下：

| 优先级 | 梯队 | 判据 | 使用场景 |
|---|---|---|---|
| **P0** | 一 | ≥3 fail/min | 日常触发 SDC 的核心负载；新实验/新假说的默认选择；率标定基准 |
| **P1** | 二 | 2–3 fail/min | P0 不可用或需要换骨架时的替代；取证主力（gps）在此级 |
| **P2** | 三 | 1–2 fail/min | K-cells 家族主战场；需要较长窗口累积样本的实验 |
| **P3** | 四 | 0.1–1 fail/min | 机制对照、梯度定位（源数梯度、nop 间距、dump 抑制等）；eigen 家族在此级 |
| **P4** | 五 | <0.1 / 间歇 / 特殊条件 | 仅用于特定机制验证（lane 宽度、seed 依赖、并发判别等），不作日常触发 |

### 7.2 跨梯队功能角色（正交标注，不改变优先级）

- **日常 SDC 门**：`movbe`（P0）
- **诊断主力**：`mrn_reloaded_2src_alu`（P0）+ K-cells 7 用例（P1/P2，两晚 100% 复现）
- **签名/取证采集**：`neon_rot_ldr_at_top_rowmajor_dualcmp`（P3，签名采集专用）、`neon_rot_ldr_at_top_rowmajor_gps`（P1，数据带来源标签）
- **机制对照锚点**：nop 系列（P4/P5 梯队内 0/1/2/4 间距曲线）、`neon_rot_u8x16`（lane 宽塌缩）、`neon_rot_store_only` / `agu_stress_store_only`（无 reload 对照）、`memcpy1`（并发判别）

### 7.3 使用约束（复跑前必查）

- ⚠️ **未注册 meson，复跑前须先挂接**：`arm0102_kreg_select`（P2）、`arm0102_kreg_not`（P3）、`arm0102_fma_f32`（P4）、`arm0102_kreg_logic`（P4）。
- ⛔ **禁止按原样复跑**：`neon_rot_ldr_at_top` 原版（整机硬冻结史，见 `NEON_PROBE_MACHINE_FREEZE_20260904.md`；其衍生变体不在禁跑之列）。
- **口径未决**：`mrn_rmw_fwd` 两口径差 27×（8-25 短窗 1.8 vs V6.2.3 干净复测 0.067），引用其率时必须注明口径。
- **panic 截断轮不计率**：`k3res` 的 114/15min、`neon_rot_ldr_at_top_ldr4` 的截断轮均已剔除，勿再纳入均值。

---

## 8. 排序口径与注意事项

- **率不可比的部分**：跨夜晚存在 0.45×~4× 的整体波动（七用例逆序复跑 7/7 同向降至 45%，未归因），所以梯队边界附近的次序有不确定性——**同一晚内的跨用例排序才严格可靠**；movbe 系的 5min 短窗率与 30min 率也不完全可比（短窗偏高）。
- **K-cells 6 变体**按官方战役首晚（09-13）排，两晚数值都列出；`k7p_rand` 与 `k5inter_rand` 的相对次序在两晚间翻转。
- **已剔除/排除**：`movbe_dump_probe_c`（390 fail 但为多核 FP 风暴，非锁 179）、`neon_rot_ldr_at_top` 原版（整机硬冻结）、SiliFuzz 污染窗口（08-26 15:44~28）数据、V5 双计统计。
- **当前推荐主力**（登记册 §七，`CORE179_ALL_VALID_SDC_TESTCASES_20260923.md`）：K-cells 7 用例（~1–2/min，两晚 100% 复现）+ `mrn_reloaded_2src_alu`（3.5/min）作诊断主力，`dualcmp` 作签名采集。

## 9. 关联文档

- `CORE179_ALL_VALID_SDC_TESTCASES_20260923.md` — 用例判定标准、逐用例出处、灭活对照附录、排除项（上位登记册）
- `CORE179_VALID7_RERUN_REVERSED_ORDER_20260915.md` — 跨夜 0.45× 波动的来源实验
- `CORE179_READPATH_K_CELLS_BATCH2_RESULTS_20260914.md` — K-cells 两晚战役数据
- `MOVBE_SDC_CORE179_LOCALIZATION_REPORT_V6.md` — movbe 系率口径（短窗 vs 30min）
- `SDC_LOG_MASTER_RECORD.csv` — 全量 fail 日志主记录
