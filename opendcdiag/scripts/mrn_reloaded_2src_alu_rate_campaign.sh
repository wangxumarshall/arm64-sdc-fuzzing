#!/bin/bash
# ============================================================================
# mrn_reloaded_2src_alu 单用例 SDC 触发率战役                          2026-09-30
#
# 测试对象: mrn_reloaded_2src_alu (二代构造类触发器, 与 top5 战役同口径单测)
# 登记册背景 (docs/CORE179_ALL_VALID_SDC_TESTCASES_20260923.md #30):
#   - 历史证据: 126 fail / 36min (~3.5/min), 首失败均值 15.3s
#   - fail 全锁核 179; 排除 179 同 seed 复算 0 fail (确定性核实)
#   - 二代最高率触发器; top-5 总排名第 3 (~8.2/min rowmajor > ~3.9 sub > ~3.5 本例)
#   - 历史测量在 09-01~04 时代, 无近期复测 —— 本脚本即为其当前率测量
#
# 运行口径 (与 top5_sdc_rate_campaign.sh / K-cells 战役完全一致):
#   - 全核 192 含 179, 显式 taskset -c 0-191 (防 shell 亲和掩码继承事故)
#   - auto seed, 绝不固定 -s (fixed-lcg-seed-methodology-error)
#   - 默认单格 30m, 可用 DURATION 环境变量覆盖 (例: DURATION=10m ./scripts/...)
#   - 日志全部落盘, 含监控日志, 不写 /tmp (panic 重启丢 /tmp 的教训)
#   - fail 计数 = 行首两空格 `  result: fail` 块数 (唯一 fail 块口径,
#     非 miscompare 关键词); 三法交叉: 块切分 / thread 字段 / cpu-mask X 位
#
# 监控 (long-test-monitor-pin-away-from-179 硬性要求):
#   - 本脚本自身与监控进程全部钉核 0, 绝不上 179; 主测试不额外绑核(全核压力)
#   - 每 60s 采样: 当前格 / 进程存活与亲和 / 当前累计 fail / 温度 / load
#
# 输出: builddir/campaign_mrn_reloaded2src_<ts>/
#   env.txt        环境指纹 (二进制 sha256 / git / 在线核 / 进程快照)
#   monitor.log    监控采样 (落盘)
#   runs/<t>.log   完整 -o 日志;  runs/<t>.stderr
#   results.csv    机器可读结果
#   summary.md     分析块 + 实测率总表
#
# 用法: ./scripts/mrn_reloaded_2src_alu_rate_campaign.sh
#       DURATION=10m ./scripts/mrn_reloaded_2src_alu_rate_campaign.sh
# ============================================================================
set -u
cd "$(dirname "$0")/.."

BIN=builddir/opendcdiag
DURATION=${DURATION:-30m}
TARGET_CORE=179        # SDC 缺陷核
PIN_CORE=0             # 脚本/监控钉此核 (非 179)
NCORES_EXPECTED=192

TESTS=(
  mrn_reloaded_2src_alu
)
REF_RATE=(
  "~3.5/min(126/36m,首失败均值15.3s)"
)

TS=$(date +%Y%m%d_%H%M%S)
OUTDIR="builddir/campaign_mrn_reloaded2src_$TS"
mkdir -p "$OUTDIR/runs"

log() { echo "[$(date '+%F %T')] $*" | tee -a "$OUTDIR/campaign.log"; }

# 本脚本自身钉核 0: 之后所有子进程(监控/python)默认继承, 绝不碰 179;
# 主测试由 run_cell 里显式 taskset -c 0-191 覆盖为全核掩码, 不受影响
taskset -pc "$PIN_CORE" $$ > /dev/null 2>&1 || { log "FATAL: 无法将脚本钉到核 $PIN_CORE"; exit 1; }

# ---------------- 预检 ----------------
dur_to_sec() {
  # 坑: local 的多赋值必须拆行 —— bash 先展开本行全部参数再执行赋值,
  # 同行 ${d%...} 引用的是尚未赋值的 d, set -u 下报 unbound variable
  local d=$1
  local n=${d%[smh]} u=${d: -1}
  case $u in s) echo $((n)) ;; m) echo $((n*60)) ;; h) echo $((n*3600)) ;; *) echo -1 ;; esac
}
# 先格式校验, 保证 dur_to_sec 只见干净输入 (否则 "10sm" 之类会掉进算术展开噪音)
[[ "$DURATION" =~ ^[0-9]+[smh]$ ]] || { log "FATAL: DURATION='$DURATION' 非法 (须如 90s/10m/1h)"; exit 1; }
NOMINAL_SEC=$(dur_to_sec "$DURATION")

