# sdc-fuzzing — 100 个 core179 SDC 复现用例生成机制

**日期:** 2026-08-07
**目标:** 自动化生成 100 个 SDC 检测用例,每个用例都能复现 core179 核 SDC 问题。
**依据:** [CORE179_SDC_ROOTCAUSE_REPORT.md](CORE179_SDC_ROOTCAUSE_REPORT.md) §11.2 根因 + §10.5 libc-only MRU + §11.6 E2E。

## 1. 机制总览

`sdc-fuzzing` 是一个**用例生成机制**(generator)+**负载编排器**(orchestrator)+**验证器**(verifier)的组合,
产出 100 个 opendcdiag 标准 sandstone 测试(`sdc_fuzz_000`..`sdc_fuzz_099`),每个用例:

1. **链接 Eigen 机器码**(`SimplicialCholesky::factorize()` numeric 列更新),即经验证的 core179 SDC 触发序列(报告 §10.4:纯 C 全不触发,只有 Eigen 编译产物触发);
2. **保留全部触发前提**:core 179 单线程 + 同 socket(PkgID 19062)满载(≥47 核) + N≥256 + numeric factorize;
3. **检测损坏**:CRC32(整段 x)与 golden 比,不等即 `report_fail_msg` 报告,并记录 `elem[0]` actual/golden + xor popcount + cluster 标签。

## 2. 为什么 100 个用例"不同"且都能复现同一故障家族

报告 §11.2 根因:core179 乱序执行引擎在 numeric factorize 列更新循环下的**状态泄漏**,
可疑泄漏点 = **物理寄存器重命名表 / ROB / LSU store buffer** 三者。用户明确"core179 核存在多个逻辑单元故障"。

100 个用例按这三个可疑泄漏点**分簇** × 触发前提参数变体:

| 簇 | 数量 | 偏向的泄漏点 | 构造 |
|---|---|---|---|
| **rename** | 34 | 物理寄存器重命名表(长存活 d4 累加器跨内层循环,最长占用) | 主要 mode 1 numeric-only(重命名表最长持续占用,§10.2 触发率最高);N 256/384/512 改变列循环深度 |
| **rob** | 33 | ROB / 投机状态(长依赖链填满执行窗口) | mode 0 compute-both:symbolic 刷新 ROB 状态后紧邻 numeric,暴露跨阶段状态泄漏(§10.2 状态泄漏签名) |
| **lsu** | 33 | LSU store buffer(间接寻址写回压力) | mode 1 + 稀疏度/nnz 变体(seed 改密度) + b 向量变体;差分 perf:Eigen l1d_refill 4×、mem_access 2.5× 纯 C(§10.4) |

每个用例 = {簇, N, matrix_seed, mode, b_seed} 确定性派生(无随机),100 个组合覆盖三可疑泄漏点 × 触发前提参数空间。
差异维度全部经验证不破坏触发(§10.3 N≥256 均触发固定 elem[0];§5 两 seed 都触发全 179;§10.2 numeric-only 与 compute-both 都触发;§8 损坏在写回与 b 无关)。

## 3. 文件清单

```
opendcdiag/
├── scripts/
│   ├── generate_sdc_fuzz_cases.py   # 生成器:吐出 100 case_NNN_*.cpp + meson.build + cases_index.csv
│   ├── sdc_fuzz_run.sh              # 负载编排器:47 核满载 + 单用例/批跑/子集 在 core 179
│   └── sdc_fuzz_verify.py           # 验证器:同窗口 MRU 对照 + 签名校验
├── tests/cpu/arm64/
│   ├── meson.build                  # 加了 subdir('sdc_fuzzing')
│   └── sdc_fuzzing/
│       ├── meson.build              # 自动生成,列 100 case 文件,链 eigen3_dep
│       ├── sdc_fuzz_case_template.h # 共享触发/CRC/判定逻辑(镜像 libc-only MRU)
│       ├── case_000_rename.cpp ... case_099_rename.cpp  # 100 个用例(自动生成)
│       └── cases_index.csv          # 用例参数清单
└── builddir_sdc/                    # sdc-owned 构建目录
    └── opendcdiag                   # 含 100 个 sdc_fuzz_* 测试的二进制
```

