# CORE179 SDC：22 个测试用例负载类型 / 输入方式 / 指令序列对照表

> 日期：2026-09-01
> 范围：把 22 测试 30min 全核含 179 实测中每个测试的**负载类型、输入方式、指令序列**逐个记录，作为"触发 vs 不触发"对比的底层数据。
> 数据来源：10 个测试 objdump 字节级取证（与主二进制交叉验证一致），12 个源码层面分析。
> 可追溯产物：`movbe_log/objdump_7tests/all_7_run_disasm.txt`（810 行，含 10 个完整 objdump）。
> 前序：`docs/CORE179_22_TESTS_LOAD_AND_INSTRUCTION_ANALYSIS.md`（22 测试实测结果）、`docs/CORE179_TRIGGER_SEQUENCE_HARDWARE_PATH_ANALYSIS.md`（触发归因，本表整合其探针否定结论）。

---

## 一、字段定义

对每个测试记录：
- **负载类型**：测试压测的硬件单元/机制（forwarding / L1D阵列读 / 纯ALU / 寄存器间 / 向量通路 / 不可用）
- **输入方式**：数据从哪来——源 load 数、store 值来源（原值/ALU加工）、buffer 共享性(per-thread/init共享)、buffer 大小
- **指令序列**：内层循环的 ARMv8 微操作序列（objdump 实测，纯 C 测试标编译器生成）
- **store→load 关系**：是否同址、是否背靠背、时序间隔
- **触发结果**：22tests 30min 全核 192 含 179 + auto seed 的唯一 fail 块数

---

## 二、22 个测试逐个记录

### A 组：走 store→load forwarding 路径（8 个）

#### 1. mrn_rmw ✅ 触发 ~0.2/min
- **负载类型**：ALU 读改写 + store-to-load forwarding（memory renaming + forwarding 双压）
- **输入方式**：2 源 load（srcA, srcB，各 8KB 共享只读），store 值 = ALU 加工（add/sub/eor/and 按 i%4 轮换），temp/dst 各 8KB per-thread
- **指令序列**(objdump 内层循环)：
  ```
  ldr x0,[srcA,i]; ldr x3,[srcB,i]; eor/and/add/sub x2,x0,x3(数据ALU);
  add x0,temp,i; str x2,[x0]; ldr x0,[x0](forwarding重载); add x2,dst,i; str x0,[x2]
  ```
- **store→load 关系**：同址同寄存器 x0，背靠背 0 间隔，纯 forwarding
- **触发**：6 唯一 fail 块，全 thread 179

#### 2. mrn_nuke ❌ 0-fail
- **负载类型**：纯拷贝 store-to-load forwarding（无 ALU，压 store buffer/renaming）
- **输入方式**：1 源 load（src 8KB 共享只读），store 值 = 原值未加工，temp/dst 各 8KB per-thread
- **指令序列**(objdump)：
  ```
  ldr x1,[src,i]; add x0,temp,i; str x1,[x0]; ldr x0,[x0](forwarding重载);
  add x1,dst,i; str x0,[x1]
  ```
- **store→load 关系**：同址同寄存器 x0，背靠背 0 间隔，与 mrn_rmw 微操作**字节同构**
- **触发**：0
- **与 mrn_rmw 差异**：store 前无数据 ALU（原值搬），1 源 load 而非 2 源。v2 探针证明仅加 eor 不翻转触发。

#### 3. mrn_pairs ❌ 0-fail
- **负载类型**：8 路展开 store-to-load forwarding（拉开时序间隔）
- **输入方式**：1 源 load，store 值原值，temp/dst 各 8KB per-thread
- **指令序列**(objdump)：8×`str x1,[temp+k]` 后 8×`ldr x9,[temp+k]; str x9,[dst+k]`
- **store→load 关系**：同址但时序拉开 7 条 store（非背靠背）
- **触发**：0

#### 4. mrn_reloaded ❌ 0-fail
- **负载类型**：1/4/8 字节三粒度 store-to-load forwarding
- **输入方式**：1 源 load，store 值原值，temp8/32/64 各 1/4/8KB per-thread
- **指令序列**(objdump, byte 子循环)：
  ```
  ldr x2,[src]; add x1,temp8,i; strb w2,[x1]; ldrb w1,[x1](forwarding);
  ldr x2,[src]; ldrb w4,[x2,i]; cmp w4,w1
  ```
- **store→load 关系**：同址同寄存器 x1，背靠背，**sub-word**（1/4 字节）
- **触发**：0

