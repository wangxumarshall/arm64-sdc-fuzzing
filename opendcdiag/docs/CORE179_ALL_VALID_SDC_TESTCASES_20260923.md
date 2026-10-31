# CORE179 全部有效 SDC 测试用例总登记册（2026-09-23）

依据：docs/ 全部 55 篇 CORE179 文档通读 + `builddir/`/`movbe_log/` 日志档案交叉核验
（cpu-mask X 位解码 + `thread:` 字段 + `exit:` 行三法交叉）。
本册为完整总登记册；`docs/CORE179_VALID_SDC_TESTCASES_20260914.md`（K-cells 7 用例）
是本册第四代的子集，非全集。

## 一、判定标准与口径

**有效用例判定**：触发过 SDC——出现唯一 `result: fail` 块（非 grep miscompare 双计），
fail 锁定逻辑核 179（cpu-mask 192 位中唯一 X 位 / `thread: 179`），其余 191 核零错误，
且有可追溯证据（docs 记载或幸存日志/yaml）。

**运行口径**（各代通用）：`taskset -c 0-191 ./builddir/opendcdiag -e <测试名> -n 192 -T 30m`，
全核 192 含 179、auto seed（永不固定）、日志落盘。fail 数 = 唯一 fail 块数
（22tests movbe 69 含 retry → 57 唯一；mrn_rmw 11 → 6）。

**数据可信度分层**：
- ⚠️ **SiliFuzz 污染窗口 2026-08-26 15:44 ~ 8-28**：期间数据作废不引用（8-27 movbe nop 批全 0-fail 作废）；
  V4.5 两轮 30min（movbe_l2/mrn_rmw_l1d，8-26 15:36–16:36）与窗口重叠，但均有 8-25 / 8-31 干净复测背书
- **V5 统计误判**（V6 修正）：movbe/movbe_dump/movbe_l1d 曾被误报"5min 0 fail"（实为 9~15 fail）；
  mrn_rmw 系被双计 2×；本册一律采用 V6 8-28 干净复测口径
- **V1 固定 LCG seed 方法错误**（V2 §8）："H PASS" 系 seed 运气；F/G1/G2 的 0/5 为固定 seed 污染
- **无 yaml 不参与结论**（L1D_EXCLUSION 附录）：movbe_l1d "17/3min"（V5 文字）、movbe_l2 0/30min（V4.5）、
  mrn_rmw_fwd 早期数字仅报告文字，须以 V6 8-28 / 8-30/31 yaml 复测为准
- **0\* 弱证据**：8-31 仅 grep 摘要未经三法交叉的 0-fail（mrn_rmw_l1d、mrn_rmw_diff_nop64）

## 二、总览

**57 个唯一注册测试名**，按五代（家族谱系）分组：

| 代 | 时期 | 家族 | 数量 |
|---|---|---|---|
| 一 | 2026-08 | movbe / mrn_rmw / eigen / memcpy | 25 |
| 二 | 09-01~09-04 | 正向构造 + 跨骨架移植 + AGU + NEON 早期 | 12 |
| 三 | 09-05~09-12 | neon_rot_ldr_at_top 家族 + arm0102 | 14 |
| 四 | 09-13~09-15 | K-cells 官方 7 用例（6 新变体 + 基线=第三代 rowmajor） | 6 新 |
| 五 | 09-16~09-17 | 签名采集（dualcmp / str3_checkall，已归入第三代家族表） | — |

## 三、第一代：movbe / mrn_rmw / eigen / memcpy（2026-08）

### 3.1 movbe 系（7 个）

