#!/usr/bin/env python3
"""解析 movbe_dump 的二进制日志(/tmp/movbe_dump_<pid>.bin)。
每条记录56字节, struct格式: Q I I I I I I I (timestamp_us, cpu, iteration, index, input, expected_swapped, actual_swapped, actual_val, xor_val)
按记忆 eigen-dump-binary-log-added 的 unpack 格式: '<QIIIIIIQQQ' (实际是 Q I I I I I I I = 8+4*7=36? 不对, 算一下)
实际字段: timestamp_us(8) + cpu(4)+iteration(4)+index(4)+input(4)+expected(4)+actual_swapped(4)+actual_val(4)+xor(4) = 8+28 = 36字节?
源码 struct movbe_dump_record: uint64_t + 7×uint32_t = 8+28 = 36字节.
但记忆说是56字节, 可能含padding. 以源码实际sizeof为准.
"""
import sys, struct, glob, os

# 按 C struct 布局: uint64_t + 7×uint32_t, 无padding(已紧凑?) 实际 GCC 默认按自然对齐, uint64_t在前8对齐, 7个uint32_t连续28字节, 总36, 但struct尾padding到40(8对齐)
# 试 36 和 40 两种
FMT_36 = '<Q7I'   # 8 + 28 = 36
FMT_40 = '<Q7I4x' # 8 + 28 + 4padding = 40

def try_parse(data, fmt):
    sz = struct.calcsize(fmt)
    recs = []
    for off in range(0, len(data)-sz+1, sz):
        try:
            recs.append(struct.unpack(fmt, data[off:off+sz]))
        except: break
    return recs

def main():
    bins = sorted(glob.glob('/tmp/movbe_dump_*.bin'))
    if not bins:
        print("无 /tmp/movbe_dump_*.bin", file=sys.stderr); sys.exit(1)
    all_recs = []
    for b in bins:
        data = open(b,'rb').read()
        if not data: continue
        # 试两种大小
        recs = try_parse(data, FMT_36)
        if not recs or len(data) % 36 != 0:
            recs = try_parse(data, FMT_40)
        for r in recs:
            all_recs.append((os.path.basename(b),) + r)
    print(f"共 {len(all_recs)} 条记录 from {len(bins)} 个bin文件\n")
    print(f"{'#':>3} {'bin':<28} {'cpu':>4} {'iter':>6} {'idx':>6} {'input':>10} {'exp_swap':>10} {'act_swap':>10} {'act_val':>10} {'xor':>10}  bitpos")
    for i,(bn,ts,cpu,it,idx,inp,es,asw,av,xor) in enumerate(all_recs):
        # 算翻转位(xor的非零位)
        bits = [str(b) for b in range(32) if (xor>>b)&1]
        bitpos = ','.join(bits) if bits else '?'
        print(f"{i+1:>3} {bn:<28} {cpu:>4} {it:>6} {idx:>6} {inp:#010x} {es:#010x} {asw:#010x} {av:#010x} {xor:#010x}  [{bitpos}]")

if __name__ == '__main__':
    main()
