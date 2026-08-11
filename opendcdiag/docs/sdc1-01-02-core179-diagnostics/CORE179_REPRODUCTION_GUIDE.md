# 核心 179 SDC 故障快速复现方案

**创建日期:** 2026-08-11
**目标:** 在最小步骤、最短时间内复现核 179 的静默 SDC 故障,并提供对照实验确认故障特异性。
**配套文档:** [CORE179_SDC_ROOTCAUSE_REPORT.md](CORE179_SDC_ROOTCAUSE_REPORT.md)(根因分析)、[CORE179_SDC_DIAGNOSTIC_PROBES.md](CORE179_SDC_DIAGNOSTIC_PROBES.md)(探针索引)、[build_mru_eigenmc.sh](build_mru_eigenmc.sh)(MRU 构建脚本)
**已验证:** 本方案于 2026-08-11 在本机(4 路 Kunpeng 920,192 核,openEuler 24.03 SP3)端到端实跑通过。

---

## 1. 复现原理(三要素)

核 179 SDC 是**负载敏感的乱序执行引擎状态泄漏缺陷**,触发需同时满足三个条件,缺一不可:

| 要素 | 要求 | 本机对应 |
|---|---|---|
| ① 故障核 | 核 179 | CPU 179,PkgID 19062,Module 23340 |
| ② 同 socket 满载 | 同 socket ≥47 核满载压力 | cpu144–191 排除 179 后 47 核 |
| ③ 矩阵规模 | N≥256(规模阈值) | MRU 内置 N≥256,已满足 |

**为什么用 MRU 而不是直接 opendcdiag:** 报告 §10.4 证伪了所有纯 C 重写变体(0 触发)——触发的是 Eigen 模板展开后的**精确机器码序列**(supernodal factorize 列更新循环:标量 fmsub + 间接 ldr/str + 长存活 d4 累加器 + 每次调用 malloc/free 工作区),GCC 无法从重写源码复现。故 MRU 采用"纯 C 驱动 + Eigen 编译机器码对象"形式,`ldd` 仅 libc+libm,满足 DFT/量产筛选向量"零第三方库依赖"约束。

**故障签名(判定依据):**
- x-crc mismatch(求解结果向量 CRC 不匹配)
- 固定损坏 elem[0](结果向量首元素,非随机位置)
- 多位翻转 21-32 bit(数据混叠,非单 bit SEU)
- 偶发 SEGV(混叠数据被解引用为指针时)
- 静默:无 PMU `memory_error`、无 EDAC 计数、无同步异常

---

## 2. 前置检查

```bash
# 1. 核 179 在线
cat /sys/devices/system/cpu/cpu179/online                              # 应为 1
# 2. 核 179 在第 4 socket (PkgID 19062)
cat /sys/devices/system/cpu/cpu179/topology/physical_package_id       # 应为 19062
# 3. opendcdiag 二进制存在 (本机用 builddir_sdc,非 builddir)
ls -l /home/sdc/sdc-fuzzing/opendcdiag/builddir_sdc/opendcdiag
# 4. Eigen 源码树存在 (vendored,非 submodule)
ls -d /home/sdc/sdc-fuzzing/opendcdiag/third-part/Eigen
# 5. 编译器
g++ --version | head -1; gcc --version | head -1
```

若核 179 已被下线(`online=0`,报告 §12.1 的即时隔离措施),需先恢复:
```bash
echo 1 > /sys/devices/system/cpu/cpu179/online   # 需 root
```

---

## 3. 路径适配说明(重要)

本方案已按本机实际布局修正路径,与根因报告 §13.2 的标准命令有两处差异:

| 项 | 报告 §13.2 假设 | 本机实际 | 处理 |
|---|---|---|---|
| 仓库根 | `~/arm64-sdc-fuzzing/opendcdiag` | `/home/sdc/sdc-fuzzing/opendcdiag` | 全路径用绝对路径 |
| 构建目录 | `builddir/` | `builddir_sdc/` | 二进制取 `builddir_sdc/opendcdiag` |
| Eigen 源 | `EIG` 默认 `$HOME/arm64-sdc-fuzzing/...` | `third-part` 在 `/home/sdc/sdc-fuzzing/...` | `build_mru_eigenmc.sh` 需通过 `export EIG=...` override |

下文步骤已包含这些修正,可直接复制执行。