| # | 测试名 | 源文件 | 触发证据（fail/时长/日期） | 核验证 | 性质 |
|---|---|---|---|---|---|
| 1 | `movbe` | `tests/cpu/misc/movbe.cpp` | 15/5min（~3.0/min，V6 8-28）；22/15min；**57 唯一块/30min**（22tests 08-31~09-01） | 全 thread 179 | 稳态·日常 SDC 门首选 |
| 2 | `movbe_dump` | `tests/cpu/misc/movbe_dump.cpp` | 10/5min（V6 8-28）；32/5min（12.7.1 8-25 baseline）；42 样本/5×5min（09-01，翻转 11–25 位均 16.8 位无固定坏位） | core 179 only（V1 起） | 稳态 ~2/min |
| 3 | `movbe_l1d` | `tests/cpu/misc/movbe_l1d_vs_l2.cpp` | 9/5min（V6 8-28 干净复测）；二进制 patch 变体 rev/mul/add/nop 各 2–3 fail/~3min 全 179（V4，非指令特异证据） | X 位=179 | 稳态 ~1.8/min |
| 4 | `movbe_dump_golden` | `tests/cpu/misc/movbe_dump_golden.cpp` | 45/30min（yaml 071555，08-30/31 批最高） | 179 | 稳态 |
| 5 | `movbe_dump_probe_xn` | `tests/cpu/misc/movbe_dump_probe_xn.cpp` | 1/30min（yaml 114537） | 179 | 低频 |
| 6 | `movbe_dump_probe_h` | `tests/cpu/misc/movbe_dump_probe_h.cpp` | V2/V3 auto-seed 1/10 seed 触发；V6 8-28 0/5min | 触发时 179 | 间歇（1/10 seed） |
| 7 | `movbe_dump_probe_x` | `tests/cpu/misc/movbe_dump_probe_x.cpp` | V2/V3 auto-seed 1/5 seed 触发；V6 0/5min | 触发时 179 | 间歇（1/5 seed） |

⚠️ **排除**：`movbe_dump_probe_c`（390 fail/5min）——多核 FP 一致性风暴机制，fail 非单核 179，
与 179 SDC 非同一缺陷（V1 §4.1、V6 §V6.6"不推荐作检测器"）。

### 3.2 mrn_rmw 系（8 个）

| # | 测试名 | 源文件 | 触发证据 | 核验证 | 性质 |
|---|---|---|---|---|---|
| 8 | `mrn_rmw` | `tests/cpu/misc/mrn_rmw.cpp` | 2/5min（V6 8-28）；1/15min（V3）；**6 唯一块/30min**（22tests） | 全 thread 179 | 稳态 ~0.2–0.4/min |
| 9 | `mrn_rmw_dump` | `tests/cpu/misc/mrn_rmw_dump.cpp` | 2/5min（V6）；1/15min（V3，xor 35/64 位最高密度）；2/60min（8-30/31，recompute 3 样本全 `[ALU-COMPUTE-WRONG]`） | 179 | 稳态 |
| 10 | `mrn_rmw_fwd` | `tests/cpu/misc/mrn_rmw_fwd_vs_l1d.cpp` | 18/10min（8-25）；1/5min（8-28）；1/15min（V6.2.3 干净复测 0.067/min） | 179 | 稳态 |
| 11 | `mrn_rmw_diff` | `tests/cpu/misc/mrn_rmw_fwd_vs_diff.cpp`（V3 记 fwd_vs_l1d.cpp，两文档有出入） | 10/10min（8-25）；8/30min（8-30/31，8 条 100% ldr(tempB) 读错）；4/5min（12.7.1） | 179 | 稳态 |
| 12 | `mrn_rmw_diff_64k` | `tests/cpu/misc/mrn_rmw_diff_footprint.cpp` | 19/~8min（yaml 164554，被重启截断，瞬时 2.375/min） | 179 | 稳态 |
| 13 | `mrn_rmw_nop` | `tests/cpu/misc/mrn_rmw_timing_probe.cpp` | 6/10min（8-25）；11/30min（8-30/31）；2/30min（8-28 复测 0.067/min） | 179 | 稳态低频 |
| 14 | `mrn_rmw_nop1` | 同上 | 1/10min（8-25）；1/30min（8-30/31）；2/30min（8-28） | 179 | 稳态低频 |
| 15 | `mrn_rmw_nop4` | 同上 | 1/30min（8-30/31）；1/30min（8-28 复测 0.033/min） | 179 | 稳态低频 |

nop 曲线（V6.2.3 干净复测）：0/1/2 nop 持平 ~0.067/min → 4 nop 减半 → ≥8 nop 归零（单调，推翻 V5 非单调）。

### 3.3 eigen 系（9 个，全部低率/间歇，需长跑）

