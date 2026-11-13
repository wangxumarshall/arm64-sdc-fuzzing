#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FARRON-02 —— 日志风险分级 + 两模式（优先/例行）4 核组在线检测（2026-10-31 用户规格）

第一步 日志检测（风险分级，每满足一条概率提升一个量级 ×10）:
  条件1(硬门) SEL 无硬件报错 —— 有硬错类条目 → 显示"某某硬件故障"并终止 SDC 检测路径
  条件2 ≥2 种应用软件报错 且 ≥60% 错误集中于同一物理核 → ×10
       (种类口径 = 受害者软件种类 Comm; 两口径之争见 DESIGN.md §FARRON-02)
       【用户原注: 梅婷有一块类似特征的主板，预计 8 月底到华为】
  条件3 30 天内 ≥3 次非计划重启 → ×10
  条件4 以 30 天为一阶段, 某阶段软件层错误总数种类多且数量也多(对比前一阶段) → ×10
第二步 优先检测:
  条件1+条件2 → 优先检测故障集中核所在 4 核组 ±1 组（周边核心）
  条件1 但无条件2 → 例行: 高负载在线模式, 30min/轮, 4 核/组, 每组 10s, 每轮 1 组
其他不变(承 v1.1): 温度控制器/凉检调度/温度补偿窗长/用例池/裁决规则/-O3 指纹钉死

两处必要修正(2026-10-31 审查, 依据 10-25 三构型对照实验
             docs/CORE179_FARRON_PERF_VALIDATION_20261025.md §一):
  ① 检测窗 = 4 核组独占(应用迁出组内核心再测) —— 与应用共享(分时)构型实测零检出
  ② 深度测试 = 整槽 48 核窗 + 按 fail 块核归属裁决 —— 单核钉核构型实测零检出
  (4 核组共振阈值未知: n=1 独占=死, 47+1 分时=死, n=48 整槽=活; n=4 属未测区,
   4h 验收的优先模式本身即 n=4 共振测量)

用法:
  python3 farron02.py --selftest                        # 纯逻辑自检(无 sudo/无真实执行)
  python3 farron02.py --assess-only                     # 真实日志风险分级报告(SEL/journal/重启史)
  python3 farron02.py --stub-run                        # 全流程桩演示(不跑真负载/不动应用)
  python3 farron02.py --duration 14400 --outdir <dir>   # 实机运行(驱动 opendcdiag + 应用迁出)
