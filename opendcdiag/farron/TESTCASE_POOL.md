# FARRON 测试用例池名单（Testcase Pool）

**生成日期**：2026-10-25
**判定标准**：
- **活跃级（Active）**——成功检测到错误的测试用例：在本机（Kunpeng 920，逻辑核 179 SDC 缺陷）战役中产生过唯一 `result: fail` 块，fail 锁定逻辑核 179（cpu-mask 唯一 X 位 / thread 179 三法交叉），其余核零错误，且有可追溯证据（docs 记载或幸存日志/yaml）。
- **基础级（Basic）**——从未检测出错误的测试样例：有运行记录但从未触发 SDC（灭活对照），或尚无战役记录（状态未入账）。

**权威依据**：`docs/CORE179_ALL_VALID_SDC_TESTCASES_20260923.md`（57 用例总登记册）、`docs/CORE179_SDC_TESTCASE_PRIORITY_TIERS_20261022.md`（五梯队排序）。

**统计总览**：活跃级 **57** ／ 基础级 **83**（灭活对照 70 + 未入账 13）／ 特殊排除 8。

---

## 一、活跃级（Active，57 个）——已证实可检测 179 号核 SDC

### P0 第一梯队（≥3 fail/min，6 个）——主力触发器

| # | 测试用例 | 触发率 | 备注 |
|---|---|---|---|
| 1 | `neon_rot_ldr_at_top_rowmajor` | ~8.5/min（七轮均值 255/30min） | 全史最高率稳态；1019/1019 fail 全 179 |
| 2 | `neon_rot_ldr_at_top_sub` | ~3.9/min | 纯升序扫描 |
| 3 | `mrn_reloaded_2src_alu` | ~3.5/min（126/36min） | 标量最高率触发器 |
| 4 | `neon_rot_ldr_at_top_str3` | ~3.3/min（四轮跨 6 天） | 第 3 条 store |
| 5 | `movbe` | ~3.0/min 短窗（30min 口径 1.9） | 日常 SDC 门首选 |
| 6 | `neon_rot_ldr_at_top_mla` | ~3.0/min（单轮） | 乘加变体 |

### P1 第二梯队（2-3 fail/min，5 个）

| # | 测试用例 | 触发率 | 备注 |
|---|---|---|---|
| 7 | `neon_rot_ldr_at_top_rowmajor_gps` | 2.9/min | 取证主力（数据带来源标签） |
| 8 | `mrn_rmw_diff_64k` | ~2.4/min（截断轮） | 瞬时率 |
| 9 | `..._k7p_rand` | 2.6 / 1.1（两晚） | K-cells 首晚全场最高 |
| 10 | `..._k5inter_rand` | 2.4 / 1.7 | 与 k7p_rand 次序不稳 |
| 11 | `movbe_dump` | ~2/min | 8-25 短窗峰值 6.4 |

### P2 第三梯队（1-2 fail/min，11 个）——K-cells 主战场

| # | 测试用例 | 触发率 |
|---|---|---|
| 12 | `..._k3res` | 1.9 / 1.4 |
| 13 | `movbe_l1d` | ~1.8 |
| 14 | `mrn_rmw_fwd` | 1.8 ↔ 0.067（口径差异 27×，引用须注明） |
| 15 | `movbe_dump_golden` | 1.5 |
| 16 | `..._k7p_hiham` | 1.5 / 0.3 |
| 17 | `..._k7p_one` | 1.4 / 0.3 |
| 18 | `arm0102_kreg_select` ⚠️未注册meson | 1.3 |
| 19 | `mrn_pairs_2src_alu` | ~1.3 |
| 20 | `..._k5far` | 1.2 / 0.5 |
| 21 | `neon_rot_ldr_at_top_ldr4` | ~1.2（panic 截断轮） |
| 22 | `neon_rot_2src` | ~1.1 |

### P3 第四梯队（0.1-1 fail/min，15 个）——机制对照/梯度

