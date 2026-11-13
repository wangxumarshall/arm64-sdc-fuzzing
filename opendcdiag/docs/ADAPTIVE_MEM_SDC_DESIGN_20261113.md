# 自适应访存类 SDC 测试用例（adaptive_mem_sdc）设计文档 v2 —— 2026-11-13

> 状态：**待用户批准**（批准后进入实现）
> v1 决策记录：2026-11-13 会话，5 个设计点用户拍板（§1.3）
> v2 修订：builder check 抓出 6 个问题，全部按项目既定规则裁决修正（§1.4 修订日志；
> 其中运行期模型整体重写为"框架原生 fork 循环 + 共享内存锚点"）

## 1. 目标与假设

### 1.1 跨机器经验（用户提供，本设计的公理）

1. **机器上位数最多的 SIMD 指令最容易触发 SDC**：
   - 鲲鹏 920（本机，ARMv8.1-A，无 SVE）：NEON(128b) > 非 NEON
   - 鲲鹏 920B：SVE(256b) > NEON
   - 鲲鹏 950：SVE2 > SVE
2. **高精度浮点优先**：FP64 组合全无效才降级整数。
3. **无中间负载在另一台机器上是有效负载**（本机历史为死，跨机器结论不同，保留为有效选项）。
4. **str=4 在其他机器上有效**（本机 2026-11-13 刚证 FP64 str4/str5 = 0！！！，但跨机器保留 4）。

### 1.2 设计目标

单测试用例（框架内一个注册名），一次部署自动完成：
**探测机器最宽 SIMD → 按优先级序列逐组合扫描（每组合 30min 时间片）→ 检测到 SDC 即停并
报告是哪个组合抓到的**。最坏情况（全组合无效）15h 全扫完正常退出。

### 1.3 已拍板的设计决策（2026-11-13，用户）

| # | 决策点 | 结论 |
|---|---|---|
| 1 | 中间负载清单 | **5 种**（"6 种"为口误）：FP64 轮换 / 整数轮换 / 空 / mla(s32) / sub(u64) |
| 2 | 优先级字典序 | **数据类型 > ldr 数量 > str 数量 > 中间负载** |
| 3 | str=4 | **保留**（其他机器有效；本机容错） |
| 4 | 冒烟 | **需要**：全组合快速轮扫验证 golden（防某组合 golden bug 假阳性） |
| 5 | 战役策略 | 30min/组合，SDC 即停，最坏全扫 |

### 1.4 v2 修订日志（builder check 6 项，全部按项目规则裁决）

