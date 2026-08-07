# CORE179 SDC 诊断探针完整索引

**文档日期:** 2026-08-06(2026-08-07 修订:补全全部探针 + libc-only MRU)
**适用目录:** `opendcdiag/docs/sdc1-01-02-core179-diagnostics/`
**目的:** 本目录下全部诊断程序(探针)的功能、依赖、构建命令与所属调查层的完整索引。**本文是 [CORE179_SDC_ROOTCAUSE_REPORT.md](CORE179_SDC_ROOTCAUSE_REPORT.md) 的配套工具索引**,聚焦"每个探针是什么、干什么用、为什么存在";根因结论、完整实验数据、证据矩阵请参阅主报告。

---

## 1. 文档定位

本目录是针对 4 路 Kunpeng 920(192 核 ARM64)服务器"核 179 SDC"的完整诊断工具包,由两类产物构成:

- **三份报告**(分析结论):
  - [CORE179_SDC_ROOTCAUSE_REPORT.md](CORE179_SDC_ROOTCAUSE_REPORT.md) — 主根因报告(六层假设排除法 + MRU + E2E);
  - [CORE179-SDC-related-instruction-funcion-unit.md](CORE179-SDC-related-instruction-funcion-unit.md) — 物理层假说补充(di/dt 电压瞬态、涉及指令、可疑功能单元;早期物理推测,最终根因见主报告 §11);
  - 本文(CORE179_SDC_DIAGNOSTIC_PROBES.md)— 探针完整索引。
- **20+ 自研探针源码 + 构建脚本**(取证工具):本文逐一说明。

核心思路:主报告用"分层假设排除法"逐层证伪假设,每一层都对应一个或多个探针来提供可复现的实验证据。探针不是通用 benchmark,而是**为证伪某一具体假设而专门设计的自校验微基准**——每个探针先算一次 golden,再循环比对,不符即报 MISCOMPARE/fail。

---

## 2. 探针总表(按角色分组)

> **检查字段**列说明:成功 MRU 与 Eigen 参考探针校验 **x**(求解结果向量,损坏发生在 `x[0]`);纯 C 负对照中多数只校验 **D**(因子对角线)——这是它们未能触发的一个线索(损坏经 solve 传播到 x,见主报告 §10.4)。

### 2.1 成功 MRU(★推荐交付件,libc-only,已端到端验证★)

| 文件 | 语言 | 依赖 | 检查字段 | 一句话用途 |
|---|---|---|---|---|
| `mru_eigenmc.c` | C | libc/libm | x | 纯 C 驱动:构建 SPD 稀疏矩阵 A,调用 Eigen 机器码 `escanalyze`/`escfactorize`/`escsolve`,CRC 校验 x |
| `eigen_cabidrv.cpp` | C++ | Eigen(编译期) | — | Eigen `SimplicialCholesky` 的 C-ABI 包装,`-fno-exceptions -fno-rtti`,本地 new/delete→malloc/free,消除 libstdc++ 依赖 |
| `build_mru_eigenmc.sh` | sh | g++/gcc | — | 一键构建:`g++ -fno-exceptions -c eigen_cabidrv.cpp` → `gcc mru_eigenmc.c eigen_cabidrv.o -o mrueig -lm` |

**`ldd mrueig` 证明运行时仅依赖 libc + libm**(无 libstdc++、libgcc_s、Eigen .so)。E2E 验证:179 满载 6-24/3000 fails(复现);176 满载 0;179 单核 0;下线 179 后 0。损坏签名:elem[0] 固定、多位(10-28 bit)、数据混叠。

### 2.2 Eigen 参考复现(触发,但链接 libstdc++)

| 文件 | 语言 | 依赖 | 检查字段 | 一句话用途 |
|---|---|---|---|---|
| `esdiag_phase2.cpp` | C++17 | Eigen 5.0 + libstdc++ | x | 分离 symbolic/numeric,mode 1 = analyzePattern 一次 + 重复 factorize+solve(主报告第六层削减 2 的探针,与原 opendcdiag eigen_sparse 同源) |