| # | 测试名 | 源文件 | 触发证据 | 性质 |
|---|---|---|---|---|
| 16 | `eigen_gemm_float_dynamic_square` | `tests/cpu/eigen_gemm/gemm_float_dynamic_square.cpp` | 11 样本/30min（8-12 历史，中位 12 位，尾数 85%）；1/15min（V3）；6/5min（12.7.1）→ L1D 禁用 0 | 稳态低频 |
| 17 | `eigen_gemm_float_dynamic_square_dump` | `.../gemm_float_dynamic_square_dump.cpp` | 1/15min（V3，[0,20]，xor 10/32 位） | 稳态低频 |
| 18 | `eigen_gemm_double_dynamic_square` | `.../gemm_double_dynamic_square.cpp` | 11 样本/30min（8-12，中位 28 位，尾数 93% 最密）；1/15min（V3）；3/5min（12.7.1） | 稳态低频 |
| 19 | `eigen_gemm_double_dynamic_square_dump` | `.../gemm_double_dynamic_square_dump.cpp` | 1/15min（V3，[0,92]，21/64 位） | 稳态低频 |
| 20 | `eigen_gemm_cdouble_dynamic_square` | `.../gemm_cdouble_dynamic_square.cpp` | 历史 1（28 位）；V3 §8.7 复测 1/15min（ttf 94.9s，24 位） | 低率/间歇 |
| 21 | `eigen_gemm_double14` | `.../double14.cpp` | 44 fail（8-12）；complement campaign 3/5 runs 触发（最频繁 double 路径；isApprox 容差先触发故无 bit 数据） | 稳态（5min 窗口常漏） |
| 22 | `eigen_svd` | `tests/cpu/eigen_svd/svd.cpp` | 11/30min（8-12，5/11 恰 1 位——SVD 单位翻转签名）；re-test 0/15min（窗口未中） | 低率 |
| 23 | `eigen_svd_double2` | `tests/cpu/eigen_svd/svd_double.cpp`（注册名 double2） | 1/15min（v3 re-test，mask=0x1 恰 1 位，V 阵 1-ULP） | 低率 |
| 24 | `eigen_svd_cdouble_noavx512` | `tests/cpu/eigen_svd/svd_cdouble_noavx512.cpp` | 历史 1（22 位）；re-test 0/15min | 最低率 |

eigen 位翻转统计（BITFLIP §3.3）：85–93% 集中在 IEEE-754 尾数、符号位免疫；SVD 路径单位翻转、GEMM 路径 1–24 位多位。

### 3.4 memcpy（1 个）

| # | 测试名 | 源文件 | 触发证据 | 性质 |
|---|---|---|---|---|
| 25 | `memcpy1` | `tests/cpu/memory/memcpy1.cpp` | 6 fail（8-15/16 全套件并发跑法，全 179）；单测复测 0（5min 固定 seed + 10min 11180-seed）| **仅全套件并发压力下触发**（判别变量=并发） |

## 四、第二代：正向构造 / 跨骨架移植 / AGU / NEON 早期（09-01~09-04）