| # | 问题 | 裁决 | 依据 |
|---|---|---|---|
| 1 | **运行期模型**：框架是 `fork_each_test` 短命子进程循环（每子进程重跑 test_init、新 LCG seed，历史率全在此机制下测得）；v1 的"init 一次 + 进程内 epoch 切换"不成立，combo 会永远停在 0，且本机冠军配方必中而掩盖故障 | **保持框架原生 fork 循环（方案 B）**：组合选择由墙钟锚点在**每个子进程 init 时**决定；锚点/SDC 标志/verify 计数放小的命名共享内存对象；进程内热切换机制整体删除（子进程短命，天然不需要） | 永不固定 LCG seed 是既定方法论；A 案（fracture_loop_count 拉满 + 单子进程 19h）= 单 seed 长跑，违反方法论且率不可比 |
| 2 | **SDC 即停语义**：框架 fail 从不退出进程（历史 1h 役 127 个 fail 块直到 -T 才停）；log_error 本身产生 fail 块会污染两法交叉 | **脚本看门狗轮询 run.log，首个 `result: fail` 块即 SIGKILL 主进程**（铁律：SIGKILL+pgrep 验证）；shm 标志作进程内兜底（置位后子进程快速返回）；组合标签写在 report_fail_msg 文本里；总结行走脚本 monitor.log，不用 log_error | sigkill-rule；恰好一个 fail 块 = 最干净的"哪个组合抓到"报告 |
| 3 | **verify 粒度**：v1"每组合 1 loop"在 fork 循环下每个子进程活 ~秒级，字面实现只会重复扫 combo 0，冒烟空转 | **verify 模式改 shm 轮转计数**：每个子进程 init 时原子递增计数器 → 跑 `counter % 30` 号组合；fork 流 ~7 子进程/s → 30 组合数秒内全覆盖，`-T 60s` 每组合被验 ~10 次+ | builder 建议 + shm 已在案 |
| 4 | **空负载的 FP64/int 六槽重复**：空负载下 res=a 走原始随机位，FP64 与 int 的机器码逐位相同，6 槽是纯重复（白烧 3h + 命中时双标签歧义） | **去重为 30 实例**：空负载只在 int 段出现（空负载的 dtype 本就不可观测，其排序位置任意） | 我的裁决 |
| 5 | **指令集冲突**：v1 整数轮换写 add/sub/eor/and（rowmajor 父版实为 add/eor/and/orr）；mla 写了融合 vmlaq（用户表格与现有 mla 测试实为分解式 vmul+vadd/vsub，且分解式才可嵌套 ldr3 链）；扫序纪律未写明（rowmajor 交替升降、mla/sub 单调） | **整数轮换 = add/eor/and/orr（父版底盘）**；**mla = 分解式**（svmul_s32；svadd_s32(mul,a)；svsub_s32(b,mul)；sveor_s32——用户表格原文即此）；**扫序各随其父**：FP64/int 轮换交替升降（与 fp64 父版同构，objdump 门需要）、mla/sub 单调（与其父测试一致） | 与家族底盘及用户表格逐字对齐 |
| 6 | **中途重启语义**（panic/看门狗后重启，18h 白烧？） | **不续跑**：重启 = 从 combo 0 重新扫（本机 combo 0 几分钟命中，代价小；新机器以简单性优先）；shm 锚点键含主进程 PID，重启自然新键新锚 | 我的裁决 |

## 2. 三步设计

### 第一步：确认 SIMD 指令类型（运行期探测）

```
getauxval(AT_HWCAP):
  HWCAP_SVE2 → SVE2 路径（鲲鹏 950 类）
  否则 HWCAP_SVE → SVE 路径（鲲鹏 920B 类）
  否则 HWCAP_ASIMD → NEON 路径（本机鲲鹏 920）
```

- 三路径热循环**编译期全部实例化**（SVE/SVE2 独立翻译单元 `-march=armv8.2-a+sve+sve2`，
  编译期无需硬件），运行期只选函数指针表。
- SVE/SVE2 用 ACLE 写一遍，`sv*` intrinsic 自动用满运行期 VL（`svcntb()` 查询）；
  SVE2 段暂与 SVE 共码，未来可加 sqdmulh 等专属轮换槽。

### 第二步：数据类型优先级

FP64 段（6 实例）先扫完，全无效才进 int 段（24 实例）。dtype 是字典序最高位，自然实现。

### 第三步：组合空间（30 实例/指令集，空负载去重后）

| 维度 | 取值（优先级序） | 说明 |
|---|---|---|
| 数据类型 | FP64 > int | FP64 = f64 lane；int = u64 lane（64b lane 阈值绑定） |
| ldr 源数 | 2 > 3 | 喂给 ALU 的独立源；scratch 顶置护栏 ldr 常在不计源 |
| str 数量 | 2 > 3 > 4 | temp→junk*→dst，dst 永远最后；单次 per-sweep memcmp(dst) 纪律 |
| 中间负载 | FP64轮换 > 空 > mla > sub | FP64 段兼容 {FP64轮换}；int 段兼容 {int轮换, 空, mla, sub}（空 dtype 不可观测，只入 int 段） |

**完整 30 实例优先级序列**（数组硬编码）：

