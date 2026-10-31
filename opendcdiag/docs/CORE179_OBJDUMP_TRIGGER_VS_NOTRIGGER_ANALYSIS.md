# CORE179 SDC：触发组 vs 不触发组 objdump 热循环对比分析

> 日期：2026-09-01
> 范围：对 22 测试 30min 实测中"触发 SDC 的 2 个"与"同走 forwarding 却 0-fail 的 5 个"共 7 个测试，逐条 objdump 反汇编热循环，找出区分"触发布局 vs 不触发布局"的指令特征。
> 数据来源：`builddir/tests/cpu/libtests_base.a.p/*.o` 反汇编（与主二进制 `opendcdiag` 交叉验证一致，`.o` 8-27 编译、8-31 14:11 链接，22tests 17:23 起跑用的就是这份）。
> 可追溯产物：`movbe_log/objdump_7tests/all_7_run_disasm.txt`（7 个完整反汇编）+ `binary_movbe_run_verify.txt`（binary 交叉验证）。
> 前序：22 测试 30min 实测见 `docs/CORE179_22_TESTS_LOAD_AND_INSTRUCTION_ANALYSIS.md` §四。

---

## 一、7 个测试的实测触发结果（复述）

| 测试 | 唯一 fail 块 / 30min | 率 | 路径（22tests 记忆描述） |
|---|---|---|---|
| **movbe 原始版** | 57 | ~1.9/min | （记忆称"L1D 阵列读"） |
| **mrn_rmw 原始版** | 6 | ~0.2/min | （记忆称"str→ldr forwarding"） |
| mrn_nuke | 0 | 0 | forwarding |
| mrn_pairs | 0 | 0 | forwarding 拉开 |
| mrn_reloaded | 0 | 0 | forwarding 三宽度 |
| mem_disambiguation | 0 | 0 | forwarding 三模式 |
| part_store_fwd_jit | 0 | 0 | JIT 背靠背 forwarding |

全部 fail 均在 thread 179。

---

## 二、objdump 实测热循环（修正记忆/文档的多处描述）

### 1. movbe_run（触发 1.9/min）—— 修正：不是"ALU 字节交换不压 forwarding"，而是"L1D 同址重读"

源码 `tests/cpu/misc/movbe.cpp` 热循环（`TEST_LOOP(1<<13)`，内层 `i<16384`）：
```c
val = data->input[i];            // load input
val = __builtin_bswap32(val);    // rev  (第1个bswap)
data->swapped[i] = val;          // store swapped
val = __builtin_bswap32(val);    // rev  (第2个bswap ← 源码有,编译后消失!)
if (val != data->input[i]) ...   // 重读 input 比较
```

**编译后实际微操作**（objdump，已与 binary 交叉验证逐条一致）：
```
68: ldr  w1,[x2,x3,lsl#2]  ; (A) load input[i]      ← x2=input基址
6c: rev  w4, w1            ; (B) bswap32            ← 只剩1个rev!
70: str  w4,[x5,x3,lsl#2]  ; (C) store swapped[i]   ← x5=swapped基址(异址!)
74: ldr  w4,[x2,x3,lsl#2]  ; (D) load input[i]重读  ← 与(A)同址! x2=input
78: cmp  w4, w1            ; (E) cmp 重读值 vs 原值(A)
```

**关键修正**：
1. **第二个 `__builtin_bswap32(val)` 被 DCE 优化掉了**（编译器识别 `bswap(bswap(x))=x`，cmp 直接拿重读的 input 与原 w1 比）。源码 2 个 bswap → objdump 只 1 个 `rev`。这与记忆 `movbe-dump-compiler-dce-root-cause` 记录的"DCE 改变热循环"是同一类现象。
2. **第 70 行 store 到 x5（swapped），第 74 行 load 从 x2（input）——不同址**，所以第 74 行**不是 store→load forwarding**。
3. **第 68 行和第 74 行是同一地址（x2, x3, lsl#2）的两次 ldr** —— 这是纯 **L1D 阵列重读**。两次 ldr 之间隔 2 条（rev, str）。
4. 因此 movbe 实际触发路径是"L1D 阵列读 → 重读同址 ldr 不一致"，与记忆 `l1d-read-path-sdc-confirmed`（movbe_l1d 走 L1D 阵列读触发）、`isolated-recross-golden-protocol`（movbe 真实错在两次 ldr 读同址不一致）**一致**，但修正了 22tests 记忆里"ldr input→rev→str swapped→rev→cmp val"的描述（cmp 用的是重读的 input，不是寄存器里原 val；第 2 个 rev 不存在）。