### 2.3 字节级定位探针(第五层)

| 文件 | 语言 | 依赖 | 检查字段 | 一句话用途 |
|---|---|---|---|---|
| `esdiag3.cpp` | C++17 | Eigen 5.0 + libstdc++ | A + x | **核心交付探针**:固定输入 A,分离"输入损坏"vs"计算损坏";报告 A_corrupt / x_wrong / popcount |
| `esdiag2.cpp` | C++17 | Eigen 5.0 + libstdc++ | x | 打印 elem[0] 损坏的字节级模式(地址/actual/xor/popcount) |
| `esdiag_elem0.cpp` | C++17 | Eigen 5.0 + libstdc++ | x | 逐元素定位损坏(确认固定 elem[0],报告 bad_idx/popcount) |
| `esdiag_N.cpp` | C++17 | Eigen 5.0 + libstdc++ | x | 扫描矩阵规模 N(确认 N≥256 阈值 + elem[0] 固定) |

### 2.4 纯 C 负对照 MRU(均不触发,证伪假设)

| 文件 | 语言 | 依赖 | 检查字段 | 证伪的假设 |
|---|---|---|---|---|
| `mru_full_sparse.c` | C | libc/libm | D | "纯 C 忠实重建完整 Eigen 算法可复现"(足迹/算法假设)— 0 触发 |
| `mru_coldl1d.c` | C | libc/libm | D | "匹配 Eigen 4× L1D-refill 特征可触发"(L1D 压力假设)— 0 触发 |
| `mru_solve.c` | C | libc/libm | x | "缺 solve 阶段导致纯 C 不触发"(缺 solve 假设)— 0 触发 |
| `mru_pure_c.c` | C | libc/libm | D | 纯 C 标量基线变体 |
| `mru_sparse.c` | C | libc/libm | D | 稀疏 CSC LDL^T |
| `mru_dense.c` | C | libc/libm | D | 密集 LDL^T |
| `mru_neon.c` | C | libc/libm + arm_neon | D | 密集 LDL^T + NEON intrinsics(vfmaq_f64) |
| `mru_ace.c` | C | libc/libm | D | 8×128-bit FMA 累加器(高 ACE+IBR)+paired load |
| `mru_branch.c` | C | libc/libm | D | + 数据相关不可预测分支(高 branch-miss) |
| `mru_asm.c` | C | libc/libm | D | 内联汇编精确复现 Eigen 热循环(fmsub + indirect ldr/str) |

**全部 0 触发**,共同证伪"纯 C 可复现"假设 → 指向"需 Eigen 编译产物的精确指令序列交织"。

### 2.5 第六层削减探针(单一操作充分性)

| 文件 | 语言 | 依赖 | 检查字段 | 一句话用途 |
|---|---|---|---|---|
| `minimal_probe.c` | C | libc | D | 三变体(dense dot / SpMV / gather),证明单一操作不触发 |
| `fma_probe.c` | C | libc | D | 纯 FMA 循环,证明纯 FMA 不触发 |

### 2.6 功能单元探针(第三层)

| 文件 | 语言 | 依赖 | 检查字段 | 一句话用途 |
|---|---|---|---|---|
| `probe.c` | C | libc + NEON/ACLE | 各单元 | 8 功能单元逐一压测自检(ALU/FPU/NEON/L1D/L2L3/分支/CRC) |
| `fpprobe.c` | C | libc | C | CRC 敏感浮点探针(向量乘 + 点积,压力下自检),排除浮点 pipe 损坏 |

### 2.7 辅助工具

| 文件 | 语言 | 依赖 | 一句话用途 |
|---|---|---|---|
| `loadgen.c` | C | libc | `fork` N worker 制造满载压力,重现触发条件(核 179 仅满载下触发) |

---

