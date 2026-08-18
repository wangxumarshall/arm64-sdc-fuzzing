#!/usr/bin/env python3
"""
SDC bit-level XOR analyzer
==========================

对一批 SDC(静默数据损坏)错误样本做 bit 级异或分析,判断故障更接近:
  A 假设 — "电压噪声导致的位翻转"            (典型特征: 汉明重量低, 1~3 bit)
  B 假设 — "寄存器/数据被错误替换成另一个真实存在的值"
           (典型特征: 汉明重量接近位宽一半, 且 actual 精确匹配 context 中某个值)

输入文件: Eigen 案例的 all_fail_blocks.log
  每个 Fail Block 含:
    actual data:   32 字节 (8 个 uint32 / 4 个 double), 小端
    expected data: 32 字节, 与 actual 一一对应
  解析粒度: 每个 double (64 bit) 作为一条记录.

context 候选集(用于精确匹配判定):
  - 同一 block 内的其他 expected double 值(排除当前记录自身位置)
  - 全部所有 block 的全部 expected double 值
  若某条记录的 actual 精确等于候选集中任一值 -> 支持 B 假设, 并标出来源.
"""

import struct
import sys
import math
import statistics
from collections import Counter

# ----------------------------------------------------------------------
# 可调参数
# ----------------------------------------------------------------------
BIT_WIDTH = 64                      # 64 位 (double)
BYTES_PER_ELEM = BIT_WIDTH // 8     # 8 字节 / double
# 每个 block: 2 行 actual(各16字节) + 2 行 expected(各16字节)
#          = 64 字节 = 8 个 double
ELEMS_PER_BLOCK = 64 // BYTES_PER_ELEM   # 每个 block 8 个 double

# 判定阈值 (汉明重量)
LOW_HW_THRESHOLD = 3                # HW <= 3 -> 支持位翻转(A)
HALF_BITWIDTH = BIT_WIDTH // 2      # 32
NEAR_HALF_TOLERANCE = BIT_WIDTH // 8  # 容差 ±8


# ----------------------------------------------------------------------
# 日志解析
# ----------------------------------------------------------------------
def parse_bytes_from_line(line):
    """从一行形如 '  a0 ba bd 40  2e 04 25 40 ...' 中提取字节列表."""
    tokens = line.split()
    out = []
    for t in tokens:
        if len(t) == 2:
            try:
                out.append(int(t, 16))
            except ValueError:
                pass
    return out


def parse_log(path):
    """
    解析 all_fail_blocks.log, 返回 blocks 列表.
    每个 block = {'id': int, 'actual': bytes(32), 'expected': bytes(32)}
    """
    blocks = []
    cur_id = None
    cur_state = None          # 'actual' / 'expected'
    cur_actual = []
    cur_expected = []
    cur_block_ids = []

    with open(path, 'r') as f:
        for raw in f:
            line = raw.rstrip('\n')
            s = line.strip()
            if s.startswith('========== Fail Block'):
                # 解析 block id
                try:
                    bid = int(s.replace('========== Fail Block', '').replace('==========', '').strip())
                except ValueError:
                    bid = -1
                # flush 上一块
                if cur_id is not None:
                    blocks.append({
                        'id': cur_id,
                        'actual': bytes(cur_actual),
                        'expected': bytes(cur_expected),
                    })
                cur_id = bid
                cur_actual = []
                cur_expected = []
                cur_state = None
            elif s == 'actual data:':
                cur_state = 'actual'
            elif s == 'expected data:':
                cur_state = 'expected'
            elif cur_state in ('actual', 'expected'):
                bs = parse_bytes_from_line(line)
                if cur_state == 'actual':
                    cur_actual.extend(bs)
                else:
                    cur_expected.extend(bs)
        # flush 最后一块
        if cur_id is not None:
            blocks.append({
                'id': cur_id,
                'actual': bytes(cur_actual),
                'expected': bytes(cur_expected),
            })
    return blocks


def bytes_to_doubles(b):
    """32 字节(小端) -> 4 个 double."""
    return [struct.unpack('<d', b[i:i + BYTES_PER_ELEM])[0]
            for i in range(0, len(b), BYTES_PER_ELEM)]


def double_to_uint64(d):
    """double -> 64 位无符号整数(按 IEEE754 位模式)."""
    return struct.unpack('<Q', struct.pack('<d', d))[0]


def uint64_to_double(u):
    return struct.unpack('<d', struct.pack('<Q', u))[0]


# ----------------------------------------------------------------------
# 核心: 每条记录的分析
# ----------------------------------------------------------------------
def hamming_weight(x):
    return bin(x).count('1')


def flipped_bit_positions(xorval, width=BIT_WIDTH):
    """返回翻转的 bit 位号列表(0 = 最低位)."""
    return [i for i in range(width) if (xorval >> i) & 1]