#### 5. mem_disambiguation ❌ 0-fail
- **负载类型**：三模式系统压 store-to-load forwarding + 内存消歧（全宽/部分重叠/重复store训练）
- **输入方式**：模式1：2 源 load（off, val），store 值原值，buf 4KB per-thread
- **指令序列**(objdump, 模式1)：
  ```
  ldr x4,[off,i]; ldr x5,[val,i]; add x6,buf,off(地址ALU); str x5,[x6];
  ldr x6,[x6](forwarding); cmp x5,x6
  ```
- **store→load 关系**：同址同寄存器 x6，背靠背 0 间隔，与 mrn_rmw 微操作同构
- **触发**：0（模式2/3 也 0）
- **与 mrn_rmw 差异**：2 源 load 同 mrn_rmw，但 store 值原值未加工（地址 ALU 而非数据 ALU）

#### 6. partial_store_forwarding ❌ 0-fail
- **负载类型**：partial store-to-load forwarding（随机位宽部分重叠 + shadow 比对）
- **输入方式**：随机位宽（1/2/4/8B）store + 随机重叠 load，buf 256B per-thread 栈上
- **指令序列**(objdump, 纯 C volatile)：`strh/strb w0,[addr]; ldrh/ldrb wN,[addr]`（编译器按 size switch）
- **store→load 关系**：同址部分重叠，时序随机
- **触发**：0

#### 7. part_store_fwd_jit ❌ 0-fail
- **负载类型**：JIT 生成窄 store + 紧接宽 load 同址（partial forwarding，时序最窄）
- **输入方式**：1 源 load（随机 pattern），buf 32B 栈上 per-thread
- **指令序列**(objdump run)：`random32×2 → blr x2(JIT函数内 strb+ldrh/strh+ldr/...)`，store→load 藏在函数调用后
- **store→load 关系**：JIT 函数内背靠背，但**经 blr 间接调用**隔开时序
- **触发**：0

#### 8. atomic_seq_cst ❌ 0-fail
- **负载类型**：C++11 seq_cst 原子 store/load（STLR→LDAR release-acquire forwarding）
- **输入方式**：1 源 load（golden），store 值原值，shared/golden 各 32KB 共享
- **指令序列**(objdump)：
  ```
  ldr x4,[val,i]; add x1,base,idx(地址ALU); stlr x4,[x1]; (ldr x1重取指针);
  add x0,base,idx; ldar x5,[x0](forwarding); cmp x4,x5
  ```
- **store→load 关系**：同址，STLR→LDAR 背靠背（release-acquire forwarding）
- **触发**：0
- **与 mrn_rmw 差异**：store 值原值未加工，用 STLR/LDAR（带排序语义）而非普通 str/ldr

---

### B 组：forwarding 但中间隔屏障（2 个）

#### 9. mfence ❌ 0-fail
- **负载类型**：双 store 间全内存屏障保证可见性
- **输入方式**：1 源 load（golden_a），store 值原值，store_a/store_b 各 32KB 共享
- **指令序列**(objdump)：
  ```
  ldr x3,[src_a,i]; str x3,[store_a,i]; dmb ish; ldr x3,[src_b,i];
  str x3,[store_b,i]; ldr x5,[store_a,i](重载); ldr x4,[store_b,i](重载); cmp
  ```
- **store→load 关系**：verify load 紧跟 store，但**中间插 DMB SY** drain store buffer，可能改走 L1D 阵列读
- **触发**：0

#### 10. mfence_pure ❌ 0-fail
- **负载类型**：纯屏障隔离 load 与 store
- **输入方式**：1 源 load（src），store 值原值，src/dst 各 32KB 共享
- **指令序列**(objdump)：
  ```
  ldr x4,[src,i]; dmb ish; ldr x3,[golden_dst,i]; str x3,[dst,i];
  ldr x5,[dst,i](重载); cmp x5,x4; ldr x1,[dst,i]
  ```
- **store→load 关系**：dst 的 verify load 紧跟 store（forwarding），但**隔 DMB**；src load 走 L1D 阵列读
- **触发**：0

---

### C 组：不走 store→load forwarding（11 个）

#### 11. movbe ✅ 触发 ~1.9/min
- **负载类型**：字节交换可逆性（ALU 字节交换 + L1D 同址重读）
- **输入方式**：1 源 load（input 64KB 共享只读），store 值 = ALU 加工（rev），swapped 64KB 共享
- **指令序列**(objdump，修正：源码 2 个 bswap，编译后第 2 个被 DCE 消失)：
  ```
  ldr w1,[input,i]; rev w4,w1(数据ALU); str w4,[swapped,i];
  ldr w4,[input,i](同址重读!); cmp w4,w1
  ```