## 3. 关键探针详解

### 3.1 `esdiag3.cpp` — 核心:输入/计算损坏分离(决定性)

**对应主报告第五层 D4 实验。** 工作原理:
1. 用固定 seed 的 LCG(`rng_state*1103515245+12345`)构建一个 256×256 对称稀疏矩阵 **A**(**只构建一次**);
2. 用 `__crc32cb`(字节级 CRC32)对 A 的 value 数组做校验,记为 `a_crc`(固定基准);
3. `b = VectorXd::Random(N)`,用 `SimplicialCholesky` 求解一次得到 golden,对其 CRC 记为 `gold_crc`;
4. 循环 `iters` 次:重新 CRC 校验 A(若不符 `acorrupt++`);用**全新 solver 对象**重新 `compute(A).solve(b)`,对 x CRC(若不符 `fails++`);前 3 次失败打印 `a_crc_ok` 标志;
5. 输出 `RESULT: A_corrupt=%d/%d  x_wrong=%d/%d`。

**证伪的假设:** "输入数据 A/b 被破坏导致结果错"。**决定性结论:** A_corrupt=0/3000,x_wrong=28/3000,每次失败 `a_crc_ok=1` → 损坏发生在**计算过程本身**。

```bash
g++ -O2 -std=gnu++17 -march=armv8.1-a+crc+crypto -I$EIG esdiag3.cpp -o esdiag3
taskset -c 179 ./esdiag3 3000 12345   # 需同 socket 满载才触发
```

### 3.2 `esdiag2.cpp` — 字节级损坏模式(决定性)

`esdiag3` 的前驱,不做输入/计算分离,而是**打印损坏的字节级细节**(主报告第五层 D2/D3)。对前 5 次失败打印:`k`、`x[0]addr`、`actual`、`actual bits`、`xor`(actual ^ expected)、`pc`(`__builtin_popcountll`)。

**证伪的假设:** "随机单粒子翻转 SEU"。**决定性结论:** 损坏固定 elem[0](固定栈地址)、翻转 21-30 位(非单 bit)、actual 与 expected 完全无关(数据混叠)。

### 3.3 `esdiag_phase2.cpp` — Eigen 参考 MRU(第六层削减 2)

分离 symbolic/numeric,验证**哪个阶段触发**:
- mode 0 = `compute()` 每次(symbolic+numeric);
- mode 1 = `analyzePattern()` 一次 + 重复 `factorize()`+`solve()`(**numeric-only**);
- mode 2 = `analyzePattern()` 每次只做 symbolic + 一次 factorize+solve。

**关键结论:** mode 1(numeric-only)15/1500(1.0%);mode 0(compute-both)4/1500(0.27%);solve-only 0/2000。**numeric-only ≈ 4× compute-both** → symbolic 重做刷新状态缓解 → 状态泄漏型缺陷签名(主报告 §11.2)。

```bash
g++ -O2 -std=gnu++17 -march=armv8.1-a+crc+crypto -I$EIG esdiag_phase2.cpp -o esphase2
taskset -c 179 ./esphase2 1500 12345 1   # mode=1 numeric-only
```

### 3.4 `mru_eigenmc.c` + `eigen_cabidrv.cpp` — libc-only 成功 MRU(★交付件★)

**主报告 §10.5 的可交付 MRU。** 纯 C 驱动调用 Eigen 编译机器码对象;`eigen_cabidrv.cpp` 用 `-fno-exceptions -fno-rtti` 编译并本地提供 `operator new/delete`/`__throw_length_error` stub,消除全部 libstdc++ 符号;最终 `mrueig` 的 `ldd` 仅 libc + libm。构建:`./build_mru_eigenmc.sh`。运行:`taskset -c 179 ./mrueig 3000 12345`(需满载),预期 6-24/3000 fails,健康核 176 = 0。

### 3.5 `probe.c` — 8 功能单元微架构探针(第三层)

