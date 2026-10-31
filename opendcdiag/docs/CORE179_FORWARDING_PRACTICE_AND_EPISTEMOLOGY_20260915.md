# CORE179 流水线转发的理解与实践(2026-09-15)

依据:neon_rot_ldr_at_top_rowmajor 家族反汇编实录(`builddir/opendcdiag` objdump,
2026-09-15 抓取)+ 两世代实验的既有结论(记忆与 docs 可追溯数据)。
本文回答:"我们如何理解流水线转发、如何用它做实验、以及哪些话不能说"。

## 一、理解:转发是"比较+选择"电路,不是抽象概念

教科书层面:流水线把指令切成 IF/译码/执行/访存/写回,结果要到 WB 才进寄存器堆,
但后继指令在 EX 就要用——数据冒险。解法是在功能单元输入端加旁路多路器,
从流水寄存器里把在途结果直接抢过来,不等写回。

对本项目真正重要的是它的物理形态:转发网络 = 比较器(执行旁路里是源寄存器号
匹配;访存转发里是**地址**匹配)+ 多路器 + 跨越半个流水段的长线。它是时序
关键路径之一,也是"数据从哪来"的最终裁决点。由此两条:

1. 它有真实的物理面积和时序代价,不是免费的抽象;
2. 它分两个层面,本项目两个都碰过:
   - **执行旁路**(load/ALU 结果 → 下一条指令的操作数);
   - **访存转发**(在途 store 的数据按地址匹配直接喂给 load,不过 L1D)。

## 二、物化:热循环里每一条依赖边都是旁路边

基线 `neon_rot_ldr_at_top_rowmajor` 主循环体(objdump 实录,降序段 @`ca870`):

```asm
ldr  x1, [x19, #16]        ; ← scratch 基址重读(每元素)
add  x1, x1, x0            ;   地址合成
ldr  q0, [x1]              ; ① 顶部第3条ldr(scratch,结果不被消费)
ldr  x1, [x19]             ; ← srcA 基址重读
add  x1, x1, x0
ldr  q0, [x1]              ; ② 源A
ldr  x1, [x19, #8]         ; ← srcB 基址重读
add  x1, x1, x0
ldr  q1, [x1]              ; ③ 源B(②③=双源load)
and  w1, w2, #0x3          ; i%4 分派(编译器做成分支跳表)
cmp  / b.eq / b.ne
orr  v0.16b, v0.16b, v1.16b; ④ 轮换ALU:add v.2d / eor / and / orr 按i%4轮换
str  q0, [x21, x0]         ; ⑤ 背靠背双store(temp[i])
str  q0, [x20, x0]         ;   (dst[i])
sub  x0, x0, #0x10         ; 循环控制(降序)
cmn  / b.ne                ;   回跳
```

每元素 = **3×(基址重读+地址合成+`ldr q`) → 轮换 vALU → 背靠背 2×`str q`**。
依赖图上的转发边:

| 边 | 代码位置 | 转发含义 |
|---|---|---|
| ldr q0/q1(srcA/B)→ vALU | `neon_rot_ldr_at_top_rowmajor.cpp:101-110` | **load-to-use 0 拍旁路**——不旁路就得 stall |
| vALU → str q0 ×2 | `:112-113` | **ALU→store 0 拍旁路**,res 不过寄存器堆直达两条 store |
| 顶部 ldr(scratch) | `:98` | **无转发边**——结果架构上死亡(q0 随即被 srcA 覆盖),靠 asm volatile 才没被 DCE 删掉;作用是 load 端口占用/调度压力 |
| i%4 轮换 ALU | `:105` | 每个元素换一条旁路**路由**(加法器入口 ↔ 逻辑入口) |
| 升/降交替扫描 | `:94` | 循环接缝处 str→ldr 的邻接关系翻转 |

精确表述:热循环内**没有任何一条依赖边走寄存器堆往返**,全部是 0 拍边;
而三条 load 里只有两条形成转发边,第三条故意做成死的。
"三要素配方"(≥2源load+轮换ALU+紧时序)在转发视角下即:
**所有活边都必须 0 拍 + 每元素换旁路路由 + 一条死的 load 占端口**。

各格对骨架的唯一差异(objdump 核verify):