| # | 测试名 | 源文件 | 触发证据 | 核验证 | 性质 |
|---|---|---|---|---|---|
| 26 | `mrn_nuke_2src_alu` | `tests/cpu/misc/mrn_nuke_2src_alu.cpp` | 14 fail（30min 口径 ~0.47/min；ttf 全程分布非爆发；两文档时长记载不一，以日志名 30min 为准） | 全 179 | 稳态 |
| 27 | `mem_disambig_alu` | `tests/cpu/memory/mem_disambig_alu.cpp` | 1/36min（5539 loops；确定性核实：排除 179 同 seed → 0） | 179 | 弱/间歇 |
| 28 | `mrn_nuke_dense` | `tests/cpu/misc/mrn_nuke_dense.cpp` | 1/36min（1775 loops） | 179 | 弱 |
| 29 | `mrn_pairs_2src_alu` | `tests/cpu/misc/mrn_pairs_2src_alu.cpp` | **46/36min**（~1.28/min，46 独立 seed，首失败均值 331s；确定性核实 0） | 全 179 | 稳态 |
| 30 | `mrn_reloaded_2src_alu` | `tests/cpu/misc/mrn_reloaded_2src_alu.cpp` | **126/36min（~3.5/min，全史最高率触发器**，首失败均值 15.3s；确定性核实 0） | 全 179 | 稳态 |
| 31 | `mrn_nuke_3src_alu` | `tests/cpu/misc/mrn_nuke_3src_alu.cpp` | 10/36min（9 独立 seed） | 全 179 | 稳态 |
| 32 | `mrn_nuke_4src_alu` | `tests/cpu/misc/mrn_nuke_4src_alu.cpp` | 4/36min | 全 179 | 稳态 |
| 33 | `agu_stress_2src` | `tests/cpu/misc/agu_stress_2src.cpp` | 19/30min（ttf 22–752s 全程持续） | **19/19 thread 逐条验证** | 稳态 |
| 34 | `agu_stress_store_only` | `tests/cpu/misc/agu_stress_store_only.cpp` | 1/30min（ttf 32.5s，无任何 reload 仍触发；需 1–2h 复跑确认） | 179 | 单样本 |
| 35 | `neon_rot_2src` | `tests/cpu/misc/neon_rot_2src.cpp` | 33/30min（09-03）+ 复跑 26（~1.1/min，标量同构 1.7×） | 全 thread 179 两轮 | 稳态可复现 |
| 36 | `neon_rot_store_only` | `tests/cpu/misc/neon_rot_store_only.cpp` | 14/30min（双 str 无 reload） | 全 179 | 存在性证明（机制归因经评审作废） |
| 37 | `neon_rot_u8x16` | `tests/cpu/misc/neon_rot_u8x16.cpp` | 2/30min（16×8b lane 塌缩 15×） | 全 179 | 弱 |

源 load 梯度（SRC_LOAD_GRADIENT）：1 源=0 → 2 源=14 → 3 源=10 → 4 源=4（2 源峰值，非单调）。

## 五、第三代：neon_rot_ldr_at_top 家族 + arm0102（09-05~09-12）

| # | 测试名 | 源文件 | 触发证据 | 性质 |
|---|---|---|---|---|
| 38 | `neon_rot_ldr_at_top_rowmajor` | `tests/cpu/misc/neon_rot_ldr_at_top_rowmajor.cpp` | 历轮 309（09-08）/276/244/149（09-09）/271/216（09-10）/320（09-11）/58（09-13）/18（09-14）/17（09-16），均值 ~246（≈8.2/min，**最高率稳态**）；09-11 温度战役另录 38/25min 高温 + 353/5×5min 低温 | 稳态（1019/1019 全 179） |
| 39 | `neon_rot_ldr_at_top_sub` | `.../neon_rot_ldr_at_top_sub.cpp` | 122/90/116（09-09 三轮）+ 138（09-08） | 稳态（全 179） |
| 40 | `neon_rot_ldr_at_top_rowmajor_dump` | `.../neon_rot_ldr_at_top_rowmajor_dump.cpp` | 7/12/3（09-09，dump 冷分支抑制 ~30×） | 稳态低率 |
| 41 | `neon_rot_ldr_at_top_mla` | `.../neon_rot_ldr_at_top_mla.cpp` | 89/30min（09-08，89/89 X=179 日志核验） | 单轮 |
| 42 | `neon_rot_ldr_at_top_offdiag` | `.../neon_rot_ldr_at_top_offdiag.cpp` | 27/30min（09-08，27/27 X=179） | 单轮 |
| 43 | `neon_rot_ldr_at_top_str3` | `.../neon_rot_ldr_at_top_str3.cpp` | 133（09-11）/164（09-12）/51+49（09-17）四轮跨 6 天全 179 | 稳态 |
| 44 | `neon_rot_ldr_at_top_ldr4` | `.../neon_rot_ldr_at_top_ldr4.cpp` | 29/24.9min（09-12，被第 11 次 179 panic 截断；率约为父版 1/4–1/8） | 单轮截断 |
| 45 | `neon_rot_ldr_at_top_str3_checkall` | `.../neon_rot_ldr_at_top_rowmajor_str3_checkall.cpp` | 1/30min（09-17 唯一轮，ttf 382s，thread 179；阶段 1 干净） | 低率待复跑 |
| 46 | `neon_rot_ldr_at_top_rowmajor_gps` | `.../neon_rot_ldr_at_top_rowmajor_gps.cpp` | 87/30min（09-13 P0′ B 轨，87 dump 1:1 落盘；87/87 三方互证全 179） | 稳态 |
| 47 | `neon_rot_ldr_at_top_rowmajor_dualcmp` | `.../neon_rot_ldr_at_top_rowmajor_dualcmp.cpp` | 12+12 两轮（09-16）/33 错误元素 100% 可寻回（BODY 15 例错地址读 + HEAD 9 例 16B 错位窗） | 稳态（24/24 全 179） |
| 48 | `arm0102_kreg_select` | `tests/cpu/arm-0102/arm0102_kreg_select.cpp` | 40/30min（09-08，40/40 X=179） | ⚠️ **当前未注册 meson** |
| 49 | `arm0102_kreg_not` | `tests/cpu/arm-0102/arm0102_kreg_not.cpp` | 6/30min（6/6 X=179） | 同上 |
| 50 | `arm0102_fma_f32` | `tests/cpu/arm-0102/arm0102_fma_f32.cpp` | 1/30min（1/1 X=179） | 同上 |
| 51 | `arm0102_kreg_logic` | `tests/cpu/arm-0102/arm0102_kreg_logic.cpp` | 1/30min（1/1 X=179） | 同上 |