### 2. mrn_rmw_run（触发 0.2/min）—— store→load 同址背靠背 forwarding

```
c8: add  x0,x21,x1   ; x0 = temp + i  (x21=temp基址)
cc: str  x2,[x0]     ; store temp[i] = res   ← 地址=x0
d0: ldr  x0,[x0]     ; load  temp[i]        ← 地址=x0, 与store同址同寄存器
```
store→load **同址同寄存器 x0，背靠背（0 间隔）**，纯 forwarding。store 前有 ALU（eor/and/add/sub）+ 2 个源 load（srcA, srcB）。

### 3. mrn_nuke_run（0-fail）—— 与 mrn_rmw 字节同构的 forwarding

```
84: add  x0,x22,x19  ; x0 = temp + i  (x22=temp基址)
88: str  x1,[x0]     ; store temp[i] = src   ← 地址=x0
8c: ldr  x0,[x0]     ; load  temp[i]        ← 地址=x0, 与store同址同寄存器
```
**store→load 微操作与 mrn_rmw 完全同构**（`add; str Rx,[x0]; ldr x0,[x0]`，同址同寄存器，背靠背 0 间隔）。区别仅在 store 前：mrn_nuke 只有 1 个源 load（src）无 ALU；mrn_rmw 有 2 个源 load + ALU。

### 4. mrn_reloaded_run（0-fail，byte 子循环）—— sub-word forwarding

```
a4: add  x1,x20,x3   ; x1 = temp8 + i
a8: strb w2,[x1]     ; store temp8[i] = src  ← 地址=x1
ac: ldrb w1,[x1]     ; load  temp8[i]        ← 地址=x1, 同址
```
store→load 同址同寄存器 x1，背靠背，**sub-word（1 字节）forwarding**。

### 5. mem_disambig_run 模式1（0-fail）—— 与 mrn_rmw 同构的 forwarding

```
84: add  x6,x19,x4   ; x6 = buf + offset    (x19=buf基址)
88: str  x5,[x6]     ; store buf[off] = value ← 地址=x6
8c: ldr  x6,[x6]     ; load  buf[off]         ← 地址=x6, 同址同寄存器
```
**store→load 微操作与 mrn_rmw 完全同构**（`add; str; ldr` 同址同寄存器，背靠背 0 间隔）。

### 6. part_store_fwd_jit_run（0-fail）—— JIT 背靠背，但经 `blr x2` 间接调用

热循环每轮 `random32`×2 → `blr x2`（调用 JIT 函数）。JIT 函数本身是 store+load 背靠背（源码 emit_word 生成），但从 run 的视角，store→load 隐藏在一个**函数调用**后面，且每轮有 2 次 random32 + 分支跳转，时序窗口被 random 的分支开销撑开，与 mrn_rmw 的直线循环不同构。

---

## 三、决定性对比表

### A. store→load 微操作同构性

| 测试 | store→load 形态 | 同址同寄存器? | 间隔 | 与 mrn_rmw 同构? | 触发? |
|---|---|---|---|---|---|
| **mrn_rmw** | add;str;ldr | 是(x0) | 0 | (基准) | **是 0.2/min** |
| mrn_nuke | add;str;ldr | 是(x0) | 0 | **是** | 否 0 |
| mem_disambig-m1 | add;str;ldr | 是(x6) | 0 | **是** | 否 0 |
| mrn_reloaded | add;strb;ldrb | 是(x1) | 0 | 是(sub-word) | 否 0 |
| movbe | ldr;rev;str;ldr(同址重读) | N/A(两次ldr同址x2) | 2 | 否(无forwarding) | **是 1.9/min** |

**结论 1：store→load forwarding 微操作本身不是触发判定因素**。mrn_nuke / mem_disambiguation 的 forwarding 微操作与 mrn_rmw **字节同构**（同址、同寄存器、背靠背 0 间隔），却不触发。

### B. 每轮 ldr 次数（证伪"load 次数驱动"假说）

| 测试 | 内层迭代 | 每轮 ldr 数 | 每轮 ldr 总次 | 触发? |
|---|---|---|---|---|
| movbe | 16384 | 2 | **32768** | 是 1.9/min |
| mrn_nuke | 8192 | 3 | **24576** | **否 0** |
| mrn_rmw | 1024 | 3 | 3072 | 是 0.2/min |
| mem_disambig-m1 | 512 | 3 | 1536 | 否 0 |
| mrn_reloaded | 1024 | 1 | 1024 | 否 0 |

