#!/usr/bin/env python3
# ============================================================================
# cpu_temp_avg.py — 从 ipmitool 温度采样日志解析各 CPU 平均温度
#
# 输入格式 (如 mrn_reloaded_2src_alu_rate_100.txt):
#   === 11:44:12 ===
#   CPU1_TEMP        | 77.000     | degrees C  | ok    | na | ...
#   CPU2_TEMP        | 76.000     | degrees C  | ok    | na | ...
#   ... (每块 ipmitool sdr type temperature 的 CPU 温度行)
#
# 解析规则:
#   - 传感器行 = 第 1 字段匹配 CPU<数字>_TEMP, 第 2 字段为温度读数
#     (其他温度传感器如 Inlet/Ambient 不计入; 改 SENSOR_LINE 即可扩展)
#   - 读数非数字(如 "na") → 该样本跳过并计数, 不进均值
#   - 每传感器独立统计 样本数/均值/最小/最大; 末行给全部 CPU 样本合并均值
#   - 均值按样本算术平均(采样近似等间隔), 不按时间加权
#   - 时间戳仅取首尾展示时间范围
#
# 用法:
#   ./scripts/cpu_temp_avg.py <温度日志> [<日志2> ...]     # 支持多文件逐个报告
# ============================================================================
import re
import sys

SENSOR_LINE = re.compile(r'^(?P<name>CPU\d+_TEMP)\s*\|\s*(?P<val>[^|]*?)\s*\|')
TIMESTAMP = re.compile(r'^===\s*(?P<ts>.+?)\s*===$')


def parse_file(path):
    """返回 (stats, skipped, nblocks, first_ts, last_ts)
    stats: {传感器名: [样本数, 累计和, 最小, 最大]}"""
    stats = {}
    skipped = {}
    nblocks = 0
    first_ts = last_ts = None
    with open(path, errors='replace') as f:
        for line in f:
            line = line.rstrip('\n')
            m = TIMESTAMP.match(line)
            if m:
                nblocks += 1
                if first_ts is None:
                    first_ts = m.group('ts')
                last_ts = m.group('ts')
                continue
            m = SENSOR_LINE.match(line)
            if not m:
                continue
            name, raw = m.group('name'), m.group('val')
            try:
                v = float(raw)
            except ValueError:  # "na" 等无读数样本
                skipped[name] = skipped.get(name, 0) + 1
                continue
            s = stats.setdefault(name, [0, 0.0, float('inf'), float('-inf')])
            s[0] += 1
            s[1] += v
            s[2] = min(s[2], v)
            s[3] = max(s[3], v)
    return stats, skipped, nblocks, first_ts, last_ts


def main(argv):
    if len(argv) < 2:
        print(f"用法: {argv[0]} <温度日志> [<日志2> ...]", file=sys.stderr)
        return 2
    rc = 0
    for path in argv[1:]:
        try:
            stats, skipped, nblocks, first_ts, last_ts = parse_file(path)
        except OSError as e:
            print(f"错误: 无法读取 {path}: {e}", file=sys.stderr)
            rc = 1
            continue
        print(f"文件: {path}")
        if not stats:
            print("  未解析到任何 CPU 温度样本 (格式不符?)")
            print()
            rc = 1
            continue
        print(f"  样本块: {nblocks}   时间范围: {first_ts} → {last_ts}")
        print(f"  {'sensor':<12} {'samples':>7} {'avg(C)':>8} {'min(C)':>8} {'max(C)':>8}  skipped")
        all_count, all_total = 0, 0.0
        # 并集遍历: 全 na 传感器(无任何有效样本)也要露面, 不能整行消失
        for name in sorted(set(stats) | set(skipped)):
            if name in stats:
                c, tot, lo, hi = stats[name]
                all_count += c
                all_total += tot
                avg_s, lo_s, hi_s = f"{tot / c:.2f}", f"{lo:.1f}", f"{hi:.1f}"
            else:
                c, avg_s, lo_s, hi_s = 0, "-", "-", "-"
            skip = skipped.get(name, 0)
            print(f"  {name:<12} {c:>7} {avg_s:>8} {lo_s:>8} {hi_s:>8}  "
                  f"{'na x%d' % skip if skip else '-'}")
        if all_count:
            print(f"  {'OVERALL(%d)' % len(stats):<12} {all_count:>7} "
                  f"{all_total / all_count:>8.2f}")
        print()
    return rc


if __name__ == '__main__':
    sys.exit(main(sys.argv))