## 4. 构建与运行

### 4.1 生成用例(如需重新生成)
```bash
cd ~/arm64-sdc-fuzzing/opendcdiag
python3 scripts/generate_sdc_fuzz_cases.py   # 产出 100 case + meson.build + index
```

### 4.2 构建(需 meson+ninja + Eigen 5.0 + sysroot,见 [[opendcdiag-rootless-build]])
```bash
export PATH="$HOME/.local/bin:$PATH"
SR=$HOME/rpmroot/sysroot
export PKG_CONFIG_PATH="$SR/usr/lib64/pkgconfig" PKG_CONFIG_SYSROOT_DIR="$SR"
export CXXFLAGS="-isystem $SR/usr/include" CFLAGS="-isystem $SR/usr/include"
export LDFLAGS="-L$SR/usr/lib64 -Wl,-rpath,$SR/usr/lib64"
meson setup builddir_sdc --buildtype=debugoptimized -Dssl_link_type=dynamic
ninja -C builddir_sdc opendcdiag -j8
# 确认 100 个用例已注册:
LD_LIBRARY_PATH=$SR/usr/lib64 builddir_sdc/opendcdiag --beta --list | grep -c sdc_fuzz_  # 期望 200
```

### 4.3 运行单个用例(手动)
```bash
DIAG=~/arm64-sdc-fuzzing/opendcdiag/docs/sdc1-01-02-core179-diagnostics
SET=$(echo $(seq 144 178) $(seq 180 191) | tr ' ' ',')   # 47 核 socket(排除 179)
# ⚠️ 负载必须是 eigen_sparse(报告 §13.2 标准负载),不是 loadgen!
# loadgen 简单循环不产生稀疏 Cholesky 指令序列,无法激活 core179 触发。
timeout 80 builddir_sdc/opendcdiag --beta -e eigen_sparse --cpuset "$SET" \
    -s LCG:323306158 -T 60s --output-format=tap -o /dev/null >/dev/null 2>&1 &
sleep 4
# 在 179 上跑用例:
LD_LIBRARY_PATH=$HOME/rpmroot/sysroot/usr/lib64 \
  taskset -c 179 builddir_sdc/opendcdiag --beta -e sdc_fuzz_000 \
    --cpuset 179 -T 50s --output-format=tap -o /dev/null
pkill -f "eigen_sparse --cpuset"; wait
```

### 4.4 用编排器(自动起停 eigen_sparse 负载)
```bash
scripts/sdc_fuzz_run.sh single sdc_fuzz_000 50   # 单用例 50s
scripts/sdc_fuzz_run.sh batch                    # 全 100 个(每个默认 60s,耗时较长)
scripts/sdc_fuzz_run.sh subset 000,050,099 50     # 子集
```

### 4.5 全 100 用例复现驱动(证明每个用例都能复现)
```bash
# 在重试窗口中逐个跑用例直到复现 core179 签名(eigen_sparse 负载)
python3 scripts/sdc_fuzz_reproduce_all.py --start 0 --end 100 \
    --per-window-dur 50 --max-attempts 12 --mru-iters 2500
# 产出 reproduction_report.md + reproduction_result.csv
```

## 5. 验证:100/100 复现的判定方法学(重要)

### 5.1 关键发现:负载源必须是 eigen_sparse,不是 loadgen
2026-08-07 实测证明:**触发只在 47 核负载是 `opendcdiag -e eigen_sparse`(稀疏 Cholesky 指令序列)时激活**。
用简单 `loadgen` 循环做 47 核负载 → mrueig 在 179 上 0/2000、0/4000 fail(休眠,负载错误);
用 `eigen_sparse` 负载 → mrueig 在 179 上 2/2000 fail,sdc_fuzz 用例多次 fail(签名一致)。
这本身就是报告的核心结论之一(触发需要稀疏 Cholesky 的特定指令序列,§10.4)。
→ 所有编排/验证脚本均用 **eigen_sparse 作负载源**,禁止用 loadgen。

