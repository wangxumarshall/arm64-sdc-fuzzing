#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FARRON 日志预筛器（LogScanner）—— 在主动测试之前, 从内核/系统日志提取核心级错误指纹
依据(2026-10-25 实测验证): 当前 boot 的 journal 中 67 条 'WARNING: CPU: 179' __do_kernel_fault
全部锁定 179(100% 聚集, 其余 191 核零条), 与 9 月 panic 前兆链(spurious fault 全 179)同指纹。

用法:
  python3 log_scanner.py                     # 扫描当前 boot 全部内核日志
  python3 log_scanner.py --since "2026-10-25 11:00"   # 只扫某时刻之后(增量模式)
  python3 log_scanner.py --threshold 3 --json         # 输出JSON(供FARRON主程序消费)
输出:
  - 每核错误计数 + 聚类裁决(计数≥threshold的核 => 可疑候选, 连证据样本)
  - 用户态崩溃行计数(无核号, 仅总量告警)
FARRON 集成: 启动时全量预筛(可疑核直接入队) + 周期增量扫描(--since 上次时间戳)
"""
import argparse
import json
import re
import subprocess
import sys
import time

# 核心号捕获模式: (正则, 标签) —— 按信号强度排序
ERROR_PATTERNS = [
    (re.compile(r'WARNING: CPU: (\d+)'),                          'kernel_fault_warning'),
    (re.compile(r'spurious[^\n]*?CPU[: ]+(\d+)', re.I),            'spurious_fault'),
    (re.compile(r'Oops[^\n]*?CPU[: ]+(\d+)', re.I),                'kernel_oops'),
    (re.compile(r'kernel BUG[^\n]*?CPU[: ]+(\d+)', re.I),          'kernel_bug'),
    (re.compile(r'(?:MCE|SEA|external abort|hardware error)[^\n]*?CPU[: ]+(\d+)', re.I), 'hw_error'),
]
# 良性白名单(启动噪声/热插拔记录等, 不算错误指纹)
BENIGN = re.compile(
    r'Booted secondary|GICv3|I-cache|psci: CPU|CPU features|Boot CPU|'
    r'SMP: Total|Brought up|CPU\d+ is off|Command line|Memory:')
# 用户态崩溃信号(无核号, 计总量)
USER_CRASH = re.compile(r'segmentation fault|segfault|internal compiler error|signal 11', re.I)


def scan(since=None, threshold=3):
    cmd = ['sudo', 'journalctl', '-k', '--no-pager', '-o', 'short']
    if since:
        cmd += ['--since', since]
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=60).stdout
    except Exception as e:
        return {'error': f'journalctl 失败: {e}'}

    per_core = {}          # core -> [(tag, line)]
    user_crash_lines = 0
    for line in out.splitlines():
        if BENIGN.search(line):
            continue
        for pat, tag in ERROR_PATTERNS:
            m = pat.search(line)
            if m:
                per_core.setdefault(int(m.group(1)), []).append((tag, line.strip()))
                break
        if USER_CRASH.search(line):
            user_crash_lines += 1

    flagged = {}
    for core, evs in sorted(per_core.items()):
        if len(evs) >= threshold:
            flagged[core] = {
                'count': len(evs),
                'tags': sorted({t for t, _ in evs}),
                'first': evs[0][1][:120],
                'last': evs[-1][1][:120],
                'samples': [l for _, l in evs[:3]],
            }
    return {
        'scanned_at': time.strftime('%F %T'),
        'since': since or '(当前boot全部)',
        'kernel_lines_scanned': len(out.splitlines()),
        'per_core_error_counts': {c: len(v) for c, v in sorted(per_core.items())},
        'flagged_cores': flagged,          # => FARRON 可疑队列, 附日志证据
        'user_crash_lines': user_crash_lines,
        'threshold': threshold,
    }


def main():
    ap = argparse.ArgumentParser(description='FARRON 日志预筛器')
    ap.add_argument('--since', default=None, help='只扫该时刻之后(增量模式)')
    ap.add_argument('--threshold', type=int, default=3, help='判可疑的每核最小错误数')
    ap.add_argument('--json', action='store_true', help='JSON输出(供主程序)')
    args = ap.parse_args()
    r = scan(args.since, args.threshold)
    if args.json:
        print(json.dumps(r, ensure_ascii=False, indent=2))
        return
    if 'error' in r:
        print('❌', r['error']); sys.exit(1)
    print(f"═══ FARRON 日志预筛 @ {r['scanned_at']} (范围 {r['since']}, "
          f"扫描 {r['kernel_lines_scanned']} 行内核日志) ═══")
    if not r['per_core_error_counts']:
        print("  各核错误指纹: 无(日志干净)")
    for c, n in r['per_core_error_counts'].items():
        mark = '🚨' if c in r['flagged_cores'] else '  '
        print(f"  {mark} CPU{c}: {n} 条错误指纹")
    if r['user_crash_lines']:
        print(f"  ⚠️ 用户态崩溃类行: {r['user_crash_lines']} (无核号, 建议触发全量扫描)")
    if r['flagged_cores']:
        print(f"\n  裁决: 以下核心日志证据充分, 直接送入可疑队列(免主动预筛):")
        for c, info in r['flagged_cores'].items():
            print(f"  🚨 CPU{c} [{info['count']}条 {','.join(info['tags'])}]")
            print(f"      首条: {info['first']}")
            print(f"      末条: {info['last']}")
    else:
        print("\n  裁决: 无达阈值核心(主动测试仍为主渠道)")


if __name__ == '__main__':
    main()
