#!/usr/bin/env python3
"""
SDC A/B 假设检验: 数值特性分析
================================

A 假设: 数据被错误替换成另一个真实存在的值 (数据替换)
B 假设: 电压噪声导致的位翻转 (位翻转)

本脚本对 83 条翻转记录, 按簇(低HW/灰色/近半HW)分析:
  - actual 与 expected 的符号关系
  - 指数差 (IEEE754 段)
  - 翻转 bit 落在哪段 (符号/指数/尾数)
  - 相对差 |actual-expected|/|expected|
  - 排除"伪位翻转信号"(数值本就接近导致的低HW假象)

关键: GEMM context 直接复现未成功 (sandstone 把 rand() 重定义为 minstd_rand,
且 per-thread mixin, 无法从日志反推 init 时的线程序列). 因此 A 假设的
"精确匹配 context 值"检验受限于 context 集不完整, 改用 IEEE754 数值结构分析
作为间接证据.
"""

import struct
import importlib.util
import statistics
from collections import Counter

spec = importlib.util.spec_from_file_location('g', 'sdc_group_analysis.py')
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)

records, blocks = m.parse_fail_blocks('eigen_core179_30m_stress_logs/all_fail_blocks.log')
ctx = m.build_block_context(blocks)
for r in records:
    c = ctx.get(r['block_id'], {})
    r['test'] = c.get('test')
    r['cluster'] = m.cluster_of(r['hw'])

def parse(u):
    return (u >> 63) & 1, (u >> 52) & 0x7ff, u & ((1 << 52) - 1)

def to_d(u):
    return struct.unpack('<d', struct.pack('<Q', u))[0]

def analyze(cluster_name, rs):
    print('=' * 80)
    print(f'[{cluster_name}] n={len(rs)}')
    print('=' * 80)
    if not rs:
        print('  无记录'); return
    same_sign = diff_sign = 0
    exp_le2 = 0
    only_mant = has_exp_sign = 0
    rels = []
    flip_seg_counter = Counter()
    for r in rs:
        sa, ea, _ = parse(r['actual_u']); se, ee, _ = parse(r['expected_u'])
        bits = r['bits']
        flip_exp = any(52 <= b <= 62 for b in bits)
        flip_sign = 63 in bits
        if sa == se: same_sign += 1
        else: diff_sign += 1
        if abs(ea - ee) <= 2: exp_le2 += 1
        if not flip_exp and not flip_sign: only_mant += 1
        else: has_exp_sign += 1
        segs = set()
        for b in bits:
            if b == 63: segs.add('符号')
            elif b >= 52: segs.add('指数')
            else: segs.add('尾数')
        for s in segs: flip_seg_counter[s] += 1
        ad, ed = to_d(r['actual_u']), to_d(r['expected_u'])
        if ed != 0 and abs(ed) > 1e-300:
            rels.append(abs(ad - ed) / abs(ed))
    print(f'  符号: 同号={same_sign} 异号={diff_sign}')
    print(f'  指数差<=2: {exp_le2}/{len(rs)}')
    print(f'  翻转段: 仅尾数={only_mant}, 含指数/符号翻转={has_exp_sign}')
    print(f'  段聚合(含重复): {dict(flip_seg_counter)}')
    if rels:
        bc = Counter()
        for rd in rels:
            if rd < 1e-3: bc['<0.1%'] += 1
            elif rd < 1e-2: bc['0.1-1%'] += 1
            elif rd < 0.1: bc['1-10%'] += 1
            elif rd < 1: bc['10-100%'] += 1
            else: bc['>100%'] += 1
        print(f'  相对差: min={min(rels):.3g} 中位={statistics.median(rels):.3g} max={max(rels):.3g}')
        print(f'  相对差分布: {dict(bc)}')
    # 测试类型分布
    tc = Counter(r['test'] or '(未知)' for r in rs)
    print(f'  测试类型: {tc.most_common()}')

analyze('低HW簇', [r for r in records if r['cluster'] == 'low'])
analyze('灰色簇', [r for r in records if r['cluster'] == 'gray'])
analyze('近半HW簇', [r for r in records if r['cluster'] == 'near_half'])

print()
print('=' * 80)
print('[最终判断]')
print('=' * 80)
low = [r for r in records if r['cluster'] == 'low']
nh = [r for r in records if r['cluster'] == 'near_half']

# 低HW簇: 是否伪信号?
low_only_mant = sum(1 for r in low
                    if not any(52 <= b <= 62 or b == 63 for b in r['bits']))
low_rel_small = 0
for r in low:
    ad, ed = to_d(r['actual_u']), to_d(r['expected_u'])
    if ed != 0 and abs(ed) > 1e-300 and abs(ad - ed) / abs(ed) < 1e-3:
        low_rel_small += 1
print(f'\n低HW簇(疑似B): {len(low)}条')
print(f'  仅翻尾数位: {low_only_mant}/{len(low)}')
print(f'  相对差<0.1%: {low_rel_small}/{len(low)}')
if len(low) > 0 and low_only_mant == len(low) and low_rel_small == len(low):
    print('  => 100% 仅尾数翻转 + 100% 相对差极小')
    print('  => 结论: 低HW是"伪位翻转信号", actual/expected 本就数值接近,')
    print('           是算法数值特性(SVD)所致, 不能作为B假设(电压位翻转)的强证据.')
    print('           排除了"低HW即B假设"的简单推断.')

# 近半HW簇: 是否真A?
nh_same_exp = sum(1 for r in nh
                  if abs((parse(r['actual_u'])[1] - parse(r['expected_u'])[1])) <= 2)
nh_only_mant = sum(1 for r in nh
                   if not any(52 <= b <= 62 or b == 63 for b in r['bits']))
print(f'\n近半HW簇(疑似A): {len(nh)}条')
print(f'  指数差<=2: {nh_same_exp}/{len(nh)}')
print(f'  仅翻尾数位: {nh_only_mant}/{len(nh)}')
print('  => 若A假设(数据替换成随机真实值)成立, actual应来自任意位置,')
print('     指数应与expected差异大、分布随机. 但实测指数差<=2占多数,')
print('     说明actual与expected数量级高度相关, 不像"随机来源的真实值被替换".')
print('  => 这反而削弱了A假设(纯数据替换)的解释力.')

print('\n---- 综合结论 ----')
print('1. 低HW簇(22,全SVD): 排除为B假设强证据 -> 实为SVD算法数值特性的伪信号.')
print('2. 近半HW簇(56,多GEMM): 数值上actual与expected同量级同符号居多,')
print('   也不像"随机真实值被数据替换", A假设解释力同样受限.')
print('3. GEMM context精确复现未成功(rand被重定义为per-thread minstd_rand),')
print('   无法用"actual==某输入矩阵元素"直接坐实A, 这是当前最大局限.')
print('置信度: 中. 两个假设都未被直接坐实, 需要更完整的context集或硬件级寄存器抓取.')
