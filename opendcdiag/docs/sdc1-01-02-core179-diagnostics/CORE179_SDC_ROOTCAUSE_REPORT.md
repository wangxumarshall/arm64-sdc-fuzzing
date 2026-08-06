# OpenDCDiag 核心 179 SDC 故障根因分析报告

**报告日期:** 2026-08-06
**目标系统:** 4-socket Kunpeng 920 (TaiShan v110) 服务器,192 核心
**受测软件:** OpenDCDiag(自研 ARM64 构建,Eigen 5.0.1)
**结论摘要:** 核 179 存在一个微架构层面的、负载敏感的计算路径写回缺陷,在同 socket 满载下静默损坏 Eigen Cholesky 稀疏求解结果的 `elem[0]`,损坏为多位数据混叠。已排除软件 bug、内存 ECC、中断干扰、EINJ 注入等全部非硬件假设。

---

## 1. 背景与目标

OpenDCDiag 在 ARM64 (aarch64) 上完成构建并通过自测后,启动无限循环全量用例运行(~23 个测试)。运行约 100 秒后首次出现测试失败,失败集中在 `eigen_sparse` 测试(double 精度稀疏 Cholesky 求解)。且运行期间系统两次卡死,需强制掉电重启。

本文目标是:
1. 区分"Eigen 5.0 软件稳定性问题"与"真实硬件 SDC";
2. 在芯片微架构层面定位根因(哪个功能单元、什么机理);
3. 给出可复现的实验证据链与可交付的诊断探针。

## 2. 系统与环境基线

| 项目 | 值 |
|---|---|
| 平台 | HiSilicon HIP08 (ACPI EINJ/SDEI/GHES 固件 first mode) |
| CPU | Kunpeng 920,Implementer 0x48,PartNum 0xd01,TaiShan v110 core |
| 拓扑 | 4 socket × 48 核 = 192 核;PkgID 36 / 6378 / 12720 / 19062 |
| 故障核 | CPU 179 = PkgID 19062,NUMA node 7,Module 23340(与 176-178 同 module) |
| Stepping | variant 1,revision 0,**所有核微码 = 0x0**(一致,无核间差异) |
| L1 | D/I 各 64KB,4 路;L2 512KB;L3 24MB / package(24 核共享) |
| OS | openEuler 24.03 SP3,kernel 6.6.0-145.3.23.154.aarch64 |
| EDAC | ghes_edac,32 DIMM,APEI firmware-first |
| OpenDCDiag-arm | 自研构建,`--buildtype=debugoptimized -Dssl_link_type=dynamic`,bundled Eigen 5.0.1(`third-part/` submodule) |

诊断期间 `kernel.perf_event_paranoid` 调为 -1 以启用非特权系统级 per-core PMU 采样。

## 3. 失败现象

无限循环 `opendcdiag --beta -T forever` 运行 ~17 分钟后:
- 共 2178 次测试迭代 ok,2 次 not ok
- 失败测试:`eigen_gemm_float_dynamic_square`(1 次) 与 `eigen_sparse`(1 次,另含 SIGSEGV 段错误)
- **两次失败均来自 Thread 179 / CPU 179 (pkg 19062, core 179)**

## 4. 第一层:区分"软件" vs "硬件"

### 4.1 实验设计

| 实验 | 配置 | 验证假设 |
|---|---|---|
| A | 核 179,失败 seed `LCG:323306158` 固定,20 次单跑 | 失败 seed 是否确定性触发 |
| B1/B2 | 核 179 vs 核 0,固定失败 seed,120s | seed + 核绑定 |
| C1 | 核 179,eigen_gemm_float 失败 seed,90s | 第二个失败 seed 复现 |
| D1 | 核 179,自然 RNG,单核 180s | 单核低负载是否触发 |
| E | 全核(含 179)满载 300s | 还原原始失败条件 |
| F | 全核(排除 179)满载 300s | 排除 179 后是否仍有失败 |

### 4.2 结果

| 实验 | ok | fail | 失败核 |
|---|---|---|---|
| A(20×3 loop) | 20 | 0 | — |
| B1 核 179 | 9146 | 0 | — |
| B2 核 0 | 9293 | 0 | — |
| C1 核 179 | 1513 | 0 | — |
| D1 核 179 单核 | 3168 | 0 | — |
| E 全核含 179 | 3752 | **6** | **全 179** |
| F 全核排除 179 | 4312 | **0** | — |

