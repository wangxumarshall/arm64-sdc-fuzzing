#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GPS 签名分类器 — CORE179 读路径定位战役 Phase 0' 离线工具(2026-09-13)

输入:neon_rot_ldr_at_top_rowmajor_gps fail dump(fail_cpuN_sweepM.bin)
     —— GPS 版测试冷路径写出的五缓冲上下文(dst/expected/srcA/srcB/scratch)
输出:9 桶签名分类 + 部分字粒度直方图 + 汉明直方图 + 错位窗 mod-8 直方图

设计文档:docs/CORE179_READPATH_LOCALIZATION_CAMPAIGN_20260913.md §6

用法:
  python3 gps_classify.py <dump.bin> [<dump2.bin> ...]
  python3 gps_classify.py --dir movbe_log/gps_rowmajor/

桶定义(与文档 §6.1 对齐;判定顺序即优先级):
  wrong_line    错线:got 恰为工作集另一 64B 线里的完整 8B 字
  wrong_word    错字:got 恰为同 64B 线内另一 8B 字
  misalign_win  错位窗:got 的 8 字节在工作集字节流中连续出现,但起点 mod-8 ≠ 0
  field_subst   字段替换:off|~off 字段被另一源字同字段替换(09-13 首轮主族 93%)
  splice_AB     两源拼接:一个 8B 值里同时含 A-magic 与 B-magic 字节痕迹
  partial_word  部分字:与期望仅部分字节错(1/2/4B 粒度直方图)
  bitflip_like  位翻转样:不可寻回且汉明 ≤4 bit
  scratch_src   scratch 源:got 为 scratch 缓冲里的完整字(单独复核通道)
  alu_mixin     ALU 混入:与某个重构的 (a OP b) 结果整词相等(接口预留,见 TODO)
  unknown       未分类:不来自工作集任何位置 → 在途数据(bypass/ALU 方向强约束)
