# SDC 汇编测试套件（346 例）分类整理 与 CORE179 现役用例对照（2026-10-30）

> **来源**：用户提供的外部套件分析稿（`lib/Arm/` + `lib/groupA~M/`，共 346 个 .S 汇编用例；源文件未在本仓库树内定位到，整理以原稿为准）。
> **结构**：§一~§四 = 原稿整理（信息保全、同构变体合并）；§五 = CORE179 现役用例的四维映射分析（本次新增）。

---

## 一、套件总览（14 组）

| 组 | 文件数 | 核心测试目标 |
|---|---|---|
| Arm | 28 | 原生综合测试（ALU/FPU/SIMD/Cache/MDU） |
| groupA | 17 | SinglePress 单拍瞬时功耗峰值 |
| groupB | 4 | TSRT 整数可靠性（ALU/CRC/Compare） |
| groupC | 7 | TSRT 浮点可靠性（Compare/Convert/Round） |
| groupD | 5 | TSRT SIMD 标量可靠性 |
| groupE | 10 | TSRT SIMD 向量可靠性 |
| groupF | 17 | LoadStore 访存可靠性 |
| groupG | 2 | Branch 分支预测压力 |
| groupH | 25 | Base/LSE 原子操作/DataReverse |
| groupI | 71 | SIMD+内存循环拷贝混合压力（最大组） |
| groupJ | 25 | 128-bit SIMD 内存拷贝+运算 |
| groupK | 40 | 精细化运算（FMUL 20 变体系统化遍历） |
| groupL | 39 | 20 次写压力+单拍测试 |
| groupM | 56 | 循环+累积校验（SDC 检测精度最高） |

> **计数待核实（2026-10-30 双版比对注记）**：① groupH 表头 25 但各节仅枚举 13 个文件（差 12 个未分析，两版同病）；② groupI 类别求和 69（若 P14 系列按文件清单 1+1+1+8+1+1+1+1+1+1=17 计则为 73）与表头 71 不符；③ 原稿结论称"5 种互补检测机制"而附录 B 实列 8 种。三处均继承自原分析稿，以实际目录核对为准。

## 二、通用五段式框架（346 例统一）

1. **Prologue**：STP 保存 X1-X30；MRS 保存 NZCV/FPCR/FPSR；SIMD 测试加存 Q0-Q31
2. **Data Setup**：MOVZ/MOVK 加载随机/特定模式；SIMD 经 FMOV 构造 128-bit 操作数；访存测试初始化缓冲区
3. **Compute Kernel**（文件间差异核心）：标签循环 `xxx_label_0/1/2`，循环计数 ~10 次，重复目标指令序列
4. **Verification**：CBNZ 寄存器校验 / SUB/SUBS+CBNZ 期望值对比 / [LoopCheck] 循环后累积校验
5. **Epilogue**：TestEnd 存寄存器→输出缓冲区→LDP 恢复→RET；TestFail 同构返回

## 三、分组详述（同构变体已合并）

### Arm 组（28）：原生综合
- **ArmIntAluP01/P02**：60+ 条/循环混合整数指令（算术/逻辑/移位/位域/比较/CSEL/CRC32/CLS），打满 4-wide 发射；CRC32 天然高 IBR（雪崩）；条件码链延长 ACE 存活；变体换操作数扩大故障注入空间
- **ArmIntCcP01**：30+ 条 CCMN 遍历全部 16 种条件码——NZCV 4-bit 几乎零逻辑掩蔽
- **ArmIntMduP01/P02**：MADD/SMSUBL/UMADDL 激活 64-bit 乘法器（面积/功耗最大单元之一）；CRC32 共享多项式乘法通路
- **ArmIntCacheWriteReadP01~P06**：STR 步长写入→LDR 回读验证。P02-P03 跨 cache line 步长；**P04-P05 写后立即读（Store-Forwarding）**；P06 大步长触发 L1 miss→L2
- **ArmFp\***（Comparison/MiniMaxi/MovMadd）：FCMP/FCMPE/FCSEL（信息压缩比极高）；FMAX/FMIN 的 NaN 处理；FMADD 融合乘加（FPU 最高功耗、单次舍入更敏感）
- **ArmSimd\***（Add/Arithmetic/Compare/Complex/Crypto/Element/Conversion/Imm/Mov/Pair/Permute/Reduce/WideNarrow/Unary）：SCVTF/FCVT 全舍入模式；UMINP/ADDP 成对压缩（跨 lane 通路）；ZIP/UZP/TRN/EXT 重排网络；ADDV 归约（全元素传播）；宽化/窄化位宽转换；一元运算零掩蔽
- 单文件 12K-25K 行

