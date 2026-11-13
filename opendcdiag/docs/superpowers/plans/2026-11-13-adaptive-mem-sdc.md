# adaptive_mem_sdc 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现已批准的 v2 设计（docs/ADAPTIVE_MEM_SDC_DESIGN_20261113.md）：单测试用例 `adaptive_mem_sdc`，运行期探测最宽 SIMD（SVE2>SVE>NEON），按 30 实例优先级序列每组合 30min 扫描，SDC 即停即报组合标签。

**Architecture:** 框架原生 fork_each_test 循环不改动；每子进程 init 时读 shm 墙钟锚点选组合（verify 模式读轮转计数器）；NEON 引擎在主文件（模板实例化 30 个 noinline 热循环），SVE/SVE2 引擎在独立翻译单元（`-march=…+sve2` 编译，本机编过不运行）；脚本层 SIGKILL-on-first-fail 实现即停。

**Tech Stack:** C++（GCC 12.3.1, aarch64, `gnu++23`）、NEON intrinsic + 内联 asm、SVE ACLE（`arm_sve.h`）、POSIX shm（`shm_open`/`mmap`）、Meson、bash 战役脚本。

**Spec:** `docs/ADAPTIVE_MEM_SDC_DESIGN_20261113.md`（v2，已批准；本计划所有编号引用该文档）

## Global Constraints

- 本机鲲鹏 920 = ARMv8.1-A **无 SVE 硬件**；SVE TU 必须在本机**编译通过**（零警告）但运行期永不选中。
- **永不修改框架 fork/auto-seed 机制**（spec §4.0）；不固定 LCG seed。
- 所有 load 走 `__asm__ volatile`（DCE 护栏，NEON 用 `ldr %q0, [%1]`，SVE 用 `ld1d` asm）；store 用 intrinsic（`vst1q_*`/`svst1`）；**dst 永远最后一条 str**；检查纪律 = 每 sweep 一次 `memcmp(dst, expected)`。
- `TEST_LOOP(test, 1<<8)`、`COUNT=1024`、缓冲 `aligned_alloc(64, COUNT*sizeof(vec))`，全部 30 实例统一。
- 冷路径（fill/golden/报表辅助）`__attribute__((noinline))`；golden 在 init 用与热循环**同一内建序列**重算。
- 组合标签必须出现在 `report_fail_msg` 文本内；**禁用 `log_error` 做总结**（会产生 fail 块污染两法交叉）。
- 杀 opendcdiag 只准 **SIGKILL + pgrep 验证**；重编译前先 `cp` 备份 builddir/opendcdiag；构建零新增警告。
- 战役掩码：阶段 1 = `96-178,180-189`(-n 93, 179 下线)，阶段 2 = `96-189`(-n 94, 179 上线)；监控钉 0-7；风扇 AUTO。

## Review Focus

1. **空负载 DCE**：empty 槽的 srcB/srcC 值未消费，intrinsic load 会被删 → 槽静默退化。测试：Task 2 objdump 门专查 empty×ldr3 实例（须见 4 条 ldr、load 与 str 组之间零 ALU/零删除）。
2. **mla golden 假阳性**：收窄掩码在 fill 与 golden 间不一致 → 健康核误报。测试：Task 2 verify 门（93 核 × 30 组合 × ~10 seed 全 0 fail!!!）；收窄源**持久化**（父版 mla L78-80 模式）。
3. **FMA 收缩**：FP64 ldr3 若写成 `(a×b)+c` 会被 `-ffp-contract` 融合成 fmadd → 编码漂移。测试：Task 2 公式钉死 `(a×b)×c` + objdump 门实例 3（FP64×ldr3×str2）无 `fmadd`。
4. **shm 锚点竞态**：后到子进程在创建者写锚点前读取 → 组合时钟错乱。测试：Task 1 verify 门（covfile 30 唯一组合 = 计数器跨子进程共享的实证）+ O_EXCL/ready-flag 模式钉死。
5. **verify 覆盖空转**：fork 循环下若计数器不工作，冒烟只重复 combo 0。测试：Task 1/2/4 的覆盖率断言 `sort -u | wc -l == 30`。