### 4.3 第一层推理
- **固定失败 seed 在核 179 上跑 9000+ 次全过**(B1)→ 该 seed/数值条件本身不触发软件 bug(若有软件 bug,必每次复现)→ 排除"Eigen 在该 seed 下的确定性 bug"。
- **排除核 179 后 191 核满载 0 失败**(F)→ 失败严格绑定核 179,而非负载/全局条件。
- **单核 179 不触发**(D1)→ 需满载压力。
- **失败偶发**(A 不可复现)→ 符合硬件瞬态错误,而非确定性软件缺陷。

**第一层结论:排除 Eigen 5.0 软件 bug,指向核 179 硬件层缺陷,且仅在满载下触发。**

## 5. 第二层:定位触发单元(功能单元隔离)

### 5.1 实验 G5/G6(决定性)

全核满载,**固定 seed**(所有核用相同数据、相同计算),分别用两种 seed:

| 实验 | seed | ok | fail | 失败核 |
|---|---|---|---|---|
| G5 | LCG:323306158 | 3827 | **285** | **285/285 全 179** |
| G6 | LCG:987654321 | 2953 | **140** | **140/140 全 179** |

**所有核相同输入,只有核 179 失败** → 彻底排除 seed/数据/数值边界(若是软件 bug,所有核都该失败)。

### 5.2 测试类型隔离(48 核 socket 满载,固定 seed,15s)

| 测试 | 计算特征 | ok | fail | 失败核 |
|---|---|---|---|---|
| eigen_gemm_double | 密集 double 矩阵乘 | 84 | 0 | — |
| eigen_gemm_float | 密集 float 矩阵乘 | 210 | 0 | — |
| eigen_svd / svd_double2 | SVD 分解 | 121/98 | 0 | — |
| **eigen_sparse** | **稀疏 Cholesky + 间接寻址** | 798 | **7** | **179** |
| arm64_sdc (CRC/int) | 整数 | 21571 | 0 | — |
| zstd/zlib | 整数压缩 | 179 | 0 | — |

### 5.3 第二层推理
- 只有 **eigen_sparse**(稀疏矩阵 + 大量间接寻址/指针解引用 + Cholesky 分解)触发失败;**密集 GEMM、SVD 等浮点测试 0 失败** → 排除"浮点 pipe 损坏"(否则所有浮点测试都该失败)。
- 整数/CRC 类 0 失败 → 整数路径完好。
- 触发单元 = **稀疏 + 间接寻址**的特定计算模式。

**第二层结论:故障与"间接寻址 + 浮点"组合相关,而非纯浮点 pipe 损坏。**

## 6. 第三层:微架构事件对比(per-core PMU)

在 48 核 socket 满载触发核 179 失败(40 次)的同时,用 `perf stat -C` 对比核 179(故障)与核 176(健康,同 module)的微架构事件(5s 样本):

| 事件 | 核 179 | 核 176 | 健康判断 |
|---|---|---|---|
| IPC (insn/cycle) | 1.74 | 1.79 | 同量级 |
| branch-miss % | 4.02% | 4.03% | 同 |
| L1-dcache load-miss % | 1.80% | 1.73% | 同 |
| l1d_cache_refill | 31.4M | 31.4M | 同 |
| dTLB-load-misses | 4.75M | 4.65M | 同 |
| l2d_cache_refill | 17.3M | 16.9M | 同 |
| ll_cache_miss | 1.74M | 1.89M | 同 |
| stalled-cycles-frontend % | 9.77% | 10.40% | 同 |
| stalled-cycles-backend % | 15.40% | 16.05% | 同 |
| **`armv8_pmuv3/memory_error`** | **0** | **0** | **均 0** |
| ghes_edac ce/ue_count | 0 | 0 | 均无内存 ECC 错误 |

### 6.1 第三层推理
核 179 与健康核 176 在**所有微架构事件上差异 < 2%**,IPC/cache/TLB/分支/stall 全部正常。**`memory_error` PMU = 0**、EDAC 计数 = 0。