| 格 | 指令序列差异 |
|---|---|
| k5far / k5inter_rand | ②③ 的寻址换成 `src[2i]`/`src[2i+1]`(交错单缓冲),load/store/ALU 数不变 |
| k7p ×4 | **指令序列零差异**,只换内存填充(全0/全1/打标随机/0x55AA) |
| k3res | **指令序列零差异**,仅循环边界常数 0x400→0x1000(footprint 4×) |
| k4gap(零格) | ③④ 之间插 **8×nop** |
| k4bgap(零格) | ④⑤ 之间插 8×nop |
| k2pureload(零格) | 删 ⑤ 两条 `str q`,④ 后改 `eor v3.16b` 累加;校验移冷路径比对累加器 |

## 三、实践:两个世代的转发实验

**世代一(movbe/mrn_rmw,2026-08):显式打 store→load 转发窗口。**
同址 str→ldr 重读,nop 梯度曲线:0/1/2 nop 存活(~0.067 fail/min),
8/16/64 归零——"窗口 ≤2 拍"结论的出处。
代价:部分数据处于 SiliFuzz 污染窗口(2026-08-26 起),已标记降权。

**世代二(neon_rot 家族,2026-09):改打旁路邻接性。**
热循环里 store 写的 temp/dst 从不被 load 回来——所以 k2pureload(0 fail)
证明的是"**store 在场必要**",**不是**"store→load 转发必要"。这两句不可混。

四零格的干预与读法:

| 干预 | 破坏的边 | 结果 |
|---|---|---|
| k4gap:load→ALU 插 8 nop | load-to-use 旁路 | 0 fail |
| k4bgap:ALU→store 插 8 nop | ALU→store 旁路 | 0 fail |
| k2pureload:删 store | 上一条边 + store buffer 压力 | 0 fail |
| k7p_zero:数据全 0 | 数据门控(非转发边) | 0 fail |

工程纪律(血泪教训换来的):
- **干预必须在反汇编里核verify**——编译器会重排,源码加 nop ≠ 二进制里有 nop;
- 架构死亡的 load 必须 asm volatile,否则被 DCE(neon DCE 坑);
- dump 只能进冷分支,否则改掉热循环调度(30× 率塌缩教训);
- 变体间热循环须逐指令同构,否则不是单变量实验;
- 删临时测试永远手删注册行,不 git checkout(09-13 事故)。

## 三A、六格逐格完整指令序列(objdump 实录,2026-09-15 补)

六段全部从 `builddir/opendcdiag` 二进制逐字提取(降序主干 + op 分支体 +
边界常数),不做合并。基线序列见 §二;每段 ★ 标记与基线的差异点。

### 1. k5far @`cb6c4`(单缓冲交错双源)

```asm
; 边界: x1=0x7fe0(源索引起点)  x0=0x3ff0  w3=0x3ff(1023)
; 寄存器: x19=数据结构基址  x23=temp  x21=dst
;         x0=目标字节偏移(步进0x10)   x1=源字节偏移(步进0x20=双倍!)
 ldr  x2, [x19, #8]          ; scratch 基址
 add  x2, x2, x0             ; + x0
 ldr  q0, [x2]               ; ① 顶部死load(scratch)
 ldr  x2, [x19]              ; src 基址(单缓冲)
 add  x2, x2, x1             ; + x1
 ldr  q1, [x2]               ; ② 源A = src[2i]  (A族,偶)
 ldr  x2, [x19]              ; src 基址再读
 add  x4, x1, #0x10          ; ★ x1+0x10 → 相邻元素!
 add  x2, x2, x4
 ldr  q0, [x2]               ; ③ 源B = src[2i+1] (B族,奇,与A物理相邻32B)
 and  w2, w3, #0x3           ; i%4
 cmp  w2, #0x2
 b.eq cb7d4                  ; → and
 cmp  w2, #0x3
 b.ne cb69c                  ; → add
 orr  v0.16b, v0.16b, v1.16b ; ④ op=3
 sub  w3, w3, #0x1
 sub  x1, x1, #0x20          ; ★ 源索引步进=2元素
 str  q0, [x23, x0]          ; ⑤ 双store
 str  q0, [x21, x0]
 sub  x0, x0, #0x10
 cmn  x0, #0x10
 b.ne cb6c4                  ; 回跳
```

op 分支体(主干外四目标,每元素走一条):

```asm
cb69c:  cmp w2, #0x1
        b.eq cb7dc                    ; → eor
        add v0.2d, v0.2d, v1.2d       ; op=0(add) fall-through
        str q0, [x23, x0]             ; (add 内联,其余跳转)
cb7d4:  and v0.16b, v0.16b, v1.16b   ; op=2
        b   cb720                    ; 回 store 段
cb7dc:  eor v0.16b, v0.16b, v1.16b   ; op=1
        b   cb720
```

