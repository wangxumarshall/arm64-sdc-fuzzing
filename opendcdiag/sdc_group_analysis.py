#!/usr/bin/env python3
"""
SDC 分组分析 (v2): 基于 83 条字节级 XOR 结果做分组统计
================================================================

数据集: all_fail_blocks.log 里的 83 条翻转 double (字节级全量比对所得,
       包含 Eigen isApprox 未单独报告的"隐藏"翻转元素).
测试类型/offset: 通过每个 block 的 expected_dump 指纹反查原始日志
                core179_eigen_30m_20260812_084903.log 得到.

任务:
  1. 按 fail block 分组: 列出块内各出错 double 的 HW, 判断簇内一致/分裂.
  2. 位置索引 vs HW 簇.
  3. 测试类型 vs HW 簇.
  4. 汇总表 + 关联结论.
"""

import struct
import re
import sys
import statistics
from collections import defaultdict, Counter

RAW_LOG = 'eigen_core179_30m_stress_logs/core179_eigen_30m_20260812_084903.log'
FAIL_BLOCKS = 'eigen_core179_30m_stress_logs/all_fail_blocks.log'

LOW_HW_MAX = 8          # HW <= 8  -> 低 HW 簇 (位翻转倾向)
NEAR_HALF_MIN = 18      # HW >= 18 -> 近半 HW 簇 (数据替换倾向); 9~17 灰色

ELEMS_PER_BLOCK = 8     # 64 字节 = 8 double


def hw(x):
    return bin(x).count('1')

def bit_positions(x, width=64):
    return [i for i in range(width) if (x >> i) & 1]

def cluster_of(h):
    if h <= LOW_HW_MAX:
        return 'low'
    if h >= NEAR_HALF_MIN:
        return 'near_half'
    return 'gray'


# ============================================================
# A. 解析 all_fail_blocks.log -> 83 条记录 (字节级全量)
# ============================================================
def parse_fail_blocks(path):
    """
    返回 records 列表, 每条 = block 内一个翻转 double.
    字段: block_id, pos_in_block, actual_u, expected_u, xor, hw, bits
    """
    blocks = []          # [{'id':int, 'actual':bytes(64), 'expected':bytes(64)}]
    cur_id = cur_state = None
    cur_a = cur_e = []
    for raw in open(path):
        s = raw.strip()
        if s.startswith('========== Fail Block'):
            if cur_id is not None:
                blocks.append({'id': cur_id, 'actual': bytes(cur_a), 'expected': bytes(cur_e)})
            try:
                cur_id = int(s.replace('========== Fail Block', '').replace('==========', '').strip())
            except ValueError:
                cur_id = -1
            cur_a = []   # 注意: 不能写 cur_a = cur_e = [] (会别名同一 list)
            cur_e = []
            cur_state = None
        elif s == 'actual data:':
            cur_state = 'actual'
        elif s == 'expected data:':
            cur_state = 'expected'
        elif cur_state in ('actual', 'expected'):
            toks = [t for t in s.split() if re.fullmatch(r'[0-9a-fA-F]{2}', t)]
            bs = bytes(int(t, 16) for t in toks)
            if cur_state == 'actual':
                cur_a.extend(bs)
            else:
                cur_e.extend(bs)
    if cur_id is not None:
        blocks.append({'id': cur_id, 'actual': bytes(cur_a), 'expected': bytes(cur_e)})

    records = []
    for blk in blocks:
        a, e = blk['actual'], blk['expected']
        for i in range(ELEMS_PER_BLOCK):
            seg_a = a[i*8:(i+1)*8]
            seg_e = e[i*8:(i+1)*8]
            if len(seg_a) < 8 or len(seg_e) < 8:
                continue
            au = struct.unpack('<Q', seg_a)[0]
            eu = struct.unpack('<Q', seg_e)[0]
            xor = au ^ eu
            if xor == 0:
                continue  # 该 double 未翻转
            records.append({
                'block_id': blk['id'],
                'pos_in_block': i,
                'actual_u': au,
                'expected_u': eu,
                'xor': xor,
                'hw': hw(xor),
                'bits': bit_positions(xor),
            })
    return records, blocks