对 8 个功能单元分别压测并自检,每个先算基准再重复 `it` 次比对,不符返回 MISCOMPARE:

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

`main` 先 warmup,再按 `probe_id` 运行(0=全跑,1..8 单跑)。配合主报告第三层 per-core PMU 对照(核 179 与 176 微架构事件差异 < 2%),共同排除"某一具体功能单元损坏"。

```bash
gcc -O3 -march=armv8.1-a+crc+crypto -std=gnu17 -Wno-incompatible-pointer-types probe.c -o probe
taskset -c 179 ./probe 0 2000      # 全部 8 项
taskset -c 179 ./probe 2 2000       # 仅 FPU_double
```

### 3.6 `minimal_probe.c` — 三变体单一操作探针(第六层削减 1)

无 Eigen 依赖,由 `arg1` 选择:变体 1 `v_dense`(密集点积,无间接寻址,对照组)、变体 2 `v_spmv`(CSR 稀疏矩阵向量乘,间接寻址 + 双精度)、变体 3 `v_gather`(指针追踪,重度间接)。**全部 0 触发** → 证明需 Cholesky 特定多阶段序列,而非单一操作。

### 3.7 `loadgen.c` — 负载生成器(辅助)

`fork` N 个 worker,死循环做无意义 FP+int 运算;`alarm(secs)`/`SIGTERM` 置 `stop`。核 179 仅满载下触发(单核 0%),`loadgen` 不依赖 opendcdiag,可把探针钉在 179、用 loadgen 在其余核制造压力,隔离被测程序与负载来源。

```bash
gcc -O2 loadgen.c -o loadgen
./loadgen 47 40        # 47 worker 跑 40s
```

---

## 4. 探针与六层假设排除法的映射

每个探针都服务于主报告中某一调查层,用来证伪一个具体假设(详见主报告 §14):

| 调查层 | 证伪的假设 | 使用的探针 | 结论 |
|---|---|---|---|
| 第一层(软件 vs 硬件) | Eigen 在该 seed 有确定性 bug | opendcdiag 自身 + 核对照 | 排除软件 |
| 第二层(触发测试类型) | 浮点 pipe 损坏 | opendcdiag 测试矩阵 + `fpprobe.c` | 仅稀疏 Cholesky 触发 |
| 第三层(微架构事件) | cache/LSU/TLB/分支/FPU 损坏 | `probe.c` + per-core PMU | 微架构全正常 |
| 第四层(实时内核监控) | 失败伴随硬件错误事件;挂死是内存 ECC | 满载 + dmesg/EDAC 跟踪 | 失败静默、挂死非 ECC |
| 第五层(字节级损坏) | 输入数据损坏;单 bit SEU | `esdiag3.cpp` + `esdiag2.cpp` + `esdiag_elem0.cpp` | 计算过程损坏 elem[0],多位混叠 |
| 第六层(MRU 削减) | Cholesky 整体 vs 单一操作;symbolic vs numeric;规模 | `minimal_probe.c`/`fma_probe.c`/`esdiag_phase2.cpp`/`esdiag_N.cpp` + 9 个纯 C 负对照 + 差分 perf | 需 numeric factorize;状态泄漏型;N≥256 |
| 交付(最小复现) | (构造可复现 DFT 向量) | **`mru_eigenmc.c` + `eigen_cabidrv.cpp`(libc-only)** | 端到端验证通过 |
| 全程(辅助) | — | `loadgen.c` | 制造满载触发条件 |

---

## 5. 构建与运行速查

