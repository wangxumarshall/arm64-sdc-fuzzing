# CORE179 SDC 诊断探针功能与证据链说明

**文档日期:** 2026-08-06
**适用目录:** `opendcdiag/docs/sdc1-01-02-core179-diagnostics/`
**目的:** 说明本目录下各诊断程序(探针)的功能、工作原理,以及它们如何串成定位"核 179 静默数据损坏(SDC)"根因的证据链。本文是 [CORE179_SDC_ROOTCAUSE_REPORT.md](CORE179_SDC_ROOTCAUSE_REPORT.md) 的配套索引,聚焦"每个程序是干什么用的、为什么存在";根因结论与完整实验数据请参阅主报告。

---

## 1. 文档定位

本目录是针对 4 路 Kunpeng 920(192 核 ARM64)服务器"核 179 SDC"的完整诊断工具包,由两类产物构成:

- **两份报告**(分析结论):
  - [CORE179_SDC_ROOTCAUSE_REPORT.md](CORE179_SDC_ROOTCAUSE_REPORT.md) — 主根因报告(五层假设排除法)
  - [CORE179-SDC-related-instruction-funcion-unit.md](CORE179-SDC-related-instruction-funcion-unit.md) — 物理机理补充(稀疏矩阵 di/dt 电压瞬态、涉及指令与可疑功能单元)
- **六个自研探针源码 + 对应已编译二进制**(取证工具):本文逐一说明。

核心思路:主报告用"分层假设排除法"逐层证伪假设,每一层都对应一个或多个探针来提供可复现的实验证据。探针不是通用 benchmark,而是**为证伪某一具体假设而专门设计的自校验微基准**。

---

## 2. 目录构成一览

| 文件 | 语言 | 依赖 | 类别 | 一句话用途 |
|---|---|---|---|---|
| `esdiag3.cpp` / `esdiag3` | C++17 | Eigen 5.0 | 决定性探针 | 固定输入 A 重复 Cholesky 求解,分离"输入损坏" vs "计算损坏" |
| `esdiag2.cpp` / — | C++17 | Eigen 5.0 | 决定性探针 | 打印 elem[0] 损坏的字节级模式(地址/actual/xor/popcount) |
| `fpprobe.c` / `fpprobe` | C | 无 | 排除探针 | 纯浮点 CRC 自检,验证"浮点 pipe 是否损坏" |
| `probe.c` / `probe` | C | NEON/ACLE | 排除探针 | 8 个功能单元逐一压测自检,定位"哪个单元坏了" |
| `minimal_probe.c` / — | C | 无 | 精细化探针 | 三变体:测试间接寻址本身能否复现 elem[0] 混叠 |
| `loadgen.c` / `loadgen` | C | 无 | 辅助工具 | fork N worker 制造满载压力,重现触发条件 |

> Eigen root 路径:`/home/sdc/arm64-sdc-fuzzing/opendcdiag/third-part`(Eigen 5.0.1 submodule)。

---

## 3. 诊断背景(简述)

OpenDCDiag(ARM64 构建,bundled Eigen 5.0.1)在全量满载运行约 17 分钟后,仅**核 179** 上的 `eigen_sparse`(稀疏 Cholesky 求解)静默算错,偶发整机挂死。关键特征(详见主报告):

- 固定 seed 在核 179 上单跑 9000+ 次全过 → 排除 Eigen 确定性软件 bug;
- 排除核 179 后 191 核满载 0 失败 → 失败严格绑定核 179;
- 单核 179 不触发,需同 socket 满载 → 负载敏感;
- per-core PMU 与健康核差异 < 2%、`memory_error` = 0、EDAC = 0 → 微架构层完全正常却静默算错。

这一"微架构正常却算错"的悖论,正是需要自研字节级探针(而非通用 PMU)来定位损坏模式的原因。

---

## 4. 逐个探针详解

### 4.1 `esdiag3.cpp` — 核心:输入/计算损坏分离(决定性)

**这是本目录的核心交付件**,对应主报告第 9 节 D4 实验。