---

### Task 1: 骨架——共享头、shm、组合分发、meson 注册（桩实现）

**Files:**
- Create: `tests/cpu/misc/adaptive_mem_sdc.h`
- Create: `tests/cpu/misc/adaptive_mem_sdc.cpp`
- Modify: `tests/cpu/meson.build`（misc 列表，`neon_rot_ldr_at_top_rowmajor_fp64_str5.cpp` 条目之后，同一守卫块内）

**Interfaces:**
- Produces（后续任务依赖的精确签名）:

```c
// adaptive_mem_sdc.h —— 两引擎共享
enum AdaptDtype { DT_FP64, DT_INT };
enum AdaptLoad  { LOAD_FP64ROT, LOAD_INTROT, LOAD_EMPTY, LOAD_MLA, LOAD_SUB };
enum AdaptSweep { SWEEP_ALT, SWEEP_MONO };
struct ComboDef { AdaptDtype dt; int ldr; int str; AdaptLoad load; const char *label; };
#define ADAPT_COMBO_COUNT 30
extern const ComboDef kComboTable[ADAPT_COMBO_COUNT];   // 精确 30 行见 Step 1
#define ADAPT_SLICE_SECONDS 1800

struct AdaptiveShm {            // shm 布局（创建者一次写 ready/anchor）
    uint32_t ready;             // 0→1（__atomic_store_n release）
    uint32_t verify_ctr;        // __atomic_fetch_add
    uint32_t sdc_flag;          // 检出后置 1（__atomic_store_n）
    struct timespec anchor;     // 墙钟锚点
};
// ⚠️ 跨进程共享内存不用 std::atomic（需 placement-new，进程间不适用）——
// 全部原子操作走 GCC __atomic_* 内建于上述 plain uint32_t 字段。

struct test;                    // 框架前向声明（sandstone.h）
// 引擎入口（Task 2 实现 NEON 版，Task 3 实现 SVE 版；本任务提供桩）
int adaptive_neon_run_combo(struct test *test, int cpu, int combo);
int adaptive_sve_run_combo(struct test *test, int cpu, int combo);   // Task 3 才有真体
```

- [ ] **Step 1: 写 `adaptive_mem_sdc.h`**——上述接口 + `kComboTable` 30 行精确定义（spec §2 表）：

```
#0-5   FP64: (ldr2,str2)(ldr2,str3)(ldr2,str4)(ldr3,str2)(ldr3,str3)(ldr3,str4)，全 LOAD_FP64ROT
#6-9   int,ldr2,str2:  INTROT / EMPTY / MLA / SUB
#10-13 int,ldr2,str3:  同负载序
#14-17 int,ldr2,str4:  同负载序
#18-21 int,ldr3,str2:  同负载序
#22-25 int,ldr3,str3:  同负载序
#26-29 int,ldr3,str4:  同负载序
```