| # | 测试用例 | 触发率 |
|---|---|---|
| 23 | `neon_rot_ldr_at_top_offdiag` | 0.9 |
| 24 | `mrn_rmw_diff` | 0.27–1.0 |
| 25 | `agu_stress_2src` | 0.63 |
| 26 | `mrn_nuke_2src_alu` | ~0.47 |
| 27 | `neon_rot_store_only` | 0.47 |
| 28 | `mrn_rmw` | 0.2–0.4 |
| 29 | `neon_rot_ldr_at_top_rowmajor_dualcmp` | 0.4（签名采集专用） |
| 30 | `mrn_rmw_dump` | 0.03–0.4 |
| 31 | `mrn_nuke_3src_alu` | 0.28 |
| 32 | `eigen_gemm_float_dynamic_square` | ~0.37 |
| 33 | `eigen_gemm_double_dynamic_square` | ~0.37 |
| 34 | `eigen_svd` | ~0.37 |
| 35 | `neon_rot_ldr_at_top_rowmajor_dump` | ~0.24（dump 冷分支抑制 30×） |
| 36 | `arm0102_kreg_not` ⚠️未注册meson | 0.2 |
| 37 | `mrn_nuke_4src_alu` | 0.11 |

### P4 第五梯队（<0.1 / 间歇 / 特殊条件，20 个）——条件级

| # | 测试用例 | 触发率/性质 |
|---|---|---|
| 38 | `mrn_rmw_nop` | 0.067 |
| 39 | `neon_rot_u8x16` | 0.067（lane 宽塌缩对照） |
| 40 | `mrn_rmw_nop1` | 0.067 |
| 41 | `eigen_gemm_float_dynamic_square_dump` | 0.067 |
| 42 | `eigen_gemm_double_dynamic_square_dump` | 0.067 |
| 43 | `eigen_gemm_cdouble_dynamic_square` | 0.067 |
| 44 | `eigen_svd_double2` | 0.067 |
| 45 | `movbe_dump_probe_xn` | 0.033 |
| 46 | `mrn_rmw_nop4` | 0.033 |
| 47 | `agu_stress_store_only` | 0.033（单样本，需长跑确认） |
| 48 | `neon_rot_ldr_at_top_str3_checkall` | 0.033（待复跑） |
| 49 | `arm0102_fma_f32` ⚠️未注册meson | 0.033 |
| 50 | `arm0102_kreg_logic` ⚠️未注册meson | 0.033 |
| 51 | `mem_disambig_alu` | 0.028 |
| 52 | `mrn_nuke_dense` | 0.028 |
| 53 | `eigen_svd_cdouble_noavx512` | 最低（历史 1；re-test 0） |
| 54 | `movbe_dump_probe_h` | 间歇（1/10 seed） |
| 55 | `movbe_dump_probe_x` | 间歇（1/5 seed） |
| 56 | `memcpy1` | 仅全套件并发下触发（6 fail；单测 0） |
| 57 | `eigen_gemm_double14` | 未定率（44 fail 历史；isApprox 先触发） |

⚠️ arm0102 四用例（#18/36/49/50）源码在 `tests/cpu/arm-0102/` 但**未挂入 meson**，复跑前须先注册。
⚠️ 跨夜率存在 0.45×~4× 整体波动；梯队边界次序有不确定性，同一晚内排序才严格可靠。

---

## 二、基础级（Basic，83 个）——从未检测出错误

### 2.1 灭活对照（有战役记录的 0-fail，70 个）——每条都是触发配方必要条件的证据