### groupA（17）：SinglePress 单拍
- Int01-03 / Float01-03 / AdvsimdScalar01-03 / AdvsimdVector01-08
- **无循环回跳**，指令线性展开一次性执行：无流水线气泡、完美打满 4-wide → **最高瞬时 di/dt、单峰功耗曲线**（voltage droop 触发导向）
- 校验仅终态 SUB 比较

### groupB（4）：TSRT 整数
- AllOperation（综合）/ Alu（纯 ALU 隔离）/ **CRCAndShiftAndMov（CRC32 雪崩：1-bit 输入翻转→输出 ~50% 翻转）** / Compare（NZCV）

### groupC（7）：TSRT 浮点
- AllOperation / Compare / 定点→浮点 / **舍入到整数（进位传播链=最敏感子单元）** / 精度转换（S↔D 扩展新增 29-bit 尾数=新鲜目标；截断改变舍入方向）/ MinMax / MovMadd

### groupD（5）/groupE（10）：TSRT SIMD 标量/向量
- 全操作/比较/转换/通用运算/极值；向量组另有 **SecureHashStandard（SHA 雪崩）**、**Signed/Unsigned 饱和运算（QC bit 额外检测点）**
- 向量级=4×32-bit 或 2×64-bit 并行，任何 lane 翻转传播到该 lane 输出

### groupF（17）：LoadStore 访存
- **AdvsimdLoadStoreP01-P07**：ST1/LD1 全元素规格（16B/8H/4S/2D...），**55AA 交替模式**，写→读→逐元素 SUB
- AdvsimdLoadDeprecatedP01-04：旧版编码路径
- FpsimdLoadStoreP01-02：标量浮点寄存器访存
- GeneralLoadStoreP01-04：**全位宽覆盖 1B/2B/4B/8B/16B**（数据总线不同宽度路径），变体覆盖寻址模式

### groupG（2）：Branch
- BranchInGeneralP01/P02：密集条件分支+BL 子程序（**分支预测器/RAS 压力**）；条件链（CSEL/CSINC/CSNEG）→条件码→分支方向

### groupH（25）：Base/LSE/DataReverse
- BaseEnLoadStoreP01-05：基础编码访存
- **BaseLseLoadStore**：LR/LDLAR + CAS 全粒度（B/H/W/D），**每对操作后立即 SUB+CBNZ（L4 立即校验）**；CAS 比较语义=天然校验
- BaseSevlWfeBrICLiteral：SEVL/WFE 事件 + BR 间接跳转（BTB）+ **IC IVAU 指令缓存无效化**
- DataReverse（Int/AdvsimdScalar/AdvsimdVector×3）：REV/REV16/REV32/REV64——**确定性 bit 映射，可逆操作验证**

### groupI（71）：MemLoopCpy（最大组）
- Base 55AA/Random 30 条 STP/LDP 基线；Base P01-P10 循环拷贝（步长变体，L1→L2 命中谱）
- SIMDFP 55AA/Random 128-bit 拷贝；**SpclBitFlip30 P01-P03 专用位翻转检测模式**
- **SIMDFPLoadStoreMemLoopCpyP01-P16**：FMOV 构造向量→STP Q 循环拷贝，寄存器组合变体
- **P13/P14 × {Add,Mul,And×2,Orr,Fneg,Mov,Ldr,ZipUzip}**：拷贝+运算混合（计算-访存耦合、di/dt 叠加）
- **P13/P14 ExtIndex0-7**：EXT 提取索引 3-bit 全遍历（索引解码通路逐位测试）
- **P13DoubleCheck / AndP01DoubleCheck / LdrCheck**：写后立即 LDR 读回（第一重）+ 循环终态（第二重）——**L5 双重校验**，立即/延迟校验差异可区分暂时性 vs 永久性故障
- P15/P16 大块拷贝（L2 压力）

### groupJ（25）：MemCpy128
- 与 groupI 同思路，拷贝块 128 字节；Add/Mul/And/Orr/Shl/Fneg 混合；Ext P01-P08；**CombOps128（ADD+MUL+AND+ORR 组合=FPU 峰值功耗）**；SpclBitFlip128；Zip/Uzip