差异点:双源地址合成——③ 的地址 = ② 的地址 + 0x10,两个 load 窗口物理相邻;
源索引 x1 步进 0x20。load/store/ALU 形态与基线全同。

### 2. k5inter_rand @`cbc24`(交错 + 自然随机)

```asm
; 边界: x1=0x7fe0  x0=0x3ff0  w3=0x3ff   ← 与 k5far 完全相同
 ldr  x2, [x19, #8]
 add  x2, x2, x0
 ldr  q0, [x2]               ; ① scratch
 ldr  x2, [x19]
 add  x2, x2, x1
 ldr  q1, [x2]               ; ② src[2i]
 ldr  x2, [x19]
 add  x4, x1, #0x10          ; ★ 同 k5far
 add  x2, x2, x4
 ldr  q0, [x2]               ; ③ src[2i+1]
 and  w2, w3, #0x3
 cmp  w2, #0x2
 b.eq cbd34                  ; → and
 cmp  w2, #0x3
 b.ne cbbfc                  ; → add
 orr  v0.16b, v0.16b, v1.16b
 sub  w3, w3, #0x1
 sub  x1, x1, #0x20          ; ★ 同 k5far
 str  q0, [x23, x0]
 str  q0, [x21, x0]
 sub  x0, x0, #0x10
 cmn  x0, #0x10
 b.ne cbc24
```

op 分支体同构(cbbfc=add fall-through / cbd2c=and / cbd3c=eor)。
**与 k5far 逐指令相同,唯一差异在 init 填充**(memset_random vs GPS 标签)
——"k5far−k5ir=标签效应,k5ir−基线=布局效应"配对的指令级基础。

### 3/4/5. k7p_rand / k7p_one / k7p_hiham @`cd0a0`(共用 k7p_run_common)

```asm
; 边界: x0=0x3ff0  w2=0x3ff(1023)  —— 回到基线的单索引寻址
; 寄存器: x24=temp  x22=dst(与基线 x21/x20 不同分配)
 ldr  x1, [x19, #16]         ; scratch
 add  x1, x1, x0
 ldr  q0, [x1]               ; ① 顶部死load
 ldr  x1, [x19]              ; srcA
 add  x1, x1, x0
 ldr  q0, [x1]               ; ② 源A
 ldr  x1, [x19, #8]          ; srcB
 add  x1, x1, x0
 ldr  q1, [x1]               ; ③ 源B
 and  w1, w2, #0x3
 cmp  w1, #0x2
 b.eq cd19c                  ; → and
 cmp  w1, #0x3
 b.ne cd07c                  ; → add
 orr  v0.16b, v0.16b, v1.16b ; ④ op=3
 sub  w2, w2, #0x1
 str  q0, [x24, x0]          ; ⑤ 双store
 str  q0, [x22, x0]
 sub  x0, x0, #0x10
 cmn  x0, #0x10
 b.ne cd0a0
```

op 分支体:

```asm
cd07c:  cmp w?, #0x1
        b.eq ...                     ; → eor
        add v0.2d, v0.2d, v1.2d      ; op=0 fall-through
cd19c:  and v0.16b, v0.16b, v1.16b   ; op=2
        b   cd088                    ; 回 store 段
cd1a4:  eor v0.16b, v0.16b, v1.16b   ; op=1
        b   cd088
```

三个测试**编译成同一段代码**(尾调用 `b cd000` common),指令序列零差异;
差别只在 init:`k7p_init_common(t, P_RAND_GPS / P_ONE / P_HIHAM)` 走
`pattern_word()` 的不同 case。纯数据平面实验——同一段序列喂不同数据。

### 6. k3res @`cd988`(footprint 4×)

```asm
; 边界: x0=0xfff0  w2=0xfff(4095!)  memcmp长度=0x10000(65536)
 ldr  x1, [x19, #16]         ; scratch
 add  x1, x1, x0
 ldr  q0, [x1]               ; ① 顶部死load
 ldr  x1, [x19]              ; srcA
 add  x1, x1, x0
 ldr  q0, [x1]               ; ② 源A
 ldr  x1, [x19, #8]          ; srcB
 add  x1, x1, x0
 ldr  q1, [x1]               ; ③ 源B
 and  w1, w2, #0x3
 cmp  w1, #0x2
 b.eq cda84                  ; → and
 cmp  w1, #0x3
 b.ne cd964                  ; → add
 orr  v0.16b, v0.16b, v1.16b
 sub  w2, w2, #0x1
 str  q0, [x23, x0]          ; ⑤ 双store
 str  q0, [x21, x0]
 sub  x0, x0, #0x10
 cmn  x0, #0x10
 b.ne cd988
```

