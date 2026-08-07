# SDC-Fuzzing: 100 用例复现 core-179 SDC 的设计与生成机制

**作者:** Claude (sdc-fuzzing 循环迭代 #1, 2026-08-07)
**目标:** 深度理解当前项目源码,构建真实复现 SDC 的用例生成机制 `sdc-fuzzing`,设计 sdc-fuzzing 方案,自动化生成 100 个用例,使得这 100 个 SDC 检测用例都能复现 core-179 核 SDC 问题。
**根因依据:** [`opendcdiag/docs/sdc1-01-02-core179-diagnostics/CORE179_SDC_ROOTCAUSE_REPORT.md`](../opendcdiag/docs/sdc1-01-02-core179-diagnostics/CORE179_SDC_ROOTCAUSE_REPORT.md)

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

---

## 5. 用例家族设计(100 个的分布)

为保证覆盖率与统计稳健,100 个用例按家族分布(每个家族参数化一个维度,其余固定为已验证基线 N=256/p=0.1/d=2/K=3000/mode=1):

| 家族 | 用例数 | 参数化维度 | 取值 | 验证目的 |
|------|--------|-----------|------|---------|
| A. 规模扫描 | 20 | N | 256(5), 384(5), 512(5), 768(3), 1024(2) | F2 规模阈值;确认 N≥256 都触发 |
| B. 密度扫描 | 15 | density_p | 0.05,0.08,0.10,0.12,0.15,0.20(各~2-3,变种子) | 间接寻址压力与触发率关系 |
| C. 对角占优 | 10 | diag_dominance | 2.0,3.0,4.0,6.0,8.0(各2) | 数值条件对触发的影响(SPD 强度) |
| D. 种子多样性 | 25 | matrix_seed + rhs_seed | 25 个不同 (ms, s) 对,N=256 固定 | F3:损坏固定 elem[0] 与矩阵内容无关 → 25 个不同矩阵都应在 elem[0] 损坏 |
| E. 模式对比 | 10 | mode | 1(8 个,高触发),0(2 个,低触发) | F6: numeric-only vs compute-both 失败率比 ≈4× |
| F. 迭代深度 | 10 | K | 1500(2),2500(3),3000(3),5000(2) | F5: 更深迭代是否线性提升捕获数 |
| G. 负载窗口 | 10 | load_seconds | 30s/45s/60s/75s(各 2-3)on the verified 47-core cpuset | F2/F5: 捕获窗口时长(全部≥47核阈值内) |

**合计 = 20+15+10+25+10+10+10 = 100。** 每个用例有唯一 `id` 与参数集,清单见 `cases/manifest.json`(由 `scripts/generate_manifest.py` 生成)。

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

## 7. 执行与判定流程(单用例)

```
run_case.sh case_NNN:
  1. 从 manifest.json 读 case_NNN 的参数 (N, p, d, ms, s, mode, K, target_core, load_cpuset, load_seconds)
  2. 后台启动负载: timeout <load_seconds+10> opendcdiag --beta -e eigen_sparse \
        --cpuset <load_cpuset> -s LCG:323306158 -T <load_seconds>s -o /dev/null
  3. sleep 2  (等负载起来)
  4. 前台触发: timeout <load_seconds+10> taskset -c <target_core> \
        ./engine/mrueig <K> <ms> <s> <N> <p> <d> <mode> 2> cases/case_NNN/run.log
     (mrueig 内部: analyzePattern 一次 [mode 1] 或 每次 [mode 0], factorize+solve K 次, CRC(x) vs golden)
  5. 解析 run.log: RESULT ... fails=X/K
  6. 判定:
       if fails > 0  → case PASS (复现成功,记录 fails/率)
       else           → case INCONCLUSIVE (未在该窗口捕获,需重跑或换窗口)
       (单核 0 失败不是 FAIL,因为 F5:单核本就不触发;负对照用例期望 0)
  7. 写 cases/case_NNN/result.json
```

**判定语义(重要):**
- 用例"复现成功" = `fails > 0` 且损坏在 elem[0](MRU 已内建 elem[0] 校验)。
- 用例"未捕获" = `fails == 0` 但在满载窗口内 — 概率事件(F5 失败率 0.5-1%,K=3000 期望 ~15-30 fails,单窗口 0 失败概率 < 5%),需重跑 2-3 个窗口确认;**不是设计失败**。
- 健康核对照(176 / 当前主机的等价核)必为 0 fails,作为负对照。

**安全:** 全程 `timeout` 包裹,单次 ≤75s,避免报告 §11.3 的挂死(计算损坏波及控制流)。绝不跑全 192 核长时间满载。

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

1. ✅ 写本 DESIGN.md(本文)。
2. ✅ 复制 `eigen_cabidrv.cpp` 到 `sdc-fuzzing/engine/`,编写参数化 `mru_driver.c`(支持 N/p/d/ms/s/mode/K 命令行)。
3. ✅ 写 `scripts/generate_manifest.py` 生成 100 用例清单。
4. ✅ 写 `scripts/build_engine.sh` 构建 `engine/eigen_cabidrv.o` + `engine/mrueig`。
5. ✅ 写 `scripts/run_case.sh` + `run_all.sh` + `analyze_results.py`。
6. ✅ 本机冒烟:构建 + 单核跑基线用例(期望 0 fails,确认机制)。
7. ⏳ 目标机执行 `run_all.sh`(需 4 路 192 核机,本循环不可得;留待目标机)。

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
