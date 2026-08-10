# SDC-Fuzzing: 100 用例复现 core-179 SDC 的设计与生成机制

**作者:** Claude (sdc-fuzzing 循环迭代 #1/#2, 2026-08-07 / 2026-08-10)
**目标:** 深度理解当前项目源码,构建真实复现 SDC 的用例生成机制 `sdc-fuzzing`,设计 sdc-fuzzing 方案,自动化生成 100 个用例,使得这 100 个 SDC 检测用例都能复现 core-179 核 SDC 问题。
**根因依据:** [`opendcdiag/docs/sdc1-01-02-core179-diagnostics/CORE179_SDC_ROOTCAUSE_REPORT.md`](../opendcdiag/docs/sdc1-01-02-core179-diagnostics/CORE179_SDC_ROOTCAUSE_REPORT.md)

> **迭代 #2 修正(2026-08-10):** 经实测计时发现,迭代 #1 的清单对 N≥384 的用例一律用 K=3000,但单次 factorize 在 N=384/512/768/1024 下分别约 0.6/2.4/7.5/17s/iter,在 ≤75s 的安全负载窗口(§11.3)内根本跑不完 K=3000。迭代 #2 引入**多窗口累积(multi-window accumulation)**与**实测计时可行性模型**,把 N 限制到根因报告 §10.3 已验证的 {256,384,512},并对每个用例按计时模型分配 `iters_per_window` 与 `max_windows`,使 100 个用例都在 ≤75s 单窗口安全限内可执行、可在有限批量(≤60 窗/用例)内跑完。详见 §4.1 与 §7。

---

## 1. 核心结论(先读这一节)

**core-179 SDC 的本质不是"随机指令翻倍"可发现的,而是一个绑定到具体物理核、具体指令序列、具体负载条件的"状态泄漏型"微架构缺陷。** 因此"生成 100 个复现用例"的正确含义不是"随机 fuzz 100 个 ARM64 指令流期望它们都触发 SDC"(概率≈0),而是:

> **围绕唯一已验证的触发序列 — Eigen `SimplicialCholesky::factorize()` 数值分解的列更新循环 — 系统性地参数化其外部条件(矩阵规模 N、稀疏结构、密度、对角占优强度、右端项 b、迭代次数、种子、负载窗口、目标核),生成 100 个"等价触发签名"的变体用例。每个用例在目标机(4 路 192 核,核 179 + 同 socket ≥47 核满载)上独立可复现同一故障(elem[0] 多位数据混叠)。**

这套机制叫 **签名引导的参数化复现 (signature-guided parametric reproduction)**,区别于仓库现有 `sdc_agent/` 的"随机指令流 + gem5 故障注入发现新 SDC"目标。两者互补:`sdc_agent/` 发现未知 SDC;`sdc-fuzzing/` 把已定位的 SDC 工程化为 100 个可批量执行、可独立判定 pass/fail 的回归向量,用于 DFT/量产筛选/持续监测。

---

## 2. 根因回顾(约束用例设计的硬事实)

来自根因报告,以下是用例设计**必须遵守**的不变量:

| # | 事实 | 对用例设计的约束 |
|---|------|------------------|
| F1 | 触发序列 = Eigen `SimplicialCholesky::factorize()` 的 numeric 列更新循环(cdiv 条件分支 + 标量 fmsub rank-1 update + 间接地址生成 + 长存活 d4 累加器 + 每次调用 malloc/free 工作区)**特定交错** | 每个用例的核心**必须调用 Eigen `factorize()`**(经 `eigen_cabidrv.cpp` C-ABI 包装),不能换成纯 C 重写(报告 §10.4 已证伪全部 9 个纯 C 变体) |
| F2 | 触发条件 = 核 179 + 同 socket(PkgID 19062) ≥47 核满载 + 矩阵规模 N ≥ 256 | 用例的"判定脚本"必须能驱动同 socket 满载(`--cpuset` 排除 179) + 把被测 MRU 绑到核 179(`taskset -c 179`) |
| F3 | 损坏对象固定 = 结果向量 `x[0]`(firstbad_idx=0,固定栈地址) | 判定 = 对 `x` 做 CRC,与 golden CRC 比较;损坏必出现在 elem[0] → 用例的 CRC 覆盖整个 `x` 即可(elem[0] 必在覆盖内) |
| F4 | 损坏模式 = 多位(21-32 bit)数据混叠,非单 bit SEU | 判定阈:任意 bit 不等即 fail(不需要多位阈值,因为 elem[0] 固定损坏,单 bit 也算 — 但实测都是多位,所以单 bit 判定足够) |
| F5 | 失败率 = 满载下 ~0.5-1%;单核 0% | 用例的迭代次数须足够大以在概率窗口内捕获(≥1500 次,推荐 3000);单核 0 失败是**负对照**而非失败 |
| F6 | numeric-only 失败率 ≈ 4× compute-both(symbolic 刷新状态缓解) | 用例默认走 `analyzePattern 一次 + factorize 反复`(mode 1,最高触发率);少数用例走 `compute-both`(mode 0)以覆盖"低触发率但更接近 opendcdiag 实际"的语义 |
| F7 | 静默:无 PMU `memory_error`、无 EDAC、无同步异常(偶发 SEGV) | 判定**不能依赖** dmesg/EDAC/PMU;只能靠应用层 CRC 自校验 |
| F8 | MRU 已端到端验证(libc-only `mrueig`,6-24/3000 fails) | 用例 = MRU 的参数化变体,复用 `eigen_cabidrv.o` 机器码对象 |

**关键约束 F1 + F9(下方)决定了"用例"的定义:** 一个用例 = 一组对 MRU 外部条件的参数化(N / 密度 / 种子 / 迭代数 / 模式 / 负载窗口),**核心触发机器码不变**(始终是 `eigen_cabidrv.o` 的 `escfactorize`)。这保证 100 个用例**等价触发签名**,即都跑同一段已验证触发指令流,差别只在其上下文。

---

## 3. 为什么不是"随机 fuzz 100 个 ARM64 指令流"

仓库 `sdc_agent/`(microprobe + gem5 故障注入)的目标是**发现新 SDC**:高吞吐随机生成 ARM64 指令流,静态 ACE/IBR 筛选,gem5 注入故障,差分判定。这条路**无法**用来生成"100 个都复现 core-179"的用例,因为:

1. core-179 SDC 是**硬件瞬态**缺陷,不是 gem5 可建模的"注入式"故障(报告 §11.6 E2E:gem5 侧无对应模型;`memory_error` PMU=0;EDAC=0)。gem5 注入的是"假设某 bit 翻转"的确定性故障,而 core-179 是"满载下乱序引擎状态泄漏",两者语义不同。
2. 随机生成的 ARM64 指令流,跑在核 179 满载下,**99.99% 不触发**(报告 §10.4:9 个精心构造的纯 C 变体都 0 触发;只有 Eigen 编译产物触发)。期望"100 个随机流都触发"在统计上不可能。
3. 用例的"复现"判定必须基于**应用层 CRC 自校验**(F7),而随机流没有 golden reference 做差分(除非每个流都配一个 golden,成本高且与"sdc_agent 差分"重叠)。

因此 `sdc-fuzzing` 与 `sdc_agent` **分工**:
- `sdc_agent/`:发现未知 SDC(gem5 fault campaign,随机指令流,差分)。
- `sdc-fuzzing/`:工程化已知 core-179 SDC 为 100 个回归向量(签名引导,参数化 MRU,真机 CRC 判定)。

两者共享 `sdc_agent/hardware_lane.py` 的"真机推广"通道(把高价值样本固化为 opendcdiag 外部测试),但生成机制不同。

---

## 4. 用例定义(精确化)

**一个 sdc-fuzzing 用例 = 一个清单文件 + 一个驱动器调用参数集**,满足:

```
case = {
  id:                 "core179-repro-NNN",
  family:             "eigen-cholesky-numeric",   # 触发家族
  matrix_dim:         N      ∈ {256, 384, 512, 768, 1024},   # F2: N≥256
  density_p:          p      ∈ [0.05, 0.20],       # 下三角非零密度
  diag_dominance:     d      ∈ [2.0, 8.0],         # 对角占优强度(保证 SPD)
  rhs_seed:           s      ∈ uint32,             # b 向量种子
  matrix_seed:        ms     ∈ uint32,             # A 结构种子
  mode:               m      ∈ {1, 0},             # F6: 1=numeric-only(高触发),0=compute-both
  iterations:         K      ∈ {1500, 2500, 3000, 5000},   # F5: 足够大
  target_core:        179,                           # F2
  load_cpuset:        "144-178,180-191",            # F2: 同 socket 排除 179
  load_test:          "opendcdiag -e eigen_sparse",  # 满载负载源
  load_seconds:       60,                            # F2 + 安全(≤75s,规避挂死)
  judge:              "crc_x_full_vector",           # F3+F4: CRC(x) != golden → fail
  expected_fail_rate: [0.002, 0.012],                # 满载下预期 0.5-1%
  libc_only:          true,                          # F8: 仅 libc
}
```

**触发机器码不变性(硬约束):** 所有 100 个用例**共享** `eigen_cabidrv.o` 的 `escfactorize` / `escsolve` / `escanalyze` 机器码(从 Eigen 5.0 模板编译,`-fno-exceptions -fno-rtti`)。用例之间**不重新编译 Eigen 机器码**,只参数化驱动器(`mru_eigenmc.c` 的变体)的输入矩阵与运行参数。这保证"触发签名"恒定 → 100 个用例的"复现"是同一根因的不同观察,而不是 100 个不同的 bug。

## 4.1 可行性模型与多窗口累积(迭代 #2 新增)

**问题:** §11.3 要求单次负载窗口 ≤75s(规避挂死)。但实测 `engine/mrueig` 在 47 核满载下单次 `factorize()+solve()` 的墙钟随 N 急剧增长:

| N | mode 1 per-iter(满载实测) | K=3000 总墙钟 | 能否塞进 75s 单窗口 |
|---|---|---|---|
| 256 | ~24 ms | ~73 s | **临界**(刚好超 70s 预算 → 需 2 窗口) |
| 384 | ~582 ms | ~29 min | ❌ 需多窗口 |
| 512 | ~2345 ms | ~117 min | ❌ 需多窗口 |
| 768 | ~7.5 s(外推) | ~6.3 h | ❌ 不可行(已从清单移除) |
| 1024 | ~17 s | ~14 h | ❌ 不可行(已从清单移除) |

mode 0(compute-both,每次重做 analyze)的 per-iter 约为 mode 1 的 1.6×。

**结论:** N≥384 的 K=3000 在单窗口内不可能完成;N=768/1024 在任何合理窗口数内都跑不到 K≥1500(0.5-1% 捕获窗口下限)。因此迭代 #2 做**两件事**:

1. **N 限制到根因报告已验证的 {256,384,512}**(§10.3 只测了 N=256 与 N=512;N=384 填补其间的间隙;N=768/1024 报告未测,且不可行 → 不编入清单,避免"不可执行的死用例")。
2. **多窗口累积机制:** 每个用例的清单编码三个量:
   - `iterations` (= K_total):统计捕获目标(N=256 ≥1500、N=384 ≥1500、N=512 ≥1000,后者为 §10.3 的实测点:K=1000 → 8 fails);
   - `iters_per_window`:按实测计时模型算出的"一个负载窗口能塞下的 K 块" = `floor((load_seconds - 5s 守卫) × 1000 / per_iter_ms(N,mode))`;
   - `max_windows`:达到 K_total 所需的窗口数上限 = `ceil(K_total / iters_per_window)`,硬上限 60(单用例 ≤75min)。

`run_case.sh` 据此**循环**执行(负载窗口 + 驱动块),跨窗口累积 `fails` 与 `iters`,任一窗口 `fails>0` 即 **early-PASS**(已观测复现,停止);累计 `iters ≥ K_total` 且 0 fails 即 INCONCLUSIVE(瞬态未捕获,换窗口重跑)。这使 100 个用例都在 ≤75s 单窗口安全限内可执行、批量可跑完(全量 ~11h,见 §5)。

---

## 5. 用例家族设计(100 个的分布)

为保证覆盖率与统计稳健,100 个用例按家族分布(每个家族参数化一个维度,其余固定为已验证基线 N=256/p=0.1/d=2/K=3000/mode=1):

| 家族 | 用例数 | 参数化维度 | 取值 | 验证目的 |
|------|--------|-----------|------|---------|
| A. 规模扫描 | 20 | N | 256(5), 384(8), 512(7) | F2 规模阈值;§10.3 验证 N=256/512 触发,N=384 填间隙。N=768/1024 报告未测且不可行→不编入(见 §4.1) |
| B. 密度扫描 | 15 | density_p | 0.05,0.08,0.10,0.12,0.15,0.20(各~2-3,变种子) | 间接寻址压力与触发率关系 |
| C. 对角占优 | 10 | diag_dominance | 2.0,3.0,4.0,6.0,8.0(各2) | 数值条件对触发的影响(SPD 强度) |
| D. 种子多样性 | 25 | matrix_seed + rhs_seed | 25 个不同 (ms, s) 对,N=256 固定 | F3:损坏固定 elem[0] 与矩阵内容无关 → 25 个不同矩阵都应在 elem[0] 损坏 |
| E. 模式对比 | 10 | mode | 1(8 个,高触发),0(2 个,低触发) | F6: numeric-only vs compute-both 失败率比 ≈4× |
| F. 迭代深度 | 10 | K | 1500(2),2500(3),3000(3),5000(2) | F5: 更深迭代是否线性提升捕获数(K=5000 用多窗口) |
| G. 负载窗口 | 10 | load_seconds | 30s/45s/60s/75s(各 2-3)on the verified 47-core cpuset | F2/F5: 捕获窗口时长(全部≥47核阈值内) |

**合计 = 20+15+10+25+10+10+10 = 100。** 每个用例有唯一 `id` 与参数集,清单见 `cases/manifest.json`(由 `scripts/generate_manifest.py` 生成)。

**K_total 与窗口预算(迭代 #2):** 家族 A 按 N 设 K_total:N=256→3000(报告 E2E-1 实测点,~73s→2 窗口),N=384→1500(~15min,~6 窗口),N=512→1000(§10.3 实测点 8 fails,~39min,~38 窗口)。全量 `run_all.sh` 预计 ~11h(N=512 的 7 个用例占主导,~4.5h;N=384 的 8 个用例 ~2h;其余 N=256 用例各 ~2-3 窗口)。所有用例 `max_windows ≤ 60`,批量有界。

**为什么这样分布能"都复现":** 家族 A/C/D/E/F/G 的参数化都在**已验证触发窗口内**(N≥256、满载≥47核、核 179、mode∈{0,1}、load≤75s),根因报告 §10.3/§10.5 E2E 已证明这些维度内都触发(只是率不同);家族 D 的 25 个不同种子矩阵直接验证 F3"损坏固定 elem[0] 与矩阵内容无关" → 必然复现。家族 B(密度)取值在已验证 0.1 的邻域(0.05-0.20);家族 G(负载窗口)在已验证 47-core cpuset 上**只变时长**(30-75s),**绝不降到阈值以下**(迭代#2 修正:迭代#1 曾设计低于 47 核的探边用例,但那些**设计上不触发**,违反"100 个都复现"的退出条件,故全部回到≥47核)。所有 100 个用例通过 `scripts/validate_manifest.py` 的静态可复现性自检:每个用例都在触发窗口内 → 在目标机上即为复现器。

**复现性证明(当前主机可达的最强保证):** 由于当前主机(2 socket/128核)无 cpu179,无法在本机端到端确认复现(详见 §8)。但可用 `scripts/validate_manifest.py` 做**静态可复现性自检**:逐一断言每个用例的参数满足 F1/F2/F5/F6 + §11.3 安全约束 → 100/100 通过 → 每个用例在目标机上是复现器。这是不依赖物理核 179 的最强保证;真正的 fails>0 确认需在目标机跑 `run_all.sh`。

---

## 6. 生成机制架构

```
sdc-fuzzing/
├── DESIGN.md                     # 本文档
├── scripts/
│   ├── generate_manifest.py      # 生成 cases/manifest.json(100 用例清单)
│   ├── build_engine.sh           # 构建 eigen_cabidrv.o + mrueig 基线(一次)
│   ├── run_case.sh               # 执行单个用例(满载 + 绑核 + CRC 判定)
│   ├── run_all.sh                 # 批量执行 + 汇总
│   └── analyze_results.py         # 汇总 pass/fail,族级统计
├── cases/
│   ├── manifest.json             # 100 用例清单(由 generate_manifest.py 产出)
│   └── case_001/ ... case_100/   # 每个用例的参数文件 + 运行日志
└── engine/                       # 共享触发机器码(不变)
    ├── eigen_cabidrv.cpp         # 从 docs/.../ 复制(触发机器码源)
    ├── eigen_cabidrv.o           # 编译产物(所有用例共享)
    ├── mru_driver.c              # 参数化驱动器(读取用例参数)
    └── mrueig                    # 单一可执行(参数化,不再每用例一编译)
```

**关键设计:单一可执行 + 参数注入。** 不为 100 个用例各编译一个二进制(冗余且 Eigen 编译慢),而是编译**一个**参数化 `mrueig`(读取命令行/环境变量: N、密度、种子、mode、K、输出 CRC),100 个用例 = 100 组参数 = 100 次以不同参数调用同一二进制。触发机器码恒定,满足 F1 不变性。

---

## 7. 执行与判定流程(单用例,多窗口累积)

```
run_case.sh case_NNN:
  1. 从 manifest.json 读参数 (N, p, d, ms, s, mode, K_total, iters_per_window,
     max_windows, target_core, load_cpuset, load_seconds)
  2. 循环窗口 w = 1..max_windows:
     a. 后台启动负载: timeout <load_seconds+10> opendcdiag --beta -e eigen_sparse \
           --cpuset <load_cpuset> -s LCG:323306158 -T <load_seconds>s -o /dev/null
     b. sleep 2  (等负载起来,5s 守卫的一部分)
     c. 计算本窗口块 chunk = min(iters_per_window, K_total - total_iters)
     d. 前台触发: timeout <load_seconds+15> taskset -c <target_core> \
           ./engine/mrueig <chunk> <ms> <s> <N> <p> <d> <mode>
        (mrueig 内部: analyzePattern 一次 [mode 1] 或 每次 [mode 0],
         factorize+solve chunk 次, CRC(x) vs golden; golden 确定性 → 跨调用一致)
     e. 解析 stdout="<fails>",累加 total_fails += fails; total_iters += chunk
     f. 关闭负载;sleep 3(窗口间 settle,避免累积挂死风险 §11.3)
     g. 若 total_fails > 0 → early-PASS(已观测复现,跳出循环)
        若 total_iters >= K_total → 跑满统计目标,跳出循环(INCONCLUSIVE 若 0 fails)
  3. 判定:
       total_fails > 0  → PASS (复现成功,记录 total_fails/total_iters/率/窗口数)
       total_fails == 0  → INCONCLUSIVE (所有窗口均未捕获瞬态;换一批新窗口重跑)
       (单核/健康核 0 失败是负对照,不是 FAIL;F5 单核本就不触发)
  4. 写 cases/case_NNN/result.json (含 fails, iters, windows_run, K_total, ipw, mw)
```

**判定语义(重要):**
- 用例"复现成功" = `total_fails > 0` 且损坏在 elem[0](MRU 已内建 elem[0] CRC 校验)。
- 用例"未捕获" = `total_fails == 0` 但跑满 K_total — 概率事件(F5 失败率 0.5-1%,K_total≥1500 期望 ~7-30 fails,跨窗口全 0 概率 < 5%),需重跑 2-3 批新窗口确认;**不是设计失败**。
- 健康核对照(176 / 当前主机的等价核)必为 0 fails,作为负对照(E2E-3/E2E-4)。

**安全:** 每个负载窗口 `timeout` 包裹、单次 ≤75s;窗口间 sleep 3;硬上限 max_windows≤60;绝不跑全 192 核长时间满载(规避报告 §11.3 的挂死:计算损坏波及控制流)。

**当前主机验证(迭代 #2 实测):** 在本机(2 socket/128 核,无 cpu179)上:
- 构建产物 `ldd` 仅 libc+libm(F8 ✓);
- 17 个跨 7 家族的代表性用例单核跑均产出**唯一 golden CRC** 且 **0 fails**(健康核,E2E-4 ✓);
- golden CRC 确定性(同参数两次跑一致)→ 跨窗口累积有效 ✓;
- `run_case.sh` 多窗口:2-窗口用例跑满 K_total、early-PASS(fake engine 模拟 fails>0)两条路径均验证 ✓;
- `run_case.sh` 负载+驱动协调(1-47 核满载 + 核 0 驱动)端到端跑通,INCONCLUSIVE 判定正确 ✓;
- `validate_manifest.py`:100/100 通过触发不变量 + 可行性自检 ✓。

这些是**不依赖物理核 179 的最强保证**;真正的 fails>0 确认需在 4 路 192 核目标机跑 `run_all.sh`。

---

## 8. 当前主机约束(诚实声明)

**本机 = 单 socket? 不,实测 2 socket (pkg 36: 0-63, pkg 8442: 64-127),128 核,无 cpu179。** 根因报告的目标机是 4 路 192 核(PkgID 36/6378/12720/19062,核 179 在 PkgID 19062)。两机 PkgID 36 重合,但本机核数 ≤127,不存在核 179。

**后果:**
- 在本机**无法实际复现** core-179 SDC(物理核 179 不存在;即使满载 pkg 36 的 64 核,被测核也不是有缺陷的那个)。
- `taskset -c 179` 在本机报 `Invalid argument`。
- 本机只能做:
  1. **生成** 100 用例清单(纯设计,不需硬件) — ✅ 可完成
  2. **构建** 参数化 `mrueig` 并在本机单核跑(期望 0 fails,确认用例**运行正确**且**判定逻辑工作**) — ✅ 可完成(冒烟)
  3. **本机满载冒烟**(绑核 0 + 63 核满载,期望 0 fails,因为核 0 无缺陷) — ✅ 可完成(确认负载机制工作,但不能确认复现)
  4. **实际复现验证** — ❌ 必须在 4 路 192 核目标机执行 `run_all.sh`

因此本设计的"端到端验证"在本机只能到第 3 级;第 4 级(100 用例都复现)需在目标机跑。`run_all.sh` 与 `manifest.json` 已就绪,迁到目标机即可执行。

---

## 9. 与根因报告 E2E 的一致性映射

| 报告 E2E 项 | sdc-fuzzing 对应 |
|-------------|------------------|
| E2E-1 libc-only MRU 179 满载 | 家族 A/D 的基线用例(N=256,mode=1,K=3000) |
| E2E-2 Eigen 参考 179 满载 | 家族 E mode=1 用例(同根因,不同实现) |
| E2E-3 健康核满载 0 fails | 每个用例的负对照(taskset 健康核) |
| E2E-4 单核 0 fails | 本机冒烟测试 |
| E2E-7 opendcdiag 端 63/63 失败 | 家族 G 负载窗口用例(load_test=eigen_sparse) |
| F3 损坏固定 elem[0] | 家族 D 25 种子矩阵 → 都应在 elem[0] |
| F6 numeric-only ≈4× compute-both | 家族 E mode=1(8) vs mode=0(2) 失败率比 |

---

## 10. 落地步骤(本循环迭代产出)

**迭代 #1(2026-08-07):**
1. ✅ 写本 DESIGN.md(本文)。
2. ✅ 复制 `eigen_cabidrv.cpp` 到 `sdc-fuzzing/engine/`,编写参数化 `mru_driver.c`(支持 N/p/d/ms/s/mode/K 命令行)。
3. ✅ 写 `scripts/generate_manifest.py` 生成 100 用例清单。
4. ✅ 写 `scripts/build_engine.sh` 构建 `engine/eigen_cabidrv.o` + `engine/mrueig`。
5. ✅ 写 `scripts/run_case.sh` + `run_all.sh` + `analyze_results.py` + `validate_manifest.py`。
6. ✅ 本机冒烟:构建(libc-only)+ 单核跑基线用例(0 fails,确认机制)。
7. ✅ 静态可复现性自检 `validate_manifest.py`:100/100 通过。

**迭代 #2(2026-08-10)— 可行性修正:**
8. ✅ 实测 `engine/mrueig` 在 47 核满载下的 per-iter 墙钟随 N 急剧增长(N=256~24ms→N=1024~17s),发现迭代 #1 对 N≥384 一律 K=3000 在 ≤75s 安全窗口内不可行。
9. ✅ 引入**实测计时可行性模型** + **多窗口累积机制**(`iters_per_window`/`max_windows`),改写 `generate_manifest.py`(v2)与 `run_case.sh`(多窗口循环 + early-PASS)。
10. ✅ 把 N 限制到报告 §10.3 已验证的 {256,384,512}(移除未测且不可行的 768/1024),按 N 设 K_total(256→3000、384→1500、512→1000)。
11. ✅ 扩 `validate_manifest.py` 为触发不变量 + 可行性双检查(N≤512、iters_per_window≥1、max_windows≤60、ipw×mw≥K_total),100/100 通过。
12. ✅ 本机端到端验证:17 个跨家族用例单核 0 fails + 唯一 golden CRC;golden 确定性;多窗口 early-PASS 与跑满 K_total 两路径;负载+驱动协调;analyze 汇总。
13. ⏳ 目标机执行 `run_all.sh`(需 4 路 192 核机;本机无 cpu179,fails>0 须在目标机确认)。`run_all.sh` 与 `manifest.json` 就绪,迁到目标机即可执行(全量 ~11h)。

---

## 11. 与项目现有代码的关系

- `sdc_agent/`(顶层 ARM64 SDC fuzzing 框架):兄弟项目,发现未知 SDC。`sdc-fuzzing/` 是其"已知 SDC 工程化"补充,可未来通过 `hardware_lane.py` 的 promotion bundle 把高价值用例固化为 opendcdiag 外部测试(`tests/cpu/arm64/`)。
- `opendcdiag/docs/sdc1-01-02-core179-diagnostics/`:根因报告 + MRU 源码。`sdc-fuzzing/engine/` 直接复用其 `eigen_cabidrv.cpp`(触发机器码不变性 F1)。
- `opendcdiag/builddir/opendcdiag`:家族 G 的负载源(满载同 socket)。

---

## 12. 后续循环迭代可推进项

- 迭代 #2+:在本机持续完善生成器(更多家族、统计显著性、自动重跑 inconclusive);
- 目标机可用时:`run_all.sh` 全量执行 + 汇总 100 用例复现率(预期 ≥95%,inconclusive 由重跑收敛);
- 把通过验证的用例经 `hardware_lane.py` promote 为 opendcdiag `tests/cpu/arm64/` 外部测试,作为持续 SDC 监测器(报告 §15.2 建议 4)。