[ "$NOMINAL_SEC" -gt 0 ] || { log "FATAL: DURATION='$DURATION' 解析为 '${NOMINAL_SEC:-空}', 非法"; exit 1; }
[ -x "$BIN" ] || { log "FATAL: $BIN 不存在, 先构建: meson setup builddir --buildtype=release && ninja -C builddir"; exit 1; }

# 测试名必须在二进制里 (防 meson 未注册 / 二进制过期)
strings "$BIN" > "$OUTDIR/.bin_strings.tmp" 2>/dev/null || true
for t in "${TESTS[@]}"; do
  grep -qx "$t" "$OUTDIR/.bin_strings.tmp" || { log "FATAL: '$t' 不在 $BIN 中 (二进制过期或未注册, 先 ninja -C builddir)"; exit 1; }
  src="tests/cpu/misc/$t.cpp"
  [ -f "$src" ] && [ "$src" -nt "$BIN" ] && log "WARN: $src 比 $BIN 新, 建议先 ninja -C builddir 再跑"
done
rm -f "$OUTDIR/.bin_strings.tmp"

# 注意: 不能用 nproc —— 它按当前进程亲和掩码计数, 本脚本已自钉核0 会得 1;
# 用 /proc/cpuinfo 数在线核(只算 online, 与亲和无关)
NPROC_NOW=$(grep -c '^processor' /proc/cpuinfo)
[ "$NPROC_NOW" -eq "$NCORES_EXPECTED" ] || { log "FATAL: 在线核数=$NPROC_NOW != $NCORES_EXPECTED (online: $(cat /sys/devices/system/cpu/online))"; exit 1; }
C179=$(cat /sys/devices/system/cpu/cpu$TARGET_CORE/online 2>/dev/null || echo 1)
[ "$C179" = "1" ] || { log "FATAL: cpu$TARGET_CORE 离线, SDC 不会触发, 先热插拔上线再跑"; exit 1; }

AVAIL_KB=$(df -Pk . | awk 'NR==2{print $4}')
AVAIL_KB=${AVAIL_KB:-0}
[ "$AVAIL_KB" -gt $((10*1024*1024)) ] || log "WARN: 磁盘剩余仅 $((AVAIL_KB/1024/1024))GB (<10GB)"

pgrep -x opendcdiag > /dev/null 2>&1 && { log "FATAL: 已有 opendcdiag 实例在运行, 先结束它"; exit 1; }

# 环境指纹 (可追溯性: 结论只认可有持久日志的 run)
BINSHA=$(sha256sum "$BIN" 2>/dev/null | cut -d' ' -f1)
{
  echo "date_utc:      $(date -u '+%F %T')Z   local: $(date '+%F %T')"
  echo "host:          $(hostname)   kernel: $(uname -r)   arch: $(uname -m)"
  echo "online_cpus:   $NPROC_NOW (from /proc/cpuinfo)   cpu_online: $(cat /sys/devices/system/cpu/online)"
  echo "cpu179:        online=$(cat /sys/devices/system/cpu/cpu179/online 2>/dev/null || echo '?')"
  echo "binary:        $BIN  mtime: $(stat -c %y "$BIN" 2>/dev/null)"
  echo "binary_sha256: $BINSHA"
  echo "git:           $(git rev-parse HEAD 2>/dev/null)  dirty_files=$(git status --porcelain 2>/dev/null | wc -l)"
  echo "cells:         ${#TESTS[@]}  duration_each: $DURATION (nominal ${NOMINAL_SEC}s)"
  echo "script_pin:    core $PIN_CORE (自身+监控)   main_test_mask: 0-191 全核含 $TARGET_CORE"
  echo "uptime:        $(uptime)"
  echo
  echo "== top-10 cpu processes at start =="
  ps aux --sort=-%cpu | head -11
} > "$OUTDIR/env.txt" 2>&1

{
  echo "# mrn_reloaded_2src_alu 单用例 SDC 触发率战役 $TS"
  echo
  echo "- 口径: 全核192含179 / taskset -c 0-191 / auto seed(无 -s) / 单格 $DURATION / 日志落盘"
  echo "- fail 计数: 行首两空格 \`  result: fail\` 块数; 三法交叉 = 块切分 / thread 字段 / cpu-mask X 位(剥':'取下标)"
  echo "- 对象: 登记册 #30 (二代), 历史证据 126/36min (~3.5/min), 无近期复测, 本 run 为当前率测量"
  echo "- 环境: kernel $(uname -r) / binary sha256 ${BINSHA:0:12} / git $(git rev-parse --short HEAD 2>/dev/null)"
  echo
} > "$OUTDIR/summary.md"
echo "rank,test,rc,wall_min,fails,unique_fail_seeds,fail_threads,mask_cores,iterations,fail_per_min,fail_per_kilo_iter,registry_ref" > "$OUTDIR/results.csv"