| # | dtype | ldr | str | 负载 | 备注 |
|---|---|---|---|---|---|
| 0 | FP64 | 2 | 2 | FP64轮换 | **本机冠军配方**（5.62/min @96-189），预期几分钟命中 |
| 1 | FP64 | 2 | 3 | FP64轮换 | |
| 2 | FP64 | 2 | 4 | FP64轮换 | 本机已知死（11-13），跨机器保留 |
| 3 | FP64 | 3 | 2 | FP64轮换 | |
| 4 | FP64 | 3 | 3 | FP64轮换 | |
| 5 | FP64 | 3 | 4 | FP64轮换 | |
| 6 | int | 2 | 2 | int轮换 | |
| 7 | int | 2 | 2 | 空 | |
| 8 | int | 2 | 2 | mla | s32 lane，数据收窄 15 位幅值 |
| 9 | int | 2 | 2 | sub | u64 进位链 |
| 10-13 | int | 2 | 3 | {int轮换,空,mla,sub} | 同序展开 |
| 14-17 | int | 2 | 4 | {int轮换,空,mla,sub} | |
| 18-21 | int | 3 | 2 | {int轮换,空,mla,sub} | |
| 22-25 | int | 3 | 3 | {int轮换,空,mla,sub} | |
| 26-29 | int | 3 | 4 | {int轮换,空,mla,sub} | |

最坏时长 = 30 × 30min = **15h**。

## 3. 热循环清单（负载 × 指令集对照，v2 对齐家族底盘）

统一骨架（每实例一个 `noinline` 函数，编译期固定编码）：

```
迭代顶部: scratch[i] 顶置 ldr (asm volatile, DCE 护栏)
        : srcA[i], srcB[i] (, srcC[i]) 双/三源 asm volatile ldr
中间负载: 按 §3 表轮换 (i%4)，或空 (res = a，b/c 仅 volatile 发出不被 DCE)
尾部:    str res → temp[i] → junk1[i] (→ junk2[i]) → dst[i]  [背靠背, dst 最后]
sweep 末: 冷路径 memcmp(dst, expected)；不一致 → report_fail_msg(含组合标签) + 置 shm SDC 标志
```

| 负载 | i%4 | NEON (128b) | SVE/SVE2 (VL) | lane | 扫序 |
|---|---|---|---|---|---|
| FP64轮换 | 0/1/2/3 | vaddq_f64 / vsubq_f64 / vmulq_f64 / vmaxq_f64 | svadd_f64 / svsub_f64 / svmul_f64 / svmax_f64 | 2×64b | 交替升降（父版同构） |
| int轮换 | 0/1/2/3 | vaddq_u64 / veorq_u64 / vandq_u64 / vorrq_u64 | svadd_u64 / sveor_u64 / svand_u64 / svorr_u64 | 2×64b | 交替升降 |
| 空 | — | （无 ALU，res = a） | （同） | 2×64b | 交替升降 |
| mla（分解式） | 0 | vmulq_s32（t=a×b） | svmul_s32 | 4×32b | 单调（随其父） |
| | 1 | vmulq_s32 + vaddq_s32(t, a)（mla 型） | svmul_s32 + svadd_s32 | | |
| | 2 | vmulq_s32 + vsubq_s32(t, b)（mls 型，实为 mul−b——父版底盘原式；原表 b−t 为转写笔误 v2.2 更正） | svmul_s32 + svsub_s32(t, b) | | |
| | 3 | veorq_s32（对照） | sveor_s32 | | |
| sub | 0/1/2/3 | vsubq_u64 / veorq_u64 / vbicq_u64 / vornq_u64 | svsub_u64 / sveor_u64 / svbic_u64 / svorr(a,svnot(b)) | 2×64b | 单调（随其父） |

- **mla 数据**：源收窄 15 位幅值（\|a×b\| ≤ 2^30，累加 < 2^31 不溢出 s32）；expected
  切换冷路径用同一内建序列重算（父版纪律）。
- **ldr3**：三源链式 `res = rot(i%4, rot(i%4, a, b), c)`（实现时对齐
  mrn_nuke_3src_alu.cpp 历史模式）；分解式 mla 天然可嵌套此链；空负载 ldr3 = res = a。
- **空负载 DCE 护栏**：load 全走 `__asm__ volatile`（父版 load_vec），值未消费指令也在。

## 4. 运行期机制（v2 整体重写：框架原生 fork 循环 + 共享内存锚点）

### 4.0 前提：框架调度模型（builder check 实证）

框架默认 `fork_each_test`：主进程持续 fork 短命子进程（每子进程重跑 test_init、
新 LCG seed = auto seed 机制、活 ~秒级），历史全部触发率在此机制下测得。
**本设计不改变该机制**——组合选择由墙钟在每个子进程 init 时决定，跨子进程推进。

### 4.1 共享内存对象（唯一跨子进程状态）