def find_exact_match(actual_d, context_pool):
    """
    在 context_pool 中精确查找 actual_d.
    context_pool: list of (value, source_str)
    返回命中来源字符串, 未命中返回 None.
    """
    for val, src in context_pool:
        # 用位模式比较, 避免 NaN/0/-0 等浮点边界歧义
        if double_to_uint64(val) == double_to_uint64(actual_d):
            return src
    return None


# ----------------------------------------------------------------------
# 主流程
# ----------------------------------------------------------------------
def main():
    if len(sys.argv) < 2:
        path = 'eigen_core179_30m_stress_logs/all_fail_blocks.log'
    else:
        path = sys.argv[1]

    print(f'[*] 解析日志: {path}')
    blocks = parse_log(path)
    print(f'[*] 解析到 {len(blocks)} 个 Fail Block')

    # 1. 把所有 block 转成 double 列表, 建立全局 context 池
    #    context 来源: 所有 block 的所有 expected double
    global_expected = []          # [(double, 'block#i/expected[j]')]
    block_doubles = []            # 每个 block 的 (actual_doubles, expected_doubles)
    for blk in blocks:
        a = bytes_to_doubles(blk['actual'])
        e = bytes_to_doubles(blk['expected'])
        block_doubles.append((blk['id'], a, e))
        for j, val in enumerate(e):
            global_expected.append((val, f'block#{blk["id"]}/expected[{j}]'))

    # 2. 逐条分析
    records = []
    for bid, a_list, e_list in block_doubles:
        for j in range(ELEMS_PER_BLOCK):
            actual_d = a_list[j]
            golden_d = e_list[j]
            au = double_to_uint64(actual_d)
            gu = double_to_uint64(golden_d)
            xorv = au ^ gu
            hw = hamming_weight(xorv)
            bits = flipped_bit_positions(xorv)

            if hw == 0:
                continue  # 该元素未翻转, 跳过

            # 构造本块 context: 同块其他 expected(排除自身位置) + 全局 expected
            local_ctx = [(e_list[k], f'block#{bid}/expected[{k}]')
                         for k in range(ELEMS_PER_BLOCK) if k != j]
            ctx_pool = local_ctx + global_expected
            match_src = find_exact_match(actual_d, ctx_pool)

            records.append({
                'id': f'{bid}/{j}',
                'block': bid,
                'index': j,
                'actual_d': actual_d,
                'golden_d': golden_d,
                'actual_u': au,
                'golden_u': gu,
                'xor': xorv,
                'hw': hw,
                'bits': bits,
                'match': match_src,
            })

    total = len(records)
    print(f'[*] 翻转的 double 记录数: {total}  (未翻转元素已跳过)')
    if total == 0:
        print('[!] 没有翻转记录, 退出.')
        return

    # ---------------- 汇总表格 ----------------
    print('\n' + '=' * 110)
    print('记录ID | actual(double) | golden(double) | XOR(hex) | HW | 翻转bit位置 | 精确匹配')
    print('-' * 110)
    for r in records:
        match_str = f'是 <- {r["match"]}' if r['match'] else '否'
        bits_str = ','.join(str(b) for b in r['bits']) if r['bits'] else '-'
        # 浮点打印成紧凑形式
        a_str = f'{r["actual_d"]:.6g}'
        g_str = f'{r["golden_d"]:.6g}'
        print(f'{r["id"]:<8} | {a_str:<16} | {g_str:<16} | '
              f'0x{r["xor"]:016x} | {r["hw"]:>2} | {bits_str:<20} | {match_str}')
    print('=' * 110)

    # ---------------- 汉明重量分布 ----------------
    hws = [r['hw'] for r in records]
    print('\n[汉明重量分布]')
    print(f'  最小值 : {min(hws)}')
    print(f'  最大值 : {max(hws)}')
    print(f'  平均值 : {statistics.mean(hws):.2f}')
    print(f'  中位数 : {statistics.median(hws)}')
    print(f'  标准差 : {statistics.pstdev(hws):.2f}' if len(hws) > 1 else '  标准差 : N/A')
    hist = Counter(hws)
    print('  直方图:')
    for hw in sorted(hist):
        bar = '#' * hist[hw]
        print(f'    HW={hw:>2}: {bar} ({hist[hw]})')

    # ---------------- 翻转 bit 位置分布 ----------------
    print('\n[翻转 bit 位置分布] (0=最低位, 63=最高位)')
    bit_counter = Counter()
    for r in records:
        for b in r['bits']:
            bit_counter[b] += 1
    print(f'  涉及的不同 bit 位: {len(bit_counter)} 个')
    # 按 bit 号排序
    for b in sorted(bit_counter):
        bar = '#' * bit_counter[b]
        # 标注该 bit 在 double 里的语义(符号/指数/尾数)
        if b == 63:
            seg = '符号位'
        elif 52 <= b <= 62:
            seg = f'指数位(bit{b})'
        else:
            seg = f'尾数位(bit{b})'
        print(f'    bit{b:>2} [{seg:<14}]: {bar} ({bit_counter[b]})')

    # 按 IEEE754 段聚合
    sign_flips = sum(bit_counter.get(b, 0) for b in range(63, 64))
    exp_flips = sum(bit_counter.get(b, 0) for b in range(52, 63))
    mant_flips = sum(bit_counter.get(b, 0) for b in range(0, 52))
    print(f'\n  按 IEEE754 段聚合(含重复计数,因一条记录可能多段都翻):')
    print(f'    符号位翻转次数合计 : {sign_flips}')
    print(f'    指数位翻转次数合计 : {exp_flips}')
    print(f'    尾数位翻转次数合计 : {mant_flips}')

    # ---------------- 精确匹配统计 ----------------
    matched = [r for r in records if r['match']]
    print(f'\n[精确匹配(context 命中)]')
    print(f'  命中记录数: {len(matched)} / {total}  ({100*len(matched)/total:.1f}%)')
    if matched:
        print('  命中明细:')
        for r in matched:
            print(f'    记录 {r["id"]}: actual(0x{r["actual_u"]:016x}) 命中 <- {r["match"]}')

    # ---------------- 判定 ----------------
    print('\n' + '=' * 70)
    print('[判定结论]')
    low_hw_count = sum(1 for h in hws if h <= LOW_HW_THRESHOLD)
    near_half_count = sum(1 for h in hws if abs(h - HALF_BITWIDTH) <= NEAR_HALF_TOLERANCE)
    match_count = len(matched)

    print(f'  HW <= {LOW_HW_THRESHOLD}(支持位翻转 A) 的记录: {low_hw_count}/{total} '
          f'({100*low_hw_count/total:.1f}%)')
    print(f'  HW 接近 {HALF_BITWIDTH}±{NEAR_HALF_TOLERANCE}(支持数据替换 B): {near_half_count}/{total} '
          f'({100*near_half_count/total:.1f}%)')
    print(f'  actual 精确匹配到 context 值(强支持数据替换 B): {match_count}/{total} '
          f'({100*match_count/total:.1f}%)')

    # 判定逻辑
    # 注意: 用户原始描述里把"低位翻转"标为B,"数据替换"标为A, 但常理位翻转->A、替换->B.
    # 这里采用直白的"位翻转 vs 数据替换"两分, 并给出置信度.
    support_flip = low_hw_count
    support_replace = match_count + near_half_count

    print('\n  ---- 初步判断 ----')
    if match_count > 0:
        print(f'  发现 {match_count} 条记录的 actual 精确等于 context 中某个真实存在的值,')
        print(f'  这是"数据被替换成另一个真实值"的强证据 -> 倾向 数据替换假设.')
        conf = '高' if match_count >= 3 else '中(样本偏少)'
        print(f'  置信度: {conf}')
    elif low_hw_count / total >= 0.7:
        print(f'  {low_hw_count}/{total} ({100*low_hw_count/total:.0f}%) 记录的汉明重量 <= {LOW_HW_THRESHOLD},')
        print(f'  典型的少量位翻转特征 -> 倾向 电压噪声位翻转假设.')
        conf = '高' if total >= 10 else '中(样本数偏少)'
        print(f'  置信度: {conf}')
    elif near_half_count / total >= 0.5:
        print(f'  {near_half_count}/{total} 记录的汉明重量接近位宽一半({HALF_BITWIDTH}),')
        print(f'  但未发现精确匹配 -> 中等倾向 数据替换假设, 但来源不明.')
        print(f'  置信度: 中')
    else:
        print(f'  汉明重量分布未明显偏向任一假设:')
        print(f'    低 HW 记录 {low_hw_count}/{total}, 近半 HW 记录 {near_half_count}/{total}, 精确匹配 0.')
        print(f'  无法明确区分, 建议增加样本或补充 context 数据集.')
        print(f'  置信度: 低')

    # 局限性提示
    print('\n  ---- 局限性 ----')
    if total < 10:
        print(f'  ⚠ 样本数 {total} 偏少, 统计结论仅供参考, 建议扩充日志样本.')
    print('  ⚠ context 候选集仅来自本日志的 expected 值; 若实际寄存器替换源不在此集,')
    print('    精确匹配会漏判(假阴性), 需补充更完整的 context 值清单.')
    print('  ⚠ 汉明重量判定基于经验阈值, 非理论硬界线; 边界样本(如 HW=4~6)需人工复核.')
    print('=' * 70)


if __name__ == '__main__':
    main()