"""

import argparse
import json
import os
import re
import subprocess
import sys
import threading
import time
from collections import Counter
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import farron as F   # 复用 v1.1 组件: TempController/FanCoordinator/TestcasePool/Topology/check_binary/温度源

FARRON02_DIR = os.path.dirname(os.path.abspath(__file__))
UNIVERSE = list(range(192))

# ---------------- farron-02 配置（叠加在 farron v1.1 默认配置上） ----------------
DEFAULT_CONFIG02 = {
    # 发现型部署: 不预排除已知缺陷核, 由日志+检测自己发现(区别于 farron v1.0 的离线标定排除)
    "initial_reliable_pool": "0-191",
    "known_defective": [],
    "count_known_defectives": False,

    # ---- 第一步: 日志风险分级 ----
    "risk_window_days": 30,
    "cond2_kind_mode": "victim_app",   # "victim_app"=受害者软件种类 | "fingerprint"=错误指纹种类
    "cond2_min_kinds": 2,              # ≥2 种应用软件报错
    "cond2_min_share": 0.60,           # ≥60% 集中于同一物理核
    "cond2_min_count": 3,              # 核归因错误总量下限(防 1-2 条噪声定级)
    "cond3_min_reboots": 3,            # 30 天内 ≥3 次非计划重启
    "cond4_min_kinds": 3,              # 阶段对比: 当前阶段种类/数量均多于前阶段, 且达绝对下限
    "cond4_min_count": 10,
    "sel_hard_patterns": [             # SEL 硬错类关键词(命中即条件1不满足)
        "machine check", "ierr", "thermal trip", "catastrophic",
        "ecc", "memory error", "bus fatal", "sensor failure",
        "critical overtemp", "fault bus", "voltage",
    ],

    # ---- 第二步: 两模式调度 ----
    "group_size": 4,                   # 4 核为一组
    "routine_window_s": 10,            # 例行: 每组 10s
    "round_period_s": 1800,            # 30min 一轮, 每轮一组(例行)
    "priority_window_s": 30,           # 优先窗时长(规格未定; 取 10-25 实验最小可靠窗 30s)
    "priority_neighbor_groups": 1,     # 周边核心 = 所在组 ±1 组
    "routine_start_group": 0,

    # ---- 深测(整槽窗修正②) ----
    "deep_test_duration": 600,         # 每用例 600s(承 v1.0)
    "deep_test_cap": 8,

    # ---- 应用迁出(修正①: 窗内组核必须独占) ----
    "app_pid_file": os.path.join(F.STATE_DIR, "sweep", "app.pid"),
    "app_full_mask": "0-191",

    "outdir": os.path.join(F.STATE_DIR, "sweep", "farron02"),
    "dry_run": False,
    "speed": 1.0,
}

_LOG_PATH = [None]


def log02(msg):
    line = f"[{time.strftime('%F %T')}] {msg}"
    print(line, flush=True)
    if _LOG_PATH[0]:
        os.makedirs(os.path.dirname(_LOG_PATH[0]), exist_ok=True)
        with open(_LOG_PATH[0], "a") as f:
            f.write(line + "\n")


def load_config02(path=None):
    cfg = dict(F.DEFAULT_CONFIG)
    cfg.update(DEFAULT_CONFIG02)
    for p in [os.path.join(FARRON02_DIR, "config02.json"), path]:
        if p and os.path.exists(p):
            with open(p) as f:
                cfg.update(json.load(f))
            log02(f"已加载配置覆盖: {p}")
    return cfg


# ================= 第一步: 日志风险分级（解析层, 纯函数） =================

MONTHS = {m: i + 1 for i, m in enumerate(
    ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"])}

# 核心归因错误指纹(承 log_scanner.py; 信号强度排序)
ERROR_PATTERNS = [
    (re.compile(r'WARNING: CPU: (\d+)'), 'kernel_fault_warning'),
    (re.compile(r'spurious[^\n]*?CPU[: ]+(\d+)', re.I), 'spurious_fault'),
    (re.compile(r'Oops[^\n]*?CPU[: ]+(\d+)', re.I), 'kernel_oops'),
    (re.compile(r'kernel BUG[^\n]*?CPU[: ]+(\d+)', re.I), 'kernel_bug'),
    (re.compile(r'(?:MCE|SEA|external abort|hardware error)[^\n]*?CPU[: ]+(\d+)', re.I), 'hw_error'),
]
BENIGN = re.compile(
    r'Booted secondary|GICv3|I-cache|psci: CPU|CPU features|Boot CPU|'
    r'SMP: Total|Brought up|CPU\d+ is off|Command line|Memory:')


def parse_sel(text):
    """ipmitool sel list -> [{date,time,sensor,event,direction,dt}]"""
    entries = []
    for line in text.splitlines():
        parts = [p.strip() for p in line.split('|')]
        if len(parts) >= 6 and re.match(r'\d{2}/\d{2}/\d{4}', parts[1] or ''):
            e = {"date": parts[1], "time": parts[2], "sensor": parts[3],
                 "event": parts[4], "direction": parts[5], "dt": None}
            try:
                e["dt"] = datetime.strptime(parts[1] + " " + parts[2][:8], "%m/%d/%Y %H:%M:%S")
            except ValueError:
                try:
                    e["dt"] = datetime.strptime(parts[1], "%m/%d/%Y")
                except ValueError:
                    pass
            entries.append(e)
    return entries


def classify_sel(entries, hard_patterns):
    """就地标注 e['class'] ∈ {hard, benign, uncat}; 返回 (hard, benign, uncat) 列表。
    注意 'non-critical' 含 'critical' 子串 —— 良性判定必须在硬错关键词不含裸 'critical' 的前提下先行排除。"""
    benign_re = re.compile(
        r'non-critical|state asserted|state deasserted|log area|event logging|'
        r'system boot|system restart|slot is disabled|informational', re.I)
    hard, benign, uncat = [], [], []
    for e in entries:
        blob = (e["sensor"] + " " + e["event"]).lower()
        if any(p in blob for p in hard_patterns):
            e["class"] = "hard"
            hard.append(e)
        elif benign_re.search(blob):
            e["class"] = "benign"
            benign.append(e)
        else:
            e["class"] = "uncat"
            uncat.append(e)
    return hard, benign, uncat


def parse_journal(text):
    """journalctl -k 输出 -> (events, 行数)。event = {core, tag, comm}。
    受害者软件名(Comm)在 WARNING 的紧随续行 'CPU: N PID: .. Comm: X' 上。"""
    lines = text.splitlines()
    events = []
    for i, line in enumerate(lines):
        m = None
        tag = None
        for pat, t in ERROR_PATTERNS:
            m = pat.search(line)
            if m:
                tag = t
                break
        if not m or BENIGN.search(line):
            continue
        core = int(m.group(1))
        comm = "unknown"
        # 受害者进程名在 WARN 块的 'CPU: N PID: .. Comm: X' 行上; 真实 journal 中该行
        # 与 WARNING 行之间隔着 'Modules linked in: ...' 模块清单(1-3 行) —— 向前扫 6 行
        for j in range(i + 1, min(i + 7, len(lines))):
            cm = re.search(r'CPU: %d PID: \d+ Comm: (\S+)' % core, lines[j])
            if cm:
                comm = cm.group(1)
                break
        events.append({"core": core, "tag": tag, "comm": comm})
    return events, len(lines)


def parse_last(text):
    """last -x -F 输出 -> (reboots, shutdowns) 两个 datetime 列表。
    兼容 ISO(2026-10-14 21:44) 与 'Wed Oct 14 21:44' 两种时间格式。"""
    reboots, shutdowns = [], []
    now = datetime.now()
    for line in text.splitlines():
        kind = "reboot" if line.startswith("reboot") else (
            "shutdown" if line.startswith("shutdown") else None)
        if not kind:
            continue
        dt = None
        iso = re.search(r'(\d{4}-\d{2}-\d{2}) (\d{2}:\d{2})', line)
        if iso:
            dt = datetime.strptime(iso.group(1) + " " + iso.group(2), "%Y-%m-%d %H:%M")
        else:
            ab = re.search(r'([A-Z][a-z]{2}) +(\d{1,2}) (\d{2}:\d{2})', line)
            if ab and ab.group(1) in MONTHS:
                mon, day = MONTHS[ab.group(1)], int(ab.group(2))
                year = now.year if (mon, day) <= (now.month, now.day) else now.year - 1
                dt = datetime(year, mon, day,
                              int(ab.group(3)[:2]), int(ab.group(3)[3:5]))
        if dt:
            (reboots if kind == "reboot" else shutdowns).append(dt)
    return reboots, shutdowns


def evaluate_conditions(cfg, sel_entries, events, prev_events, reboots, shutdowns, now=None):
    """纯逻辑: 四条件 + 模式判定。selftest 目标。"""
    now = now or datetime.now()
    W = timedelta(days=cfg["risk_window_days"])

    # 条件1: SEL 无硬件报错(仅计窗口内; 日期缺失按保守计入)
    hard_w = [e for e in sel_entries
              if e.get("class") == "hard" and (e.get("dt") is None or e["dt"] >= now - W)]
    cond1 = not hard_w

    # 条件2: ≥2 种应用软件报错 + ≥60% 集中于同一物理核
    per_core = Counter(e["core"] for e in events)
    total = sum(per_core.values())
    if cfg["cond2_kind_mode"] == "victim_app":
        kinds = {e["comm"] for e in events}
        prev_kinds = {e["comm"] for e in prev_events}
    else:
        kinds = {e["tag"] for e in events}
        prev_kinds = {e["tag"] for e in prev_events}
    top_core, top_n = (per_core.most_common(1)[0] if per_core else (None, 0))
    share = (top_n / total) if total else 0.0
    cond2 = (len(kinds) >= cfg["cond2_min_kinds"]
             and share >= cfg["cond2_min_share"]
             and top_core is not None
             and total >= cfg["cond2_min_count"])

    # 条件3: 30 天内 ≥3 次非计划重启(重启前 30min 内无 shutdown 记录 = 非计划)
    boots_w = [t for t in reboots if t >= now - W]
    unplanned = [t for t in boots_w
                 if not any(t - timedelta(minutes=30) <= s <= t + timedelta(minutes=2)
                            for s in shutdowns)]
    cond3 = len(unplanned) >= cfg["cond3_min_reboots"]

    # 条件4: 30 天为阶段, 当前阶段种类与数量均多于前一阶段(且达绝对下限)
    prev_total = len(prev_events)
    data_sufficient = prev_total > 0
    cond4 = (data_sufficient
             and len(kinds) > len(prev_kinds) and total > prev_total
             and len(kinds) >= cfg["cond4_min_kinds"] and total >= cfg["cond4_min_count"])

    multipliers = int(cond2) + int(cond3) + int(cond4)
    if not cond1:
        mode = "hardware_fault"
    elif cond2:
        mode = "priority"
    else:
        mode = "routine"
    return {
        "cond1": cond1, "cond2": cond2, "cond2_core": top_core if cond2 else None,
        "cond2_share": round(share, 3), "cond2_kinds": sorted(kinds),
        "cond3": cond3, "cond3_unplanned": len(unplanned), "cond3_planned": len(boots_w) - len(unplanned),
        "cond4": cond4, "cond4_prev_available": data_sufficient,
        "journal_total": total, "journal_per_core": dict(per_core),
        "sel_hard": [f'{e["date"]} {e["sensor"]} {e["event"]}' for e in hard_w],
        "multipliers": multipliers, "mode": mode,
    }


class LogRiskAssessor:
    """第一步: 汇聚 SEL / journal / 重启史, 调用纯逻辑判定。"""

    def __init__(self, cfg):
        self.cfg = cfg

    def _run(self, cmd, timeout=90):
        return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)

    def assess(self):
        W = self.cfg["risk_window_days"]
        r = {"time": time.strftime("%F %T"), "sel_error": None, "journal_error": None,
             "last_error": None, "raw": {}}
        # SEL
        sel_entries = []
        try:
            out = self._run(["sudo", "ipmitool", "sel", "list"])
            entries = parse_sel(out.stdout)
            hard, benign, uncat = classify_sel(entries, self.cfg["sel_hard_patterns"])
            sel_entries = entries
            r["raw"]["sel"] = {"total": len(entries), "hard": len(hard),
                               "benign": len(benign), "uncat": len(uncat),
                               "uncat_list": [f'{e["date"]} {e["sensor"]} {e["event"]}' for e in uncat]}
        except Exception as ex:
            r["sel_error"] = str(ex)
        # journal(当前阶段 + 前一阶段)
        events, prev_events = [], []
        try:
            cur = self._run(["sudo", "journalctl", "-k", "--no-pager", "-o", "short",
                             "--since", f"{W} days ago"])
            events, nlines = parse_journal(cur.stdout)
            prev = self._run(["sudo", "journalctl", "-k", "--no-pager", "-o", "short",
                              "--since", f"{2 * W} days ago", "--until", f"{W} days ago"])
            prev_events, _ = parse_journal(prev.stdout)
            r["raw"]["journal"] = {"lines": nlines, "events": len(events),
                                   "prev_events": len(prev_events)}
        except Exception as ex:
            r["journal_error"] = str(ex)
        # 重启史(wtmp 持久)
        reboots, shutdowns = [], []
        try:
            out = self._run(["last", "-x", "-F"])
            reboots, shutdowns = parse_last(out.stdout)
        except Exception as ex:
            r["last_error"] = str(ex)

        r["conditions"] = evaluate_conditions(
            self.cfg, sel_entries, events, prev_events, reboots, shutdowns)
        return r

    def report_str(self, A):
        c = A["conditions"]
        L = ["── 第一步 日志风险分级 ──"]
        sel = A["raw"].get("sel", {})
        L.append(f"条件1 SEL硬件报错: 窗口内硬错类 {len(c['sel_hard'])} 条"
                 f" (全部{sel.get('total','?')}条中 良性{sel.get('benign','?')}/未归类{sel.get('uncat','?')})"
                 f" → {'✓ 无硬件报错' if c['cond1'] else '✗ 硬件故障!'}")
        if c["sel_hard"]:
            L.append("  硬错条目: " + "; ".join(c["sel_hard"][:5]))
        L.append(f"条件2 软件报错: {c['journal_total']} 条核归因错误, "
                 f"{len(c['cond2_kinds'])} 种受害者软件({','.join(c['cond2_kinds'][:4])}...), "
                 f"核{c['cond2_core']} 占比 {c['cond2_share'] * 100:.0f}% "
                 f"→ {'✓ ×10' if c['cond2'] else '✗'}")
        L.append(f"条件3 非计划重启: {c['cond3_unplanned']} 次/{self.cfg['risk_window_days']}d "
                 f"(计划内 {c['cond3_planned']}) → {'✓ ×10' if c['cond3'] else '✗'}")
        L.append(f"条件4 阶段对比: {'数据不足(前一阶段无日志)' if not c['cond4_prev_available'] else '已比较'} "
                 f"→ {'✓ ×10' if c['cond4'] else '✗'}")
        L.append(f"风险 = 基线 × 10^{c['multipliers']}   模式 = {c['mode']}"
                 + (f" (优先核 {c['cond2_core']})" if c["mode"] == "priority" else ""))
        for k in ("sel_error", "journal_error", "last_error"):
            if A.get(k):
                L.append(f"⚠️ 采集通道异常 {k}: {A[k]}")
        return "\n".join(L)


# ================= 组几何 =================

def group_of(core, gsize):
    return core // gsize


def group_cores(g, gsize):
    return [c for c in range(g * gsize, (g + 1) * gsize) if c in UNIVERSE]


def n_groups(gsize):
    return (max(UNIVERSE) + 1) // gsize


def complement_mask(cores):
    """0-191 减去 cores 的压缩掩码串"""
    rest = sorted(set(UNIVERSE) - set(cores))
    out, i = [], 0
    while i < len(rest):
        j = i
        while j + 1 < len(rest) and rest[j + 1] == rest[j] + 1:
            j += 1
        out.append(f"{rest[i]}-{rest[j]}" if j > i else str(rest[i]))
        i = j + 1
    return ",".join(out)


# ================= 第二步: 检测窗执行 =================

def parse_window_stdout(path):
    """opendcdiag stdout -> ({失败核: fail块数}, 首个 time-to-fail)。
    计数口径 = 唯一 result:fail 块(协议: 数块不数 miscompare)。"""
    fails, first_ttf, in_fail = {}, None, False
    try:
        fh = open(path)
    except OSError:
        return fails, first_ttf
    with fh:
        for line in fh:
            if "result: fail" in line:
                in_fail = True
                continue
            if "result:" in line and "result: fail" not in line:
                in_fail = False
                continue
            if not in_fail:
                continue
            m = re.search(r'time-to-fail:\s*([\d.]+)', line)
            if m and first_ttf is None:
                first_ttf = float(m.group(1))
            m = re.search(r'logical:\s*(\d+)', line)
            if m:
                c = int(m.group(1))
                fails[c] = fails.get(c, 0) + 1
    return fails, first_ttf


class GroupRunner:
    """检测窗执行器(修正①: 窗内核心必须从应用迁出, 组独占)。
    同一机制服务两种窗: 4 核组窗(优先/例行)与整槽 48 核窗(深测)。"""

    def __init__(self, cfg, binary):
        self.cfg = cfg
        self.binary = binary
        self.warned_no_app = False

    def app_pids(self):
        try:
            main = int(open(self.cfg["app_pid_file"]).read().strip())
        except Exception:
            return []
        pids = [main]
        out = subprocess.run(["pgrep", "-P", str(main)],
                             capture_output=True, text=True).stdout.split()
        pids += [int(x) for x in out]
        return [p for p in pids if os.path.exists(f"/proc/{p}")]

    def set_app_mask(self, mask):
        pids = self.app_pids()
        if not pids and not self.warned_no_app:
            log02(f"⚠️ 应用 pid 文件无有效进程({self.cfg['app_pid_file']}) —— 窗内独占退化为无应用可迁")
            self.warned_no_app = True
        for p in pids:
            subprocess.run(["taskset", "-pc", mask, str(p)], capture_output=True)
        return len(pids)

    def run_window(self, case, cores, dur, tag):
        cores_s = ",".join(str(c) for c in sorted(cores))
        t0 = time.time()
        self.set_app_mask(complement_mask(cores))
        t_evict = time.time() - t0
        outlog = os.path.join(self.cfg["outdir"], f"win_{tag}.stdout")
        cmd = ["taskset", "-c", cores_s, self.binary, "-e", case,
               "-n", str(len(cores)), "-T", f"{dur}s",
               "--ignore-os-error", "--ignore-timeout"]
        t1 = time.time()
        with open(outlog, "w") as out:
            subprocess.run(cmd, stdout=out, stderr=subprocess.STDOUT, cwd=F.REPO_DIR)
        t_run = time.time() - t1
        t2 = time.time()
        self.set_app_mask(self.cfg["app_full_mask"])
        t_restore = time.time() - t2
        fails, first_ttf = parse_window_stdout(outlog)
        return {"case": case, "cores": sorted(cores), "dur": dur,
                "evict_s": round(t_evict, 2), "run_s": round(t_run, 2),
                "restore_s": round(t_restore, 2), "fails": fails,
                "first_ttf": first_ttf, "stdout": outlog,
                "ts": time.strftime("%F %T")}


class StubGroupRunner(GroupRunner):
    """桩执行器: 不动应用/不跑真二进制。script = [(case子串, 目标核集合, {核: fail数})]"""

    def __init__(self, cfg, binary, script=None):
        super().__init__(cfg, binary)
        self.script = script or []
        self.calls = []

    def set_app_mask(self, mask):
        self.calls.append(("mask", mask))
        return 0

    def run_window(self, case, cores, dur, tag):
        self.calls.append(("run", case, sorted(cores), dur, tag))
        time.sleep(min(dur, 0.05))
        fails = {}
        for substr, target, f in self.script:
            if substr in case and (target & set(cores)):
                fails = {c: n for c, n in f.items()}
                break
        return {"case": case, "cores": sorted(cores), "dur": dur,
                "evict_s": 0.0, "run_s": 0.05, "restore_s": 0.0, "fails": fails,
                "first_ttf": 12.3 if fails else None, "stdout": "(stub)",
                "ts": time.strftime("%F %T")}


# ================= Farron-02 主状态机 =================

class Farron02:
    def __init__(self, cfg, runner=None, assessor=None, temp_src=None, speed=None):
        self.cfg = cfg
        self.speed = speed or cfg.get("speed", 1.0)
        self.topo = F.Topology(cfg)
        self.pool = F.TestcasePool(F.POOL_JSON)
        self.ctrls = {name: F.TempController(name, cfg) for name in cfg["sockets"]}
        self.fan = F.FanCoordinator(cfg, dry_run=cfg.get("dry_run", False))
        self.runner = runner or GroupRunner(cfg, cfg["opendcdiag"])
        self.assessor = assessor or LogRiskAssessor(cfg)
        self.temp_src = temp_src or F.read_temps_ipmitool
        self.reliable = set(F.Topology.parse_cpuexpr(cfg["initial_reliable_pool"], set(UNIVERSE)))
        self.masked = set()
        self.retired_sockets = []
        self.suspicious = {}          # core -> {"cases": [...], "attempts": int}
        self.rotation = cfg["routine_start_group"]
        self.case_idx = 0
        self.round_idx = 0
        self.last_temps = {}
        self.stop = threading.Event()
        self.timeline = []            # [{event, ts, detail}]
        self.csv_path = os.path.join(cfg["outdir"], "farron02_windows.csv")
        os.makedirs(cfg["outdir"], exist_ok=True)
        if not os.path.exists(self.csv_path):
            with open(self.csv_path, "w") as f:
                f.write("ts,round,mode,group,cores,case,dur_s,cf,evict_s,run_s,"
                        "restore_s,n_fails,fail_cores,first_ttf\n")
        self.assessment_log = os.path.join(cfg["outdir"], "farron02_assessment.jsonl")
        # v1.2 修正(4h 验收缺陷#2): 用例按二进制实际可用集过滤
        # (用例池含未注册 meson 的 arm0102_* 等, 会造成 0.01s 空转窗)
        self.available_cases = None
        if not cfg.get("dry_run"):
            self.available_cases = self._probe_available_cases()
            if self.available_cases is not None:
                missing = [c for c, _ in self.pool.active_order()
                           if c not in self.available_cases]
                if missing:
                    log02(f"用例过滤: 池中 {len(missing)} 个用例不在二进制 --list, 本轮跳过: {missing}")

    def _probe_available_cases(self):
        """二进制 --list 实际可用用例名集合(格式: '序号 名称 \"描述\"'); 失败返回 None(不过滤)。"""
        try:
            out = subprocess.run([self.cfg["opendcdiag"], "--list"],
                                 capture_output=True, text=True, timeout=60).stdout
        except Exception as ex:
            log02(f"⚠️ --list 探测失败({ex}), 用例不过滤")
            return None
        names = set()
        for line in out.splitlines():
            parts = line.split()
            if len(parts) >= 2 and parts[0].isdigit():
                names.add(parts[1])
        return names or None

    # ---- 基础设施 ----
    def sampler(self):
        while not self.stop.is_set():
            try:
                temps = self.temp_src() or {}
            except Exception:
                temps = {}
            self.last_temps = dict(temps)
            for name, t in temps.items():
                if name in self.ctrls:
                    for ev in self.ctrls[name].update(t):
                        if ev[0] in ("derate_on", "derate_off"):
                            log02(f"温度控制器 {name}: {ev[0]} (界={self.ctrls[name].boundary}°C)")
            self.stop.wait(self.cfg["sample_interval"] / self.speed)

    def socket_hot(self, name):
        t = self.last_temps.get(name)
        return t is not None and t > self.cfg["cool_threshold"]

    def cool_wait(self, sockets, max_wait):
        waited = 0
        while waited < max_wait and all(self.socket_hot(s) for s in sockets):
            self.stop.wait(self.cfg["sample_interval"] / self.speed)
            waited += self.cfg["sample_interval"]
        return waited

    def comp_factor(self, sockets):
        if not self.cfg.get("temp_comp_enable"):
            return 1.0
        temps = [self.last_temps[s] for s in sockets if s in self.last_temps]
        if not temps:
            return 1.0
        return F.temp_compensation_factor(max(temps), self.cfg)

    def next_case(self):
        order = [c for c, _ in self.pool.active_order()]
        if self.available_cases:
            order = [c for c in order if c in self.available_cases]
        if not order:
            return None
        case = order[self.case_idx % len(order)]
        self.case_idx += 1
        return case

    def mark(self, event, detail=""):
        self.timeline.append({"event": event, "ts": time.strftime("%F %T"), "detail": detail})
        log02(f"◉ {event} {detail}")

    def csv_row(self, round_i, mode, group, res, cf):
        with open(self.csv_path, "a") as f:
            f.write(f'{res["ts"]},{round_i},{mode},{group},"{"+".join(map(str, res["cores"]))}",'
                    f'{res["case"]},{res["dur"]},{cf:.2f},{res["evict_s"]},{res["run_s"]},'
                    f'{res["restore_s"]},{sum(res["fails"].values())},'
                    f'"{";".join(f"{c}:{n}" for c, n in sorted(res["fails"].items()))}",'
                    f'{res["first_ttf"] if res["first_ttf"] is not None else ""}\n')

    # ---- 深测(修正②: 整槽 48 核窗, 按 fail 核归属裁决) ----
    def deep_test(self, core):
        sock = self.topo.socket_of(core)
        sock_cores = self.topo.socket_cores(sock)      # 整槽 48 核(共振需要; 只裁决 core 的 fail)
        cases = list(dict.fromkeys(
            self.suspicious.get(core, {}).get("cases", [])
            + [c for c, _ in self.pool.active_order()]))[: self.cfg["deep_test_cap"]]
        for case in cases:
            if self.ctrls[sock].derating:
                log02(f"深测等待: {sock} 降载中")
                while self.ctrls[sock].derating and not self.stop.is_set():
                    self.stop.wait(self.cfg["sample_interval"] / self.speed)
            if self.cfg.get("cool_schedule_enable") and self.socket_hot(sock):
                w = self.cool_wait([sock], self.cfg["cool_wait_max_deep"])
                if w:
                    log02(f"深测凉检等待 {w}s({sock} 过热)")
            dur = int(min(self.cfg["deep_test_duration"] * self.comp_factor([sock]),
                          self.cfg["deep_test_duration"] * self.cfg["temp_comp_max"]))
            self.fan.boost(f"深测 核{core}")
            try:
                res = self.runner.run_window(case, sock_cores, dur, f"deep_r{self.round_idx}_{core}")
            finally:
                self.fan.restore()
            self.csv_row(self.round_idx, "deep", "socket_" + sock, res, self.comp_factor([sock]))
            log02(f"深测 核{core} 用例 {case} ({dur}s, 整槽{len(sock_cores)}核): "
                  f"{sum(res['fails'].values())} fail {res['fails'] or ''}")
            if core in res["fails"]:
                self.mark("深测确认", f"核{core} 用例{case} 复现 {res['fails'][core]} fail")
                return True
        return False

    def verdict(self, core):
        sock = self.topo.socket_of(core)
        if self.cfg["count_known_defectives"]:
            defectives = {c for c in self.masked if self.topo.socket_of(c) == sock} | {core}
        else:
            defectives = {core}
        if len(defectives) < self.cfg["retire_threshold"]:
            self.masked |= defectives
            self.reliable -= defectives
            self.mark("裁决-屏蔽", f"{sock} 缺陷核 {sorted(defectives)} < {self.cfg['retire_threshold']}"
                                   f" → 屏蔽, 其余返回可靠池")
        else:
            self.retired_sockets.append(sock)
            self.reliable -= set(self.topo.socket_cores(sock))
            self.mark("裁决-整槽退役", f"{sock} 缺陷核 {sorted(defectives)} ≥ {self.cfg['retire_threshold']}"
                                       f" → {sock} 全部核心移出可靠池")

    # ---- 主循环 ----
    def run(self, max_seconds=None):
        log02(f"FARRON-02 启动 可靠池={len(self.reliable)}核 "
              f"组大小={self.cfg['group_size']} 例行窗={self.cfg['routine_window_s']}s "
              f"优先窗={self.cfg['priority_window_s']}s 周期={self.cfg['round_period_s']}s"
              f"{' [STUB]' if isinstance(self.runner, StubGroupRunner) else ''}")
        th = threading.Thread(target=self.sampler, daemon=True)
        th.start()
        t0 = time.time()

        while not self.stop.is_set():
            if max_seconds and time.time() - t0 > max_seconds:
                break
            # 每轮刷新第一步评估
            A = self.assessor.assess()
            with open(self.assessment_log, "a") as f:
                f.write(json.dumps({"round": self.round_idx, "A": A}, ensure_ascii=False,
                                   default=str) + "\n")
            log02(f"── 轮 {self.round_idx} ──\n" + self.assessor.report_str(A))
            c = A["conditions"]
            self.mark("评估", f"轮{self.round_idx} 模式={c['mode']} 风险=×10^{c['multipliers']}")

            if c["mode"] == "hardware_fault":
                log02("❌ 硬件故障(SEL 硬错类在案) —— 按 spec 显示并终止 SDC 检测路径: "
                      + "; ".join(c["sel_hard"][:5]))
                self.mark("硬件故障-终止", ";".join(c["sel_hard"][:5]))
                break

            # 可疑队列优先: 深测(整槽窗) → 裁决
            pending = [k for k, v in self.suspicious.items() if v["attempts"] == 0]
            if pending:
                core = pending[0]
                self.suspicious[core]["attempts"] += 1
                if self.deep_test(core):
                    self.verdict(core)
                    self.suspicious.pop(core, None)
                else:
                    log02(f"核 {core} 深测未复现 → 返回在线状态(保留观察, 新 fail 再入队)")
                self.persist()
                continue

            # 检测窗
            if c["mode"] == "priority":
                g0 = group_of(c["cond2_core"], self.cfg["group_size"])
                nb = self.cfg["priority_neighbor_groups"]
                groups = [g0] + [g for d in range(1, nb + 1) for g in (g0 - d, g0 + d)]
                groups = [g for g in groups if 0 <= g < n_groups(self.cfg["group_size"])]
                window_s = self.cfg["priority_window_s"]
                mode = "priority"
            else:
                groups = [self.rotation % n_groups(self.cfg["group_size"])]
                self.rotation += 1
                window_s = self.cfg["routine_window_s"]
                mode = "routine"

            round_waited = set()   # 本轮已做过凉检等待的插座(同插座多组只等一次)
            for g in groups:
                cores = [c2 for c2 in group_cores(g, self.cfg["group_size"]) if c2 in self.reliable]
                if not cores:
                    continue
                sockets = {self.topo.socket_of(c2) for c2 in cores}
                if self.cfg.get("cool_schedule_enable"):
                    cool = [c2 for c2 in cores if not self.socket_hot(self.topo.socket_of(c2))]
                    if cool and len(cool) < len(cores):
                        log02(f"凉检调度: 热插座核本轮跳过, 组{g} 只测 {len(cool)}/{len(cores)} 核")
                        cores = cool
                    elif not cool and not (sockets & round_waited):
                        wmax = self.cfg["cool_wait_max_deep"] if mode == "priority" \
                            else self.cfg["cool_wait_max"]
                        w = self.cool_wait(sockets, wmax)
                        round_waited |= sockets
                        # v1.2 修正(4h 验收缺陷#1): 优先组等待后必跑, 不因转凉早退丢窗
                        # ("每 30min 必测一次"是硬要求); 例行组保留 v1.1 等凉再覆盖语义
                        if w < wmax and mode != "priority":
                            continue
                        log02(f"凉检等待 {w}s 后执行 (mode={mode}; 优先组不丢窗)")
                cf = self.comp_factor(sockets)
                dur = int(window_s * cf)
                case = self.next_case()
                if case is None:
                    break
                self.fan.boost(f"{mode}轮 组{g}")
                try:
                    res = self.runner.run_window(case, cores, dur, f"r{self.round_idx}_g{g}")
                finally:
                    self.fan.restore()
                self.csv_row(self.round_idx, mode, g, res, cf)
                log02(f"检测窗[{mode}] 轮{self.round_idx} 组{g}({len(cores)}核) {case} "
                      f"{dur}s(×{cf:.2f}) evict={res['evict_s']}s run={res['run_s']}s "
                      f"restore={res['restore_s']}s → {sum(res['fails'].values())} fail {res['fails'] or ''}")
                for core, n in res["fails"].items():
                    if core in self.reliable:
                        self.pool.mark_suspicious(core, case)
                        ent = self.suspicious.setdefault(core, {"cases": [], "attempts": 0})
                        if case not in ent["cases"]:
                            ent["cases"].append(case)
                        self.mark("检出", f"轮{self.round_idx} {case} 核{core} {n} fail块"
                                           f" → 可疑级, 待深测(整槽窗)")
                    else:
                        log02(f"(核{core} 已屏蔽/退役, fail 不计新错误: {n})")
            self.round_idx += 1
            self.persist()

            # 睡到下一周期边界
            if max_seconds:
                nxt = t0 + self.round_idx * self.cfg["round_period_s"] / self.speed
                remain = min(nxt - time.time(), t0 + max_seconds - time.time())
                if remain > 0:
                    self.stop.wait(remain)
            else:
                self.stop.wait(self.cfg["round_period_s"] / self.speed)

        self.persist()
        self.write_summary()
        log02("FARRON-02 退出")

    def persist(self):
        state = {"time": time.strftime("%F %T"),
                 "reliable_pool": sorted(self.reliable), "masked_cores": sorted(self.masked),
                 "retired_sockets": self.retired_sockets,
                 "suspicious": {str(k): v for k, v in self.suspicious.items()},
                 "timeline": self.timeline}
        with open(os.path.join(self.cfg["outdir"], "state02.json"), "w") as f:
            json.dump(state, f, ensure_ascii=False, indent=1)

    def write_summary(self):
        first = next((t for t in self.timeline if t["event"] == "检出"), None)
        summ = {"rounds": self.round_idx, "masked": sorted(self.masked),
                "retired_sockets": self.retired_sockets,
                "first_detection": first, "timeline": self.timeline}
        with open(os.path.join(self.cfg["outdir"], "summary02.json"), "w") as f:
            json.dump(summ, f, ensure_ascii=False, indent=1)


# ================= selftest（纯逻辑, 无 sudo/无真实执行） =================

def selftest():
    ok = True

    def check(name, cond):
        nonlocal ok
        print(f"  {'✅' if cond else '❌'} {name}")
        ok = ok and cond

    cfg = load_config02()

    print("SEL 解析/分类自检:")
    sel_text = ("\n".join([
        "  1 | 10/14/2026 | 11:13:36 | Event Logging Disabled #0x94 | Log area reset/cleared | Asserted",
        "  2 | 10/14/2026 | 16:26:55 | Processor #0x4f | State Asserted | Asserted",
        "  3 | 10/15/2026 | 09:00:00 | Temperature #0x03 | Upper Non-critical going high | Asserted",
        "  4 | 10/16/2026 | 09:00:00 | Memory #0x0a | Correctable ECC | Asserted",
        "  5 | 10/17/2026 | 09:00:00 | Processor #0x0 | Machine Check | Asserted",
        "  6 | 10/18/2026 | 09:00:00 | Weird Sensor | Strange Event | Asserted",
    ]))
    entries = parse_sel(sel_text)
    check("6 条解析", len(entries) == 6 and entries[0]["sensor"].startswith("Event Logging"))
    hard, benign, uncat = classify_sel(entries, cfg["sel_hard_patterns"])
    check("硬错类=2 (ECC + Machine Check)", len(hard) == 2)
    check("'Upper Non-critical' 不误伤为硬错(良性)", any("Temperature" in e["sensor"] for e in benign))
    check("'State Asserted' 归良性", any(e["sensor"].startswith("Processor") for e in benign))
    check("未知事件归未归类(非硬错)", len(uncat) == 1)

    print("journal 解析自检:")
    jtext = "\n".join([
        "Oct 23 13:03:09 h kernel: Booted secondary CPU 178",      # 良性
        "Oct 23 13:03:09 h kernel: WARNING: CPU: 179 PID: 1 at arch/arm64/mm/fault.c:494 __do_kernel_fault+0x130",
        "Oct 23 13:03:09 h kernel: Modules linked in: udp_diag inet_diag binfmt_misc nft_fib_inet",
        "Oct 23 13:03:09 h kernel:  i2c_designware_core hisi_trng_v2 dm_mirror aes_neon_bs",
        "Oct 23 13:03:09 h kernel: CPU: 179 PID: 1 Comm: irqbalance Kdump: loaded",
        "Oct 23 13:04:43 h kernel: WARNING: CPU: 179 PID: 2 at arch/arm64/mm/fault.c:494 __do_kernel_fault+0x130",
        "Oct 23 13:04:43 h kernel: Modules linked in: udp_diag inet_diag",
        "Oct 23 13:04:43 h kernel: CPU: 179 PID: 2 Comm: control Kdump: loaded",
        "Oct 23 13:05:00 h kernel: WARNING: CPU: 4 PID: 3 at foo",
        "Oct 23 13:05:00 h kernel: CPU: 4 PID: 3 Comm: bash",
    ])
    events, nlines = parse_journal(jtext)
    check("3 条核归因事件(良性行剔除, Comm 跨越模块清单行)",
          len(events) == 3 and nlines == 10)
    check("受害者软件提取(irqbalance/control/bash)",
          {e["comm"] for e in events} == {"irqbalance", "control", "bash"})
    check("核归因 179×2 + 4×1",
          Counter(e["core"] for e in events) == Counter({179: 2, 4: 1}))

    print("重启史解析自检:")
    ltext = "\n".join([
        "reboot   system boot  6.6.0 2026-10-14 21:44:02 still running",
        "reboot   system boot  6.6.0 2026-10-14 20:48:11 - gone down",
        "shutdown system down  6.6.0 2026-10-14 20:47:30 - 2026-10-14 20:47:55 (00:25)",
        "reboot   system boot  6.6.0 Wed Oct 14 19:54:00 still running",
    ])
    reboots, shutdowns = parse_last(ltext)
    check("3 次重启(ISO+月份名混合)", len(reboots) == 3 and len(shutdowns) == 1)

    print("四条件判定自检(合成场景):")
    now = datetime(2026, 10, 31, 10, 0, 0)

    def mk_sel(sensor, event):
        lst = parse_sel(f"  9 | 10/20/2026 | 09:00:00 | {sensor} | {event} | Asserted\n")
        classify_sel(lst, cfg["sel_hard_patterns"])
        return lst

    sel_ok = mk_sel("Temperature #0x03", "Upper Non-critical going high")
    ev = ([{"core": 179, "tag": "kernel_fault_warning", "comm": c}
           for c in ["irqbalance", "control", "pgrep", "bash", "awk", "irqbalance"]])
    rb = [datetime(2026, 10, d, 12, 0) for d in (2, 3, 14, 14, 14, 14, 14, 14, 14, 14)]
    c = evaluate_conditions(cfg, sel_ok, ev, [], rb, [], now=now)
    check("场景A(本机今日实况): 条件1✓ 条件2✓(核179) 条件3✓(10次非计划) 条件4✗(前阶段无数据)",
          c["cond1"] and c["cond2"] and c["cond2_core"] == 179 and c["cond3"] and not c["cond4"]
          and c["mode"] == "priority" and c["multipliers"] == 2)
    c2 = evaluate_conditions(cfg, mk_sel("Memory #0a", "Correctable ECC"),
                             ev, [], rb, [], now=now)
    check("场景B(SEL 有硬错): 硬件故障模式", c2["mode"] == "hardware_fault" and not c2["cond1"])
    c3 = evaluate_conditions(cfg, sel_ok, ev[:2], [], rb[:1], [], now=now)
    check("场景C(1 种软件+1 次重启): 例行模式, 零乘子",
          c3["mode"] == "routine" and c3["multipliers"] == 0)
    c4 = evaluate_conditions(cfg, sel_ok, ev + ev, ev[:1], rb, [], now=now)
    check("场景D(前阶段 1 种/1 条 → 当前 5 种/12 条): 条件4✓",
          c4["cond4"] and c4["multipliers"] == 3)

    print("组几何自检:")
    check("核179 → 组44(176-179)", group_of(179, 4) == 44
          and group_cores(44, 4) == [176, 177, 178, 179])
    check("组44 互补掩码 = 0-175,180-191", complement_mask({176, 177, 178, 179}) == "0-175,180-191")
    check("优先组序列 = [44,43,45]±", [44] + [g for d in range(1, 2) for g in (44 - d, 44 + d)]
          == [44, 43, 45])
    check("quarter(12核): 核179 → 组14(168-179), 16组且组不跨插槽",
          group_of(179, 12) == 14 and group_cores(14, 12) == list(range(168, 180))
          and n_groups(12) == 16
          and all(g * 12 // 48 == (g * 12 + 11) // 48 for g in range(16)))
    check("组14 互补掩码 = 0-167,180-191", complement_mask(set(range(168, 180))) == "0-167,180-191")

    print("窗口 stdout 解析自检:")
    wtext = """  test: foo
  result: fail
  fail: { cpu-mask: 'X...', time-to-fail: 426.093, seed: 'LCG:1'}
  threads:
  - thread: 0
    id: { logical: 179, core: 179 }
    state: failed
  result: pass
  threads:
  - thread: 1
    id: { logical: 180, core: 180 }