`shm_open` 命名对象（键 = 环境变量 `ADAPTIVE_MEM_SDC_KEY`（脚本提供），缺省回退
主进程 PID 派生；首个子进程创建并初始化）：

```c
struct AdaptiveShm {
    struct timespec anchor;   // 战役起始墙钟（首个子进程写入一次）
    atomic<uint32_t> verify_ctr;  // verify 模式轮转计数器
    atomic<uint32_t> sdc_flag;    // 任一子进程检出 SDC 后置 1
    char isa_tag[8];          // "NEON"/"SVE"/"SVE2"（首个子进程探测写入，日志用）
};
```

数据集（srcA/B/C/scratch/expected/temp/dst/junk）**全部 per-child**——每子进程 init
重新 fill + 重算 expected（auto seed 本来如此），无共享写、无竞态、无需锁。

### 4.2 正式模式：墙钟组合选择

每个子进程 init 时：
`combo_idx = clamp((now - shm->anchor) / 1800s, 0, 29)` → 装载该组合的热循环函数指针
+ fill + expected。子进程生命周期内组合不变；组合推进靠墙钟跨子进程完成。
shm 标志置位后：后续子进程 init 见标志 → test_run 直接返回（进程空转到脚本收割）。

### 4.3 SDC 即停（脚本主停 + shm 兜底）

- 子进程检出 miscompare → `report_fail_msg("adaptive_mem_sdc combo#N
  [isa/dtype/ldr/str/load] ... miscompare")`（**fail 块自带组合标签**）→ shm 标志置 1。
- **脚本看门狗**轮询 run.log：首个 `result: fail` 块 → 提取组合标签 → **SIGKILL 主进程
  + pgrep 验证**（铁律）→ monitor.log 写总结行（组合四元组、第几分钟、脚本侧统计）。
- 总结不用 log_error（会产生 fail 块污染两法交叉）。

### 4.4 verify 模式（冒烟/正确性自检）

- 触发：环境变量 `ADAPTIVE_MEM_SDC_VERIFY=1`（脚本阶段 1 设置）。
- 每个子进程 init 原子递增 `verify_ctr` → 跑 `ctr % 30` 号组合 → fork 流 ~7 子进程/s
  → 30 组合数秒全覆盖；`-T 60s` 每组合被验 ~10 次以上（不同 seed 反复验证 golden）。
- 标准：阶段 1 verify 全 0 fail!!!（两法交叉）→ 阶段 2 才正式跑。

## 5. 工程结构

| 文件 | 内容 | 编译 |
|---|---|---|
| `tests/cpu/misc/adaptive_mem_sdc.cpp` | shm、探测、优先级序列表、组合分发、NEON 30 实例热循环 | 默认（本机 armv8.1） |
| `tests/cpu/misc/adaptive_mem_sdc_sve.cpp` | SVE/SVE2 30 实例热循环（ACLE） | `-march=armv8.2-a+sve+sve2`（本机可编译运行不选） |
| `tests/cpu/meson.build` | 注册 + SVE 单元特殊编译参数 | |

- 编译验证门：本机 ninja 零警告编过 SVE 单元；objdump 抽查实例 0 热循环与 fp64 父版
  编码同构（3 ldr + 4 槽 FP64 轮换 + 2 背靠背 str + 交替升降）。
- 二进制指纹验证 + **重编译前备份**（11-13 教训：ninja 前先 cp）。

## 6. 战役协议（脚本层）

- **阶段 1（verify 冒烟）**：179 下线（96-178,180-189，-n 93），`ADAPTIVE_MEM_SDC_VERIFY=1`，
  `-T 60s`，须全 30 组合 0 fail!!!（两法交叉）。
- **阶段 2（正式）**：179 上线，96-189（-n 94，CPU3+CPU4，与现役系列同掩码同风扇可比），
  auto seed，`ADAPTIVE_MEM_SDC_KEY=<新键>`，`-T 16h`（30×30min+开销兜底）+ 脚本看门狗
  SIGKILL-on-first-fail + 19h 脚本超时双兜底。