op 分支体(cd964 起):`cmp/b.eq → add v0.2d`(fall-through)、
`and`/`eor` 跳转体。与基线的全部差异:循环边界常数 0x3ff→0xfff、
偏移起点 0x3ff0→0xfff0、memcmp 长度 0x4000→0x10000,
寄存器分配微调(x21/x20→x23/x21)。指令形态 100% 同构。

### 六格横向对照(每格循环一轮的真实指令构成)

| 格 | 寻址模式 | 源索引步进 | 相邻源合成 | 边界常数 | vALU | ldr/str q |
|---|---|---|---|---|---|---|
| 基线 | x0 单索引 | 0x10 | 无 | 0x3ff | 4 op ×2 向 | 3/2 |
| k5far | **x1 双索引(0x20)** | 0x20 | **`add x4,x1,#0x10`** | 0x3ff | 4 op ×2 向 | 3/2 |
| k5inter_rand | 同 k5far | 0x20 | 同 k5far | 0x3ff | 4 op ×2 向 | 3/2 |
| k7p ×3 | x0 单索引(同基线) | 0x10 | 无 | 0x3ff | 4 op ×2 向 | 3/2 |
| k3res | x0 单索引(同基线) | 0x10 | 无 | **0xfff(4×)** | 4 op ×2 向 | 3/2 |

六格指令序列归成三种形态:**交错形态**(k5far/k5ir:双索引+相邻源地址合成)、
**基线形态**(k7p 三兄弟+k3res:单索引,仅数据或边界不同)、基线本身。
转发边结构(①死load、②③→④零拍、④→⑤零拍)在全部六格中一字不差地保留
——"单变量"承诺的指令级兑现。

## 四、认识论边界:能说的与不能说的

**不能说的**(既定教训:干预解耦不可能):插 nop 同时改了两件事——
是否走旁路路径,和时序余量。四零格只证明"所有边都必须 0 拍",
**不能**证明"缺陷骑在旁路通路上"。路径与时延在这类干预下绑死。

**反向也要诚实**:早年 objdump 对比(7 测试,2026-09-01)显示触发与不触发
测试的 forwarding 微操作**同构**——转发结构存在但不触发,即转发不充分。
所以转发是必要条件的侧写,不是充分条件,更不是故障位点。

**当前签名实际指向的层次**(读路径首轮 + K-cells 批次 2):
- 字段替换源 = 地址近邻(k5far:79/79 错位窗命中);
- mod-8 错位窗(头部族复现内核 mod-8 错位窗);
- got = exp ± X·(2³²−2¹⁶) 100% 符合,且 **eor 零例**;
- op 强偏置(orr 71% / and 23% / eor 5% / add 1%)。

其中"eor 零例"最有分量:若缺陷是旁路线上的位翻转,eor 的输出会同样出错——
它没有。损伤是"**拿错了哪个数据**(地址捕获/数据装配级)",
不是"数据在通路上被翻位"。叠加进位链形状的 ±X 签名,
矛头指向**装配/选择级**而非旁路网络本身。

## 五、一句话总结

对转发的实践不是"证明缺陷在转发网络里",而是把它当坐标系用:
四零格钉死"每条活边都必须 0 拍"的配方边界,
签名(eor 免疫、字段搬运、mod-8 错位窗)排除"缺陷在旁路数据线"候选。
转发是排除法和定位的地形图,不是已被指认的凶手。

## 数据追溯

- 反汇编:`builddir/opendcdiag`(@`ca870` 基线 / `cb6c4` k5far / `cbc24` k5ir /
  `cd0a0` k7p common / `cd988` k3res / `cc5..` k4gap / `cc034` k2pureload,
  2026-09-15 抓取,六格完整序列见 §三A)
- 家族源码:`tests/cpu/misc/neon_rot_ldr_at_top_rowmajor{,_k5far,_k5inter_rand,
  _k3res,_k7pattern,_k4gap,_k4bgap,_k2pureload}.cpp`
- 两晚战役数据:docs/CORE179_VALID7_RERUN_REVERSED_ORDER_20260915.md
- 签名数据:docs/CORE179_READPATH_P0_GPS_FIRST_SIGNATURES_20260913.md、
  docs/CORE179_READPATH_K_CELLS_BATCH2_RESULTS_20260914.md