- **store→load 关系**：store(swapped) 与 load(input) **异址**，**非 forwarding**；两次 ldr 同址读 input = **L1D 阵列重读**
- **触发**：57 唯一 fail 块，全 thread 179，index 随机分布
- **机制**：对同一 L1D 行窄窗内两次 ldr 不一致（印证 isolated-recross-golden-protocol）

#### 12. mite ❌ 0-fail
- **负载类型**：MITE switch（指令解码器切换 + 分支预测 + ALU）
- **输入方式**：1 源 load（input 2KB 共享只读），ALU 链（add/eor/sub + 条件乘 13/17）
- **指令序列**(objdump)：
  ```
  ldr w0,[input,i]; add w0,w0,w1; eor w0,w0,w1; sub w0,w0,w1(数据ALU链);
  tst; mul; csel; ubfx; add; (无 str→ldr 同址)
  ```
- **store→load 关系**：无同址 store→load，纯 ALU+分支
- **触发**：0

#### 13. mrn_flags ❌ 0-fail
- **负载类型**：ALU 标志位 + 条件选择（mvn/cmp/csel）
- **输入方式**：1 源 load（src 8KB 共享只读），store 值 = ALU 加工（mvn/csel），dst 8KB per-thread
- **指令序列**(objdump)：
  ```
  ldr x0,[src,i]; mvn x0,x0(数据ALU); cmp x0,#0; csel x0,x22,x0,eq;
  str x0,[dst,i](异址,无重载)
  ```
- **store→load 关系**：src 与 dst 异址，**无 store 后紧邻重载**
- **触发**：0（有数据 ALU 但无重载 → 印证"数据ALU单独不充分"）

#### 14. modified_sort ❌ 0-fail
- **负载类型**：冒泡排序变体压 memory renaming
- **输入方式**：随机初始化 src 2KB → memcpy dst → std::sort golden → 手写冒泡，per-thread
- **指令序列**(objdump, 纯 C++)：memcpy/memcmp→LDP/STP；冒泡 temp=src[j];src[j]=src[j+1];src[j+1]=temp→LDR+STR 序列
- **store→load 关系**：RMW 同址但非紧贴（取决于展开），测 renaming 非直接 forwarding
- **触发**：0

#### 15. move_elimination_jit ❌ 0-fail
- **负载类型**：JIT 长链寄存器间 MOV（压 renamer/move elimination）
- **输入方式**：无内存 load（mmap 4096×2B JIT 代码），纯寄存器间
- **指令序列**(objdump, JIT emit_word)：`ORR Xd,XZR,Xsr`(=MOV 64位) ×256 + RET
- **store→load 关系**：无，纯寄存器间不访存
- **触发**：0

#### 16. move_elimination_8_jit ❌ 0-fail
- **负载类型**：JIT 8 位寄存器间 MOV（ARM64 降级 32 位）
- **指令序列**：`ORR Wd,WZR,Wsr`(=MOV 32位) ×256 + RET，验低字节
- **store→load 关系**：无
- **触发**：0

#### 17. move_elimination_vec_evex_jit ❌ 0-fail
- **负载类型**：JIT 向量寄存器间 MOV（NEON ORR）
- **指令序列**：`ORR Vd.16B,Vn,Vn`(=MOV 128位 NEON) ×128 + 1对 LDR/STR Qt（不紧贴）
- **store→load 关系**：1 对 LDR/STR 但隔 128 条 ORR，非 forwarding
- **触发**：0

#### 18. movdq2q ❌ 0-fail
- **负载类型**：vector→GPR element move（NEON V0 低64位→X0）
- **输入方式**：load low/high_parts 各 8KB 共享只读，构造 128 位 vector
- **指令序列**(objdump, ARM-only 文件)：`ld1 → fmov/vmov 到 V0 → mov Xd,Vm.d[0] → 寄存器比较`
- **store→load 关系**：无 store，纯 load→vector→GPR move
- **触发**：0

#### 19. movq2dq ❌ 0-fail
- **负载类型**：GPR→vector 标量 move（fmov，高64清零）
- **输入方式**：load values 2KB 共享只读
- **指令序列**(objdump)：`ldr → fmov Dd,Rn → vgetq_lane_u64 提取`
- **store→load 关系**：无 store，纯 load→GPR→fmov
- **触发**：0

#### 20. movmskpspd ❌ 0-fail
- **负载类型**：向量符号位提取为 mask（USHR 移位隔离符号位）
- **输入方式**：load fvalues(4KB float)/dvalues(4KB double) 共享只读
- **指令序列**(objdump, aarch64 asm)：`ldr q0,[buf] → ushr v0.4s,#31 → umov w,Vs[idx]`(ps)；`ushr v0.2d,#63`(pd)
- **store→load 关系**：无 store，纯 load→向量 ALU 移位→element move
- **触发**：0

