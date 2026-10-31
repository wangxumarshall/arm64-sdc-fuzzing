# 计划：把"2源load+ALU依赖链"移植到其他 mrn 类骨架

## 目标

验证"2源load+ALU依赖链"（已在 mrn_nuke_2src_alu 强触发 14fail/36min）是否是**通用可移植触发特征**——放到其他 mrn 类骨架上能否也触发 179 SDC。

## 候选筛选

mrn 类核心测试：
- mrn_rmw：已触发（2源+ALU基准）✅
- mrn_nuke：0-fail，已加2src_alu触发（变体1）✅
- mrn_pairs：0-fail（8store→8load，时序拉开7条）→ **改造**
- mrn_reloaded：0-fail（byte/dword/qword store→load背靠背）→ **改造**
- mrn_flags：0-fail（纯ALU+分支，无store→load路径）→ **不适合**（没有load/store骨架可加2源load）

选定 2 个候选：**mrn_pairs_2src_alu**、**mrn_reloaded_2src_alu**

## 改造方案

### 变体5：mrn_pairs_2src_alu

**mrn_pairs 原版**：1源src，8store(原值)→8load(forwarding，但时序拉开7条)，0-fail。

**改造点**：
1. src单数组 → srcA+srcB双源
2. store原值 → store(a op b)ALU结果（轮换add/sub/eor/and）
3. **8+8展开改回逐元素store→load背靠背**（去掉时序拉开，恢复触发前提）
   - 这一步是关键：mrn_pairs 0-fail 的根因之一是时序拉开7条，若保持8+8即使加2源+ALU可能仍0-fail
   - 但这也引入第二变量（时序+ALU）。为干净对照，做**两个子版本**：
     - 5a. mrn_pairs_2src_alu：2源+ALU + 逐元素背靠背（两个变量都改，看是否触发）
     - 5b. mrn_pairs_2src_alu_keep8：2源+ALU + 保持8+8展开（只改ALU，看8+8是否灭活）
   - 对比5a/5b能分离"2源+ALU"vs"时序拉开"的影响

**骨架**：
```
5a(逐元素): for i: a=srcA[i]; b=srcB[i]; res=a op b; store(temp[i],res); store(dst[i],load(temp[i]));
5b(8+8):   for i+=8: 8x(a=srcA; b=srcB; res; store temp); 8x(load temp→dst)
```

### 变体6：mrn_reloaded_2src_alu

**mrn_reloaded 原版**：1源(src8/src32/src64)，byte/dword/qword各store→load背靠背，存原值，0-fail。

**改造点**：
1. 只改 qword 段（64位，与mrn_rmw/mrn_nuke同粒度）——byte/dword段保持原样或删掉，聚焦qword
2. src64单数组 → srcA+srcB双源
3. store原值 → store(a op b)ALU结果
4. 骨架不变：store_qword(&temp[i], res); load_qword(&temp[i])背靠背

**骨架**：
```
for i: a=srcA[i]; b=srcB[i]; res=a op b; store_qword(&temp[i],res); r=load_qword(&temp[i]); cmp(r,expected)
```

## 文件清单（4个新变体）
- `tests/cpu/misc/mrn_pairs_2src_alu.cpp`（5a，逐元素背靠背）
- `tests/cpu/misc/mrn_pairs_2src_alu_keep8.cpp`（5b，保持8+8）
- `tests/cpu/misc/mrn_reloaded_2src_alu.cpp`（6，qword段双源+ALU）

## meson.build 注册
misc 区块加3行。

## 验证协议（两阶段 [[arithmetic-test-sdc-verification-protocol]]）
1. 阶段1：排除179核60s须0-fail（证明变体无bug）
2. 阶段2：全核192含179+auto seed 36min（30min×120%，-T设总时间）坐实
3. 用串行脚本一口气跑完（run_variants_30min_serial.sh模式），不让用户中途点yes
4. 低率变体做确定性核实（排除179+同seed→0fail）区分真SDC vs bug

## 判别逻辑
- 多个骨架加2源+ALU都触发 → "2源load+ALU依赖链"是通用可移植触发特征
- 5a触发+5b不触发 → 时序拉开灭活（8+8即使加ALU也不触发），印证"紧时序必要"
- 都不触发 → 2源+ALU不是充分条件，还依赖别的（如mrn_nuke骨架特定）
