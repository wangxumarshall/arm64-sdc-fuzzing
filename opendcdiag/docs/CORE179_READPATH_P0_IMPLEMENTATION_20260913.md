# CORE179 读路径定位战役 P0/P0′ 实现记录(2026-09-13)

配套设计文档:`docs/CORE179_READPATH_LOCALIZATION_CAMPAIGN_20260913.md`(本文只记录实现与验证事实,不重复设计)。

## 一、交付物

| 交付物 | 路径 | 状态 |
|---|---|---|
| P0 标量 64b 底盘 | `tests/cpu/misc/neon_rot_ldr_at_top_rowmajor_scalar64.cpp` | 构建通过,冒烟 4×pass |
| P0′ GPS 打标底盘(B 轨) | `tests/cpu/misc/neon_rot_ldr_at_top_rowmajor_gps.cpp` | 构建通过,冒烟 4×pass |
| 离线签名分类器 | `scripts/gps_classify.py` | 语法通过,待首批 dump 验证 |
| meson 注册 | `tests/cpu/meson.build`(同族聚集,紧跟 rowmajor_dump) | 完成 |

## 二、objdump 同一性验证(支柱 B 的核心检查)

方法:提取三个 `*_run` 函数的**内层循环体**(后向分支界定),归一化(去地址、去分支目标、寄存器重命名)后逐指令对比。

### 2.1 GPS 版 vs 父底盘(决定性检查)

- 内层循环体 **21 条指令完全一致**(寄存器重命名 x21/x20→x23/x21 以外零差异):3×`ldr q`(scratch/srcA/srcB,同 `ldr q0,[x1]` 形状)+ i%4 轮换 ALU(`add v0.2d`/`eor`/`and`/`orr .16b`,同分支调度形状)+ 背靠背 `str q0` 双 store + rowmajor `sub x0,#0x10` 反向扫描 + `cmn x0,#0x10` 循环条件。
- 结构体布局:GPS 结构体同为 4 指针(`srcA/srcB/scratch/expected`),成员偏移 `[x19,#0/8/16/24]` 与父版完全一致——热循环的基地址装载编码相同。
- **差异仅在函数级,不在循环级**:GPS 因冷路径含 `snprintf/fopen/fwrite` 触发栈保护(`__stack_chk_guard`),prologue/epilogue 多 8 条栈保护指令、寄存器分配整体移位(x21→x23 等)。这些指令每次 TEST_LOOP 外层迭代仅执行一次,热循环内不可见。

### 2.2 标量 64b 版(P0,新底盘,无同构参照)

- 骨架形状逐条对齐:3×标量 `ldr x`(scratch/srcA/srcB)+ 轮换 ALU + 背靠背双 `str x3` + rowmajor `sub x2,#0x8` 反向扫描 + 冷路径 `memcmp`(0x4000 = 2048×8B)。
- 已知实现差异(记录,非偏差):标量版 ALU 轮换被 GCC 编成 **csel 链**(`and/orr/add` 预计算 + `csel` 选择)而非 NEON 版的分支形状;标量无 NEON 版的 `b.eq` 分发链。这是标量单元自身的编译结果,改变的是 ALU 指令的**调度形状**——正好是 K7 lane 轴要测的维度之一,不构成骨架偏差。
- 足迹:2048×8B = 16 KiB/缓冲,与父版 1024×16B = 16 KiB 相同。

### 2.3 冷路径隔离验证(GPS dump 纪律)

控制流追踪:内层循环 → `bl memcmp`(0x14c)→ `cbnz w0, 0x250`(只在 miscompare 时跳转)→ dump 块(`__snprintf_chk/fopen64/5×fwrite` 0x27c–0x2f8)。**dump 块只能由 cbnz-memcmp 进入,热循环内无任何条件分支指向它**——满足"连冷分支都不能碰"的家族纪律(对比 rowmajor_dump 变体的 30× 抑制教训)。

## 三、GPS 编码(实现定稿,对设计文档 §6.2 的具体化)

每 64b 字:`magic(16b) | byte_off(16b) | ~byte_off(16b) | generation(16b)`

- magic:srcA=0xA5A5、srcB=0x5A5A(互补)、scratch=0x0F0F
- byte_off:字在缓冲内的字节偏移(0..16383),互补字段兼做字段级完整性校验
- **generation 恒 0**(设计修正,见下)

### 3.1 设计期修正(为什么 gen 恒定)

初版设计"每 TEST_LOOP 迭代轮转 generation"实现时被否决,两个理由:
1. 轮转需每轮重写 srcA/srcB/scratch → golden(init 算一次)失效,memcmp 全线假 fail;
2. 重写让源缓冲变脏线(刚 store 过)——正是战役要冻结的 cache 状态混淆。

陈旧代桶归属 **K2 存储几何变体**(那里有真实 store→reload 窗口,存的数据本身带 gen);本底盘每轮产出相同值,"旧数据落错槽"由 byte_off 自解析,不需要 gen。分类器相应不设陈旧代桶的活跃检查。

### 3.2 ALU 混入桶的离线重构(设计修正)

初版的 `alu_ref` 常量表(存 ALU magic)被否决:ALU 结果由打标数据算出,离线分类器从快照可重构任意 `a OP b` 候选,常量表无信息量。分类器保留 `alu_mixin` 接口(TODO),首批样本到位后按实际 fail 值形状启用。

## 四、分类器实现说明

9 桶判定顺序(即优先级):整词寻回(错线/错字)→ 错位窗 → 两源拼接 → 部分字(1B/2B/4B/scat 直方图)→ 位翻转样(≤4bit 汉明)→ scratch 复核 → ALU 混入(预留)→ unknown。

- 快照检索:`Snapshot` 类一次构建三源缓冲的整词哈希表 + 连续字节流(错位窗可能跨缓冲边界——本身是信息);
- **已验证可用性前提**(设计文档 §6.1 "全部未分类≠失败"的前提):分类器带自检——打标数据的错位窗/错字命中会在 detail 里回报 `tag_off=`,与实际位置交叉核对;首批 dump 到位后先跑自检再出结论;
- 汉明直方图、mod-8 直方图、部分字粒度直方图三表齐出。

## 五、验证状态与待跑

| 项 | 状态 |
|---|---|
| 构建 | ninja 全通过 |
| 冒烟(5s×2 线程×2 测试) | 4× result: pass,0 误报,0 dump |
| 内层循环同一性(parent vs gps) | 21 指令一致(寄存器重命名外零差异) |
| 待跑:P0 标量底盘 30min 全核 | 排程中(阶段 1:排除 179 跑 191 核须 0 fail;阶段 2 全核 192 含 179) |
| 待跑:P0′ GPS B 轨 30min 全核 | 同上;fail 产出后分类器吃首批 dump |
| A 轨基线 | 父底盘(rowmajor,自然随机数据)三轮战役数据已有(223/244/276 均值口径见设计文档 §3.3),无需重跑 |

## 六、环境注意事项(排程前核对)

- 磁盘:`/home` 99% 满(剩 15G)。GPS dump 每文件 5×16KiB=80KiB,按 champion 率(223 fail/30min)上界估算 30min ≈ 18MB——可承受,但排多个 GPS 格前先清旧数据。
- dump 路径为相对路径 `movbe_log/gps_rowmajor/`(运行时 CWD),长跑前确认 CWD 有写权限;180 核并行全 fail 的最坏情况(级联误报)会到 14GB——若阶段 1 出现非 179 fail,先停跑查框架。
- 179 当前在线(cpu179/online=1),nproc=192,与协议要求一致。