### 5.2 触发的瞬态性
core179 SDC 触发是**瞬态/负载窗口敏感**的(报告 §15.1:"有的窗口 6-24/3000,有的 0/3000")。
触发率 ~0.5-1%/iter(活跃时)。所以单个短时 run 可能 0 fail(活跃窗口内也如此);
需要 **重试窗口**驱动每个用例直到复现。

### 5.3 判定:用例"复现 core179 SDC"的标准
- 用例 fail 并输出签名:`core179 SDC: x crc mismatch ... elem[0]=X (golden Y) popcount=N bits [cluster]`
- 签名特征:固定 elem[0] + 多位 popcount(10-32 bit),排除单 bit SEU(1 bit)
- 用 `scripts/sdc_fuzz_reproduce_all.py` 在重试窗口中逐个跑,直到每个用例都捕获到该签名

### 5.4 运行复现驱动
```bash
python3 scripts/sdc_fuzz_reproduce_all.py --start 0 --end 100 \
    --per-window-dur 50 --max-attempts 12 --mru-iters 2500
# 每个 50s 窗口:eigen_sparse 负载 + 用例在 179 + MRU 同窗口对照
# 用例一旦 fail 且签名校验通过(elem[0]+popcount≥10),标记 REPRODUCED,继续下一个
# 产出 reproduction_report.md + reproduction_result.csv
```

### 5.5 验证器(同窗口 MRU 对照)
```bash
python3 scripts/sdc_fuzz_verify.py --subset 5 --per-case-dur 50 --mru-iters 2500   # 冒烟
python3 scripts/sdc_fuzz_verify.py --per-case-dur 50 --mru-iters 2500              # 全 100
```

### 5.6 当前状态(实测)
- **触发已激活**:用 eigen_sparse 负载,mrueig 2/2000 fail,sdc_fuzz_000 在 50s 内 11 次 fail(popcount 18-25 bits)。
- **3 用例子集复现验证**(2026-08-07,sdc_fuzz_reproduce_all.py start=0 end=3):
  - sdc_fuzz_000 (rename,N=256): window 1 复现,popcount=21 bits
  - sdc_fuzz_001 (rob,N=384): window 1 复现,popcount=15 bits
  - sdc_fuzz_002 (lsu,N=512): window 1 复现,popcount=14 bits
  - **3/3 REPRODUCED**,每个都有 core179 签名(elem[0]+多位)。
- **全 100 用例复现**:由 `sdc_fuzz_reproduce_all.py --start 0 --end 100` 驱动,日志 `/tmp/sdc_fuzz_reproduce_all.log`。

## 6. 损坏签名(与 MRU 一致)

每个用例 fail 时,`report_fail_msg` 输出形如:
```
core179 SDC: x crc mismatch (0x000000d9 vs golden 0x1f89120c) elem[0]=-0.932418 (golden 0.0795441) popcount=21 bits [register-rename-table]
```
- `elem[0]`:损坏固定在结果向量首元素(报告 §8.2,固定栈地址);
- `popcount`:xor(actual,golden) 的位数,core179 SDC 为多位(10-32 bit),区别于单 bit SEU(1 bit);
- `[cluster]`:该用例偏向的可疑泄漏点标签。

## 7. 与已有诊断的关系

- 本机制**复用** libc-only MRU 的触发逻辑(`mru_eigenmc.c`/`esdiag_phase2.cpp` 的 LCG RNG、矩阵构造、CRC、mode 分支),但以 **opendcdiag 标准 sandstone 测试**形态集成(用 `DECLARE_TEST` + `report_fail` + `--cpuset` 调度),即报告 §15.2 第 4 条"固化到 OpenDCDiag 测试集,作为持续 SDC 监测器"。
- libc-only MRU 仍是**黄金对照**(验证器用它做同窗口一致性判定)。