---

### D 组：ARM64 不可用（3 个）

#### 21. zero_control_vec_sse_jit ❌ 不可用
- **负载类型**：x86 SSE 不污染 YMM/ZMM 高位（纯 x86 概念）
- **指令序列**：只有 x86 JIT（emit_byte），无 aarch64 分支，init 返回 EXIT_SKIP
- **触发**：0（空跑秒退）

#### 22. zero_control_vec_evex_jit ❌ 不可用
- **负载类型**：x86 EVEX 清零 YMM/ZMM 高位
- **触发**：0（空跑秒退）

#### 23. zero_control_vec_vex_jit ❌ 不可用
- **负载类型**：x86 VEX 清零 YMM 高位
- **触发**：0（空跑秒退）

---

## 三、触发 vs 不触发：输入方式与指令序列逐特征判别

> 本节聚焦用户问题：**输入方式**和**顺序（指令序列）**是否对 SDC 有影响？
> 判别逻辑：若某特征是触发必要条件，则触发组都该有、不触发组都该无；若不触发组反例存在，则该特征无判别力（非必要）。
> objdump 基准已重新取证：mrn_rmw 内层循环 `90:e8` = `ldp取指针→ldr源A→ldr源B→eor→(分支选op)→add temp址→str→ldr(forwarding背靠背)→add dst址→str→i++`；mrn_nuke `80:a4` = `ldr源→add temp址→str→ldr(forwarding背靠背)→add dst址→str→i++`。**两者 str→ldr 均背靠背 0 间隔，微操作骨架同构，唯一差异=mrn_rmw 多 2 源 load + 数据 ALU。**

### A. 输入方式维度判别

| 子特征 | 触发组(movbe/mrn_rmw) | 不触发组反例 | 判别力 |
|---|---|---|---|
| 源 load 数 = 1 | movbe(1源) 触发 | mrn_nuke(1源) 0-fail | ❌ 1源既触发又不触发，非判据 |
| 源 load 数 = 2 | mrn_rmw(2源) 触发 | mem_disambig(2源) 0-fail | ❌ 2源既触发又不触发，非判据 |
| store 值经数据 ALU 加工 | movbe(rev)/mrn_rmw(eor) 都有 | mrn_flags(mvn)有却0; mrn_nuke无也... | ❌ v2探针否定(加eor不翻转)+mrn_flags反例 |
| store 值 = 原值未加工 | — | mrn_nuke/mem_disambig/atomic 原值0-fail | ❌ 不触发组特征，非充分 |
| buffer 共享(init共享) | movbe(64KB共享) | mrn_nuke(8KB per-thread)0-fail | ❌ 共享性无单调关系 |
| buffer per-thread | mrn_rmw(8KB per-thread) | mrn_nuke(8KB per-thread)0-fail | ❌ 同 per-thread 一触一不触 |
| buffer 大小 64KB | movbe(64KB) | footprint跨度2000倍都触发已证伪 | ❌ [[footprint-independent-of-l1d-size]] |
| 输入数据值有某bit固定 | 42条跨5轮独立样本无constant bit | — | ❌ [[sdc-trigger-input-constant-bit-analysis]] |

**输入方式判别结论**：输入方式的每一个子特征——源 load 数、store 值是否经 ALU、buffer 共享性/大小、输入数据值——**都没有判别力**。同一输入方式既出现在触发组也出现在不触发组。**输入方式不决定 SDC 是否触发。**

### B. 顺序（指令序列）维度判别

| 子特征 | 触发组(movbe/mrn_rmw) | 不触发组反例 | 判别力 |
|---|---|---|---|
| store→load forwarding 背靠背(0间隔) | mrn_rmw(str→ldr背靠背) | mrn_nuke(str→ldr背靠背同构)0-fail; mem_disambig背靠背0-fail | ❌ 背靠背forwarding非充分(同构却不触发) |
| 第二次访存走 L1D 阵列重读 | movbe(两次ldr同址) | mrn_rmw无此模式却触发 | ⚠️ 只解释movbe不跨族 |
| 第二次访存走 store buffer forwarding | mrn_rmw(forwarding) | mrn_nuke/mem_disambig同forwarding却0-fail | ❌ forwarding非充分 |
| store 值经 ALU 后再 forwarding | mrn_rmw(eor→str→ldr) | v2探针(asm固定寻址,加eor)30min 0-fail | ❌ 因果被探针否定(相关性真) |
| 每轮 ldr 绝对次数高 | movbe 32768ldr/轮 | mrn_nuke 24576ldr/轮 0-fail | ❌ [[objdump-7tests-trigger-vs-notrigger]] 证伪load计数驱动 |
| 循环体长度短 | movbe 9条 | mrn_nuke 10条0-fail; mrn_rmw 23条触发 | ❌ 无单调关系 |
| store→load 时序窗口≤2cyc | movbe/mrn_rmw 都紧 | mrn_pairs(拉开7条)0-fail | ⚠️ 拉开确实灭活,但紧窗≠充分(mrn_nuke紧却0) |