"""

import struct
import sys
import os
import glob
from collections import Counter

COUNT = 1024                 # uint64x2 元素数
WORDS_PER_BUF = COUNT * 2    # 每 64b 字数
BUF_BYTES = WORDS_PER_BUF * 8
N_BUFS = 5                   # dst/expected/srcA/srcB/scratch

MAGIC_A   = 0xA5A5
MAGIC_B   = 0x5A5A
MAGIC_SCR = 0x0F0F

# 缓冲在 dump 中的顺序(与测试冷路径 fwrite 顺序一致)
D_DST, D_EXP, D_A, D_B, D_SCR = range(5)


def load_dump(path):
    with open(path, 'rb') as f:
        blob = f.read()
    need = BUF_BYTES * N_BUFS
    if len(blob) < need:
        raise SystemExit(f"{path}: dump 太短 {len(blob)} < {need}(需要五缓冲;末尾另有文本行)")
    bufs = []
    for k in range(N_BUFS):
        chunk = blob[k * BUF_BYTES:(k + 1) * BUF_BYTES]
        bufs.append(list(struct.unpack(f'<{WORDS_PER_BUF}Q', chunk)))
    return bufs


class Snapshot:
    """全工作集快照:整词索引表 + 字节流(错位检索用,一次构建)。"""

    def __init__(self, bufs):
        self.bufs = bufs
        self.word_table = {}                       # 8B bytes -> [(buf_k, word_idx)]
        for k in (D_A, D_B, D_SCR):
            for idx, w in enumerate(bufs[k]):
                self.word_table.setdefault(w.to_bytes(8, 'little'), []).append((k, idx))
        # 三个源缓冲连成一条字节流(错位窗可能跨缓冲边界——本身也是信息)
        self.blob = b''.join(
            w.to_bytes(8, 'little') for k in (D_A, D_B, D_SCR) for w in bufs[k])
        self.buf_base = [0, 0, 0, 0, 0]
        base = 0
        for k in (D_A, D_B, D_SCR):
            self.buf_base[k] = base
            base += BUF_BYTES

    def find_word(self, word_val):
        return self.word_table.get(word_val.to_bytes(8, 'little'), [])

    def find_bytes(self, needle):
        """needle(≤8B bytes)在快照字节流中的所有出现位置(快照内偏移,字节粒度)。"""
        hits = []
        start = 0
        while True:
            pos = self.blob.find(needle, start)
            if pos < 0:
                return hits
            hits.append(pos)
            start = pos + 1

    def locate(self, blob_pos):
        """快照字节流偏移 -> (缓冲名, 缓冲内字节偏移)。"""
        for k, name in ((D_A, 'srcA'), (D_B, 'srcB'), (D_SCR, 'scratch')):
            if self.buf_base[k] <= blob_pos < self.buf_base[k] + BUF_BYTES:
                return name, blob_pos - self.buf_base[k]
        return '?', blob_pos


def hamming(a, b):
    return bin(a ^ b).count('1')


def decode_tag(word_val):
    """解一个候选 GPS 字:合法返回 (magic, byte_off),否则 None。"""
    magic = (word_val >> 48) & 0xFFFF
    off = (word_val >> 32) & 0xFFFF
    compl = (word_val >> 16) & 0xFFFF
    if magic not in (MAGIC_A, MAGIC_B, MAGIC_SCR):
        return None
    if compl != (~off & 0xFFFF):
        return None
    return magic, off


def classify_word(idx, got, want, snap):
    """对一个出错 8B 字做桶分类。返回 (bucket, detail)。
    判定顺序:整词寻回(错线/错字)→ 错位窗 → 拼接 → 部分字 → 位翻转 → unknown。"""
    # 1) 整词恰好是工作集另一个字 → wrong_line / wrong_word
    hits = snap.find_word(got)
    if hits:
        # 期望位置来自 dst 的 idx;命中位置在哪个缓冲、哪个字
        k, widx = hits[0]
        name = {D_A: 'srcA', D_B: 'srcB', D_SCR: 'scratch'}[k]
        if widx // 8 == idx // 8 and k == D_A:      # 同 64B 线(8 word/线)
            bucket = 'wrong_word'
        else:
            bucket = 'wrong_line'
        tag = decode_tag(got)
        toff = f"tag_off={tag[1]}" if tag else "tag=x"
        return bucket, f"from={name}[{widx}] {toff} (want_word_off={idx * 8})"

    gb = got.to_bytes(8, 'little')

    # 2) 错位窗:8 字节在快照字节流中连续出现且起点 mod-8 ≠ 0
    bhits = snap.find_bytes(gb)
    if bhits:
        name, off = snap.locate(bhits[0])
        return 'misalign_win', f"from={name}@byte{off} (mod8={off % 8})"

    # 3) 两源拼接:8B 里同时含 A-magic 与 B-magic 的 2 字节大端痕迹
    if b'\xa5\xa5' in gb and b'\x5a\x5a' in gb:
        return 'splice_AB', f"got={got:#018x}"

    # 3.5) 字段替换(2026-09-13 首轮主族签名,166/178):got 的
    #      off|~off 字段(byte2-5)被另一 srcA 字的同字段替换,
    #      替换后互补校验仍通过。检测:got 的中段 32b 在快照另一
    #      字中寻回 → 记录源字与元素距离。该桶优先于部分字
    #      (部分字是它的字节粒度子集视图)。
    got_mid = (got >> 16) & 0xFFFFFFFF
    if got_mid != ((want >> 16) & 0xFFFFFFFF):
        # got 中段 32b(off|~off 字段)与期望不同:在源缓冲找它的来源字。
        # 注:got 是 ALU 结果,magic 段或/与后已非 a5a5/5a5a,不能用 magic 预筛。
        for k in (D_A, D_B, D_SCR):
            for j, w in enumerate(snap.bufs[k]):
                if ((w >> 16) & 0xFFFFFFFF) == got_mid:
                    d = j // 2 - idx // 2
                    return 'field_subst', f"src={ {D_A:'A',D_B:'B',D_SCR:'scr'}[k] } elem_dist={d:+d}"

    # 4) 部分字:与期望只有部分字节差
    xor = got ^ want
    err_bytes = [i for i in range(8) if ((xor >> (8 * i)) & 0xFF) != 0]
    if 0 < len(err_bytes) < 8:
        if len(err_bytes) == 1:
            gran = '1B'
        elif len(err_bytes) == 2 and err_bytes[1] == err_bytes[0] + 1:
            gran = '2B'
        elif len(err_bytes) == 4 and err_bytes == list(range(err_bytes[0], err_bytes[0] + 4)):
            gran = '4B'
        else:
            gran = 'scat'
        return 'partial_word', f"errbytes={err_bytes} gran={gran}"

    # 5) ALU 混入(接口预留):got 等于某个重构的 (a OP b) 整词。
    #    快照可重构任意候选;Phase 0' 首批样本到位后按需启用(避免当前 O(n) 猜测)。
    # TODO: alu_mixin 重构通道

    # 6) 位翻转样:低汉明且不可寻回
    h = hamming(got, want)
    if h <= 4:
        return 'bitflip_like', f"hamming={h}"

    # 7) scratch 单查复核(word_table 已含 scratch,此处冗余兜底)
    if snap.find_word(got) and any(
            snap.bufs[D_SCR][j] == got for j in range(max(0, idx - 8), min(WORDS_PER_BUF, idx + 9))):
        return 'scratch_src', 'nearby scratch word'

    return 'unknown', f"hamming={h} got={got:#018x} want={want:#018x}"


def classify_dump(path):
    bufs = load_dump(path)
    snap = Snapshot(bufs)
    dst, expected = bufs[D_DST], bufs[D_EXP]

    buckets = Counter()
    details = []
    gran_hist = Counter()
    ham_hist = Counter()
    mis_hist = Counter()
    dist_hist = Counter()

    for idx in range(WORDS_PER_BUF):
        got, want = dst[idx], expected[idx]
        if got == want:
            continue
        bucket, detail = classify_word(idx, got, want, snap)
        buckets[bucket] += 1
        details.append((idx, bucket, detail))
        if bucket == 'partial_word':
            gran_hist[detail.split('gran=')[-1]] += 1
        if 'hamming=' in detail:
            ham_hist[int(detail.split('hamming=')[-1].split()[0])] += 1
        if 'mod8=' in detail:
            mis_hist[int(detail.split('mod8=')[-1].rstrip(')'))] += 1
        if 'elem_dist=' in detail:
            dist_hist[int(detail.split('elem_dist=')[-1])] += 1

    return buckets, details, gran_hist, ham_hist, mis_hist, dist_hist


def main():
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        sys.exit(1)
    if args[0] == '--dir':
        paths = sorted(glob.glob(os.path.join(args[1], 'fail_cpu*_sweep*.bin')))
        if not paths:
            raise SystemExit(f"{args[1]}: 无 fail_cpu*_sweep*.bin")
    else:
        paths = args

    total = Counter()
    for p in paths:
        buckets, details, gran, ham, mis, dist = classify_dump(p)
        n = sum(buckets.values())
        print(f"== {os.path.basename(p)}  ({n} 个出错字) ==")
        for b, c in buckets.most_common():
            print(f"  {b:14s} {c:4d}  ({100 * c / max(n, 1):.0f}%)")
        if gran:
            print(f"  partial gran hist: {dict(gran)}")
        if mis:
            print(f"  misalign mod8 hist: {dict(sorted(mis.items()))}")
        if dist:
            print(f"  field_subst elem-dist hist: {dict(sorted(dist.items()))}")
        if ham:
            print(f"  hamming hist: {dict(sorted(ham.items()))}")
        for idx, b, d in details[:10]:
            print(f"    word[{idx}] {b}: {d}")
        if len(details) > 10:
            print(f"    ... ({len(details) - 10} more)")
        total.update(buckets)

    if len(paths) > 1:
        print("== TOTAL ==")
        for b, c in total.most_common():
            print(f"  {b:14s} {c:4d}")


if __name__ == '__main__':
    main()
