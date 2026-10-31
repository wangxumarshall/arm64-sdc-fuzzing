#!/usr/bin/env python3
"""FARRON 唤醒延迟探针 (2026-10-27 时延角度 6h 部署)
每 50ms 睡眠一次, 测实际超期(µs) = 调度器唤醒延迟的代理指标;
每秒聚合一行 CSV, 6h 仅 ~21600 行/探针.
用法: taskset -c <core> python3 latency_probe.py <输出csv> <插槽名>
输出: ts,socket,n,mean_us,max_us  (ts=该秒起始 epoch; n≈20)
"""
import sys, time

out_path, sock = sys.argv[1], sys.argv[2]
f = open(out_path, "a", buffering=1)
f.write("ts,socket,n,mean_us,max_us\n")
while True:
    t0 = time.time()
    deadline = t0 + 1.0
    samples = []
    while True:
        a = time.monotonic_ns()
        time.sleep(0.05)
        b = time.monotonic_ns()
        samples.append((b - a) // 1000 - 50000)   # µs 超期
        if time.time() >= deadline:
            break
    f.write(f"{int(t0)},{sock},{len(samples)},{sum(samples)//len(samples)},{max(samples)}\n")