---

## 4. 复现步骤

### 步骤 1:构建 MRU(约 10 秒)

```bash
DIAG=/home/sdc/sdc-fuzzing/opendcdiag/docs/sdc1-01-02-core179-diagnostics
OD=/home/sdc/sdc-fuzzing/opendcdiag/builddir_sdc/opendcdiag
export EIG=/home/sdc/sdc-fuzzing/opendcdiag/third-part   # 必须 override,脚本默认路径不匹配本机

bash $DIAG/build_mru_eigenmc.sh
# 产物:$DIAG/mrueig,ldd 应仅显示 libc + libm
ldd $DIAG/mrueig
```

### 步骤 2:单核冒烟(负对照,应 0 fail)

确认 MRU 正常工作 + 验证"单核不触发"特性。

```bash
timeout 60 taskset -c 179 $DIAG/mrueig 500 12345
# 预期:RESULT eigen-MC MRU: 0/500 fails
```

### 步骤 3:满载触发(核心步骤,复现故障)

**安全约束:** 47 核 socket 满载 + 单次 ≤75s + `timeout` 包裹。**禁止全 192 核长跑**(报告 §11.3:早期两次长跑导致系统挂死,掉电复位;挂死根因是计算损坏波及控制流,非内存 ECC)。

```bash
# 后台:47 核 socket 满载(144-191 排除 179),60s
SET=$(echo $(seq 144 178) $(seq 180 191) | tr ' ' ',')
timeout 75 $OD --beta -e eigen_sparse --cpuset "$SET" -s LCG:323306158 \
    -T 60s --output-format=tap -o /tmp/core179_load.log >/dev/null 2>&1 &
sleep 2

# 前台:核 179 单线程跑 MRU
timeout 70 taskset -c 179 $DIAG/mrueig 3000 12345
# 预期:6-24/3000 fails (elem[0] 多位混叠),偶发 SEGV
wait
```

### 步骤 4:健康核对照(应 0 fail,证明核特异性)

同样负载窗口,改在健康核 176(同 module,核 176-178 同 module 但仅 179 故障)上跑 MRU。

```bash
SET=$(echo $(seq 144 175) $(seq 177 191) | tr ' ' ',')   # 排除 176(对照核)
timeout 75 $OD --beta -e eigen_sparse --cpuset "$SET" -s LCG:323306158 \
    -T 60s --output-format=tap -o /tmp/core179_load2.log >/dev/null 2>&1 &
sleep 2
timeout 70 taskset -c 176 $DIAG/mrueig 3000 12345
# 预期:RESULT eigen-MC MRU: 0/3000 fails
wait
```

---

## 5. 判定标准

| 实验 | 配置 | 预期结果 | 验证什么 |
|---|---|---|---|
| 步骤 2 | 核 179 单核无负载 | 0 fail | MRU 正常 + "单核不触发"特性 |
| 步骤 3 | 核 179 + 47 核满载 | **6-24/3000 fails** | **故障复现** ✅ |
| 步骤 4 | 核 176 + 47 核满载 | 0 fail | 核 179 特异(非全局噪声) |

**三组对照全部符合预期 → 复现确认。** 仅步骤 3 出 fails、其余两组 0 fails,即可判定为核 179 的负载触发 SDC,排除 MRU 自身 bug / 全局噪声 / 软件确定性缺陷。

### 2026-08-11 本机实跑结果(已验证)

| 实验 | 结果 |
|---|---|
| 满载 179(步骤 3) | **8/3000 fails**(k=4/83/105/132/159/224/233/246)+ 1 SEGV ✅ |
| 单核 179(步骤 2) | 0/500 ✅ |
| 满载 176(步骤 4) | 0/3000 ✅ |

故障签名样例输出:
```
eigen-MC MRU: golden x-crc=0x1f89120c x[0]=0.079544081970445032 nnz=3488
k=4   x-crc mismatch (0x7388f7d3 vs 0x1f89120c) x[0]=0.0795447 (golden 0.0795441)
k=83  x-crc mismatch (0x0616c942 vs 0x1f89120c) x[0]=0.0794385 (golden 0.0795441)
...
timeout: the monitored command dumped core     # 偶发 SEGV,预期行为
```

---

## 6. 一键脚本(可选)

将步骤 1–4 封装为单脚本,方便重复执行:

```bash
#!/bin/bash
# repro_core179.sh — 一键复现核 179 SDC,含三组对照
set -e
DIAG=/home/sdc/sdc-fuzzing/opendcdiag/docs/sdc1-01-02-core179-diagnostics
OD=/home/sdc/sdc-fuzzing/opendcdiag/builddir_sdc/opendcdiag
export EIG=/home/sdc/sdc-fuzzing/opendcdiag/third-part

echo "=== 步骤 1: 构建 MRU ==="
bash $DIAG/build_mru_eigenmc.sh

echo "=== 步骤 2: 单核 179 冒烟 (预期 0 fail) ==="
timeout 60 taskset -c 179 $DIAG/mrueig 500 12345

echo "=== 步骤 3: 满载 179 (预期 6-24/3000 fails) ==="
SET=$(echo $(seq 144 178) $(seq 180 191) | tr ' ' ',')
timeout 75 $OD --beta -e eigen_sparse --cpuset "$SET" -s LCG:323306158 \
    -T 60s --output-format=tap -o /tmp/core179_load.log >/dev/null 2>&1 &
sleep 2
timeout 70 taskset -c 179 $DIAG/mrueig 3000 12345 || true
wait 2>/dev/null

echo "=== 步骤 4: 满载 176 对照 (预期 0 fail) ==="
SET=$(echo $(seq 144 175) $(seq 177 191) | tr ' ' ',')
timeout 75 $OD --beta -e eigen_sparse --cpuset "$SET" -s LCG:323306158 \
    -T 60s --output-format=tap -o /tmp/core179_load2.log >/dev/null 2>&1 &
sleep 2
timeout 70 taskset -c 176 $DIAG/mrueig 3000 12345
wait 2>/dev/null
echo "=== 完成 ==="
```

---

## 7. 安全约束与缓解

| 约束 | 原因 | 措施 |
|---|---|---|
| 单次满载 ≤75s | 长跑可能触发系统挂死(报告 §11.3,两次掉电复位) | 所有满载命令用 `timeout 75` 包裹 |
| 不全 192 核长跑 | 挂死根因是计算损坏波及控制流,非内存 ECC(EDAC 全程 0) | 仅用 47 核 socket 满载 |
| 偶发 SEGV | 混叠数据被解引用为指针 | MRU 步骤 3 加 `\|\| true`,SEGV 属预期 |
| 长期稳定 | 生产环境隔离故障核 | `echo 0 > /sys/devices/system/cpu/cpu179/online`(报告 §12.1) |

**永久隔离(需 root,重启失效需配合内核参数):**
```bash
echo 0 > /sys/devices/system/cpu/cpu179/online                 # 即时下线
# 或内核启动参数永久隔离:
# isolcpus=179
```
报告 §12.1 验证:191 核(排除 179)满载 60s = 3085 ok / 0 失败,系统稳定。

---

## 8. 触发率波动说明

故障属负载敏感型瞬态缺陷,触发率随负载窗口波动(报告 §15.1):同一 47 核满载,有的窗口 6-24/3000,有的 0/3000。

- 若步骤 3 跑出 0 fails,**不等于故障消失**——可能是恰好落在非活跃窗口。
- 处理:重复步骤 3 两三次,或延长 `mrueig` 迭代数到 5000–10000;在故障活跃窗口内对照 Eigen 参考探针(`esdiag_phase2.cpp`,报告 §13.2 方式 B)同跑以确认一致性。
- 本机 2026-08-11 实跑首次即出 8/3000,属活跃窗口。

---

## 9. 关联文档

- [CORE179_SDC_ROOTCAUSE_REPORT.md](CORE179_SDC_ROOTCAUSE_REPORT.md) — 完整根因分析(6 层假设排除法)
- [CORE179_SDC_DIAGNOSTIC_PROBES.md](CORE179_SDC_DIAGNOSTIC_PROBES.md) — 全部探针索引与构建说明
- [CORE179-SDC-related-instruction-funcion-unit.md](CORE179-SDC-related-instruction-funcion-unit.md) — 物理层假说补充
- [build_mru_eigenmc.sh](build_mru_eigenmc.sh) — MRU 构建脚本
- [reproduction_report.md](reproduction_report.md) — 早期复现记录
- [reproduction_result.csv](reproduction_result.csv) — 早期复现数据