# ============================================================
# B. 从原始日志反查 block -> (test, seed, iteration, offset) 上下文
#    策略: 在原始日志里搜每个 block 的 expected_dump 第一行指纹(前16字节),
#          定位到出错点 dump 块, 再回溯其所属 - test: 块的元数据.
# ============================================================
def build_block_context(blocks):
    """
    blocks: 来自 all_fail_blocks 的 list, 已含 expected bytes(64).
    返回 block_id -> {test, seed, iteration, retry, loop_count, offset, reported_actual_u}
    """
    # 1) 一次性读原始日志所有行 (14MB, 可接受)
    with open(RAW_LOG) as f:
        lines = f.readlines()

    # 2) 给每行打标记, 建索引
    #    用每个 block 的 expected dump 的前 16 字节(第一行)做指纹
    fingerprints = {}    # fp_str -> block_id
    for blk in blocks:
        fp_bytes = blk['expected'][:16]
        if len(fp_bytes) < 16:
            continue
        fp = ' '.join(f'{b:02x}' for b in fp_bytes)
        fingerprints[fp] = blk['id']

    # 3) 扫描原始日志, 维护当前 test 上下文, 同时识别 expected data dump 行
    ctx = {}             # block_id -> context dict
    cur_test = cur_seed = cur_iter = cur_retry = cur_loop = None
    cur_offset = None
    cur_reported_actual_u = None
    # 当遇到 'expected data:' 后的 dump 行, 若其前16字节匹配某指纹, 则记录
    expect_data_mode = False
    cur_expect_dump = []

    i = 0
    n = len(lines)

    def try_flush_dump():
        """dump 结束时, 用前16字节指纹查 block_id 并写入上下文."""
        nonlocal cur_expect_dump, expect_data_mode
        if cur_expect_dump:
            fp = ' '.join(f'{b:02x}' for b in cur_expect_dump[:16])
            if fp in fingerprints:
                bid = fingerprints[fp]
                if bid not in ctx:
                    ctx[bid] = {
                        'test': cur_test, 'seed': cur_seed,
                        'iteration': cur_iter, 'retry': cur_retry,
                        'loop_count': cur_loop, 'offset': cur_offset,
                        'reported_actual_u': cur_reported_actual_u,
                    }
            cur_expect_dump = []
        expect_data_mode = False

    while i < n:
        s = lines[i].strip()

        if s.startswith('- test: '):
            try_flush_dump()   # dump 可能刚结束, 先 flush
            cur_test = s[len('- test: '):].strip()
            cur_seed = cur_iter = cur_retry = cur_loop = None
            cur_offset = None
            cur_reported_actual_u = None
            i += 1
            continue

        m = re.match(r"state:\s*\{.*seed:\s*'([^']+)',\s*iteration:\s*(\d+),\s*retry:\s*(\w+)", s)
        if m:
            cur_seed = m.group(1)
            cur_iter = int(m.group(2))
            cur_retry = m.group(3)
            i += 1
            continue

        m = re.match(r'loop-count:\s*(\d+)', s)
        if m:
            cur_loop = int(m.group(1))
            i += 1
            continue

        m = re.match(r'offset:\s*\[\s*(\d+),\s*(\d+)\s*\]', s)
        if m:
            cur_offset = (int(m.group(1)), int(m.group(2)))
            i += 1
            continue

        m = re.match(r"actual:\s*'0x([0-9a-fA-F]+)", s)
        if m:
            cur_reported_actual_u = int(m.group(1), 16)
            i += 1
            continue

        if s == 'expected data:':
            expect_data_mode = True
            cur_expect_dump = []
            i += 1
            continue
        if s == 'actual data:':
            expect_data_mode = False
            i += 1
            continue

        if expect_data_mode:
            toks = [t for t in s.split() if re.fullmatch(r'[0-9a-fA-F]{2}', t)]
            if toks:
                cur_expect_dump.extend(int(t, 16) for t in toks)
            else:
                # dump 结束 (遇到空行或非字节内容)
                try_flush_dump()
        i += 1

    # 文件末尾再 flush 一次
    try_flush_dump()
    return ctx