### groupK（40）：精细化运算
- Base：ADD/SUB 32/64-bit 扩展、MADD64、**SDIV64（20+ 周期长驻留=高 ACE 击中概率）**、MOVZ32（高 16-bit 必须为零→寄存器堆检测）
- SimdFp：ABS/FABS（符号位）、FCSEL（条件码）、FDIV（长驻留）、FMOV、ORR（0→1 翻转）、PMULL×2（多项式雪崩）、SHL×2（移位网络）、SMAX、SMLAL（宽化+乘加）
- **SimdFpFMULP01-P20（20 变体系统化遍历）**：2D/4S/2S 精度 × by-element 索引 × 数据模式——乘法器每条数据通路/输入组合全覆盖

### groupL（39）：SinglePress20W 写压力
- Int/Float/AdvsimdScalar(P01-07)/AdvsimdVector(P01-20) × 20 次连续写
- **WAW 写压力**：20 次 Write-After-Write 测寄存器堆写端口；128-bit 向量写功耗更高；单拍执行（无循环）叠加瞬时峰值

### groupM（56）：LoopCheck 循环累积校验（检测精度最高组）
- Base：Add/Sub/Madd/Sdiv ×P01-P04——**双层循环 10×10=100 次累积**，任何单次位翻转→累积终值偏离→SUB 硬编码期望值比较
- SimdFp：Abs/Add/Fabs/Fdiv/Fmul(P01-P08)/Mla/Orr/Pmull/Shl(P01-P06)/Smax/Smlal
- 机理：累积放大微偏差；ORR 累积的 0→1 翻转永久置位；SMAX 单次比较翻转后续无法纠正

## 四、四个附录分类表

### A. 故障触发机制

| 触发机制 | 测试组 | 物理原理 |
|---|---|---|
| di/dt 电压跌落 | SinglePress (A/L), Arm | 瞬时高电流 → IR Drop |
| 功能单元高压 | Arm(Simd/MDU), K, M | 高功耗单元长时间激活 |
| 缓存压力 | Arm(Cache), F, I, J | L1/L2 颠簸与写回 |
| 寄存器堆写压力 | L (20W) | 连续写入寄存器堆 |
| 分支预测压力 | G | 密集条件分支+子程序调用 |
| 原子操作竞争 | H (LSE) | CAS/Store-Load 原子对 |

### B. 故障检测机制

| 检测机制 | 检测原理 | IBR |
|---|---|---|
| SUB+CBNZ 比较 | 结果 vs 期望值 | 依赖指令类型 |
| 累积校验 (M) | 循环累积放大微偏差 | 高 |
| 写-读回验证 (F/I/J/Cache) | 写入后读回比较 | 高 |
| CRC 雪崩 | 1-bit 输入→50% 输出翻转 | 极高 |
| 条件码传播 | NZCV 翻转→条件行为改变 | 高（4-bit 近零掩蔽） |
| 原子操作校验 (LSE) | CAS 语义+原子性保证 | 高 |
| 位翻转模式 (SpclBitFlip) | 专用 0/1 交替模式 | 高 |
| 逆向操作验证 (DataReverse) | REV→REV 还原 | 高（确定性映射） |

### C. 指令类别与功耗权重

| 指令类别 | 功耗 | SDC 敏感度 |
|---|---|---|
| FMUL/FMLA/FMADD（128-bit 乘加） | ★★★★★ | 极高 |
| FDIV/SDIV（除法，长驻留） | ★★★★☆ | 高 |
| SCVTF/FCVTZS（转换） | ★★★★☆ | 高 |
| CRC32（多项式乘法） | ★★★★☆ | 极高（雪崩） |
| MADD/SMSUBL（整数乘加） | ★★★★☆ | 高 |
| STP Q/LDP Q（128-bit 访存） | ★★★☆☆ | 中-高 |
| ADD/SUB/AND/ORR（基础 ALU） | ★★☆☆☆ | 中 |
| FMOV/MOVZ（数据传送） | ★☆☆☆☆ | 低 |

### D. 测试精度等级

| 等级 | 模式 | 优点 | 缺点 |
|---|---|---|---|
| L0 无校验 | SinglePress | 最大 di/dt 触发 | 不检测 SDC |
| L1 终态校验 | Arm/TSRT | 简单高效 | 只检测终态偏差 |
| L2 写-读校验 | LoadStore/Cache | 检测内存通路 | 不检测计算故障 |
| L3 累积校验 | LoopCheck | 放大微偏差 | 精度有限 |
| L4 立即校验 | LSE | 每条指令后校验 | 覆盖窄 |
| L5 双重校验 | DoubleCheck | 时序+终态双检 | 时间长 |

---

## 五、CORE179 现役用例在此体系中的定位（新增分析）

### 5.1 现役用例与热循环结构