# ---------------- 监控 (钉核0, 60s 采样, 落盘) ----------------
MONLOG="$OUTDIR/monitor.log"; CURCELL="$OUTDIR/.current_cell"; CURLOG="$OUTDIR/.current_log"
: > "$MONLOG"; echo "-" > "$CURCELL"; : > "$CURLOG"
(
  while true; do
    ts=$(date '+%F %T')
    alive=$(pgrep -c -x opendcdiag 2>/dev/null || true); alive=${alive:-0}
    cur=$(cat "$CURCELL" 2>/dev/null || echo "-")
    cf=$(cat "$CURLOG" 2>/dev/null || true)
    fails=0
    if [ -n "$cf" ] && [ -f "$cf" ]; then fails=$(grep -c '^  result: fail' "$cf" 2>/dev/null || true); fi
    fails=${fails:-0}
    mask=""
    if [ "$alive" != "0" ]; then
      pid=$(pgrep -x opendcdiag | head -1)
      [ -n "$pid" ] && mask=$(awk '/^Cpus_allowed_list/{print $2}' /proc/$pid/status 2>/dev/null)
    fi
    temp=$(timeout 5 ipmitool sdr type temperature 2>/dev/null | grep -oE '[0-9]+ degrees C' | head -1 || true)
    echo "$ts cell=$cur alive=$alive mask=${mask:--} fails_so_far=$fails temp=${temp:-n/a} load=$(cut -d' ' -f1 /proc/loadavg)" >> "$MONLOG"
    sleep 60
  done
) &
MONPID=$!
trap 'kill "$MONPID" 2>/dev/null; wait "$MONPID" 2>/dev/null' EXIT
trap 'log "被中断, 清理监控后退出"; exit 130' INT TERM

# ---------------- 单格执行 ----------------
run_cell() {
  local rank=$1 name=$2 ref=$3
  local logf="$OUTDIR/runs/$name.log"
  echo "$name" > "$CURCELL"; echo "$logf" > "$CURLOG"
  echo "[$(date '+%F %T')] START rank=$rank $name (ref $ref, nominal ${NOMINAL_SEC}s)" >> "$MONLOG"
  log "START rank=$rank/${#TESTS[@]} $name  登记册参考率=$ref  预计结束 $(date -d "+$NOMINAL_SEC seconds" '+%T')"

  local t0 t1 rc wall
  t0=$(date +%s)
  taskset -c 0-191 "$BIN" -e "$name" -T "$DURATION" -n 192 \
    --ignore-os-error --ignore-timeout -o "$logf" -q \
    > /dev/null 2> "$OUTDIR/runs/$name.stderr"
  rc=$?
  t1=$(date +%s)
  wall=$((t1 - t0))
  echo "-" > "$CURCELL"; : > "$CURLOG"
  echo "[$(date '+%F %T')] END rank=$rank $name rc=$rc wall=${wall}s" >> "$MONLOG"
  log "END rank=$rank $name rc=$rc wall=${wall}s"

  # 分析立即落盘 (钉核0; 若后续 panic, 已完成格的数据已持久化)
  python3 - "$name" "$logf" "$wall" "$rank" "$ref" "$rc" "$OUTDIR" "$NOMINAL_SEC" <<'PYEOF'
import re, sys
from collections import Counter

name, logf, wall_s, rank, ref, rc, outdir, nominal = sys.argv[1:9]
wall_s, nominal = int(wall_s), int(nominal)
try:
    text = open(logf, errors='replace').read()
except OSError:
    text = ''

blocks = text.split('- test:')
fb = [b for b in blocks if 'result: fail' in b]           # 交叉口径: 块切分
raw = len(re.findall(r'^  result: fail', text, re.M))     # 主口径: 行首两空格

seeds, threads, maskcores, ttfs = set(), Counter(), Counter(), []
for b in fb:
    m = re.search(r"seed: '([^']+)'", b)
    seeds.add(m.group(1) if m else '?')
    t = re.search(r'^  - thread: (\d+)', b, re.M)
    threads[t.group(1) if t else '?'] += 1
    cm = re.search(r"cpu-mask: '([^']+)'", b)
    if cm:
        # 必须剥 ':' (192 位分 4 组), 否则核号算错 (kcells 教训)
        for i, c in enumerate(cm.group(1).replace(':', '')):
            if c == 'X':
                maskcores[i] += 1
    tf = re.search(r'time-to-fail: ([0-9.]+)', b)
    if tf:
        ttfs.append(float(tf.group(1)))

it = re.findall(r'# Loop iteration (\d+) finished', text)
iters = max(map(int, it)) if it else 0

wall_min = wall_s / 60.0
fails = raw
rate = fails / wall_min if wall_min > 0 else 0.0
kiter = f"{fails / (iters / 1000.0):.2f}" if iters else "n/a"
thr = ' '.join(f'{k}x{v}' for k, v in sorted(threads.items())) or '-'
msk = ' '.join(f'{k}x{v}' for k, v in sorted(maskcores.items())) or '-'
ttf = f"min={min(ttfs):.1f}s mean={sum(ttfs)/len(ttfs):.1f}s max={max(ttfs):.1f}s" if ttfs else "n/a"
xchk = "一致" if raw == len(fb) else f"⚠️不一致 raw={raw} blocks={len(fb)}"
trunc = "" if wall_s >= nominal * 9 // 10 else " ⚠️TRUNCATED(实跑<90%名义)"
nolog = "" if text.strip() else " ⚠️日志缺失或为空"

block = f"""## rank{rank} {name}
- 登记册参考率: {ref}
- 运行: rc={rc}  实跑 {wall_min:.1f} min (名义 {nominal//60} min){trunc}{nolog}
- fail 块数 (主口径 `  result: fail`): **{fails}**   块切分交叉核对: {xchk}
- 唯一 fail seed 数: {len(seeds)}
- thread 分布: {thr}
- cpu-mask X 位分布: {msk}
- 迭代数: {iters}   **fail/min: {rate:.3f}**   fail/千迭代: {kiter}
- time-to-fail: {ttf}
"""
with open(f"{outdir}/summary.md", "a") as f:
    f.write(block + "\n")
with open(f"{outdir}/results.csv", "a") as f:
    f.write(f"{rank},{name},{rc},{wall_min:.1f},{fails},{len(seeds)},{thr},{msk},{iters},"
            f"{rate:.4f},{kiter},{ref.replace(',', ';').replace('，', ';')}\n")
print(block)
PYEOF

  # 截断保护: 单格战役, 格提前退出 = 系统性问题(参数/二进制/panic), 中止并保留已落盘分析
  if [ "$wall" -lt $((NOMINAL_SEC / 2)) ]; then
    log "FATAL: $name 仅 ${wall}s (<50% 名义 ${NOMINAL_SEC}s), 中止; 检查 $BIN 与参数 (stderr: $OUTDIR/runs/$name.stderr)"
    exit 1
  fi
}