# ============================================================
# 主分析
# ============================================================
def main():
    print(f'[*] 解析 {FAIL_BLOCKS}')
    records, blocks = parse_fail_blocks(FAIL_BLOCKS)
    print(f'[*] 字节级翻转记录: {len(records)} 条 (来自 {len(blocks)} 个 block)')

    print(f'[*] 反查原始日志建立 block->test 上下文')
    ctx = build_block_context(blocks)
    mapped = sum(1 for r in records if r['block_id'] in ctx)
    print(f'[*] 测试类型映射成功: {mapped}/{len(records)} 条')

    for r in records:
        c = ctx.get(r['block_id'], {})
        r['test'] = c.get('test')
        r['seed'] = c.get('seed')
        r['iteration'] = c.get('iteration')
        r['loop_count'] = c.get('loop_count')
        r['offset'] = c.get('offset')
        r['reported'] = (c.get('reported_actual_u') == r['actual_u'])  # 该翻转是否为原始日志单值所报告
        r['cluster'] = cluster_of(r['hw'])

    by_block = defaultdict(list)
    for r in records:
        by_block[r['block_id']].append(r)

    # ---------------- 任务1 ----------------
    print('\n' + '=' * 110)
    print('[任务1] 按 fail block 分组')
    print('=' * 110)
    consistent = split = single = 0
    for bid in sorted(by_block):
        rs = by_block[bid]
        clusters = set(r['cluster'] for r in rs)
        n = len(rs)
        if n == 1:
            single += 1; tag = '单出错点'
        elif len(clusters) == 1:
            consistent += 1; tag = f'同簇({clusters.pop()})'
        else:
            split += 1; tag = f'分裂({",".join(sorted(clusters))})'
        hw_l = [r['hw'] for r in rs]
        pos_l = [r['pos_in_block'] for r in rs]
        print(f'  Block {bid:>3}: n={n} | HW={hw_l} | pos={pos_l} | {tag}')
    print(f'\n  汇总: 单出错点={single} | 多出错同簇={consistent} | 多出错分裂={split}')

    # ---------------- 任务2 ----------------
    print('\n' + '=' * 110)
    print('[任务2] block 内位置索引 (0..7) 与 HW 簇')
    print('=' * 110)
    for cl in ['low', 'gray', 'near_half']:
        rs = [r for r in records if r['cluster'] == cl]
        if not rs:
            print(f'  {cl:<10}: 无记录'); continue
        pc = Counter(r['pos_in_block'] for r in rs)
        front = sum(c for p, c in pc.items() if p is not None and p < 4)
        back = sum(c for p, c in pc.items() if p is not None and p >= 4)
        dist = ', '.join(f'p{p}:{c}' for p, c in sorted(pc.items(), key=lambda x: (x[0] is None, x[0])))
        print(f'  {cl:<10} (n={len(rs)}): {dist}')
        print(f'             前4(p0-3)={front}, 后4(p4-7)={back}')

    # ---------------- 任务3 ----------------
    print('\n' + '=' * 110)
    print('[任务3] 测试类型与 HW 簇')
    print('=' * 110)
    by_test = defaultdict(list)
    for r in records:
        by_test[r['test'] or '(未知)'].append(r)
    for t in sorted(by_test):
        rs = by_test[t]
        cc = Counter(r['cluster'] for r in rs)
        hws = [r['hw'] for r in rs]
        print(f'  {t:<38} n={len(rs):<3} | 低:{cc["low"]:<3} 灰:{cc["gray"]:<3} 近半:{cc["near_half"]:<3} '
              f'| HW min={min(hws)} max={max(hws)} 中位={statistics.median(hws)}')

    # ---------------- 任务4 汇总表 ----------------
    print('\n' + '=' * 120)
    print('[任务4] 汇总表')
    print('=' * 120)
    print(f'{"block":>5} | {"出错数":>4} | {"各HW":<24} | {"各pos":<14} | {"各簇":<16} | {"测试类型":<30} | offset')
    print('-' * 120)
    for bid in sorted(by_block):
        rs = by_block[bid]
        hw_l = [r['hw'] for r in rs]
        pos_l = [r['pos_in_block'] for r in rs]
        cl_l = [r['cluster'] for r in rs]
        t = rs[0]['test'] or '(未知)'
        off = rs[0]['offset']
        print(f'{bid:>5} | {len(rs):>4} | {str(hw_l):<24} | {str(pos_l):<14} | {str(cl_l):<16} | {t:<30} | {off}')

    # ---------------- 关联结论 ----------------
    print('\n' + '=' * 110)
    print('[关联结论] 两簇与 位置/测试类型/唯一性/是否被报告 的关联')
    print('=' * 110)

    # 位置关联
    low_pos = [r['pos_in_block'] for r in records if r['cluster'] == 'low' and r['pos_in_block'] is not None]
    nh_pos = [r['pos_in_block'] for r in records if r['cluster'] == 'near_half' and r['pos_in_block'] is not None]
    print('\n  [位置]')
    if low_pos:
        print(f'    低HW簇   位置均值={statistics.mean(low_pos):.2f} 中位={statistics.median(low_pos)} '
              f'(n={len(low_pos)}) 分布={dict(Counter(low_pos))}')
    if nh_pos:
        print(f'    近半HW簇  位置均值={statistics.mean(nh_pos):.2f} 中位={statistics.median(nh_pos)} '
              f'(n={len(nh_pos)}) 分布={dict(Counter(nh_pos))}')
    if low_pos and nh_pos:
        d = abs(statistics.mean(low_pos) - statistics.mean(nh_pos))
        print(f'    位置均值差={d:.2f} -> {"存在" if d >= 1.5 else "无"}系统性差异')

    # 测试类型关联
    print('\n  [测试类型]')
    for cl in ['low', 'gray', 'near_half']:
        rs = [r for r in records if r['cluster'] == cl]
        if not rs:
            continue
        tc = Counter(r['test'] or '(未知)' for r in rs)
        print(f'    {cl:<10} (n={len(rs)}): {tc.most_common()}')

    # 唯一性关联
    print('\n  [块内唯一性]')
    for cl in ['low', 'gray', 'near_half']:
        rs = [r for r in records if r['cluster'] == cl]
        if not rs:
            continue
        only = sum(1 for r in rs if len(by_block[r['block_id']]) == 1)
        print(f'    {cl:<10} (n={len(rs)}): 块内唯一={only}/{len(rs)} ({100*only/len(rs):.0f}%)')

    # 是否被原始日志单值报告 (hidden 翻转)
    print('\n  [是否被原始日志 isApprox 单值报告]')
    for cl in ['low', 'gray', 'near_half']:
        rs = [r for r in records if r['cluster'] == cl]
        if not rs:
            continue
        rep = sum(1 for r in rs if r['reported'])
        print(f'    {cl:<10} (n={len(rs)}): 被报告={rep}/{len(rs)} ({100*rep/len(rs):.0f}%) '
              f'(其余为隐藏翻转)')

    # 综合判断
    print('\n  ---- 综合判断 ----')
    cc = Counter(r['cluster'] for r in records)
    print(f'  全局簇分布: 低HW={cc["low"]} 灰色={cc["gray"]} 近半HW={cc["near_half"]} (总{len(records)})')
    print(f'  分裂 block 数: {split}')
    if split > 0:
        # 哪些 block 分裂? 低+近半 混合?
        split_blocks = [bid for bid in by_block
                        if len(set(r['cluster'] for r in by_block[bid])) > 1]
        print(f'  分裂 block: {split_blocks}')
        # 分裂 block 里, 哪个 pos 是低, 哪个 pos 是近半?
        for bid in split_blocks:
            rs = by_block[bid]
            detail = [(r['pos_in_block'], r['cluster'], r['hw']) for r in rs]
            print(f'    block {bid}: {detail}')


if __name__ == '__main__':
    main()
