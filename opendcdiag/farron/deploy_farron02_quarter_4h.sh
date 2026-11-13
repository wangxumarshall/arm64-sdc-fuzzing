#!/bin/bash
# FARRON-02 四分之一插槽变体 4h 验收 (2026-11-01 用户指令):
#   每30min一窗 × 每窗30s × 12核(=插槽48核的1/4, 连续序号)
#   日志锁定单核故障 → 优先测故障核所在四分之一(179 → [168-179])
#   其余同上次 4h: stress-ng 全核192 worker 在线应用 + 三采样 + 看门狗
# 相对上次的两处 v1.2 修正: 优先组不丢窗(凉检等待后必跑) / 用例按 --list 过滤(无空转窗)
set -u
REPO="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO"
OUT="$REPO/farron/state/sweep/farron02_quarter_4h"
DUR=14400
SAMPLER=$((DUR+900))
mkdir -p "$OUT" farron/state/sweep
log(){ echo "[$(date '+%F %T')] $*" | tee -a "$OUT/deploy.log"; }
fail(){ log "!! 部署中止: $*"; exit 1; }

log "=== FARRON-02(1/4插槽变体) 4h 部署开始 ==="

# 0) 残留负载
pgrep -x opendcdiag >/dev/null && fail "opendcdiag 已在运行"
ps aux | grep [s]tress-ng | grep -v grep | grep -q stress && fail "stress-ng 已在运行"
pgrep -f "farron02\.py" >/dev/null && fail "farron02 已在运行"
pgrep -f "python3.*farron\.py" >/dev/null && fail "farron v1 已在运行"

# 1) 前提核验
[ "$(cat /sys/devices/system/cpu/cpu179/online 2>/dev/null)" = "1" ] || fail "cpu179 offline"
SHA=$(sha256sum builddir/opendcdiag | cut -c1-16)
[ "$SHA" = "a05c17631da3e1a2" ] || fail "二进制指纹 $SHA ≠ a05c17631da3e1a2"

# 2) 自检 + 桩 + 评估通道 (硬门)
python3 farron/farron02.py --selftest >/dev/null 2>&1 || fail "selftest 未通过"
log "selftest 通过"
timeout 150 python3 farron/farron02.py --stub-run --config farron/config02_quarter.json > "$OUT/stub_console.log" 2>&1 \
  || fail "stub-run 未通过(见 $OUT/stub_console.log)"
grep -q "裁决-屏蔽" "$OUT/stub_console.log" || fail "stub-run 未走到裁决"
log "stub-run 全流程通过"
python3 farron/farron02.py --assess-only > "$OUT/assess_precheck.txt" 2>&1 \
  || fail "assess-only 失败"
grep -q "模式 = priority" "$OUT/assess_precheck.txt" \
  && log "assess-only: priority 模式(预期)" \
  || log "⚠️ 预检非 priority(见 assess_precheck.txt), 以运行时判定为准"

# 3) 空闲基线 60s
read -r _ u1 n1 s1 i1 w1 q1 sq1 st1 _ < /proc/stat
sleep 60
read -r _ u2 n2 s2 i2 w2 q2 sq2 st2 _ < /proc/stat
B=$(( (u2+n2+s2+q2+sq2+st2)-(u1+n1+s1+q1+sq1+st1) ))
T=$(( (u2+n2+s2+i2+w2+q2+sq2+st2)-(u1+n1+s1+i1+w1+q1+sq1+st1) ))
[ "$T" -gt 0 ] || fail "基线采样异常"
PCT=$(awk "BEGIN{printf \"%.3f\", $B*100/$T}")
echo "idle_busy_pct=$PCT" > "$OUT/idle.txt"
log "空闲基线 busy=${PCT}%"

# 4) 应用: stress-ng 全核
nohup taskset -c 0-191 stress-ng --cpu 192 --timeout 5h -q > "$OUT/stress_ng.log" 2>&1 &
APP=$!
echo $APP > farron/state/sweep/app.pid
disown
sleep 8
NW=$(pgrep -f stress-ng | wc -l)
[ "$NW" -ge 190 ] || { pkill -x stress-ng-cpu; pkill -x stress-ng; fail "stress-ng 进程数异常: $NW"; }
log "stress-ng: pid=$APP 进程数=$NW (全核 192 worker, 5h 兜底)"

# 5) 三采样 + 看门狗 (钉 0-7: 远离一切 12 核窗)
nohup taskset -c 0-7 bash farron/cpu_total_sampler.sh "$OUT" $SAMPLER >/dev/null 2>&1 & disown
nohup taskset -c 0-7 bash farron/app_cpu_sampler.sh "$OUT" $SAMPLER >/dev/null 2>&1 & disown
nohup taskset -c 0-7 bash farron/temp_monitor_5s.sh "$OUT/temp_5s.log" $SAMPLER >/dev/null 2>&1 & disown
nohup taskset -c 0-7 bash farron/watchdog_cont.sh "$OUT/temp_5s.log" >/dev/null 2>&1 & disown
log "采样器 + 看门狗(98°C×2) 已启动(钉0-7)"

# 6) farron-02 4h, 四分之一配置 (脱离会话)
setsid nohup taskset -c 0-7 python3 farron/farron02.py --duration $DUR --outdir "$OUT" \
  --config farron/config02_quarter.json > "$OUT/farron02_console.log" 2>&1 < /dev/null &
FPID=$!
disown
log "farron-02(1/4插槽) 已启动(pid=$FPID, ${DUR}s) —— 结束约 $(date -d "+4 hour" '+%F %T')"
log "=== 部署完成 ==="