**工作原理:**
1. 用固定 seed 的 LCG(`rng_state*1103515245+12345`)构建一个 256×256 对称稀疏矩阵 **A**(**只构建一次**,后续不再重建);
2. 用 `__crc32cb`(字节级 CRC32)对 A 的 value 数组做校验,记为 `a_crc`(固定基准);
3. `b = VectorXd::Random(N)`,用 `SimplicialCholesky` 求解一次得到 golden,对其 CRC 记为 `gold_crc`;
4. 循环 `iters` 次,每次:
   - 重新 CRC 校验 A → 若与 `a_crc` 不符,`acorrupt++`(输入被破坏?);
   - 用**全新 solver 对象**重新 `compute(A).solve(b)`,对结果 x CRC,若与 `gold_crc` 不符,`fails++`(计算结果错?);
   - 前 3 次失败打印 `a_crc_ok` 标志;
5. 输出 `RESULT: A_corrupt=%d/%d  x_wrong=%d/%d`。

**它证伪的假设:** "输入数据 A/b 被破坏导致结果错"。
**决定性结论:** A_corrupt = 0/3000(输入全程完好),x_wrong = 28/3000(结果错),且每次失败时 `a_crc_ok=1` → 损坏发生在**计算过程本身**,而非输入数据。

**用法:**
```bash
g++ -O2 -std=gnu++17 -march=armv8.1-a+crc+crypto -I$EIG esdiag3.cpp -o esdiag3
taskset -c 179 ./esdiag3 3000 12345   # iters=3000, rng_seed=12345
```

### 4.2 `esdiag2.cpp` — 字节级损坏模式(决定性)

`esdiag3` 的前驱,不做输入/计算分离,而是**打印损坏的字节级细节**,对应主报告第 9.2 节 D2/D3 实验。

**工作原理:** A 构建一次、golden 求解一次后,循环重新求解并比较 `x(0) != golden(0)`。对前 5 次失败,打印:
- `k`(迭代号)、`x[0]addr`(结果首元素地址)、
- `actual`(实际值)、`actual bits`(实际位模式)、
- `xor`(actual ^ expected)、`pc`(`__builtin_popcountll` 翻转位数)。

**它证伪的假设:** "随机单粒子翻转(SEU,只翻 1 bit、随机位置)"。
**决定性结论:**
- 损坏**固定在 elem[0]**(结果向量首元素,固定栈地址)→ 非随机位置;
- 翻转 **21–30 位** → 非单 bit SEU;
- actual 值(-15.68、-0.63 等)与 expected(-0.93)完全无关 → **数据混叠**(其他计算数据覆盖了 elem[0])。

### 4.3 `fpprobe.c` — 纯浮点 pipe 探针(排除)

**工作原理:** 固定数组 `A[i]=(i+1)*0.5`、`B[i]=(i+1)*1.5`,做向量乘 `C=A*B` 并对 C 做 CRC(基准 `gold`);循环 `iters` 次重算并比对 CRC → `mismatch`。再做点积 `dp=sum(A*B)` 循环比对 → `dp_fail`。任一不符返回 1。

**它证伪的假设:** "浮点运算 pipe 本身损坏"。
**结论:** 健康核永不失配;即便是故障核,纯浮点密集运算也不是触发条件 → 真正触发需要"稀疏 + 间接寻址"组合,而非纯浮点 pipe 损坏(否则所有浮点测试都该失败)。配合主报告第 5.2 节测试类型矩阵(eigen_gemm/eigen_svd 0 失败,仅 eigen_sparse 失败)共同排除该假设。

**用法:**
```bash
gcc -O3 -march=armv8.1-a+crc+crypto -std=gnu17 fpprobe.c -o fpprobe
taskset -c 179 ./fpprobe 1000000
```

### 4.4 `probe.c` — 8 功能单元微架构探针(排除/定位)

**工作原理:** 对 8 个功能单元分别压测并自检,每个探针先算一次基准,再重复 `it` 次比对,不符返回 1(MISCOMPARE):