```bash
# 环境准备
export PATH="$HOME/.local/bin:$PATH"
export LD_LIBRARY_PATH="$HOME/rpmroot/sysroot/usr/lib64:$LD_LIBRARY_PATH"
cd ~/arm64-sdc-fuzzing/opendcdiag
EIG=$PWD/third-part
DIAG=$PWD/docs/sdc1-01-02-core179-diagnostics

# === ★推荐:libc-only MRU(一键构建)===
$DIAG/build_mru_eigenmc.sh                      # 产 $DIAG/mrueig,ldd 仅 libc+libm

# === Eigen 参考探针(链接 libstdc++)===
g++ -O2 -std=gnu++17 -march=armv8.1-a+crc+crypto -I$EIG $DIAG/esdiag_phase2.cpp -o /tmp/esphase2
g++ -O2 -std=gnu++17 -march=armv8.1-a+crc+crypto -I$EIG $DIAG/esdiag3.cpp       -o /tmp/esdiag3
g++ -O2 -std=gnu++17 -march=armv8.1-a+crc+crypto -I$EIG $DIAG/esdiag2.cpp       -o /tmp/esdiag2

# === 纯 C 探针(仅 libc/libm)===
gcc -O2 -march=armv8.1-a+crc+crypto -ffp-contract=fast -std=gnu17 $DIAG/mru_full_sparse.c -o /tmp/mruf -lm
gcc -O2 -march=armv8.1-a+crc+crypto -ffp-contract=fast -std=gnu17 $DIAG/mru_coldl1d.c   -o /tmp/mrucold -lm
gcc -O2 -march=armv8.1-a+crc+crypto -ffp-contract=fast -std=gnu17 $DIAG/mru_solve.c     -o /tmp/mrusolv -lm
gcc -O2 -march=armv8.1-a+crc+crypto -std=gnu17                       $DIAG/minimal_probe.c -o /tmp/mprobe
gcc -O3 -march=armv8.1-a+crc+crypto -std=gnu17                       $DIAG/fma_probe.c     -o /tmp/fmaprobe
gcc -O3 -march=armv8.1-a+crc+crypto -std=gnu17                       $DIAG/fpprobe.c       -o /tmp/fpprobe
gcc -O3 -march=armv8.1-a+crc+crypto -std=gnu17 -Wno-incompatible-pointer-types $DIAG/probe.c -o /tmp/probe
gcc -O2                                                              $DIAG/loadgen.c       -o /tmp/loadgen

# === 触发实验(安全:47 核 socket 满载 + 单次 ≤75s,不触发挂死)===
SET=$(echo $(seq 144 178) $(seq 180 191) | tr ' ' ',')   # 144-191 排除 179
timeout 75 builddir/opendcdiag --beta -e eigen_sparse --cpuset "$SET" -s LCG:323306158 \
    -T 60s --output-format=tap -o /tmp/load.log >/dev/null 2>&1 &
sleep 2
# 在核 179 跑 MRU:
taskset -c 179 $DIAG/mrueig 3000 12345           # 预期:6-24/3000 fails(elem[0] 多位混叠)
# 健康核对照:taskset -c 176 $DIAG/mrueig 3000 12345  → 0 fails
```

> 单独跑探针时,需用 `loadgen` 或 opendcdiag 在同 socket 其余核上制造满载,否则单核 179 不触发(触发率满载 ~0.5-1%,单核 0%)。触发率随机器/负载窗口波动,属负载敏感型瞬态缺陷;建议在故障活跃窗口内同时跑 Eigen 参考(`esphase2`)与 MRU(`mrueig`)以对照确认一致性。

---

## 6. 关联文档

- [CORE179_SDC_ROOTCAUSE_REPORT.md](CORE179_SDC_ROOTCAUSE_REPORT.md) — 主根因报告(六层假设排除、完整实验数据、证据矩阵、MRU、E2E 验证、缓解措施);
- [CORE179-SDC-related-instruction-funcion-unit.md](CORE179-SDC-related-instruction-funcion-unit.md) — 物理层假说补充(di/dt 电压瞬态、涉及指令、可疑功能单元;早期物理推测,最终微架构根因见主报告 §11);
- `opendcdiag/CLAUDE.md` — 项目构建说明(Eigen 5.0.1 submodule 处理、ARM64 构建命令)。