**结论 2：触发与"每轮 ldr 绝对次数"无单调关系**。mrn_nuke 每轮 24576 次 ldr（比 mrn_rmw 的 3072 多 8 倍）却 0-fail；mrn_rmw 仅 3072 次却触发。**证伪记忆 `sdc-trigger-constant-probability-per-ldr` 的"load 次数越多越易触发"推论**——该假说的"低概率随机错×load 次数"模型无法解释 mrn_nuke 高 load 次数却 0-fail。触发因素必在更精细的指令上下文/时序布局，而非 load 绝对计数。

> 注：`sdc-trigger-constant-probability-per-ldr` 的核心观察（"str→ldr 须≤2cyc 短窗口，evict 走 L2=0"）仍可能成立——mrn_nuke 虽 load 多，但其 store→load 时序窗口若与 mrn_rmw 不同（见下），仍可区分。本对比**只证伪"load 绝对计数驱动"，不证伪"短窗口驱动"**。

### C. 循环体指令数（展开度）

| 测试 | 循环体指令数 | 触发? |
|---|---|---|
| movbe | 9 | 是 |
| mrn_nuke | 10 | 否 |
| mem_disambig-m1 | 11 | 否 |
| mrn_reloaded | 11 | 否 |
| mrn_rmw | 23 | 是 |

**结论 3：循环体长度（展开度）无单调区分力**。mrn_rmw 23 条触发，mrn_nuke 10 条不触发；movbe 9 条触发，mrn_nuke 10 条不触发——无单调关系。

---

## 四、综合结论

### 已确认的
1. **触发 ≠ "走 store→load forwarding"**：mrn_nuke / mem_disambiguation 的 forwarding 微操作与 mrn_rmw 字节同构却 0-fail。forwarding 路径是**必要不充分**条件。
2. **触发 ≠ "load 绝对次数多"**：mrn_nuke 每轮 ldr 24576 次（8×于 mrn_rmw）却 0-fail。证伪 `sdc-trigger-constant-probability-per-ldr` 的 load 计数推论。
3. **movbe 真实路径 = L1D 同址重读**（非 forwarding）：两次 `ldr w?,[x2,x3,lsl#2]` 读同一 input 地址，第 2 个 bswap 被 DCE。修正记忆/文档多处描述。
4. **mrn_rmw 触发 vs mrn_nuke 不触发，差异不在 forwarding 微操作**（同构），而在 store 前上下文：mrn_rmw 有 **2 源 load + ALU（eor/and/add/sub）**，mrn_nuke 仅 1 源 load 无 ALU。这是目前最值得追的线索。

### 仍未区分的（开放问题）
mrn_rmw(触发) 与 mrn_nuke(不触发) 的 forwarding 微操作字节同构、buffer 同为 8KB per-thread、store→load 同址背靠背，**唯一可见差异是 store 前的源 load 数 + ALU**。可能的解释方向：
- (a) ALU 在 store 前引入的额外周期/资源占用改变了 store buffer 提交时序，使 forwarding 命中不同的时序窗口；
- (b) 2 源 load vs 1 源 load 改变了 load 端口/LSQ 占用，间接影响 forwarding 路径的时序竞态；
- (c) 仍可能是编译期寻址/寄存器分配的更细微差异（需逐字节对比 mrn_rmw vs mrn_nuke 的完整循环体）。

这三个方向都需要进一步**逐字节对比 mrn_rmw 与 mrn_nuke 的完整 23/10 条循环体**，或构造"在 mrn_nuke 骨架上逐步加 ALU/源 load"的探针变体来二分定位。这是下一步。

---

## 五、对既有记忆的修正清单

| 记忆 | 原描述 | objdump 实测修正 |
|---|---|---|
| `22tests-30min-only-movbe-mrn-rmw-trigger` | movbe 路径"ldr input→rev→str swapped→rev→cmp val" | 实际：第 2 个 rev 被 DCE 消失；cmp 拿重读的 input vs 原 w1。热循环是 ldr;rev;str;ldr(同址重读);cmp |
| `load-port-downstream-sdc-confirmed` 等 | movbe 原始版"不走 store→reload" | 部分对：不走 forwarding（store 异址）；但走"同址 ldr 重读"（L1D 阵列读），这是另一种 reload |
| `sdc-trigger-constant-probability-per-ldr` | "load 次数越多越易触发"（movbe 高频因 load 多） | **证伪**：mrn_nuke load 次数 8×于 mrn_rmw 却 0-fail。load 计数非驱动因素 |
| `movbe-probe-abcd-sdc-location` 等"两次 ldr 读同址不一致" | movbe 真实错在两次 ldr 读同址 | **印证且精确化**：objdump 68/74 行确为同址(x2,x3,lsl#2)两次 ldr |