| probe_id | 名称 | 压测对象 |
|---|---|---|
| 1 | `ALU_int` | 整数乘/异或/移位链 |
| 2 | `FPU_double` | 双精度点积 |
| 3 | `FPU_float` | 单精度点积 |
| 4 | `NEON_vec` | NEON `vmlaq` 向量异或归约 |
| 5 | `L1D_cache` | 32KB 缓冲区 CRC(压 L1D) |
| 6 | `L2L3_mem` | 大缓冲区 CRC(压 L2/L3/内存) |
| 7 | `Branch_pred` | 条件分支(`O0` noinline,压分支预测) |
| 8 | `CRC_engine` | `__crc32cw` 字级 CRC(压 CRC 硬件单元) |

`main` 先做 warmup,再按 `probe_id` 运行(0=全跑,1..8 单跑),打印每项 `ok`/`MISCOMPARE`。

**它证伪的假设:** "某一具体功能单元(cache/LSU/TLB/分支/FPU/CRC)损坏"。
**定位逻辑:** 若某单元损坏,对应项报 MISCOMPARE。配合主报告第 6 节 per-core PMU 对照(核 179 与健康核 176 全部微架构事件差异 < 2%)共同排除该层假设——即 cache/LSU/TLB/分支/浮点/内存子系统均无损坏。

**用法:**
```bash
gcc -O3 -march=armv8.1-a+crc+crypto -std=gnu17 -Wno-incompatible-pointer-types probe.c -o probe
taskset -c 179 ./probe 0 2000      # 全部 8 项,各 2000 次
taskset -c 179 ./probe 2 2000      # 仅 FPU_double
```

### 4.5 `minimal_probe.c` — 最小间接寻址探针(精细化)

**工作原理:** 无 Eigen 依赖,提供三个变体(由 `arg1` 选择),每个都先算 golden CRC,再循环 `iters` 次比对:

| 变体 | 名称 | 计算特征 |
|---|---|---|
| 1 | `v_dense` | 密集点积(**无**间接寻址)— 对照组 |
| 2 | `v_spmv` | CSR 稀疏矩阵向量乘 `y[i]=val[i]*x[col[i]]`(间接寻址 + 双精度) |
| 3 | `v_gather` | 指针追踪 `idx=next[idx]` 累加(重度间接,模拟 Cholesky 消去树遍历) |

**它回答的问题:** "间接寻址本身(不依赖 Cholesky)能否复现 elem[0] 混叠?"
- 若能 → 触发条件不限于 Cholesky,间接寻址即可;
- 若不能 → 损坏是 Cholesky 特定计算路径所致。

这是主报告第二层(触发单元隔离:仅稀疏 Cholesky + 间接寻址触发)的精细化拆解,用于把"稀疏 + 间接寻址"这一组合进一步分解到最小可复现要素。

**用法:**
```bash
gcc -O2 -march=armv8.1-a+crc+crypto -std=gnu17 minimal_probe.c -o mprobe
taskset -c 179 ./mprobe 2 5000     # SpMV 变体
```

### 4.6 `loadgen.c` — 负载生成器(辅助)

**工作原理:** `fork` 出 N 个 worker,每个 worker 在死循环里做无意义的 FP+int 运算(`s=s*a+b; a*=1.0000001; z+=i*2654435761`);`alarm(secs)`/`SIGTERM` 置 `stop` 标志,worker `_exit`。

**它的用途:** 制造同 socket 满载压力以重现触发条件。核 179 的 SDC 只在满载下出现(单核 0%),而 `loadgen` 不依赖 opendcdiag 本体,可单独把 `esdiag3`/`minimal_probe` 钉在核 179 上、用 `loadgen` 在其余核上制造压力,从而**隔离被测程序与负载来源**。

**用法:**
```bash
gcc -O2 loadgen.c -o loadgen
./loadgen 47 40        # 47 个 worker 跑 40 秒(配合核 179 上的探针)
```

---

## 5. 探针与五层假设排除法的映射

每个探针都服务于主报告中某一调查层,用来证伪一个具体假设:

| 调查层 | 证伪的假设 | 使用的探针 / 工具 | 结论 |
|---|---|---|---|
| L1 软件 vs 硬件 | Eigen 在该 seed 有确定性 bug | opendcdiag 自身 + 核对照(B1/B2) | 排除软件 |
| L2 触发测试类型 | 浮点 pipe 损坏 | opendcdiag 测试矩阵 + `fpprobe.c` | 仅稀疏 Cholesky 触发 |
| L3 功能单元损坏 | cache/LSU/TLB/分支/FPU 损坏 | `probe.c` + per-core PMU | 微架构全正常 |
| L4 输入 vs 计算损坏 | 输入数据 A/b 被破坏 | **`esdiag3.cpp`** | A 完好,计算过程损坏 |
| L5 字节级损坏模式 | 随机单 bit SEU | **`esdiag2.cpp`** | 固定 elem[0]+多位混叠 |
| L6 间接寻址充分性 | Cholesky 特定路径 vs 间接寻址 | `minimal_probe.c` | 拆解最小触发要素 |
| 全程 | 制造满载触发条件 | `loadgen.c` | 复现负载环境 |

**最终根因(微架构层,见主报告第 10 节):** 核 179 存在一个负载敏感的计算路径写回缺陷——在同 socket 满载 + Eigen Cholesky 稀疏求解(间接寻址 + 浮点)下,把"其他数据"混叠写入结果向量 `elem[0]` 的固定存储位置(21–30 位多位翻转,非单 bit SEU),且全程静默(无 PMU `memory_error`、无 EDAC 计数、无同步异常)。

---

## 6. 构建与运行速查

```bash
# 环境准备
export PATH="$HOME/.local/bin:$PATH"
export LD_LIBRARY_PATH="$HOME/rpmroot/sysroot/usr/lib64:$LD_LIBRARY_PATH"
cd ~/arm64-sdc-fuzzing/opendcdiag
EIG=$PWD/third-part
DIAG=$PWD/docs/sdc1-01-02-core179-diagnostics

# 构建全部探针
g++ -O2 -std=gnu++17 -march=armv8.1-a+crc+crypto -I$EIG $DIAG/esdiag3.cpp  -o /tmp/esdiag3
g++ -O2 -std=gnu++17 -march=armv8.1-a+crc+crypto -I$EIG $DIAG/esdiag2.cpp  -o /tmp/esdiag2
gcc -O3 -march=armv8.1-a+crc+crypto -std=gnu17                       $DIAG/fpprobe.c      -o /tmp/fpprobe
gcc -O3 -march=armv8.1-a+crc+crypto -std=gnu17 -Wno-incompatible-pointer-types \
                                                                    $DIAG/probe.c        -o /tmp/probe
gcc -O2 -march=armv8.1-a+crc+crypto -std=gnu17                       $DIAG/minimal_probe.c -o /tmp/mprobe
gcc -O2                                                               $DIAG/loadgen.c      -o /tmp/loadgen

# 触发实验:47 核 socket 满载(excl 179)+ esdiag3 在核 179
SET=$(seq 144 178 | tr '\n' ','; seq 180 191 | tr '\n' ',' | sed 's/,$//')  # 144-191 排除 179
builddir/opendcdiag --beta -e eigen_sparse --cpuset "$SET" -s LCG:323306158 \
    -T 40s --output-format=tap -o /tmp/load.log >/dev/null 2>&1 &
sleep 1
taskset -c 179 /tmp/esdiag3 3000 12345
# 预期:核 179 出现 A_corrupt=0 / x_wrong>0(多位,elem[0]);健康核 176 = 0/0
```

> 单独跑探针时,需用 `loadgen` 或 opendcdiag 在同 socket 其余核上制造满载,否则单核 179 不触发(触发率满载 ~0.5–1.25%,单核 0%)。

---

## 7. 关联文档

- [CORE179_SDC_ROOTCAUSE_REPORT.md](CORE179_SDC_ROOTCAUSE_REPORT.md) — 主根因报告(完整实验数据、证据矩阵、缓解措施)
- [CORE179-SDC-related-instruction-funcion-unit.md](CORE179-SDC-related-instruction-funcion-unit.md) — 物理机理补充(di/dt 电压瞬态、涉及指令、可疑功能单元)
- `opendcdiag/CLAUDE.md` — 项目构建说明(Eigen 5.0.1 submodule 处理、ARM64 构建命令)