| 家族 | 用例 | 证明的必要条件 |
|---|---|---|
| movbe probe（4） | `probe_a`、`probe_b`、`probe_d`、`probe_e` | store 必要 / 紧时序必要 / 地址推进 / 同 LLC 域 |
| movbe 变体（2） | `movbe_l1d_v_rev`、`movbe_l2` | 寻址模式级敏感 / evict-L2 路径不触发 |
| mrn_rmw 时序/逐出（5） | `mrn_rmw_nop8`、`nop16`、`nop64`、`mrn_rmw_l1d`、`mrn_rmw_diff_nop64` | 时序窗口 ≥8cyc 关闭 / 逐出路径 |
| 22tests 其余 21（21） | `mrn_nuke`、`mrn_pairs`、`mrn_reloaded`、`mem_disambiguation`、`partial_store_forwarding`、`part_store_fwd_jit`、`atomic_seq_cst`、`mfence`、`mfence_pure`、`mite`、`mrn_flags`、`modified_sort`、`move_elimination_jit`×3、`movdq2q`、`movq2dq`、`movmskpspd`*、`zero_control_vec_*_jit`×3* | 1源+原值forwarding不触发 / 纯ALU不触发（mrn_nuke 为微操作同构关键反例） |
| 构造变体（8） | `mrn_nuke_recross`、`mrn_pairs_2src_alu_keep8`、`mrn_nuke_2src_add/_sub/_eor/_and`、`probe_asm_fwd` v1/v2 | 同址重读移植失败 / 松时序灭活 / 轮换 ALU 必要 / 单加 ALU 仍 1 源不触发 |
| AGU（2） | `agu_stress_1src`、`agu_stress_unaligned` | 1 源不触发 / 寻址改动→布局灭活 |
| NEON 早期（3） | `neon_rot_1src`、`neon_rot_u32x4`、`neon_rot_fwd_probe` | 1 源不触发 / 4×32b lane=0 / 布局敏感 |
| K-cells 零格（4） | `..._k2pureload`、`..._k4gap`、`..._k4bgap`、`..._k7p_zero` | 零 store 灭活 / 紧时序双向必要 / 全 0 数据静默 |
| 读路径 P0（1） | `..._rowmajor_scalar64` | 标量 64b 直译归零（触发绑定 NEON lane 组织） |
| 单元隔离（6） | `tlbstress`、`lsqfill`、`rfport`、`robfill`、`robfill_np`、`prefetch` | 六单元隔离均不触发（tlbstress/prefetch 归因力强；lsqfill/rfport/robfill 未饱和） |
| str/ldr 梯度（3） | `neon_rot_ldr_at_top_str4`、`..._str4_checkall`、`..._ldr5` | 第 4 store / 第 5 ldr 后归零 |
| arm0102 其余（6） | `arm0102_fma_f64`、`swizzle`、`ins_ext`、`kreg_mask`、`kreg_mask_vceq`、`kreg_mask_dump` | — |
| 短窗压力（3） | `stress_sub`、`stress_xor`、`stress_fma` | 单指令压力 5min 全 0（短窗不反证） |
| cache 变体（2） | `cachebounce_sdc`、`cache_stress_civac` | 30min 各全 0（2026-08-31 战役） |

\* `movmskpspd` 与 `zero_control_vec_*_jit`×3 在 aarch64 上架构性不可用（x86 概念），非机制灭活，同时见 §三特殊项。

### 2.2 状态未入账（无战役记录，13 个）——从未在 SDC 战役中运行

`adcx`、`adcxlong`、`adcx_odox_interleaved`（tests/cpu/arithmetic/）
`adcx_arm`、`bigint_mulx_arm`、`cbw_arm`、`fisttp_arm`（tests/cpu/arithmetic_arm/）
`neon_rot_ldr_at_top_priv`、`neon_rot_ldr_at_top_dump`（冻结时代产物）
`eigen_svd_jacobi`（仅 5min no-discrimination 一轮）
`movbe_str_multiload`、`movbe_l1d_variants`（仅"30min 未触发"文字，无 yaml）
`core179_kernel_sdc_repro`（内核态复现器混合负载，无 fail 记录）

---

## 三、特殊排除项（8 项）——不参与两级分类

| 项 | 原因 |
|---|---|
| `movbe_dump_probe_c` | 390 fail/5min 但为多核 FP 一致性风暴，fail 非锁 179，与 179 缺陷不同源 |
| `neon_rot_ldr_at_top`（原版） | ⚠️ **禁跑**——全核下整机硬冻结 2/2（09-04），非 SDC 用例 |
| `sched_storm_baseline/futex/thread/hybrid` | 调度路径刺激器，设计上不产生 result:fail |
| `eigen_sparse` | 15.5s 秒退，触发能力未定 |
| `eigen_gemm_double_ab_split` | 探针损坏（380× 慢），0 不可读，触发能力未定 |

**作废数据注记**：09-10 晚 v2 饱和战役四项（lsqfill_v2/rfport_v2/rowmajor+邻核storm/rowmajor_ctl）因亲和性掩码事故整体作废（179 在线但从未运行测试线程），既非有效也非对照；SiliFuzz 污染窗口（2026-08-26 15:44 ~ 08-28）期间数据一律不引用。

---

## 四、使用指引（现行口径）

- **日常 SDC 门**：`movbe`（或 P0 任一）
- **诊断主力**：`mrn_reloaded_2src_alu` + K-cells 7 用例（P2）
- **签名采集**：`neon_rot_ldr_at_top_rowmajor_dualcmp` + `..._rowmajor_gps`
- **2026-10-24/25 新增口径**：CPU4-only 48 核（144-191）配置下 `neon_rot_ldr_at_top_rowmajor` 14.9/min 持平全机满载——**采样本只需本插槽负载**，风险最低
- 复跑前必查：arm0102 四用例须先注册 meson；`neon_rot_ldr_at_top` 原版禁跑；率比较须 ≥1h 窗口或多窗口交替（爆发/潜伏周期主导单窗率）