- [ ] **Step 2: 写 `adaptive_mem_sdc.cpp` 桩**——实现：
  - `shm_setup()`：名字 = `"/adaptive_mem_sdc_" + (getenv("ADAPTIVE_MEM_SDC_KEY") ?: "dflt")`；`shm_open(O_CREAT|O_EXCL|O_RDWR)` 成功者为创建者（`ftruncate` 到 `sizeof(AdaptiveShm)`、`mmap`、`clock_gettime(CLOCK_MONOTONIC)` 写 anchor、`ready=1` release）；`EEXIST` 者打开后自旋 `ready==1` acquire。
  - `pick_combo(shm)`：`getenv("ADAPTIVE_MEM_SDC_VERIFY")` 非空 → `shm->verify_ctr.fetch_add(1) % 30`；否则 `min((now-anchor)/ADAPT_SLICE_SECONDS, 29)`。若 `sdc_flag` 已置位 → 返回 -1。
  - ISA 探测：`getauxval(AT_HWCAP2) & HWCAP2_SVE2 → SVE2`；否则 `getauxval(AT_HWCAP) & HWCAP_SVE → SVE`；否则 `HWCAP_ASIMD → NEON`（**SVE2 位在 AT_HWCAP2**，勿查 AT_HWCAP）。
  - covfile：`getenv("ADAPTIVE_MEM_SDC_COVFILE")` 非空时每子进程 init 追加一行 `"<iso时间> <pid> <isa> <mode> <combo>\n"`（`O_WRONLY|O_APPEND|O_CREAT`，单次 `write`）。
  - `test_init`=shm+探测+covfile；`test_run`=选组合（-1 直接 `EXIT_SUCCESS`）→ 按 ISA 分发 `adaptive_{neon|sve}_run_combo`（本任务两者都是桩：仅 `return EXIT_SUCCESS`）；`test_cleanup` 空。`DECLARE_TEST(adaptive_mem_sdc, …)`，`TEST_QUALITY_PROD`。
  - 非 aarch64 守卫与父版文件相同（`#if defined(__aarch64__)` 包实现）。
- [ ] **Step 3: meson 注册**——`tests/cpu/meson.build` misc 列表 `str5` 条目后加一行 `'misc/adaptive_mem_sdc.cpp',`（该 cpp 先不注册 SVE TU，Task 3 再加）。
- [ ] **Step 4: 构建与管线门**（顺序执行）：
  1. `cp builddir/opendcdiag backups/$(date +%Y%m%d)_pre_adaptive_$(sha256sum builddir/opendcdiag | cut -c1-12)/opendcdiag`（先备份！）
  2. `ninja -C builddir` → 零新增警告（已知 -Wrestrict 等除外）
  3. `./builddir/opendcdiag --list | grep adaptive_mem_sdc` → 出现一行
  4. verify 管线证明：`ADAPTIVE_MEM_SDC_VERIFY=1 ADAPTIVE_MEM_SDC_KEY=t1 ADAPTIVE_MEM_SDC_COVFILE=/tmp/cov1.txt timeout 60 taskset -c 0-7 ./builcdiag -e adaptive_mem_sdc -n 4 -T 30s --ignore-os-error --ignore-timeout -o /tmp/t1.log -q`；然后 `awk '$4=="verify"{print $5}' /tmp/cov1.txt | sort -u | wc -l` → **30**（= shm 计数器跨子进程轮转的端到端实证）；`grep -c 'result: fail' /tmp/t1.log` → 0
- [ ] **Step 5: Commit**

```bash
git add tests/cpu/misc/adaptive_mem_sdc.h tests/cpu/misc/adaptive_mem_sdc.cpp tests/cpu/meson.build
git commit -m "feat(arm64): adaptive_mem_sdc 骨架——shm 组合时钟/verify 轮转/ISA 探测/covfile 管线"
```

---

### Task 2: NEON 30 实例热循环引擎（模板 + 填充 + golden）

**Files:**
- Modify: `tests/cpu/misc/adaptive_mem_sdc.cpp`（桩替换为真引擎；`adaptive_mem_sdc.h` 若需补 `#include` 不动接口）

**Interfaces:**
- Consumes: Task 1 的 `kComboTable`/`ComboDef`/shm 接口；父版惯用法（`load_vec` asm volatile、`vst1q` store、`memset_random`、`TEST_LOOP`）。
- Produces: `int adaptive_neon_run_combo(struct test*, int cpu, int combo)` 真体——Task 3 的 SVE 版与之行为对齐（同 fill/golden/检查纪律）。

- [ ] **Step 1: 实现模板热循环**——签名钉死：

