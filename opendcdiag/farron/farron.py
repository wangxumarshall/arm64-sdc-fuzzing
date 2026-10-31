#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FARRON —— 在线 SDC 健康管理系统（v1.0，2026-10-25）
设计规格见 farron/DESIGN.md。

状态机：
  可靠资源池 → 在线状态（定期测试 + 温度控制器） → 可疑状态（深度测试） → 裁决（屏蔽核 / 整颗处理器退役）

温度控制器（严格按规格）：
  - 滑动窗口 W 内超过一半记录高于当前边界 B → 提高边界（应用正常工作温度本就偏高，避免频繁降载）
  - 只有最新温度 window.tail() > B 才触发降载
  - 温度回落至边界以下（tail() < B）才解除降载

温度灵敏度融入（2026-10-30 三点改造；校准源 CORE179_TEMPERATURE_RESEARCH_20261027.md）：
  ① 温度补偿窗长——SDC 表达率每 +3.5°C 减半（53°C 锚点）→ 窗长按 2^((T-53)/3.5) 逆比延长（上限 ×4）
  ② 凉检调度——插座 >55°C 的核本轮跳过、等凉再覆盖；深测限时等待（180s）
  ③ 检测轮风扇协同拉 100%（温度/振动两候选机理同向：全扇=最高表达率），轮后恢复；凭据走环境变量或 bmc.env（不落库）

用法：
  python3 farron.py --selftest        # 温度控制器规格自检
  python3 farron.py --dry-run         # 模拟温度/测试结果的全状态机演示（不跑真负载）
  python3 farron.py                   # 实机运行（驱动 builddir/opendcdiag + ipmitool）
  python3 farron.py --status          # 查看当前状态文件