⚠️ arm0102 四用例：源码在 `tests/cpu/arm-0102/`（10 个文件），09-08 战役日志有效，
但当前未挂入 `tests/cpu/meson.build`——复跑前须先重新注册。

## 六、第四代：K-cells 官方 7 用例（09-13~09-15）

官方登记册 `docs/CORE179_VALID_SDC_TESTCASES_20260914.md`（含基线 = 第三代 #38）：

| # | 测试名 | 源文件 | 09-13 夜 | 09-14 逆序复跑 | 性质 |
|---|---|---|---|---|---|
| 52 | `..._k5far` | `.../neon_rot_ldr_at_top_rowmajor_k5far.cpp` | 37 | 16 | 稳态 |
| 53 | `..._k5inter_rand` | `.../neon_rot_ldr_at_top_rowmajor_k5inter_rand.cpp` | 72 | 50 | 稳态 |
| 54 | `..._k7p_rand` | `.../neon_rot_ldr_at_top_rowmajor_k7pattern.cpp` | 78（首晚全场最高） | 34 | 稳态 |
| 55 | `..._k7p_one` | 同上（枚举区分） | 42 | 8 | 稳态 |
| 56 | `..._k7p_hiham` | 同上 | 44 | 9 | 稳态 |
| 57 | `..._k3res` | `.../neon_rot_ldr_at_top_rowmajor_k3res.cpp` | 58（补跑完整轮；114/15min 为 panic 截断突发期不计） | 41 | 稳态 |

7/7 两晚全部复现、fail 全 179；合计 389→176（0.45× 同向塌缩，成因未决——顺序与夜级状态混叠，
跨日率差异不做因果解读）。共享骨架：顶部第 3 死 ldr + 双源 load + i%4 轮换 vALU（v0.2d）+ 背靠背双 str + 冷分支 memcmp。

## 七、稳态检测器选型（现行推荐）

**早期口径（V6 §V6.6，08-28 干净复测）**：
- 日常 SDC 门（高频）：`movbe`（~3/min）
- 备选高频：`movbe_dump` / `movbe_l1d`（~2/min、~1.8/min）
- 中频验证：`mrn_rmw` / `mrn_rmw_dump` / `mrn_rmw_fwd`（~0.2–0.4/min）
- 间歇探测（需 30min+/多 seed）：`movbe_l1d_v_rev` / `probe_h` / `probe_x` / `probe_e`

**现行口径（09-14 后）**：K-cells 7 用例（~1–2 fail/min 量级，两晚 100% 复现）+
`mrn_reloaded_2src_alu`（历史最高率 3.5/min）作为诊断主力；
`neon_rot_ldr_at_top_rowmajor_dualcmp`（09-16）为签名采集专用。

## 八、0-fail 灭活对照附录（反面证据，非有效用例）

**触发配方必要条件侧写**（每一条 0-fail 都是一个必要条件的证据）：