- 中途重启（panic/看门狗）：**从 combo 0 重扫**（不续跑，§1.4-6）；shm 键含键源自然隔离。
- 监控钉 0-7；看门狗 98°C×2；env logger + 温度全程；风扇 AUTO。
- **CPU 频率最高环境**：本机无 OS DVFS 恒 2.6GHz（自动满足）；脚本含可移植分支——目标机
  有 governor 则设 performance 再开跑。
- 启动：setsid + nohup 脱离，实盘 `/home/sdc/adaptive_mem_sdc/`。
- 预期（本机）：实例 0 几分钟命中即停；若触发窗口休眠按序下探，15h 全扫完 exit:pass 报 0。

## 7. 验收标准

1. 本机 ninja 全量编译零警告（SVE 单元含）；objdump 实例 0 编码同构验证。
2. verify 模式 30 组合全覆盖轮扫（日志证明每组合 ≥10 子进程）且全 0 fail!!!（排除 179）。
3. 正式役命中 SDC：恰好 1 个 fail 块、含组合标签、miscompare 文本在场（两法交叉），
   归因走 id 行三字段互证；脚本 monitor.log 有组合总结行。
4. 全扫完无 SDC：exit:pass、0 fail 块 = 0 miscompare（两法交叉）。
5. 战役收尾写 RESULTS.md（docs/ 惯例）+ 记忆存档。

## 8. 开放问题（实现前明确，不阻塞批准）

- ldr3 链式细节对齐 mrn_nuke_3src_alu.cpp（实现时以其源码为准）。
- SVE 单元 GCC 12.3.1 编译若有坑（sizeless 类型/intrinsic 可用性），降级
  `-march=armv8-a+sve` + SVE2 段 target attribute，实现时裁决。
- 920B/950 实机验证属后续战役（先交付 920 可跑版本 + 编译期就绪的 SVE/SVE2 路径）。
- verify 计数器在 `-T 60s` 内的覆盖数以实测为准（验收 §7.2 有硬指标兜底）。

## 附录 v2.1（2026-11-13，实现期修订）

**FP64 段填充改为 NaN-free**（实现 Task 2 时 verify 门抓出的根因修复）：
裸随机位里的 sNaN 对（双操作数皆 sNaN 的 lane）在 AArch64 上返回"quieted 操作数 1"，
而 GCC 利用 fadd/fmul/fmax 的交换律在不同内联副本（golden 冷循环 vs 热循环）里排出
不同操作数顺序 → 同源码两副本对 sNaN 对 lane 产生不同位结果（p≈1e-4/调用，复现器
~1e4 轮必现）。修复 = 填充时清除全 1 指数（NaN/Inf→有限值，bit62 清零），消除 payload
二义性；整数段精确无需处理。修复后 93 线程复现器 3.01 亿轮零失配、真测试 93 核 verify
60s 全 0 fail!!!。**注意：fp64 家族父版（raw NaN 数据 + init/热双副本）埋着同款潜在
雷**，其幸存纯属两副本操作数序碰巧一致——后续建议单独立案。

## 附录 v2.2（2026-11-13，家族 sNaN 修复 + 文本更正）

**fp64 家族父版 sNaN 双副本雷——确认活雷并修复**：在 33f2edb0df13 构件上 objdump 实证
父版 init-golden 副本四槽统一 op(A,B)（x6=srcA→q2 为 op1），热循环升序段 fmul(B,A)——
fmul 槽两副本操作数序分歧，双 sNaN lane 必然 golden≠hot（估算 p≈3e-5/golden；历史冒烟
全干净属概率未中）。修复 = fp64/fp64_dump/fp64_ldpstp 三文件填充 NaN-free（同
adaptive_mem_sdc 修复，三文件 179 下线冒烟 0 fail!!! 两法交叉）；**ldrh/ldrw 构造性免疫**
（u16/u32 整数精确扩宽为 double，FP 输入永非 NaN）；str4/str5 生而 NaN-free；
stress_fma 属同类暴露（golden 走标量 a*b+c、热循环走 asm fmadd，NaN 语义可异）但为
死探针未修，复活前须先修。

**mla slot2 公式更正**：父版底盘（及本实现）实为 `t−b`（vsubq_s32(mul, sb)），§3 原表
`b−t` 为用户表格转写笔误，零功能影响（golden≡hot 同式）。bin e1d1cc981468。