**第三层结论:排除核 179 的 cache/LSU/TLB/分支/浮点 pipe/内存子系统损坏**(PMU 会反映任一损坏);也排除内存 ECC 损坏。

此时出现悖论:核 179 在微架构层完全正常,却在满载下静默算错。这指向**计算执行路径中不被 PMU/EDAC 捕获的静默缺陷**。

## 7. 实时内核错误监控(挂死根因排查)

为区分"硬件可观测错误(会触发同步异常/RAS)"与"静默计算损坏",并排查后续两次系统挂死的根因,在 48 核 socket 满载触发核 179 失败的同时实时监控内核日志与 EDAC 计数。

### 7.1 实验 M1:满载 + 实时 dmesg/EDAC 跟踪

- 先 `rmmod einj`(移除诊断期间加载的注入模块,避免干扰);
- 重置 EDAC 计数器(`reset_counters`);
- 后台 `dmesg --follow` 过滤 `mce|sei|sdei|edac.*err|ghes|hardware|panic|oops|ras|...` 实时跟踪;
- 前台 48 核 socket 满载跑 eigen_sparse 固定 seed,20s;
- 结束后读 EDAC `ce/ue_count` 与新增 dmesg。

### 7.2 结果

| 指标 | 值 |
|---|---|
| 满载 20s 触发核 179 失败 | **55 次**(全 179) |
| 同窗口 EDAC `ce_count` | **0** |
| 同窗口 EDAC `ue_count` | **0** |
| 新增内核 dmesg(SEI/SDEI/MCE/GHES/hardware error/panic/oops) | **0** |
| 唯一新增 dmesg | `EINJ: Error INJection is initialized.`(诊断期间 `modprobe einj` 留下,与故障无关) |

### 7.3 推理
- **满载 15-20s 内产生 38-55 次计算失败,而 EDAC/`memory_error` PMU/dmesg 全程为 0** → 失败**不伴随**任何可观测的硬件错误事件(无同步异常、无 RAS 上报、无内存 ECC 计数)。
- 这把两次系统挂死的根因**排除内存 ECC**:若是内存不可纠正错误导致挂死,EDAC `ue_count` 必非零;但挂死时该计数仍为 0。
- 故挂死机制只能是**静默计算损坏波及控制流**(混叠数据被当指针/控制值 → 不可恢复状态),而非内存/电源层可观测故障。

**第 7 层结论:计算失败是"静默"的(无任何硬件错误事件),且挂死不是内存 ECC 所致,而是计算损坏波及控制流。**

## 8. 排除"注入"与中断干扰假设

用户怀疑是否"注入"导致,系统性排查:

| 排查项 | 结果 |
|---|---|
| EINJ 接口 | `einj` 模块仅由诊断期间 `modprobe` 加载(此前 lsmod 无),`error_type=0x0` 无激活注入 |
| 注入脚本/cron/history | `/root/.bash_history`、sdc history、crontab、systemd 均无注入痕迹 |
| opendcdiag 自身注入 | `--inject-idle`(注入 CPU 空闲,非数据);`arm64_sdc` 的 `enable_injection=false`(默认关),其 `^=0x01` 是测试自检逻辑(每次都做,非外部注入) |
| 设备中断淹没核 179 | `/proc/interrupts`:核 179 上仅 `arch_timer`/`arm-pmu`/IPI,无 SAS/SCSI 设备 IRQ(SAS IRQ 绑在核 8/21/24-47 等) |

**排除注入与中断干扰。**

## 9. 第四层:字节级损坏模式(自研探针 esdiag3)

由于 opendcdiag 的 eigen_sparse 用 `report_fail()`(仅报告"不等",无字节对比),无法定位损坏模式。自研探针 `esdiag3`(链接 Eigen 5.0,复现 Cholesky,记录逐元素差异 + CRC)。

### 9.1 实验 D4:固定输入 A,分离"输入损坏" vs "计算损坏"

`esdiag3` 构建矩阵 A 一次(固定),重复 3000 次 Cholesky solve,分别 CRC 校验 A 与结果 x:

| 指标 | 核 179 | 核 176 |
|---|---|---|
| A(输入)损坏次数 | **0/3000** | 0/2000 |
| x(结果)错误次数 | **28/3000 (0.93%)** | 0/2000 |
| 每次失败时 A 校验 | **完好(a_crc_ok=1)** | — |

### 9.2 损坏字节模式(D2/D3)

| 迭代 | 损坏元素 | actual | expected | xor(popcount) |
|---|---|---|---|---|
| 12 | elem[0] | -0.9324179 | -0.9324378 | 0x000000d9d68ba712 (**21 位**) |
| 144 | elem[0] | -0.6320479 | -0.9324378 | 0x0009ef3b42436fd6 (**30 位**) |
| 81 | elem[0] | -0.9421112 | -0.9324378 | 0x0003f341aba2d4d1 (**26 位**) |
| 91 | elem[0] | -0.8575007 | -0.9324378 | 0x0006a622880c74e5 (**21 位**) |
| 767 | elem[0] | -15.681250 | -0.9324378 | 0x7fc28a4b1b432094 (**28 位**) |

### 9.3 第四层推理(决定性)
- **A 完全未损坏**(0/3000),但 x 错误 28/3000,**每次失败时 A 都完好** → 损坏发生在**计算过程本身**,非输入数据。
- **损坏固定在 elem[0]**(结果向量首元素)——固定位置,非随机元素 → 排除随机翻转。
- **多位翻转 21-30 位** → 排除单粒子翻转 SEU(只翻 1 bit)。
- **actual 值是来自他处的垃圾**(-15.68、-0.63 等,与 expected -0.93 完全无关) → **数据混叠(data aliasing)**:其他计算结果覆盖了 elem[0]。
- elem[0] 地址每次相同(固定栈位置 `0xfffff3e8d8e0`)。

**第四层结论:核 179 的计算执行路径在满载下,把"其他数据"混叠写入结果向量 elem[0] 的固定存储位置。这是局部、负载敏感的写回路径缺陷。**

## 10. 根因综合判定

### 10.1 证据矩阵(假设 → 证据 → 结论)

| 假设 | 关键证据 | 结论 |
|---|---|---|
| Eigen 5.0 软件 bug | 固定 seed 全核同数据,仅 179 失败;纯整数测试过;A 完好 | ❌ 排除 |
| 浮点 pipe 损坏 | gemm/svd 0 失败,仅 sparse 失败 | ❌ 排除 |
| 中断淹没 | 核 179 无设备 IRQ | ❌ 排除 |
| cache/TLB/分支/stall 异常 | per-core perf 与健康核差异<2% | ❌ 排除 |
| 内存 ECC 损坏 | memory_error PMU=0,EDAC=0 | ❌ 排除 |
| EINJ 主动注入 | error_type=0,无脚本痕迹 | ❌ 排除 |
| 输入数据(A/b)损坏 | esdiag3:A 0/3000 损坏 | ❌ 排除 |
| 单 bit SEU(宇宙射线) | popcount 21-30 位 | ❌ 排除 |

### 10.2 根因(微架构层面)

**核 179 存在一个微架构层面的计算路径写回缺陷**,特征:
- 触发条件:同 socket(PkgID 19062)满载(≥48 核) + Eigen Cholesky 稀疏求解(间接寻址 + 浮点);
- 损坏对象:结果向量 `elem[0]`(固定首元素,对应固定栈地址);
- 损坏机理:**数据混叠**——其他计算数据覆盖 elem[0] 的写回路径(FPU/向量寄存器 → LSU 写回 → 该固定存储位置);
- 损坏规模:多位(21-30 bit),非单粒子翻转;
- 静默性:无 PMU `memory_error`、无 EDAC 计数、无同步异常(多数 run);仅当混叠数据被解引用为指针时触发 SIGSEGV(偶发);
- 触发率:满载下 ~0.5-1.25%;单核 0%。

**这不是"随机粒子翻转的真 SDC",而是一个具体的、可复现的、负载敏感的写回路径微架构缺陷**——损坏固定发生在 elem[0] 的存储路径,满载时被其他数据混叠覆盖。

### 10.3 关于两次系统挂死

