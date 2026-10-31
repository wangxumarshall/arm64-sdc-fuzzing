# CORE179 读路径 K-cells 批次 2 战役结果(2026-09-13 夜 ~ 09-14 凌晨)

执行:2026-09-13 20:30:13 起,11 格串行、每格 30min、全核 192(含 179)、auto seed
(`scripts/kcells_campaign.sh`,pid 2871398)。
本文档为预注册判据(设计文档 `CORE179_READPATH_K_CELLS_BATCH2_20260913.md` §13)的裁决记录。

---

## 0. 执行完整性

- 前 10 格全部完整跑满 30min(`exit:` 行 + 时间戳核对)。
- **最后一格 k3res 在 01:45:56 被第 12 次 179 内核 panic 打断**(只跑 15min/646 迭代)。
  kdump 转储:`/home/sdc/vmcore/127.0.0.1-2026-09-14-01:45:56/`(vmcore-dmesg.txt 为证)。
  机器 01:52 重启;/tmp 监控日志随 tmpfs 丢失;战役进程未走完 `kill $MONPID` 尾部。
- fail 核号:cpu-mask 解析(剥离 `:` 分隔符),**全部 fail 锁定核 179**,无一例外。

## 1. 触发裁决表

| 格 | fail 块 | 率/min | dump | 裁决 |
|---|---|---|---|---|
| k5far(P1 决定格,交错双源) | 37 | 1.25 | 37 | **触发** |
| std_rowmajor(基线) | 58 | 1.96 | 0(父测试无 dump 纪律,设计使然) | 触发 |
| k5inter_rand(交错+自然随机) | 72 | ~2.4 | 72 | 触发(高于基线) |
| k7p_rand | 78 | 2.6 | 78 | 触发 |
| k7p_one | 42 | 1.4 | 42 | 触发 |
| k7p_hiham | 44 | 1.5 | 44 | 触发 |
| **k7p_zero** | **0** | 0 | — | **不触发** |
| **k4gap(load→ALU 间 8nop)** | **0** | 0 | — | **不触发** |
| **k4bgap(ALU→str 间 8nop)** | **0** | 0 | — | **不触发** |
| **k2pureload(热循环零 store)** | **0** | 0 | — | **不触发** |
| k3res(4×footprint=256KiB) | 114(15min) | 7.7 | 113+2短 | 强触发(被 panic 截断) |

注:fail 计数口径 = 唯一 `result: fail` 块(YAML 缩进格式),非 grep miscompare 行。

## 2. 四大判别结论

### 2.1 k5far 决定格:E6 近邻串扰假说被否定

交错布局(srcA/srcB 元素在**同一地址空间**交替,地址邻居永远是另一族)下:
- 触发不受影响(37 fail);
- 但失效 got 值在交错缓冲全表中 **0/91 命中**——错误值既不是邻居族元素,也不是
  交错缓冲里任何位置的存储值。

→ 替换源**不跟随物理近邻**。"field_subst 主族 = srcA 近邻字段替换"(首轮 GPS 93%)
在交错布局下不复现,首轮的"近邻"是**缓冲身份/逻辑槽位**相关,不是物理地址相邻。

### 2.2 store 必要性坐实(k2pureload = 0 fail)

热循环零 store(xor 累加器消费,内层循环 objdump 复核:22 指令、3×ldr q、0×str)
→ 完全灭活。

了结历史矛盾:store_only(首轮 14 fail)vs fwd_probe(0 fail)——**store 与 load 消费
缺一不可**,load 结果必须经 store 回写-再读链才触发。

### 2.3 紧时序双向确认(k4gap/k4bgap 均 0 fail)

load→ALU 间 8 nop(拆 bypass 窗)与 ALU→str 间 8 nop(拆注入点)都灭活。
→ 触发要求 load→ALU→store **全链 back-to-back**。与 nop-gap 历史曲线(8/16/64 归零)一致。

### 2.4 pattern 门控(k7p 电池)

- 全 0 数据 = 0 fail(**不触发**);全 1 / 高汉明 / 随机均触发;
- 数据必须有非均匀多样性;全零地址/数据背景下故障通道静默。

## 3. 签名分类(386 dumps,861 错词)

离线逐词分析(五缓冲全工作集检索 + 16bit 字段分解 + 字节流错位窗检索)。

### 3.1 统一新签名【跨字段搬运】——本战役最大发现

```
got = exp ± X * (2^32 − 2^16)      (mod 2^64)
```