| 家族 | 0-fail 用例 | 证明的必要条件 |
|---|---|---|
| movbe probe | `probe_a`（去 store）、`probe_b`（16nop 拉时序）、`probe_d`（固定地址）、`probe_e`（远端 NUMA） | store 必要 / 紧时序必要 / 地址推进 / 同 LLC 域 |
| movbe | `movbe_l1d_v_rev`（寻址模式级敏感）、`movbe_l2`（8-31 三方法交叉 30min） | 寻址模式 / evict 路径不触发 |
| mrn_rmw | `nop8`（0/30min）、`nop16`（0/1h）、`nop64`、`mrn_rmw_l1d`（civac 逐出）、`mrn_rmw_diff_nop64`（0*） | 时序窗口 ≥8cyc 关闭 / 逐出路径 |
| 22tests 其余 21 个 | `mrn_nuke`（与 mrn_rmw 微操作字节同构却不触发——关键反例）、`mrn_pairs`、`mrn_reloaded`、`mem_disambiguation`、`partial_store_forwarding`、`part_store_fwd_jit`、`atomic_seq_cst`、`mfence`/`mfence_pure`、`mite`、`mrn_flags`（纯 ALU 有力反证）、`modified_sort`、`move_elimination*_jit`×3、`movdq2q`、`movq2dq`、`movmskpspd`、`zero_control_vec_*_jit`×3（ARM64 不可用） | 1 源 + 原值 forwarding 不触发 / 纯 ALU 不触发 |
| 构造变体 | `mrn_nuke_recross`、`mrn_pairs_2src_alu_keep8`（松时序）、`mrn_nuke_2src_add/sub/eor/and`（单指令各 36min）、`probe_asm_fwd` v1/v2 | 同址重读移植失败 / 松时序灭活 / **轮换 ALU 必要** / 单加 ALU 仍 1 源不触发 |
| AGU | `agu_stress_1src`、`agu_stress_unaligned` | 1 源不触发 / 寻址改动→布局灭活 |
| NEON 早期 | `neon_rot_1src`、`neon_rot_u32x4`、`neon_rot_fwd_probe` | 1 源不触发 / 4×32b lane=0 / 布局敏感 |
| K-cells 四零格 | `k2pureload`（零 store）、`k4gap`/`k4bgap`（8nop 双向拆）、`k7p_zero`（全 0 数据） | store+load 缺一不可 / 紧时序双向必要 / 数据激活面 |
| P0 | `rowmajor_scalar64`（0/30min，1610 迭代） | 标量 64b 直译归零（lane 绑定） |
| 单元隔离 6 变体 | `tlbstress`/`lsqfill`/`rfport`/`robfill`/`robfill_np`/`prefetch`（各两轮 30min） | 六单元隔离均不触发（tlbstress/prefetch 压力确凿生效、归因力强；lsqfill/rfport/robfill 未饱和、归因力弱） |
| str/ldr 梯度 | `str4`、`str4_checkall`（两轮）、`ldr5`（0） | 第 4 store / 第 5 ldr 后归零 |
| arm0102 其余 6 | `fma_f64`/`swizzle`/`ins_ext`/`kreg_mask`/`kreg_mask_vceq`/`kreg_mask_dump` | — |
| L1D-disable 轮 | `fwd`（0×3）、`movbe_dump`/`mrn_rmw_diff`/`eigen_gemm_float/double`/`double14`/`svd_jacobi` 全 0 | L1D 禁用灭活（归因被 §12.9 收窄为 timing-explainable，0-fail 事实有效） |
| eigen 窗口 0 | `cdouble_dump`/`eigen_svd` re-test/`svd_cdouble` re-test/`svd_jacobi`（5min no discrimination） | 低率窗口未中，**非灭活** |
| eigen 未定 | `eigen_sparse`（15.5s 秒退）、`eigen_gemm_double_ab_split`（探针损坏 380× 慢，0 不可读） | 触发能力未定 |
| 短窗不反证 | `stress_sub/xor/fma`（各 5min） | — |

**作废数据（既非有效也非对照）**：09-10 晚 v2 饱和战役四项（lsqfill_v2/rfport_v2/rowmajor+邻核 storm/rowmajor_ctl）
——亲和性掩码事故，179 在线但从未运行测试线程，整体作废；
8-27 movbe nop 批（SiliFuzz 污染）；V5 双计曲线。

## 九、专门排除项（有 fail 但非有效 SDC 用例）