```c
template <AdaptLoad LOAD, int LDR, int STR, AdaptSweep SWEEP>
static void __attribute__((noinline)) neon_hot(struct test *test, int cpu,
                                               struct NeonCtx *ctx);
// NeonCtx: { srcA/srcB/srcC/scratch/expected/temp/dst/junk1/junk2 指针, int combo; }
// vec 类型按 LOAD: FP64ROT/INTROT/EMPTY/SUB → uint64x2_t；MLA → uint32x4_t
```

  骨架（`if constexpr` 按 LOAD/LDR/STR/SWEEP 展开，语义与父版逐项对应）：
  - 顶置 `load_vec(&scratch[i])`（值弃）；源 load：LDR==2 → srcA/srcB；LDR==3 → 加 srcC。
  - 中间负载（`i%4` 用**真实索引 i**，降序扫时随 i 反转——父版语义）：
    - `LOAD_FP64ROT`：LDR2 = 父版 `fp64_rot`（vaddq_f64/vsubq_f64/vmulq_f64/vmaxq_f64）；LDR3 槽：`(a+b)+c`/`(a−b)−c`/`(a×b)×c`/`fmax(fmax(a,b),c)`（**禁 `(a×b)+c` 形态**，防 FMA 收缩）。
    - `LOAD_INTROT`：LDR2 = `vaddq_u64/veorq_u64/vandq_u64/vorrq_u64`（父版底盘）；LDR3 = 历史混合对偶式 `a^b^c`/`(a+b)^c`/`a^(b+c)`/`(a^b)+c`（mrn_nuke_3src 原式）。
    - `LOAD_EMPTY`：`res = a`（b/c 仅 volatile load 在场，无 ALU）。
    - `LOAD_MLA`（s32，父版 mla 分解式）：LDR2 槽 = `t=vmulq_s32(sa,sb)`/`vaddq_s32(t,sa)`/`vsubq_s32(sb,t)`/`veorq_u32(a,b)`；LDR3 = `t=a×b`：`res=t`/`res=t+c`/`res=c−t`/`res=a^b^c`。
    - `LOAD_SUB`：LDR2 = `vsubq_u64/veorq_u64/vbicq_u64/vornq_u64`（父版原式）；LDR3 = `(a−b)−c`/`a^b^c`/`a & ~(b|c)`/`a | ~(b&c)`。
  - 尾部 str 组背靠背：STR==2 → `temp,dst`；STR==3 → `temp,junk1,dst`；STR==4 → `temp,junk1,junk2,dst`。
  - `SWEEP_ALT`：`ascending=(sweep&1)==0; i = asc? n : COUNT-1-n`（fp64 父版）；`SWEEP_MONO`：`i=n`（mla/sub 父版）。FP64ROT/INTROT/EMPTY=ALT，MLA/SUB=MONO。
  - 每 sweep 末冷路径 `memcmp(dst, expected)`；不一致 → `report_fail_msg("adaptive_mem_sdc combo#%d [%s/%s/ldr%d/str%d/%s] data miscompare", combo, isa, dtype, ldr, str, label)` + `shm->sdc_flag=1`。每 sweep 迭代末检查 `sdc_flag`，置位即 break。
- [ ] **Step 2: 实例化表 + fill/golden**：
  - 30 个实例经宏列表实例化并填 `neon_combo_fns[30]`（顺序= `kComboTable`）。
  - `fill_sources()`：MLA → 掩码 `vandq_u32(v, vdupq_n_u32(0x0000ffff))` 并**持久化回写源**（父版 mla L78-80 模式）；其余 load 原始随机位。srcC 恒分配（LDR==3 才消费）。
  - `compute_golden()`：init 内用与热循环同一内建序列重算 expected（EMPTY → `expected[i]=srcA[i]`）。fill/golden 均 noinline 冷函数。
  - `adaptive_neon_run_combo`：分配 NeonCtx（含 per-thread temp/dst/junk）→ fill → golden → `TEST_LOOP(test, 1<<8)` 的**每次迭代调用一次 `neon_combo_fns[combo](test, cpu, &ctx)`**（模板体 = 单个完整 sweep 含升/降序内层循环与 sdc_flag 检查；每 sweep 一次间接调用，5.6ms 粒度开销可忽略）。objdump 门按"指令模式同构"判（3 ldr + 四槽轮换 + N 连 str），不要求与父版函数框架逐字节相同。