- 即 16bit 字段 f1[47:32] 减 X、f2[31:16] 加 X(或反向),tag 与 f3 不动;
- **精确公式符合 294/294(100%)**;
- X 分布:0x80(44%)、0xc0(22%)、0x100(11%)、0x180(5%)… 低幅值主导,大 X 零星;
- **op 免疫谱:eor = 0 例(完全免疫)**;orr 186 / and 68 / add 40;
- 同元素两条 lane 常成对同 X(k7p_rand 78/82 成对);
- 占比:k7p_rand 88%、k3res 57%、k5far 20%、k5ir 0。

解读约束:eor(无进位语义)完全免疫 + orr/and(本无进位)也出现 → 污染不在
运算语义本身,而是**结果通路上的数值搬运算术**;公式 `X*(2^32-2^16)` 是一个
"从 f2 到 f1 的错误借位/进位记账"。X 集中在 bit7-9 量级(0x80/0xc0/0x100),
像固定粒度的搬运单位。

### 3.2 【dst 别处 / 错位窗】

got = dst 缓冲其他位置的 8 字节窗(对齐别处 + mod8=1/5/7 错位窗):
k5ir 108/181 主导,k5far 37,k3res 76,k7p_one 26,k7p_hiham 18。
与首轮 GPS 的 misalign_win(mod-8 错位窗)与头部族(错词集中缓冲头部 w=0-5)
**同族复现**。k5far 头部污染值 19 个唯一值承载 79 错(高度重复常量样),
字节由 {00,10,ff} 构成 = tag 结构字段(byte_off/取反)错位重组。

### 3.3 【同位 A 替换】

k7p_one 66%、k7p_hiham 58% 主导:got = srcA 同位词(pattern 无 magic 时
分类器退化,但"同位替换"判定不依赖 magic)。pattern 格保留了首轮
field_subst(同位近邻替换)主族——**数据带 GPS 标签时主族回归**。

### 3.4 其它

- bitflip≤4:各格零星(2-17);
- 未溯源/在途值:k5ir 56、k5far 42、k3res 18(含 exp 单字节替换与真随机在途值);
- k5ir(自然随机)整体退化为"dst 别处 + 在途值",跨字段搬运签名消失 →
  **该签名依赖打标数据(16bit 字段结构化)才可见**,随机数据下被淹没或形态改变。

## 4. k3res 高触发率(4×footprint)

15min 114 fail(7.7/min)≈ 基线 4 倍。footprint 超出 L1D(256KiB)后触发率上升,
失效源不在"L1D 驻留集内的小热集",与 L1D 读路径(填充/驻留边界)假设一致。
(此格被 panic 截断,单 15min,下结论需复跑补满 30min。)

## 5. 第 12 次 179 panic(09-14 01:45:56)

vmcore-dmesg.txt 证据链:
1. 前奏(≥25736s 起多次):`pmdalinux`(监控守护)在 **CPU 179** 上读
   `/proc/interrupts`,`__memcpy+0x80` 命中 "spurious kernel translation fault"
   → WARNING(`__do_kernel_fault`)链,与 09-12 的 11 次完全一致;
2. 终局(142080s ≈ 01:45:56):`find_busiest_group+0x140`,`swapper/179`,
   level-3 translation fault → Oops → kdump;
3. 时间线吻合:09-12 10:17 开机 + 142080s = 09-14 01:45:56;
4. 时机:k3res 格进行中(4×footprint 读写压力最大的一格);
5. 期间内核日志另见 CPU179 两次 hotplug kill/online(5079s、23031s,系统侧操作)。

→ 第 12 次,指纹与 09-12 的 11 次完全相同。**panic 计数:12 次。**

## 6. 待办 / 遗留

- [ ] k3res 补满 30min(排除 panic 干扰后复跑);
- [ ] 跨字段搬运签名的 X 量级(0x80/0xc0/0x100)与加法器/移位器微结构的对应;
- [ ] eor 免疫谱的专项确认(eor-only 变体长跑 0 fail 预注册);
- [ ] k5ir 的"dst 别处"族与打标依赖关系(随机数据下签名形态变化);
- [ ] ⚠️ 磁盘:/home 99%(vmcore 12.3GB),需要清理或归档旧 vmcore(最早 08-14)。

## 附:分析方法备忘

- fail 块计数:grep `  result: fail`(带 YAML 两空格缩进);
- cpu-mask 核号:剥 `:` 后数 X 位置(共 192 位);
- k3res dump 尺寸 5×65536+变长文本尾;2 个截断 dump(panic 时写入一半)跳过;
- 交错缓冲重建:src_words = [A[0],B[0],A[1],B[1],…](viewA/viewB 由冷路径 materialize);
- 错位窗检索:五缓冲各自连续字节流 + raw 全流(含跨缓冲边界)。
