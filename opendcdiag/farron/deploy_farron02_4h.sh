#!/bin/bash
# FARRON-02 4h 验收部署 (2026-10-31): stress-ng 全核(192 worker) + farron-02 4h
# 验收目标(用户): 统计找到故障核心的速度 + 给在线负载造成的延迟和吞吐影响
# 流水线: 残留检查 → selftest 硬门 → stub-run 硬门 → 真实 assess-only 通道核验
#         → 空闲基线 60s → stress-ng 全核 → 三采样器+看门狗 → farron-02 4h(setsid 脱离)
# 采样器/守护钉 184-187 (组46): 优先模式只测组43-45、例行 4h 只轮到组7, 均不冲突
set -u
REPO="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO"
OUT="$REPO/farron/state/sweep/farron02_4h"
DUR=14400            # 4h
SAMPLER=$((DUR+900)) # 采样余量
mkdir -p "$OUT" farron/state/sweep
log(){ echo "[$(date '+%F %T')] $*" | tee -a "$OUT/deploy.log"; }
fail(){ log "!! 部署中止: $*"; exit 1; }

log "=== FARRON-02 4h 验收部署开始 ==="

# 0) 残留负载(与 FARRON/实验互斥铁律)
pgrep -x opendcdiag >/dev/null && fail "opendcdiag 已在运行"
pgrep -f "stress-ng" >/dev/null && fail "stress-ng 已在运行"
pgrep -f "farron02\.py" >/dev/null && fail "farron02 已在运行"
pgrep -f "python3.*farron\.py" >/dev/null && fail "farron v1 已在运行"

# 1) 前提核验
[ "$(cat /sys/devices/system/cpu/cpu179/online 2>/dev/null)" = "1" ] || fail "cpu179 offline"
SHA=$(sha256sum builddir/opendcdiag | cut -c1-16)
[ "$SHA" = "a05c17631da3e1a2" ] || fail "二进制指纹 $SHA ≠ a05c17631da3e1a2 (-O3 基线)"

# 2) 逻辑自检 + 桩全流程 (硬门)
python3 farron/farron02.py --selftest >/dev/null 2>&1 || fail "selftest 未通过"
log "selftest 通过(19 项)"
timeout 150 python3 farron/farron02.py --stub-run > "$OUT/stub_console.log" 2>&1 \
  || fail "stub-run 未通过(见 $OUT/stub_console.log)"
grep -q "裁决-屏蔽" "$OUT/stub_console.log" || fail "stub-run 未走到裁决"
log "stub-run 全流程通过(评估→优先→检出→整槽深测→裁决)"

# 3) 真实日志分级(第一步预演 + SEL/journal/last 通道核验)
python3 farron/farron02.py --assess-only > "$OUT/assess_precheck.txt" 2>&1 \
  || fail "assess-only 失败(SEL/journal/last 通道异常, 见 assess_precheck.txt)"
if grep -q "模式 = priority" "$OUT/assess_precheck.txt"; then
  log "assess-only: priority 模式(预期, 本机日志实况)"
else
  log "⚠️ 预检评估非 priority 模式(见 assess_precheck.txt) —— 继续部署, 以运行时判定为准"
fi

# 4) 空闲基线 60s (供 CPU 占比分解扣系统本底)
read -r _ u1 n1 s1 i1 w1 q1 sq1 st1 _ < /proc/stat
sleep 60
read -r _ u2 n2 s2 i2 w2 q2 sq2 st2 _ < /proc/stat
B=$(( (u2+n2+s2+q2+sq2+st2)-(u1+n1+s1+q1+sq1+st1) ))
T=$(( (u2+n2+s2+i2+w2+q2+sq2+st2)-(u1+n1+s1+i1+w1+q1+sq1+st1) ))
[ "$T" -gt 0 ] || fail "基线采样异常"
PCT=$(awk "BEGIN{printf \"%.3f\", $B*100/$T}")
echo "idle_busy_pct=$PCT" > "$OUT/idle.txt"
log "空闲基线 busy=${PCT}%"

# 5) 应用: stress-ng 全核(用户指令: 全核心)
nohup taskset -c 0-191 stress-ng --cpu 192 --timeout 5h -q > "$OUT/stress_ng.log" 2>&1 &
APP=$!
echo $APP > farron/state/sweep/app.pid
disown
sleep 8
NW=$(pgrep -f stress-ng | wc -l)
[ "$NW" -ge 190 ] || { pkill -f stress-ng; fail "stress-ng 进程数异常: $NW"; }
log "stress-ng: pid=$APP 进程数=$NW (全核 192 worker, 5h 超时兜底)"

# 6) 三采样器 + 看门狗 (钉 184-187)
nohup taskset -c 184 bash farron/cpu_total_sampler.sh "$OUT" $SAMPLER >/dev/null 2>&1 & disown
nohup taskset -c 185 bash farron/app_cpu_sampler.sh "$OUT" $SAMPLER >/dev/null 2>&1 & disown
nohup taskset -c 186 bash farron/temp_monitor_5s.sh "$OUT/temp_5s.log" $SAMPLER >/dev/null 2>&1 & disown
nohup taskset -c 187 bash farron/watchdog_cont.sh "$OUT/temp_5s.log" >/dev/null 2>&1 & disown
log "采样器(cpu_total/app_cpu 15s + temp/Power 5s) + 看门狗(98°C×2) 已启动"

# 7) farron-02 4h (脱离会话; 钉 185 与 app_cpu 采样器共核, 均轻量)
setsid nohup taskset -c 185 python3 farron/farron02.py --duration $DUR --outdir "$OUT" \
  > "$OUT/farron02_console.log" 2>&1 < /dev/null &
FPID=$!
disown
log "farron-02 已启动(pid=$FPID, ${DUR}s) —— 结束约 $(date -d "+4 hour" '+%F %T')"
log "=== 部署完成 ==="