# ---------------- 主流程 ----------------
log "预检通过: 在线核=$NPROC_NOW cpu$TARGET_CORE=online 每格=$DURATION 共${#TESTS[@]}格 预计总时长~$(( ${#TESTS[@]} * NOMINAL_SEC / 60 ))min 预计结束 $(date -d "+$(( ${#TESTS[@]} * NOMINAL_SEC )) seconds" '+%F %T')"
log "输出目录: $OUTDIR"

for i in "${!TESTS[@]}"; do
  run_cell $((i+1)) "${TESTS[$i]}" "${REF_RATE[$i]}"
done

# ---------------- 实测率总表 ----------------
python3 - "$OUTDIR" <<'PYEOF'
import csv, sys
outdir = sys.argv[1]
rows = list(csv.reader(open(f"{outdir}/results.csv")))
hdr, data = rows[0], rows[1:]

def fnum(x):
    try:
        return float(x)
    except ValueError:
        return -1.0

data.sort(key=lambda r: fnum(r[9]), reverse=True)
lines = ["", "## 实测率总表", "",
         "| 实测排名 | 测试 | 实跑min | fail块 | fail/min | fail/千迭代 | 登记册参考率 |",
         "|---|---|---|---|---|---|---|"]
tot_f, tot_w = 0, 0.0
for pos, r in enumerate(data, 1):
    tot_f += int(r[4])
    tot_w += float(r[3])
    lines.append(f"| {pos} | {r[1]} | {r[3]} | {r[4]} | {r[9]} | {r[10]} | {r[11]} |")
overall = tot_f / tot_w if tot_w else 0.0
lines += ["", f"合计: {tot_f} fail / {tot_w:.1f} min = {overall:.3f} fail/min", "",
          "注: fail 块 = 行首两空格 `  result: fail`; 跨日率差异不做因果解读",
          "(见 docs/CORE179_VALID7_RERUN_REVERSED_ORDER_20260915.md 教训)。"]
out = "\n".join(lines)
with open(f"{outdir}/summary.md", "a") as f:
    f.write(out + "\n")
print(out)
PYEOF

rm -f "$CURCELL" "$CURLOG"
echo "[$(date '+%F %T')] CAMPAIGN COMPLETE" >> "$MONLOG"
log "战役完成: 总表见 $OUTDIR/summary.md, 机器可读结果见 $OUTDIR/results.csv"