"""
    p = "/tmp/farron02_selftest_window.stdout"
    open(p, "w").write(wtext)
    fails, ttf = parse_window_stdout(p)
    check("fail 块归因核179(数块不数行), ttf 提取",
          fails == {179: 1} and abs(ttf - 426.093) < 1e-6)

    print("\n" + ("✅ 全部通过" if ok else "❌ 存在失败项"))
    return 0 if ok else 1


# ================= stub-run（全流程桩演示） =================

def stub_run(config_path=None):
    """模拟: 评估(合成=本机实况) → 优先模式 → 优先组窗检出179 → 整槽深测确认 → 裁决屏蔽。
    不跑真负载/不动应用/不调 sudo。"""
    cfg = load_config02(config_path)
    cfg["outdir"] = os.path.join(F.STATE_DIR, "sweep", "farron02_stub")
    cfg["speed"] = 60.0
    os.makedirs(cfg["outdir"], exist_ok=True)
    setup_logging(cfg["outdir"])

    class StubAssessor:
        def assess(self):
            return {"time": time.strftime("%F %T"), "sel_error": None,
                    "journal_error": None, "last_error": None,
                    "raw": {"sel": {"total": 137, "hard": 0, "benign": 137, "uncat": 0},
                            "journal": {"lines": 9, "events": 69, "prev_events": 0}},
                    "conditions": {"cond1": True, "cond2": True, "cond2_core": 179,
                                   "cond2_share": 1.0,
                                   "cond2_kinds": ["irqbalance", "control", "pgrep", "bash", "awk"],
                                   "cond3": True, "cond3_unplanned": 10, "cond3_planned": 0,
                                   "cond4": False, "cond4_prev_available": False,
                                   "journal_total": 69, "journal_per_core": {"179": 69},
                                   "sel_hard": [], "multipliers": 2, "mode": "priority"}}
        def report_str(self, A):
            return ("[STUB] 条件1✓ 条件2✓(核179, 5种受害者软件, 100%集中) "
                    "条件3✓(10次非计划重启) 条件4✗(数据不足) → 优先模式, 风险×10^2")

    class StubTemp:
        def __init__(self):
            self.i = 0
        def read(self):
            self.i += 1
            return {"CPU1": 60.0, "CPU2": 58.0, "CPU3": 52.0, "CPU4": 50.0}

    stub = StubGroupRunner(cfg, cfg["opendcdiag"],
                           script=[("neon_rot", {179}, {179: 2})])
    f = Farron02(cfg, runner=stub, assessor=StubAssessor(),
                 temp_src=StubTemp().read, speed=60.0)
    log02(f"=== STUB-RUN 演示: 评估→优先模式→优先组(组大小{cfg['group_size']})窗检出→整槽深测→裁决 ===")
    f.run(max_seconds=100)
    log02("=== STUB-RUN 结束 ===")
    print(json.dumps({"masked": sorted(f.masked), "retired": f.retired_sockets,
                      "timeline_events": [t["event"] for t in f.timeline],
                      "runner_calls": stub.calls[:8]}, ensure_ascii=False, indent=1))
    return 0


# ================= assess-only（真实日志分级报告） =================

def assess_only(config_path=None):
    cfg = load_config02(config_path)
    setup_logging(cfg["outdir"])
    A = LogRiskAssessor(cfg).assess()
    print(LogRiskAssessor(cfg).report_str(A))
    print("\n原始判定 JSON:")
    print(json.dumps(A["conditions"], ensure_ascii=False, indent=1))
    return 0


def setup_logging(outdir):
    os.makedirs(outdir, exist_ok=True)
    _LOG_PATH[0] = os.path.join(outdir, "farron02.log")


# ================= main =================

def main():
    ap = argparse.ArgumentParser(description="FARRON-02: 日志风险分级 + 两模式 4 核组在线检测")
    ap.add_argument("--selftest", action="store_true", help="纯逻辑自检")
    ap.add_argument("--assess-only", action="store_true", help="真实日志风险分级报告")
    ap.add_argument("--stub-run", action="store_true", help="全流程桩演示")
    ap.add_argument("--duration", type=int, default=None, help="运行秒数")
    ap.add_argument("--outdir", default=None, help="输出目录")
    ap.add_argument("--config", default=None, help="额外配置 JSON 路径")
    args = ap.parse_args()

    if args.selftest:
        sys.exit(selftest())
    if args.assess_only:
        sys.exit(assess_only(args.config))
    if args.stub_run:
        sys.exit(stub_run(args.config))

    cfg = load_config02(args.config)
    if args.outdir:
        cfg["outdir"] = args.outdir
    setup_logging(cfg["outdir"])
    if not F.check_binary(cfg):
        sys.exit(1)
    f = Farron02(cfg)

    def sigterm(signum, frame):
        f.stop.set()

    import signal
    signal.signal(signal.SIGTERM, sigterm)
    signal.signal(signal.SIGINT, sigterm)
    f.run(max_seconds=args.duration)


if __name__ == "__main__":
    main()