- [ ] **Step 3: objdump 门**（`nm builddir/opendcdiag | grep neon_hot` 找符号后逐个 `objdump -d --disassemble=`）：
  1. 实例 0（FP64×ldr2×str2×ALT）：3 ldr q、四槽 fadd/fsub/fmul/fmax、双向各 1 组 2 连 `str q`（与 fp64 父版编码同构）
  2. empty×ldr3 实例（#20）：4 ldr q 在场，load 与 str 组之间**零 ALU**
  3. FP64×ldr3×str2（#3）：无 `fmadd`
  4. mla×ldr2×str2（#8）：见 `vmul`+`vadd`/`vsub` 分解形态（无融合 `mla` 指令）
- [ ] **Step 4: 主机 verify 门**（真 golden 正确性证明）：
  - 179 下线：`echo 0 | sudo tee /sys/devices/system/cpu/cpu179/online`
  - `ADAPTIVE_MEM_SDC_VERIFY=1 ADAPTIVE_MEM_SDC_KEY=t2 ADAPTIVE_MEM_SDC_COVFILE=/tmp/cov2.txt timeout 200 taskset -c 96-178,180-189 ./builddir/opendcdiag -e adaptive_mem_sdc -n 93 -T 60s --ignore-os-error --ignore-timeout -o /tmp/t2.log -q`
  - 期望：`grep -c 'result: fail' /tmp/t2.log` = **0** 且 `grep -c miscompare /tmp/t2.log` = **0**（两法交叉）；`awk '$4=="verify"{print $5}' /tmp/cov2.txt | sort -u | wc -l` = **30**
  - 完成后 179 上线恢复
- [ ] **Step 5: Commit**

```bash
git add tests/cpu/misc/adaptive_mem_sdc.cpp tests/cpu/misc/adaptive_mem_sdc.h
git commit -m "feat(arm64): adaptive_mem_sdc NEON 30 实例模板引擎——5 负载×ldr×str×扫序 + objdump/verify 双门"
```

---

### Task 3: SVE/SVE2 翻译单元 + meson SVE 库 + 运行期分发

**Files:**
- Create: `tests/cpu/misc/adaptive_mem_sdc_sve.cpp`
- Modify: `tests/cpu/meson.build`（aarch64 守卫块内新增 `static_library`，仿 `tests_hsw_a` 先例 L620-638）
- Modify: `tests/cpu/misc/adaptive_mem_sdc.cpp`（分发到 `adaptive_sve_run_combo`；删除 Task 1 桩）

**Interfaces:**
- Consumes: `adaptive_mem_sdc.h` 全部接口；Task 2 引擎行为规格（同表/同 fill/同 golden/同检查纪律）。
- Produces: `int adaptive_sve_run_combo(struct test*, int cpu, int combo)` 真体（SVE 与 SVE2 共码，运行期由主文件 HWCAP 决定是否调用）。

- [ ] **Step 1: meson SVE 库**——aarch64 守卫块内：

```meson
# adaptive_mem_sdc SVE/SVE2 引擎：本机(920)编译通过但运行期不选中
sve_march = cpp.compiles('#include <arm_sve.h>\nint f(void){return 0;}',
                         args: ['-march=armv9-a+sve2']) ? ['-march=armv9-a+sve2'] : ['-march=armv8.2-a+sve2']
tests_sve_a = static_library('tests_sve',
    sources: ['misc/adaptive_mem_sdc_sve.cpp'],
    build_by_default: false,
    include_directories: [tests_common_incdirs],
    cpp_args: [tests_common_cpp_args, sve_march],   # sve_march 必须在 common 之后（后写的 -march 生效）
)
sandstone_tests += [tests_sve_a]
```

  （两候选都编不过则 `error()`——spec §5 编译门。）