现役有效用例（登记册）：`neon_rot_ldr_at_top_rowmajor` 家族（sub/str3/k-cells 变体）、`mrn_reloaded_2src_alu`、`movbe`——全部为 **opendcdiag C++ 测试 + 手写内联 asm 热循环**。热循环配方（三要素）：**≥2 源 load + ALU 依赖链轮换 + str→ldr ≤2cyc 紧时序窗**，框架级 per-thread per-iteration golden 比对（miscompare 块 + cpu-mask 核号归属）。

### 5.2 四维映射

| 维度 | 套件分类 | CORE179 现役用例 | 
|---|---|---|
| **触发机制（附录A）** | 六类应力制造随机物理事件 | **缓存压力类的定向变体**：不制造故障，而是**定向轰炸既存缺陷路径**（L1D 域 load × 紧窗口 × 次数，~1e-6/ldr 恒定概率模型）——套件未设的第七类"缺陷路径暴露" |
| **检测机制（附录B）** | 八种 | **写-读回验证 + 每迭代终态 golden 比较**（B 表"写-读验证"+"SUB+CBNZ"系）；dump 变体向取证增强扩展 |
| **指令功耗（附录C）** | FMUL★★★★★→FMOV★ | **中档**：128-bit NEON 访存（★★★）+ 基础向量 ALU（★★）——无 FMUL/FDIV/CRC/MDU 高功耗指令 |
| **精度等级（附录D）** | L0~L5 | ≈**L2（写-读）+ 每迭代 L1 终态**的复合；**刻意不用 L3 累积**（累积会混合多次低概率事件，不利归因——靠迭代×线程×时间堆暴露量） |

### 5.3 与套件设计假设的三处分歧（均有实证）

1. **触发观**：套件假设故障=需应力提高概率的随机物理事件；我们 179=既存结构性读路径缺陷，率与温度/电压/功耗**全部不相关**（2026-10-29 电压 73 时刻排除；今晨配对两臂功耗 707 vs 715W 而率 885 vs 0 fail；温度每 +3.5°C 减半但非因果、非归零量级）
2. **故障模型**：套件检测器为**位翻转**优化（55AA/SpclBitFlip/CRC 雪崩）；我们 179 的实证签名是**字段级错接/数据错窗**（GPS 主族 93% srcA 近邻字段替换非位翻转；k-cells got=exp±X·(2³²-2¹⁶) 100% 符合且 eor 零例；dualcmp 16B 错接跨界升序）→ 雪崩/位翻转模式类检测器对此增益有限，**golden 全量比对已充分捕获**
3. **检测粒度与编译耦合**：套件=.S 单文件终态校验（**全手写汇编=零编译产物变量**——对我们昨夜发现的"-O3 触发/-O0 归零"编译开关天然免疫，这是其结构优势）；我们=框架级 per-iteration miscompare+核号归属（率测量与核定位是第一公民），但热循环外围的编译产物成了新发现的 confound

### 5.4 最接近的套件用例

| 套件用例 | 我们的对应物 | 关系 |
|---|---|---|
| ArmIntCacheWriteRead **P04-P05**（写后立即读 Store-Forwarding） | `mrn_rmw` / `movbe` 同址 store→reload | 同族：store→load 转发窗口 |
| groupF AdvsimdLoadStore（55AA 写-读）+ groupI/J（SIMD 拷贝+运算混合） | `neon_rot_ldr_at_top` 家族（load+ALU 轮换+store/reload） | 最近亲：访存+计算耦合 |
| groupH **DataReverse**（REV 字节反转） | `movbe`（x86 MOVBE=搬运+字节序反转的 ARM 对应物） | 同功能类；我们用 golden 比对而非逆操作验证 |
| groupM LoopCheck 累积 | —— | **反向选择**：我们刻意不累积 |

### 5.5 互补关系与使用建议

- **套件=广谱普查**（全单元覆盖、物理应力触发、低掩蔽传播检测，为"随机故障是否存在"设计）；**我们=定点深挖**（已知缺陷路径的定向暴露 × golden 全量比对，为"既存缺陷刻画到指令/窗口级"设计）
- 若做**全机普查**（其余 191 核有无同类读路径缺陷）：优先 groupF/I/J + groupH DataReverse 类，但须接入我们的率测量框架（per-iteration miscompare + 核号归属 + auto seed）才有 179 级定位能力；SinglePress/L0 类对我们无用（功耗触发轴已排除）
- 反向移植：我们的配方三要素可直接写成 .S 单测形式——**顺带消掉编译产物 confound**（昨夜证明外围编译产物可开关检出），得到编译变量免疫的复现载体