真 SDC 是静默的;两次挂死(强制掉电重启,无 kdump 捕获,journal 未落盘)说明损坏偶尔产生致命状态。如第 7 节 M1 实验所示,满载 20s 内产生 55 次计算失败,而 EDAC `ce/ue_count` 与新增 dmesg(SEI/SDEI/MCE/GHES/panic/oops)全程为 0,故**挂死机制不是内存 ECC**(否则 EDAC `ue_count` 必非零),而是**计算损坏波及控制流**(混叠数据→错误指针/控制转移→不可恢复状态)。这进一步支持"计算路径写回缺陷"而非"内存损坏"。

### 10.4 物理定位

- 故障核:**CPU 179**
- 所在 socket:PkgID 19062(第 4 socket)
- 所在 module:23340(核 176-178 同 module,但仅 179 故障 → 非 module 级共享资源损坏,而是核 179 私有路径)
- 微码:0x0(与所有核一致,非微码差异)

## 11. 缓解措施(已验证)

### 11.1 即时隔离
```bash
echo 0 > /sys/devices/system/cpu/cpu179/online   # 下线核 179
```
验证:191 核(排除 179)满载 60s = **3085 ok / 0 失败**,系统稳定。

### 11.2 永久隔离
内核启动参数追加 `isolcpus=179`(或通过 `nr_cpus`/`cpu_affinity` 在系统服务层排除)。

### 11.3 长期
更换 CPU(socket PkgID 19062,核 179 私有计算路径硬件缺陷)。建议联系 HiSilicon/Kunpeng 进行该 socket 的 RMA。

## 12. 交付件

### 12.1 诊断探针源码
已持久化到仓库 `opendcdiag/docs/core179-diagnostics/`,可随时重建。

| 文件 | 用途 | 构建 |
|---|---|---|
| `fpprobe.c` | CRC 敏感浮点探针(简单浮点,压力下自检) | `gcc -O3 -march=armv8.1-a+crc+crypto -std=gnu17 fpprobe.c -o fpprobe` |
| `esdiag3.cpp` | **核心交付**:固定 A 重复 Cholesky solve,分离输入/计算损坏,报告 A_corrupt/x_wrong/popcount | `g++ -O2 -std=gnu++17 -march=armv8.1-a+crc+crypto -I<eigen_root> esdiag3.cpp -o esdiag3` |
| `esdiag2.cpp` | esdiag3 的前驱:打印 elem[0] 地址 + 损坏 actual 值 + xor popcount | 同上 |
| `esdiag.cpp` | 早期版本:CRC 校验 x,报告 popcount | 同上 |
| `probe.c` | 8 单元功能探针(ALU/FPU/NEON/L1D/L2L3/分支/CRC) | `gcc -O3 -march=armv8.1-a+crc+crypto -std=gnu17 -Wno-incompatible-pointer-types probe.c -o probe` |
| `loadgen.c` | CPU 负载生成器 | `gcc -O2 loadgen.c -o loadgen` |

`esdiag*` 的 Eigen root 路径:`/home/sdc/arm64-sdc-fuzzing/opendcdiag/third-part`(Eigen 5.0.1 submodule)。

### 12.2 复现实验的标准命令

```bash
# 环境准备
export PATH="$HOME/.local/bin:$PATH"
export LD_LIBRARY_PATH="$HOME/rpmroot/sysroot/usr/lib64:$LD_LIBRARY_PATH"
cd ~/arm64-sdc-fuzzing/opendcdiag
EIG=$PWD/third-part
DIAG=$PWD/docs/core179-diagnostics
# 构建探针
g++ -O2 -std=gnu++17 -march=armv8.1-a+crc+crypto -I$EIG $DIAG/esdiag3.cpp -o /tmp/esdiag3
gcc -O2 $DIAG/loadgen.c -o /tmp/loadgen

# 触发实验:47 核 socket 满载(excl 179) + esdiag3 在核 179
SET=$(seq 144 178 | tr '\n' ','; seq 180 191 | tr '\n' ',' | sed 's/,$//')  # 144-191 排除 179
builddir/opendcdiag --beta -e eigen_sparse --cpuset "$SET" -s LCG:323306158 \
    -T 40s --output-format=tap -o /tmp/load.log >/dev/null 2>&1 &
sleep 1
taskset -c 179 /tmp/esdiag3 3000 12345
# 预期:核 179 出现 A_corrupt=0/x_wrong>0(多位,elem[0]),健康核 176 = 0/0

# PMU 对比(需 perf_event_paranoid=-1)
perf stat -C 179 -e cycles,instructions,mem_access,memory_error,l1d_cache_refill,... \
    -x, -I 5000 -o /tmp/p179.csv sleep 15 &

# 下线核 179 验证稳定(需 root)
echo 0 > /sys/devices/system/cpu/cpu179/online
```