"""

import argparse
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import threading
import time
from collections import deque

FARRON_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_DIR = os.path.dirname(FARRON_DIR)
STATE_DIR = os.path.join(FARRON_DIR, "state")
POOL_JSON = os.path.join(FARRON_DIR, "testcase_pool.json")
STATE_JSON = os.path.join(STATE_DIR, "state.json")
LOG_FILE = os.path.join(STATE_DIR, "farron.log")

# ---------------- 默认配置（全部可被 config.json 覆盖） ----------------
DEFAULT_CONFIG = {
    "sockets": {"CPU1": [0, 47], "CPU2": [48, 95], "CPU3": [96, 143], "CPU4": [144, 191]},
    "initial_reliable_pool": "0-191,-179",     # 离线标定：179 为已知缺陷核，初始即排除
    "known_defective": [179],
    "window_size": 12,                          # 温度滑动窗口长度
    "sample_interval": 5,                       # 温度采样间隔（秒）
    "boundary_init_margin": 15,                 # 初始边界 = 首窗最大值 + 该裕量（°C）
    "boundary_init_fixed": None,                # 或固定初始边界（°C），优先于 margin
    "boundary_strategy": "max",                 # 自适应策略：max（窗口最大值）| step
    "boundary_step": 2.0,                       # step 策略每次提升量（°C）
    "base_test_duration": 300,                  # 基础测试时长（秒）
    "margin_full": 10,                          # 热裕量 ≥ 此值 → 基础时长
    "margin_mid": 5,                            # 5~10 → 压缩时长；<5 → 最短且仅轻量用例
    "short_duration": 120,
    "minimal_duration": 60,
    "light_tiers": ["P3", "P4"],                # 低裕量时只跑轻量梯队
    "deep_test_duration": 600,                  # 可疑状态深度测试每用例时长
    "deep_test_cap": 8,                         # 深测用例上限
    "retire_threshold": 2,                      # 同一处理器缺陷核数 ≥ 此值 → 整颗退役
    "count_known_defectives": True,             # 裁决计数含历史已屏蔽缺陷核（如 179）
    "app_tests": None,                          # 应用相关用例过滤（None=全池）
    "opendcdiag": os.path.join(REPO_DIR, "builddir", "opendcdiag"),
    "dry_run": False,

    # ---- 温度灵敏度融入（2026-10-30 三点改造；校准源 CORE179_TEMPERATURE_RESEARCH_20261027.md）----
    "temp_comp_enable": True,           # ① 温度补偿窗长：率每 +3.5°C 减半 → 窗长逆比延长
    "temp_comp_anchor": 53.0,           #    率标定锚点（53°C ≈ 满率 ~13/min，全扇 100% 实验下限）
    "temp_comp_halving": 3.5,           #    每 +3.5°C 率减半（10-24/25 两战役响应曲线）
    "temp_comp_max": 4.0,               #    补偿因子上限（更热交给②凉检调度，不跑超长窗）
    "cool_schedule_enable": True,       # ② 凉检调度：热插座的核本轮跳过、等凉再覆盖
    "cool_threshold": 55.0,             #    插座温度高于此值 → 该插座本轮不测
    "cool_wait_max": 600,               #    定期轮全热时最长等待（秒）；超时带补偿执行
    "cool_wait_max_deep": 180,          #    深测凉检等待上限（秒，更急）
    "fan_coordination": True,           # ③ 检测轮风扇协同拉 100%（温度/振动两说同向）
    "fan_revert_seconds": 3600,         #    手动档自动回退计时（安全网：进程崩溃也回自动档）
    "binary_sha256_prefix": "a05c17631da3e1a2",  # -O3 基线指纹钉死（-O0 构建零检出）
}


def load_config():
    """默认配置 + farron/config.json 覆盖（存在时）。"""
    cfg = dict(DEFAULT_CONFIG)
    cfg_path = os.path.join(FARRON_DIR, "config.json")
    if os.path.exists(cfg_path):
        with open(cfg_path) as f:
            overrides = json.load(f)
        cfg.update(overrides)
        log(f"已加载配置覆盖: {cfg_path} ({sorted(overrides)})")
    return cfg


def log(msg):
    line = f"[{time.strftime('%F %T')}] {msg}"
    print(line, flush=True)
    os.makedirs(STATE_DIR, exist_ok=True)
    with open(LOG_FILE, "a") as f:
        f.write(line + "\n")


# ================= 温度控制器（规格实现） =================
class TempController:
    """单插槽温度控制器：滑动窗口 + 动态边界 + 降载判定。"""

    def __init__(self, name, cfg):
        self.name = name
        self.cfg = cfg
        self.window = deque(maxlen=cfg["window_size"])
        self.boundary = None            # 初始边界：首窗满后设定
        self.derating = False
        self.adapt_count = 0

    def update(self, temp):
        """喂入一次温度采样，返回本步发生的事件列表。"""
        events = []
        self.window.append(temp)

        # 初始边界设定（首窗填满）
        if self.boundary is None:
            if len(self.window) == self.window.maxlen:
                base = (self.cfg["boundary_init_fixed"]
                        if self.cfg["boundary_init_fixed"] is not None
                        else max(self.window) + self.cfg["boundary_init_margin"])
                self.boundary = float(base)
                events.append(("boundary_init", self.boundary))
            return events

        # —— 边界自适应：窗口内超过一半记录已高于当前边界 ——
        above = sum(1 for t in self.window if t > self.boundary)
        if above > len(self.window) / 2:
            old = self.boundary
            if self.cfg["boundary_strategy"] == "max":
                self.boundary = float(max(self.window))
            else:  # step
                self.boundary = old + self.cfg["boundary_step"]
            self.adapt_count += 1
            events.append(("boundary_raise", old, self.boundary))

        # —— 降载判定：只有最新温度 window.tail() 超过边界才启动 ——
        tail = self.window[-1]
        if not self.derating and tail > self.boundary:
            self.derating = True
            events.append(("derate_on", tail, self.boundary))
        # —— 解除：温度回落至边界以下 ——
        elif self.derating and tail < self.boundary:
            self.derating = False
            events.append(("derate_off", tail, self.boundary))
        return events

    @property
    def margin(self):
        """热裕量 = 边界 - 最新温度（None=窗口未满）。"""
        if self.boundary is None or not self.window:
            return None
        return self.boundary - self.window[-1]


# ================= 温度灵敏度：补偿因子（①） =================
def temp_compensation_factor(temp, cfg):
    """SDC 表达率随温度的窗长补偿因子（①）。

    校准（2026-10-24/25 两战役，179/CPU4）：53°C ≈ 13/min（满率，全扇 100% 实验
    下限 52.7°C），每 +3.5°C 率减半（63.9°C → 1.78/min，~4.6-7.4×）。为维持恒定
    检出概率，窗长按率逆比延长：factor = 2^((T-53)/3.5)。
    - 低于锚点不缩短（52-53°C 已是率平台）
    - 上限 temp_comp_max（更热交给②凉检调度，不跑超长窗）
    注意：曲线在 CPU4/179 上标定，推广到其他插槽为同硅假设。"""
    if not cfg["temp_comp_enable"] or temp is None:
        return 1.0
    expo = (temp - cfg["temp_comp_anchor"]) / cfg["temp_comp_halving"]
    return min(cfg["temp_comp_max"], max(1.0, 2.0 ** expo))


# ================= 风扇协同（③） =================
class FanCoordinator:
    """检测轮风扇协同：轮前拉全扇 100%，轮后恢复原状态（③）。

    依据：温度-SDC 负关联的两候选机理（硅温度直接调制 / 风扇耦合振动）在
    "全扇 = 最高表达率" 上同向——无需等振动判别实验定案即可采用。
    凭据：环境变量 BMC_HOST/BMC_USER/BMC_PASS，或 farron/bmc.env（gitignore，
    用户自建、不落库）。手动档带 fan_revert_seconds 自动回退计时（安全网）。
    dry-run 只记日志不碰真风扇。"""

    def __init__(self, cfg, dry_run=False):
        self.cfg = cfg
        self.dry = dry_run
        env_file = os.path.join(FARRON_DIR, "bmc.env")
        if os.path.exists(env_file):                  # 凭据文件（不落库）
            for line in open(env_file):
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    os.environ.setdefault(k.strip(), v.strip())
        self.host = os.environ.get("BMC_HOST")
        self.user = os.environ.get("BMC_USER", "Administrator")
        self.pw = os.environ.get("BMC_PASS")
        self.enabled = (cfg.get("fan_coordination", True)
                        and bool(self.host) and bool(self.pw))
        self.prior = None            # (mode, level) 或 None

    def _ssh(self, *args, timeout=20, confirm=False):
        cmd = ["sshpass", "-p", self.pw, "ssh",
               "-o", "StrictHostKeyChecking=no", "-o", "UserKnownHostsFile=/dev/null",
               "-o", "ConnectTimeout=8", f"{self.user}@{self.host}", *args]
        return subprocess.run(cmd, capture_output=True, text=True,
                              timeout=timeout, input="Y\n" if confirm else None)

    def _state(self):
        out = self._ssh("ipmcget", "-d", "faninfo").stdout.lower()
        mode = "manual" if re.search(r"mode:\s*manual", out) else \
               ("auto" if re.search(r"mode:\s*auto", out) else None)
        m = re.search(r"level[:\s]+(\d+)", out)
        level = int(m.group(1)) if (m and mode == "manual") else None
        return mode, level

    def boost(self, reason=""):
        if self.dry:
            self.prior = ("(dry)", None)
            log(f"风扇协同[dry] ↑100%（{reason}）")
            return True
        if not self.enabled:
            return False
        try:
            self.prior = self._state()
            self._ssh("ipmcset", "-d", "fanmode", "-v",
                      "1", str(self.cfg["fan_revert_seconds"]), confirm=True)
            self._ssh("ipmcset", "-d", "fanlevel", "-v", "100", confirm=True)
            log(f"风扇协同↑100%（{reason}；原状态 {self.prior[0]}/{self.prior[1]}，"
                f"{self.cfg['fan_revert_seconds']}s 自动回退兜底）")
            return True
        except Exception as e:
            log(f"风扇协同失败（跳过，不影响测试）: {e}")
            return False

    def restore(self):
        if self.dry:
            if self.prior is not None:
                log(f"风扇协同[dry] 恢复 {self.prior[0]}")
                self.prior = None
            return
        if not self.enabled or self.prior is None:
            return
        mode, level = self.prior
        try:
            if mode == "manual":
                self._ssh("ipmcset", "-d", "fanmode", "-v",
                          "1", str(self.cfg["fan_revert_seconds"]), confirm=True)
                self._ssh("ipmcset", "-d", "fanlevel", "-v",
                          str(level if level is not None else 100), confirm=True)
            else:
                self._ssh("ipmcset", "-d", "fanmode", "-v", "0", confirm=True)
            log(f"风扇协同恢复: mode={mode} level={level}")
        except Exception as e:
            log(f"风扇恢复失败（{self.cfg['fan_revert_seconds']}s 自动回退兜底）: {e}")
        self.prior = None


# ================= -O3 基线指纹钉死 =================
def check_binary(cfg):
    """编译产物是检出开关（2026-10-30 发现：-O0 构建五用例零检出，P<10⁻⁴⁰⁰）。
    启动前核对二进制 sha256 前缀，不符则拒绝运行。config 置
    binary_sha256_prefix=null 可跳过（不建议）。"""
    prefix = cfg.get("binary_sha256_prefix")
    path = cfg["opendcdiag"]
    if not prefix or not os.path.exists(path):
        return True
    try:
        h = subprocess.run(["sha256sum", path], capture_output=True,
                           text=True, timeout=60).stdout.split()[0]
    except Exception as e:
        log(f"二进制指纹读取失败（放行）: {e}")
        return True
    if not h.startswith(prefix):
        log(f"❌ 二进制指纹不符：期望 {prefix}，实际 {h[:16]} —— 拒绝启动"
            f"（-O0 构建零检出；若已确认换用新基线，请更新 config.binary_sha256_prefix）")
        return False
    log(f"二进制指纹核对通过: {h[:16]}")
    return True


# ================= 用例池 =================
class TestcasePool:
    """三级用例池：可疑级 > 活跃级 > 基础级。"""

    def __init__(self, path):
        self.path = path
        with open(path) as f:
            self.data = json.load(f)

    def active_order(self):
        """活跃级按 P0→P4 顺序展开。"""
        out = []
        for tier in ("P0", "P1", "P2", "P3", "P4"):
            out += [(t, tier) for t in self.data["levels"]["active"].get(tier, [])]
        return out

    def basic_list(self):
        return list(self.data["levels"]["basic"]["inactivated"]) + \
               list(self.data["levels"]["basic"]["untested"])

    def suspicious_cases(self):
        """全部可疑级用例（并集，去重，保序）。"""
        seen, out = set(), []
        for core, cases in self.data["levels"]["suspicious"]["cores"].items():
            for c in cases:
                if c not in seen:
                    seen.add(c)
                    out.append(c)
        return out

    def mark_suspicious(self, core, testcase):
        """在线状态发现新错误：该用例针对该核标记为可疑级，更新 Testcase Pool。"""
        cores = self.data["levels"]["suspicious"]["cores"]
        cores.setdefault(str(core), [])
        if testcase not in cores[str(core)]:
            cores[str(core)].append(testcase)
        self.save()

    def save(self):
        with open(self.path, "w") as f:
            json.dump(self.data, f, ensure_ascii=False, indent=2)


# ================= 核心/插槽工具 =================
class Topology:
    def __init__(self, cfg):
        self.cfg = cfg
        self.sockets = cfg["sockets"]                      # 名 -> [lo, hi]
        self.core_socket = {}
        for name, (lo, hi) in self.sockets.items():
            for c in range(lo, hi + 1):
                self.core_socket[c] = name

    def socket_of(self, core):
        return self.core_socket[core]

    def socket_cores(self, name):
        lo, hi = self.sockets[name]
        return list(range(lo, hi + 1))

    @staticmethod
    def parse_cpuexpr(expr, universe):
        """'0-191,-179' -> set；简单解析器。"""
        out = set()
        for part in expr.replace(" ", "").split(","):
            if not part:
                continue
            neg = part.startswith("-")
            if neg:
                part = part[1:]
            if "-" in part:
                a, b = part.split("-")
                rng = set(range(int(a), int(b) + 1))
            else:
                rng = {int(part)}
            out = (out - rng) if neg else (out | rng)
        return out & universe


# ================= 健康管理器 =================
class HealthManager:
    """可靠池管理 + 可疑状态深度测试 + 屏蔽/退役裁决。"""

    def __init__(self, cfg, topo, pool, runner):
        self.cfg = cfg
        self.topo = topo
        self.pool = pool
        self.runner = runner                      # 测试执行器（真/模拟）
        universe = set(range(max(hi for _, hi in topo.sockets.values()) + 1))
        self.reliable = Topology.parse_cpuexpr(cfg["initial_reliable_pool"], universe)
        self.masked = set(cfg["known_defective"])  # 已屏蔽缺陷核
        self.retired_sockets = []
        self.suspicious_cores = []                  # 待深测队列

    def in_pool(self, core):
        return core in self.reliable and self.topo.socket_of(core) not in self.retired_sockets

    def report_anomaly(self, core, source):
        """在线状态中某核表现异常（定期测试失败/应用报错）→ 进入可疑状态。"""
        if core not in self.suspicious_cores:
            self.suspicious_cores.append(core)
            log(f"⚠️ 核 {core} 进入可疑状态（来源：{source}）")

    def deep_test(self, core, temp_gate, dur_cap=None):
        """可疑状态：取该处理器的可疑级+活跃级用例做针对性深度测试。
        temp_gate(socket) -> 可继续测试的时长秒数（0=降载暂停；Farron 侧
        gate 已含①温度补偿）。dur_cap：时长上限（含补偿后）。"""
        sock = self.topo.socket_of(core)
        cases = self.pool.suspicious_cases() + [t for t, _ in self.pool.active_order()]
        cases = cases[: self.cfg["deep_test_cap"]]
        if dur_cap is None:
            dur_cap = self.cfg["deep_test_duration"]
        confirmed = False
        for case in cases:
            dur = temp_gate(sock)
            if dur <= 0:
                log(f"深测暂停：{sock} 降载中，等待降温")
                while temp_gate(sock) <= 0:
                    time.sleep(self.cfg["sample_interval"])
                dur = min(dur_cap, temp_gate(sock))
            dur = min(dur, dur_cap)
            log(f"深测 核{core} 用例 {case} ({dur}s)")
            fails = self.runner.run(case, [core], dur)
            if core in fails:
                confirmed = True
                log(f"深测确认：核 {core} 在用例 {case} 上复现错误")
                break
        return confirmed

    def verdict(self, core):
        """健康分析：缺陷核数 < 2 → 仅屏蔽缺陷核；否则整颗处理器退役。
        计数口径：该插槽累计缺陷核（含历史已屏蔽，如已知缺陷核 179）。"""
        sock = self.topo.socket_of(core)
        if self.cfg["count_known_defectives"]:
            sock_defectives = {c for c in self.masked if self.topo.socket_of(c) == sock}
            sock_defectives.add(core)
        else:
            sock_defectives = {core}
        if len(sock_defectives) < self.cfg["retire_threshold"]:
            self.masked |= sock_defectives
            self.reliable -= sock_defectives
            log(f"✅ 裁决：{sock} 缺陷核 {sorted(sock_defectives)} < {self.cfg['retire_threshold']}"
                f" → 屏蔽之，其余核心返回可靠资源池")
        else:
            self.retired_sockets.append(sock)
            self.reliable -= set(self.topo.socket_cores(sock))
            log(f"❌ 裁决：{sock} 缺陷核 {sorted(sock_defectives)} ≥ {self.cfg['retire_threshold']}"
                f" → 整颗处理器 {sock} 退役（{sock} 全部核心移出可靠池）")

    def snapshot(self):
        return {
            "reliable_pool": sorted(self.reliable),
            "masked_cores": sorted(self.masked),
            "retired_sockets": self.retired_sockets,
            "suspicious_queue": self.suspicious_cores,
        }


# ================= 测试执行器 =================
class RealRunner:
    """驱动真实 opendcdiag。run(case, cores, dur) -> {失败核: 次数}。"""

    def __init__(self, cfg):
        self.cfg = cfg
        self.proc = None

    def run(self, case, cores, dur):
        cl = ",".join(str(c) for c in sorted(cores))
        outlog = os.path.join(STATE_DIR, f"run_{case}_{int(time.time())}.stdout")
        cmd = ["taskset", "-c", cl, self.cfg["opendcdiag"], "-e", case,
               "-n", str(len(cores)), "-T", f"{dur}s",
               "--ignore-os-error", "--ignore-timeout"]
        log(f"执行: {' '.join(cmd[:2])} ... -e {case} -n {len(cores)} -T {dur}s")
        with open(outlog, "w") as out:
            self.proc = subprocess.Popen(cmd, stdout=out, stderr=subprocess.STDOUT,
                                         cwd=REPO_DIR)
            self.proc.wait()
        self.proc = None
        return parse_fails(outlog)

    def terminate(self):
        if self.proc:
            self.proc.terminate()


def parse_fails(stdout_path):
    """解析 opendcdiag stdout：fail 块内其后的 logical: N 即失败核。"""
    fails = {}
    in_fail = False
    if not os.path.exists(stdout_path):
        return fails
    with open(stdout_path, errors="replace") as f:
        for line in f:
            if line.strip() == "result: fail":
                in_fail = True
            elif line.startswith("- test:"):
                in_fail = False
            elif in_fail:
                m = re.search(r"logical: (\d+)", line)
                if m:
                    core = int(m.group(1))
                    fails[core] = fails.get(core, 0) + 1
    return fails


class SimRunner:
    """模拟执行器（dry-run）：按脚本注入结果。"""

    def __init__(self, script=None):
        self.script = script or []      # [(case_substr, {core: n}), ...]
        self.calls = []

    def run(self, case, cores, dur):
        self.calls.append((case, list(cores), dur))
        for substr, fails in self.script:
            if substr in case:
                return {c: n for c, n in fails.items() if c in cores}
        return {}


# ================= 温度源 =================
def read_temps_ipmitool():
    """返回 {CPU名: 温度}。"""
    out = subprocess.run(
        ["sudo", "ipmitool", "sensor", "reading",
         "CPU1_TEMP", "CPU2_TEMP", "CPU3_TEMP", "CPU4_TEMP"],
        capture_output=True, text=True, timeout=10).stdout
    temps = {}
    for line in out.splitlines():
        parts = [p.strip() for p in line.split("|")]
        if len(parts) >= 2 and parts[0].endswith("_TEMP"):
            temps[parts[0].replace("_TEMP", "")] = float(parts[1])
    return temps


class TempSimulator:
    """dry-run 温度脚本：[(时刻偏移秒, {CPU名: 温度}), ...] 线性插值。"""

    def __init__(self, script):
        self.script = script
        self.t0 = time.time()

    def read(self):
        t = time.time() - self.t0
        script = sorted(self.script)
        if t <= script[0][0]:
            row = script[0][1]
        elif t >= script[-1][0]:
            row = script[-1][1]
        else:
            for (ta, ra), (tb, rb) in zip(script, script[1:]):
                if ta <= t < tb:
                    f = (t - ta) / (tb - ta)
                    row = {k: ra[k] + f * (rb[k] - ra[k]) for k in ra}
                    break
            else:
                row = script[-1][1]
        return dict(row)


# ================= 主守护进程 =================
class Farron:
    def __init__(self, cfg, runner=None, temp_src=None, speed=1.0):
        self.cfg = cfg
        self.topo = Topology(cfg)
        self.pool = TestcasePool(POOL_JSON)
        self.runner = runner or RealRunner(cfg)
        self.temp_src = temp_src or read_temps_ipmitool
        self.speed = speed                        # dry-run 时间加速
        self.ctrls = {name: TempController(name, cfg) for name in cfg["sockets"]}
        self.health = HealthManager(cfg, self.topo, self.pool, self.runner)
        self.fan = FanCoordinator(cfg, dry_run=cfg["dry_run"])
        self.rotation = {"active": 0, "basic": 0}
        self.stop = threading.Event()

    # ---- 温度采样线程 ----
    def sampler(self):
        while not self.stop.is_set():
            try:
                temps = self.temp_src()
            except Exception as e:
                log(f"温度读取失败: {e}")
                temps = None
            if temps:
                for name, tc in self.ctrls.items():
                    if name in temps:
                        for ev in tc.update(temps[name]):
                            log(f"[{name}] {ev[0]}: {list(round(x,1) for x in ev[1:])}")
                            if ev[0] == "derate_on":
                                self._set_derate_flag(name, True)
                            elif ev[0] == "derate_off":
                                self._set_derate_flag(name, False)
            self.stop.wait(self.cfg["sample_interval"] / self.speed)

    def _set_derate_flag(self, socket, on):
        os.makedirs(STATE_DIR, exist_ok=True)
        flag = os.path.join(STATE_DIR, f"derate_{socket}.flag")
        if on:
            open(flag, "w").write(time.strftime("%F %T"))
        elif os.path.exists(flag):
            os.remove(flag)

    # ---- 温度灵敏度（①②）----
    def socket_temps(self, sockets):
        """涉及插座的最新温度列表（窗口未满的跳过）。"""
        return [self.ctrls[s].window[-1] for s in sockets if self.ctrls[s].window]

    def comp_factor(self, sockets):
        """① 温度补偿因子：以涉及插座的最热者为准（最热插座主导率压制）。"""
        ts = self.socket_temps(sockets)
        if not ts:
            return 1.0
        return temp_compensation_factor(max(ts), self.cfg)

    def socket_hot(self, name):
        """② 该插座当前是否高于凉检阈值。"""
        w = self.ctrls[name].window
        return bool(w) and w[-1] > self.cfg["cool_threshold"]

    def cool_wait(self, sockets, max_wait):
        """② 等待插座降温（全热或深测场景），返回实际等待秒数。"""
        waited = 0
        while waited < max_wait and not self.stop.is_set():
            if all(not self.socket_hot(s) for s in sockets):
                break
            self.stop.wait(self.cfg["sample_interval"] / self.speed)
            waited += self.cfg["sample_interval"]
        return waited

    # ---- 测试可用时长（温度边界动态分配） ----
    def allocate(self, sockets):
        """涉及时刻槽的最小热裕量决定时长；任一降载中 → 0。"""
        margins = [self.ctrls[s].margin for s in sockets]
        if any(m is None for m in margins):
            return self.cfg["minimal_duration"]      # 窗口未满，保守短测
        if any(self.ctrls[s].derating for s in sockets):
            return 0
        m = min(margins)
        if m >= self.cfg["margin_full"]:
            return self.cfg["base_test_duration"]
        if m >= self.cfg["margin_mid"]:
            return self.cfg["short_duration"]
        return self.cfg["minimal_duration"]

    def usable_cores(self):
        """可靠池中、非降载插槽的核心。"""
        out = []
        for c in sorted(self.health.reliable):
            sock = self.topo.socket_of(c)
            if sock not in self.health.retired_sockets and not self.ctrls[sock].derating:
                out.append(c)
        return out

    # ---- 选题（可疑级 > 活跃级 > 基础级） ----
    def next_case(self, light_only=False):
        susp = self.pool.suspicious_cases()
        if susp:
            return susp[0], "可疑级"
        actives = self.pool.active_order()
        if light_only:
            actives = [(t, tier) for t, tier in actives if tier in self.cfg["light_tiers"]]
        if actives:
            t, tier = actives[self.rotation["active"] % len(actives)]
            self.rotation["active"] += 1
            return t, f"活跃级({tier})"
        basics = self.pool.basic_list()
        if basics:
            t = basics[self.rotation["basic"] % len(basics)]
            self.rotation["basic"] += 1
            return t, "基础级"
        return None, None

    # ---- 应用侧异常上报（anomaly_<core> 文件） ----
    def poll_anomalies(self):
        if not os.path.isdir(STATE_DIR):
            return
        for fn in os.listdir(STATE_DIR):
            m = re.match(r"anomaly_(\d+)$", fn)
            if m:
                core = int(m.group(1))
                if self.health.in_pool(core):
                    self.health.report_anomaly(core, f"应用上报({fn})")
                os.remove(os.path.join(STATE_DIR, fn))

    # ---- 主循环 ----
    def run(self, max_seconds=None):
        log(f"FARRON 启动 {'[DRY-RUN]' if self.cfg['dry_run'] else ''} "
            f"可靠池={len(self.health.reliable)}核 屏蔽={sorted(self.health.masked)}")
        th = threading.Thread(target=self.sampler, daemon=True)
        th.start()
        t0 = time.time()
        while not self.stop.is_set():
            if max_seconds and time.time() - t0 > max_seconds:
                break
            self.poll_anomalies()
            # 1) 可疑状态优先处理（②凉检短等 + ①补偿 gate + ③风扇协同）
            if self.health.suspicious_cores:
                core = self.health.suspicious_cores.pop(0)
                sock = self.topo.socket_of(core)
                if self.cfg["cool_schedule_enable"] and self.socket_hot(sock):
                    w = self.cool_wait([sock], self.cfg["cool_wait_max_deep"])
                    if w:
                        log(f"深测凉检等待 {w}s（插座 {sock} 过热）")
                gate = lambda s: (0 if self.ctrls[s].derating else
                                  int(self.cfg["deep_test_duration"] * self.comp_factor([s])))
                dur_cap = int(self.cfg["deep_test_duration"] * self.cfg["temp_comp_max"])
                self.fan.boost(f"深测 核{core}")
                try:
                    confirmed = self.health.deep_test(core, gate, dur_cap)
                finally:
                    self.fan.restore()
                if confirmed:
                    self.health.verdict(core)
                else:
                    log(f"核 {core} 深测未复现 → 返回在线状态（保留观察）")
                self.persist()
                continue
            # 2) 在线定期测试
            cores = self.usable_cores()
            if not cores:
                time.sleep(self.cfg["sample_interval"] / self.speed)
                continue
            sockets = {self.topo.socket_of(c) for c in cores}
            # ② 凉检调度：热插座的核本轮跳过（等凉再覆盖）；全热则限时等待
            if self.cfg["cool_schedule_enable"]:
                cool_cores = [c for c in cores if not self.socket_hot(self.topo.socket_of(c))]
                if not cool_cores:
                    w = self.cool_wait(sockets, self.cfg["cool_wait_max"])
                    if w < self.cfg["cool_wait_max"]:
                        continue            # 已转凉 → 重新评估再入循环
                    log(f"凉检等待超时（全插座>{self.cfg['cool_threshold']}°C）→ 带温度补偿执行")
                elif len(cool_cores) < len(cores):
                    hot = sorted({self.topo.socket_of(c) for c in cores} -
                                 {self.topo.socket_of(c) for c in cool_cores})
                    log(f"凉检调度：热插座 {hot} 本轮跳过（等凉再覆盖），只测 {len(cool_cores)} 凉核")
                    cores = cool_cores
                    sockets = {self.topo.socket_of(c) for c in cores}
            dur0 = self.allocate(sockets)
            if dur0 <= 0:
                time.sleep(self.cfg["sample_interval"] / self.speed)
                continue
            # ① 温度补偿窗长（热裕量基础时长 × 补偿因子）
            cf = self.comp_factor(sockets)
            dur = int(dur0 * cf)
            hot_t = max(self.socket_temps(sockets), default=None)
            light_only = dur0 <= self.cfg["minimal_duration"] and \
                all((self.ctrls[s].margin or 0) < self.cfg["margin_mid"] for s in sockets)
            case, level = self.next_case(light_only)
            if case is None:
                time.sleep(self.cfg["sample_interval"] / self.speed)
                continue
            comp_note = f" 温度补偿×{cf:.2f}@{hot_t}°C" if cf > 1.001 else ""
            log(f"定期测试 [{level}] {case} cores={len(cores)} dur={dur}s{comp_note}")
            self.fan.boost(f"定期轮 {case}")
            try:
                fails = self.runner.run(case, cores, dur)
            finally:
                self.fan.restore()
            if fails:
                for core, n in fails.items():
                    if self.health.in_pool(core):
                        # 发现新错误：用例针对该核标记可疑级，更新 Testcase Pool
                        self.pool.mark_suspicious(core, case)
                        log(f"🆕 新错误：{case} 在核 {core} 上 {n} 次 fail → 标记可疑级并更新 Testcase Pool")
                        self.health.report_anomaly(core, f"定期测试({case})")
            self.persist()
            if self.cfg["dry_run"]:
                self.stop.wait(min(dur, 2))       # 模拟节奏（真实模式 run() 已阻塞相应时长）
        log("FARRON 退出")

    def persist(self):
        os.makedirs(STATE_DIR, exist_ok=True)
        state = {
            "time": time.strftime("%F %T"),
            "health": self.health.snapshot(),
            "temperature": {n: {"boundary": c.boundary, "tail": (c.window[-1] if c.window else None),
                                "derating": c.derating, "adaptations": c.adapt_count,
                                "window": list(c.window)}
                            for n, c in self.ctrls.items()},
            "suspicious_pool": self.pool.data["levels"]["suspicious"]["cores"],
        }
        with open(STATE_JSON, "w") as f:
            json.dump(state, f, ensure_ascii=False, indent=2)


# ================= 自检：温度控制器规格验证 =================
def selftest():
    cfg = dict(DEFAULT_CONFIG)   # 自检用纯默认值，保证断言确定性
    ok = True

    def check(name, cond):
        nonlocal ok
        print(f"  {'✅' if cond else '❌'} {name}")
        ok = ok and cond

    print("TempController 规格自检:")
    # 场景1：初始边界设定 + 稳态不降载
    tc = TempController("T", cfg)
    for t in [50] * cfg["window_size"]:
        tc.update(t)
    check("首窗满后设定初始边界 (50+15=65)", tc.boundary == 65)
    check("稳态低于边界不降载", not tc.derating)
    # 场景2：窗口过半超界 → 边界升高（注意：首个70>65按规格即触发降载，属正确行为）
    for t in [70] * (cfg["window_size"] // 2 + 1):
        tc.update(t)
    check("窗口过半高于边界 → 边界自适升高 (65→70)", tc.boundary == 70)
    tc.update(65)  # 回落清位，隔离后续场景
    # 场景3：只有最新超界才降载；回落界下解除
    evs = tc.update(71)
    check("tail=71>70 → 触发降载", tc.derating and any(e[0] == "derate_on" for e in evs))
    evs = tc.update(69)
    check("tail=69<70 → 解除降载", not tc.derating and any(e[0] == "derate_off" for e in evs))
    # 场景4：历史高但最新低 → 不降载（'只有最新'规则）
    tc2 = TempController("T2", cfg)
    for t in [50] * cfg["window_size"]:
        tc2.update(t)
    for _ in range(3):
        tc2.update(80)          # 历史 3 个 80（不过半，不升界）
    evs = tc2.update(50)        # 最新回落
    check("历史高但最新低 → 不降载", not tc2.derating)
    evs = tc2.update(80)        # 最新 80 → 立即降载
    check("最新超界 → 立即降载", tc2.derating)

    print("温度补偿因子自检 (① 2026-10-30):")
    check("53°C → ×1.0（锚点，满率）", abs(temp_compensation_factor(53.0, cfg) - 1.0) < 1e-9)
    check("56.5°C → ×2.0（+3.5°C 减半的逆补偿）", abs(temp_compensation_factor(56.5, cfg) - 2.0) < 1e-6)
    check("60°C → ×4.0", abs(temp_compensation_factor(60.0, cfg) - 4.0) < 1e-6)
    check("67°C → ×4.0（上限截断，更热交给凉检调度）", abs(temp_compensation_factor(67.0, cfg) - 4.0) < 1e-6)
    check("50°C → ×1.0（低于锚点不缩短，率已到平台）", abs(temp_compensation_factor(50.0, cfg) - 1.0) < 1e-9)

    print("拓扑解析自检:")
    topo = Topology(cfg)
    universe = set(range(192))
    check("'0-191,-179' 解析", Topology.parse_cpuexpr("0-191,-179", universe) == universe - {179})
    check("核179→CPU4", topo.socket_of(179) == "CPU4")
    check("核0→CPU1", topo.socket_of(0) == "CPU1")

    print("用例池自检:")
    pool = TestcasePool(POOL_JSON)
    n_active = sum(len(pool.data["levels"]["active"][t]) for t in ("P0","P1","P2","P3","P4"))
    n_basic = len(pool.basic_list())
    check(f"活跃级=57 (实际{n_active})", n_active == 57)
    check(f"基础级=83 (实际{n_basic})", n_basic == 83)

    print("\n" + ("✅ 全部通过" if ok else "❌ 存在失败项"))
    return 0 if ok else 1


# ================= dry-run 演示 =================
def dry_run():
    """模拟温度爬升→降载→边界自适应→新错误→可疑级标记→深测→裁决的全流程。"""
    cfg = load_config()
    cfg["dry_run"] = True
    cfg["sample_interval"] = 1          # 加速采样
    # 温度脚本：CPU4 从 50 爬到 75（越过初始界）再回落
    temp_sim = TempSimulator([
        (0,   {"CPU1": 55, "CPU2": 55, "CPU3": 55, "CPU4": 50}),
        (30,  {"CPU1": 55, "CPU2": 55, "CPU3": 55, "CPU4": 75}),   # 越界 → 降载
        (45,  {"CPU1": 55, "CPU2": 55, "CPU3": 55, "CPU4": 62}),   # 回落 → 解除
        (120, {"CPU1": 55, "CPU2": 55, "CPU3": 55, "CPU4": 62}),
    ])
    # 模拟结果脚本：活跃级 movbe 在核 100 上失败（新错误→可疑级→深测复现→裁决）
    sim = SimRunner([("movbe", {100: 2})])
    f = Farron(cfg, runner=sim, temp_src=temp_sim.read, speed=1.0)
    log("=== DRY-RUN 演示：温度爬升→降载→自适应→新错误→可疑级→深测→裁决 ===")
    f.run(max_seconds=75)
    log("=== DRY-RUN 结束，最终状态 ===")
    print(json.dumps(f.health.snapshot(), ensure_ascii=False, indent=2))
    print("可疑级标记:", json.dumps(f.pool.data["levels"]["suspicious"]["cores"], ensure_ascii=False))
    print("深测调用数:", len(sim.calls), "样例:", sim.calls[:6])


def main():
    ap = argparse.ArgumentParser(description="FARRON 在线 SDC 健康管理系统")
    ap.add_argument("--selftest", action="store_true", help="温度控制器规格自检")
    ap.add_argument("--dry-run", action="store_true", help="模拟全状态机演示")
    ap.add_argument("--status", action="store_true", help="查看状态文件")
    ap.add_argument("--duration", type=int, default=None, help="运行秒数（默认无限）")
    args = ap.parse_args()

    if args.selftest:
        sys.exit(selftest())
    if args.dry_run:
        dry_run()
        return
    if args.status:
        if os.path.exists(STATE_JSON):
            print(open(STATE_JSON).read())
        else:
            print("尚无状态文件")
        return

    cfg = load_config()
    if not check_binary(cfg):
        sys.exit(1)
    f = Farron(cfg)

    def sigterm(signum, frame):
        f.stop.set()

    signal.signal(signal.SIGTERM, sigterm)
    signal.signal(signal.SIGINT, sigterm)
    f.run(max_seconds=args.duration)


if __name__ == "__main__":
    main()