| 项 | 原因 |
|---|---|
| `movbe_dump_probe_c`（390 fail/5min） | 多核 FP 一致性风暴，fail 非锁 179，与 179 缺陷不同源（V1 §4.1、V6 §V6.6） |
| `neon_rot_ldr_at_top`（原版） | 非 SDC 用例——全核下整机硬冻结 2/2（09-04），冻结后未原样重跑 |
| `sched_storm_baseline/futex/thread/hybrid` | 调度路径刺激器（newidle_balance 复现尝试），0 fail，不产生 result:fail |
| `zero_control_vec_sse_jit`、`movmskpspd`（历史全核 fail） | x86 概念在 aarch64 的架构性失败，非硬件 SDC |

## 十、"状态未入账"清单（docs 55 篇零触发记录）

以下测试源文件在 git 中有修改、`tests/cpu/meson.build` 已注册，但**全部 55 篇 docs
无任何触发（或 0-fail）战役记录**——不列入本册有效清单，状态待补测入账：

- `adcx`、`adcxlong`、`adcx_adox_interleaved`（tests/cpu/arithmetic/）
- `adcx_arm`、`bigint_mulx_arm`、`cbw_arm`、`fisttp_arm`（tests/cpu/arithmetic_arm/）
- `neon_rot_ldr_at_top_priv`（09-07 冻结矩阵判别变体，无任何运行记录）
- `neon_rot_ldr_at_top_dump`（冻结时代产物，无 30min 战役日志存档）
- `eigen_svd_jacobi`（12.7.1 一轮 5min no discrimination，无独立战役）
- `movbe_str_multiload`、`movbe_l1d_variants`（阶段 2 六变体仅确认"30min 未触发"无 yaml）

## 十一、出处索引

- 第一代：`MOVBE_SDC_CORE179_LOCALIZATION_REPORT` V1–V6（尤其 V6 §V6.2/§V6.6）、
  `CORE179_SDC_TEST_VARIANT_PATH_FUNCTIONS §五`（8-30/31 批 88 fail，yaml command-line/mtime 双校验）、
  `CORE179_22_TESTS_LOAD_AND_INSTRUCTION_ANALYSIS §四`、`CORE179_SDC_TRIGGER_INPUT_VALUES`、
  `CORE179_SDC_TRIGGER_RESEARCH_REPORT §1`、`CORE179_SDC_CAMPAIGN_INTERRUPT_RECOVERY §2.3`
- 第二代：`CORE179_TRIGGER_VARIANT_CONSTRUCTION_RESULT`、`CORE179_2SRC_ALU_PORT_RESULT`、
  `CORE179_SRC_LOAD_GRADIENT_RESULT`、`CORE179_ALU_INSTRUCTION_COMPARE_RESULT`、
  `CORE179_AGU_STRESS_RESULT`、`CORE179_ALU_AGU_SIMD_EXPERIMENTS`
- 第三代：`CORE179_NEON_ROT_LDR_AT_TOP_STABILITY_CAMPAIGN_20260909`、
  `CORE179_UNIT_CAMPAIGNS_CONSOLIDATED_20260911`、`CORE179_PANIC_ROOT_CAUSE_SCHEDULER_FINDING_20260912 §七`（ldr4）、
  日志档案 `builddir/campaign_20260908/`（mla/offdiag/sub/arm0102）、
  `builddir/campaign_20260911_str_gradient/`、`campaign_20260912_str3_retest/`、
  `movbe_log/str3_str4/`、`movbe_log/str3_checkall/`（09-17 轮）
- 第四代：`CORE179_READPATH_K_CELLS_BATCH2_RESULTS_20260914`、`CORE179_VALID_SDC_TESTCASES_20260914`、
  `CORE179_VALID7_RERUN_REVERSED_ORDER_20260915`
- 第五代（签名采集）：`CORE179_READPATH_P0_GPS_FIRST_SIGNATURES_20260913`（gps 87）、
  `CORE179_DUALCMP_33ERR_FULL_CLASSIFICATION_20260916`（dualcmp）、
  `CORE179_FORWARDING_PRACTICE_AND_EPISTEMOLOGY_20260915`
- 综述：`20260917meeting.md`（§0 事实基线"数千样本 100% 落 179"、§2 五步演化、§3.5 七用例两晚表）