- [ ] **Step 2: 写 SVE 引擎**——`#include <arm_sve.h>`，与 NEON 引擎同构：
  - 缓冲 = `COUNT × svcntd()*8` 字节（运行期 VL 查询后分配）；谓词 `svbool_t pg64=svptrue_b64()`（u64/f64 路径）/`pg32=svptrue_b32()`（mla s32 路径），run_combo 开头建一次。
  - **load 必须 asm volatile**（SVE intrinsic 同样会被 DCE——empty 槽是暴露点）：`__asm__ volatile("ld1d %0.d, p0/z, [%1]" : "=w"(out) : "r"(addr), "w"(pg) : "memory")` 形态封装 `sv_load_u64/sv_load_f64`；mla 路径 `ld1w`。store 用 `svst1_u64(pg,…)` intrinsic。
  - 负载公式与 NEON 逐槽相同（`svadd_f64/svsub_f64/svmul_f64/svmax_f64`；`svadd_u64/sveor_u64/svand_u64/svorr_u64`；mla `svmul_s32/svadd_s32/svsub_s32/sveor_s32`；sub `svsub_u64/svbic_u64/svnot+svorr`——ORN 按 spec §3 用 `svorr(a, svnot(b))`）。
  - 帧内头注释声明：SVE 路径本机不可运行验证，运行时正确性属 920B/950 后续战役（spec §8）。
- [ ] **Step 3: 主文件分发**——探测结果为 SVE2/SVE（Task 1 Step 2 的 HWCAP2 修正口径）→ `adaptive_sve_run_combo`，NEON → `adaptive_neon_run_combo`；covfile 行的 isa 字段用探测结果。
- [ ] **Step 4: 门**：
  1. 备份 → `ninja -C builddir` 零新增警告（SVE TU 含）
  2. `nm builddir/opendcdiag | grep adaptive_sve_run_combo` → 符号在场
  3. `objdump -d builddir/opendcdiag --disassemble=<sve符号>` → 见 `ld1d`/`st1d`/`fadd`/`fmul`（.d 形态）真实编码；empty×ldr3 实例 4 条 load 在场（asm 级 DCE 护栏证明）
  4. 本机运行验证（确认分发正确选 NEON）：verify 模式 30s 跑 → covfile 全部行 `isa=NEON` 且 30 组合覆盖
- [ ] **Step 5: Commit**

```bash
git add tests/cpu/misc/adaptive_mem_sdc_sve.cpp tests/cpu/misc/adaptive_mem_sdc.cpp tests/cpu/meson.build
git commit -m "feat(arm64): adaptive_mem_sdc SVE/SVE2 引擎（armv9-a+sve2 编译期就绪）+ HWCAP 分发"
```

---

### Task 4: 战役脚本（两阶段 + SIGKILL-on-first-fail 看门狗）

**Files:**
- Create: `docs/20261113/adaptive_mem_sdc/run_adaptive.sh`（模板 = `docs/20261113/fp64_str45_ab/run_str45.sh`，已验证协议）

**Interfaces:**
- Consumes: builddir 二进制（Task 3 产物，指纹当时回填脚本常量）；`ADAPTIVE_MEM_SDC_{KEY,VERIFY,COVFILE}` 三个环境变量契约。
- Produces: 实盘 `/home/sdc/adaptive_mem_sdc/{phase1,phase2}/`（run.log/monitor.log/temp_all.log/env_logger.out/covfile.txt/STATUS）+ `series_summary.txt`。