**顺序判别结论**：
- **"背靠背 forwarding"非充分**：mrn_nuke/mem_disambiguation 与 mrn_rmw 微操作字节同构（str→ldr 背靠背 0 间隔），却不触发。所以"顺序紧"不是开关。
- **"时序窗口拉开"确实灭活**：mrn_pairs（store→load 隔 7 条）0-fail，mfence（隔 DMB）0-fail——但这是**灭活条件**，不是**触发充分条件**（紧=可能触发也可能不触发，松=必不触发）。
- **顺序对 SDC 有影响，但不是"有/无"二元开关**：紧时序是**必要非充分**条件（拉开必灭活，紧着未必触发）。真正决定触发的，是紧时序之外还有别的因素（179 硬件 marginal 窗口命中）。

### C. 综合判别：输入方式×顺序的交互

把两个维度合起来看，触发 vs 不触发的真正分界**不在任何一个单维度的特征上**：

- **mrn_rmw(触发) vs mrn_nuke(0-fail)**：输入方式差(2源+ALU vs 1源无ALU) + 顺序同(都背靠背forwarding)。但 v2 探针证明单独加 ALU 不翻转 → 差异不在 ALU。
- **mrn_rmw(触发) vs mem_disambig(0-fail)**：输入方式同(2源) + 顺序同(背靠背forwarding) + 唯一差=store值是否经数据ALU。但 mrn_flags 有数据ALU却0-fail + v2探针否定 → 不在数据ALU。
- **movbe(触发) vs mite(0-fail)**：输入方式同(1源共享) + 都有数据ALU链 + 顺序差(movbe有同址重读, mite纯ALU无重载)。同址重读只解释movbe。

**没有找到"输入方式×顺序"的任何单一组合能跨两族干净区分触发与不触发。** 触发是多因素交互（紧时序是必要条件，但还需命中179硬件marginal窗口），且 movbe(L1D重读) 与 mrn_rmw(forwarding) 可能是两条独立路径。

---

## 四、探针实验对结论的修正

---

## 四、探针实验对结论的修正

### v1 探针(probe_alu_fwd) — 0-fail 无信息量
- alu_inv 变体 0-fail，但 objdump 显示编译器因 C 层 eor 依赖链每轮重取 src 指针，多余变量没对齐窗口
- 教训：功能等价改写/编译器寻址决策差异本身破坏触发

### v2 探针(probe_asm_fwd) — 0-fail 有信息量，否定数据 ALU 假说
- 用 asm 固定寻址，objdump 验证两变体 store→load forwarding 骨架字节同构，唯一差异=1 条 eor
- base(无eor) 与 alu(有eor) 各 30min 全核含 179 均 0-fail
- **结论：在 mrn_nuke 骨架(1源load+forwarding)上加/去数据 ALU 不改变触发。数据 ALU 不是 179 SDC 触发开关。**
- confound：探针仍 1 源 load，真触发 mrn_rmw 是 2 源 load+ALU+forwarding。数据 ALU 是 mrn_rmw 伴随特征但非充分开关。

### 对既有 2×2 矩阵的修正
`trigger-2x2-dataalu-reload` 记的 2×2 矩阵里"数据 ALU"维的**因果性被实验否定**（相关性仍真：movbe/mrn_rmw 确都有数据 ALU，但加了数据 ALU 不足以触发）。触发不是单变量开关，是多因素交互或两族独立机制。

---

## 五、下一步方向

放弃找"跨两族共同特征"，改为**分族各自定位**：
- **movbe 族**：单独做"两次 ldr 同址重读"时序窗口探针（改两次 ldr 间距看何时灭活）
- **mrn_rmw 族**：反向删减（2源+eor+forwarding 逐项删，看删哪项灭活）

movbe(1.9/min, L1D同址重读) 与 mrn_rmw(0.2/min, forwarding) 触发率差 10 倍、第二次访存路径不同（L1D阵列 vs store buffer），**可能是两条独立触发路径**，只都落在 179 上，不该合在一个矩阵找共同特征。