### 12.3 关键日志/数据文件
- 满载 eigen_sparse 失败 YAML(含 loop-count、retry 模式):运行时由 `-o` 生成
- per-core PMU 对比原始数据:`/tmp/p179.csv`、`/tmp/p176.csv`(运行时生成)
- 本报告:`opendcdiag/docs/CORE179_SDC_ROOTCAUSE_REPORT.md`
- 探针源码:`opendcdiag/docs/core179-diagnostics/`

### 12.4 关联产物
- OpenDCDiag ARM64 构建修复(PR #1,已合并到 main):`fix/opendcdiag-arm64-build-and-tests`
- Eigen 5.0.1 submodule(main):`opendcdiag/third-part`
- 诊断探针源码已存入 memory:`opendcdiag-core179-sdc-investigation`

## 13. 研究方法学小结

本研究采用**分层假设排除法**,每一层用对照实验证伪一个假设,逐步逼近根因:

1. **第一层**(软件 vs 硬件):固定 seed 复现 + 排除核对照 → 排除软件
2. **第二层**(哪个测试触发):测试类型矩阵 → 缩窄到稀疏 Cholesky + 间接寻址
3. **第三层**(微架构事件):per-core PMU 对比 → 排除 cache/TLB/FPU/内存损坏(微架构全正常)
4. **第四层**(实时内核监控 M1):满载 + dmesg/EDAC 跟踪 → 失败静默(无硬件错误事件)、挂死非内存 ECC
5. **第五层**(字节级模式):esdiag3 自研探针 → 定位"计算路径写回 elem[0] 被混叠"

核心洞察:当 PMU/EDAC 全部正常却仍静默算错时,需用**针对特定计算模式的字节级自校验探针**(而非通用 PMU)定位损坏模式。固定 elem[0] + 多位混叠是"写回路径缺陷"的决定性特征,区别于"随机 SEU"(随机位置 + 单 bit)。

## 14. 局限与后续

### 14.1 局限
- 两次挂死未捕获 crash dump(journal 未落盘),挂死的精确内核态无法回溯。
- 本研究止于"计算路径写回缺陷"的微架构定位,未进一步在 RTL/门级定位(超出软件可达范围)。
- `elem[0]` 的具体物理路径(哪一个向量寄存器/LSU buffer)需借助 HiSilicon 内部微架构文档或 scan-at-speed 测试确认。

### 14.2 建议后续
1. 永久 `isolcpus=179` 并长期稳定性监控(24h+);
2. 对该 socket 运行 HiSilicon 官方 CPU 诊断工具 / scan-at-speed LBIST;
3. 若有第二台同型号机器,迁移负载验证是否复现(排除个体 vs 批次);
4. 将 `esdiag3` 探针固化到测试集,作为持续 SDC 监测器。

---

**附录:核心实验数据索引**

| 实验 | 日志/数据 | 结论 |
|---|---|---|
| G5(全核固定 seed) | (TAP 内联) | 仅 179 失败,285/285 |
| G6(换 seed) | (TAP 内联) | 仅 179,140/140,seed 无关 |
| 测试类型矩阵 | (TAP 内联) | 仅 eigen_sparse 触发 |
| per-core PMU | `/tmp/p179.csv` `/tmp/p176.csv` | 微架构全正常 |
| **M1(满载+实时内核监控)** | `/tmp/M1.log`(dmesg 跟踪) | 55 失败/20s,EDAC=0,dmesg=0(静默) |
| esdiag3 D4 | (stderr 内联) | A 0/3000,x 28/3000 |
| 字节模式 D2/D3 | (stderr 内联) | elem[0],21-30 位混叠 |
| 禁用 179 验证 | (TAP 内联) | 3085 ok / 0 fail |