- [ ] **Step 1: 写脚本**——在 run_str45.sh 骨架上改：
  - 指纹门：`BINFP` 常量 = Task 3 构建后的 sha256 前 12（不匹配落 ABORT 退出）。
  - 频率最高分支（spec §6）：`/sys/devices/system/cpu/cpu0/cpufreq/scaling_governor` 存在则 best-effort `echo performance`（失败非致命）；本机不存在该路径则跳过。
  - 阶段 1（verify）：179 下线（沿用 str45 脚本核态配置段：178 上/190,191 下/179 下）；env `VERIFY=1 KEY=<key>_p1 COVFILE=$D/covfile.txt`；`taskset -c 96-178,180-189 -n 93 -T 60s`；收数后断言两法 0 fail!!! 且 `awk '$4=="verify"{print $5}' covfile.txt | sort -u | wc -l` = 30，任一不满足落 STATUS=verify_fail 并停止。
  - 阶段 2（正式）：`sleep 60`；179 上线；env `KEY=<key>_p2 COVFILE=…/covfile_p2.txt`（**新 key = 新锚点**，从阶段 2 首子进程重新计时）；`-T 16h -n 94 taskset -c 96-189` 后台起；**看门狗循环**（每 10s）：`grep -q 'result: fail' run.log` → 提取 `grep -m1 'combo#' run.log` 组合标签行 → `kill -9 <主pid>` → `pgrep -x opendcdiag` 复验（铁律）→ monitor.log 写总结（组合四元组/第几分钟/fail 行原文）→ STATUS=sdc_caught；`-T` 自然到期 → STATUS=done。监控栈（temp_monitor_5s 钉 0-7、watchdog_cont 98°C×2、sdc_env_logger）沿用 str45 脚本逐字。
  - 收尾：`rm -f /dev/shm/adaptive_mem_sdc_${key}_p*`（清理 shm）。
- [ ] **Step 2: 阶段 1 单独实跑门**——脚本支持 `PHASE1_ONLY=1 bash run_adaptive.sh`：在主机跑通 verify 阶段并检查 STATUS/覆盖率（产物即 Task 5 阶段 1 的正式结果，可复用不重跑）。
- [ ] **Step 3: Commit**

```bash
git add docs/20261113/adaptive_mem_sdc/run_adaptive.sh
git commit -m "feat(arm64): adaptive_mem_sdc 战役脚本——两阶段协议+组合覆盖率断言+SIGKILL 即停看门狗"
```

---

### Task 5: 正式役 + 收尾

**Files:**
- Create: `docs/20261113/adaptive_mem_sdc/RESULTS.md`（中文，spec §7 验收口径）
- 记忆存档：`~/.claude/projects/-home-sdc-root-arm64-sdc-fuzzing/memory/` 新档 + MEMORY.md 索引行

**Interfaces:**
- Consumes: Task 4 脚本；本机历史基线（FP64 冠军 5.62/min @96-189）。

- [ ] **Step 1: 备份二进制 + 脱机启动**——`cp builddir/opendcdiag backups/20261113_adaptive_<fp>/`；`setsid nohup bash run_adaptive.sh > runner.out 2>&1 < /dev/null &`；启动 10s 后检查 monitor.log 核态行与 covfile 开始增长。
- [ ] **Step 2: 定时检查**——预计实例 0（冠军配方）几分钟内命中；安排 ~40min 后一次性检查（STATUS / fail 块组合标签 / covfile combo 分布），若仍在跑按序下探属正常，安排最终检查（-T 16h 兜底）。
- [ ] **Step 3: 收数验收**（spec §7.3/7.4）：
  - 命中：恰好 1 个 fail 块、含 `combo#N [isa/dtype/ldr/str/load]`、miscompare 文本在场；id 行三字段互证归因核号；monitor.log 有组合总结行。
  - 全扫完：`exit:pass`、0 fail 块 = 0 miscompare（两法交叉），covfile 显示 30 组合各 ~30min 推进。
- [ ] **Step 4: 写 RESULTS.md + 记忆**（含 objdump 门与 verify 覆盖证据的引用）。
- [ ] **Step 5: Commit**

```bash
git add docs/20261113/adaptive_mem_sdc/RESULTS.md
git commit -m "docs(arm64): adaptive_mem_sdc 首役结果——组合命中/全扫结论 + 验收证据"
```
