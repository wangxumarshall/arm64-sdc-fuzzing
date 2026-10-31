#!/bin/bash
# FARRON 生产节奏·时延版部署 (2026-10-27): 6h 无人值守, 含 stub 自检
#   应用: stress-ng 191 worker (可靠池, 排除179)
#   时延层: 每插槽1个唤醒延迟探针(钉核10/58/106/154, 随应用迁移) + 1个localhost ping探针
#   FARRON: 每30min一轮逐插槽独占扫描 (prod_sweep_lat.sh, 探针同步迁移)
#   采样: 全机CPU+应用CPU(15s) + 温度(5s) + 98°C看门狗
# 用法: bash farron/deploy_prod6h_lat.sh   (子进程 nohup+disown; 总耗时~6min含自检)
set -u
REPO="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO"
OUT="farron/state/sweep/prod6h_lat"
SWEEP_S=21600; PERIOD=1800; DUR_S=22200
PIDLIST="farron/state/sweep/probe_pids.txt"
PROBE_CORES=(10 58 106 154)          # CPU1/CPU2/CPU3/CPU4 各一, 避开179与核0

mkdir -p "$OUT" farron/state/sweep
echo "=== FARRON 时延版部署开始 $(date '+%F %T') ==="
fail(){ echo "!! 部署中止: $*"; exit 1; }

# 0) 残留清理(上次战役遗留)
pkill -f "watchdog_cont.sh.*prod6h" 2>/dev/null; pkill -f "prod_sweep" 2>/dev/null
pkill -f "stress-ng --cpu" 2>/dev/null; pkill -f "latency_probe" 2>/dev/null
sleep 2

# 1) stub 自检 (~4min): 临时stress-ng + 临时探针, 验证 prod_sweep_lat 新逻辑(探针迁移/恢复)
echo "--- [1/6] stub 自检 ---"
: > "$PIDLIST"
for i in 0 1 2 3; do
  S="CPU$((i+1))"
  nohup taskset -c "${PROBE_CORES[$i]}" python3 farron/latency_probe.py "$OUT/stub_probe_$S.csv" "$S" >/dev/null 2>&1 &
  echo "$! $S" >> "$PIDLIST"
  disown
done
timeout 400 bash farron/prod_sweep_lat.sh 198 stub_lat 170 > "$OUT/stub_console.log" 2>&1
SRC=$?
sleep 2
ROWS=$(( $(wc -l < "farron/state/sweep/stub_lat/sweeps.csv" 2>/dev/null || echo 1) - 1 ))
[ $SRC -eq 0 ] || fail "stub 未正常退出(exit=$SRC), 详见 $OUT/stub_console.log"
[ "$ROWS" -ge 5 ] || fail "stub 窗口数不足($ROWS<5)"
grep -q "休眠" "farron/state/sweep/stub_lat/events.log" || fail "stub 未走到周期休眠分支"
grep -q "评估结束, 共 2 轮" "farron/state/sweep/stub_lat/events.log" || fail "stub 轮数异常"
# 探针门禁: stub 恢复后探针亲和应回到本座钉核
while read -r pid home; do
  [ -z "$pid" ] && continue
  AFF=$(taskset -pc "$pid" 2>/dev/null | grep -o '[0-9,-]*$')
  case "$home" in
    CPU1) EXP="0-47";; CPU2) EXP="48-95";; CPU3) EXP="96-143";; CPU4) EXP="144-191";;
  esac
  [ "$AFF" = "$EXP" ] || fail "探针$home 迁移逻辑异常: 亲和=$AFF 预期=$EXP"
done < "$PIDLIST"
echo "stub 通过: ${ROWS}窗, 探针迁移/回家逻辑验证 OK"
# stub 清理
pkill -f "stress-ng --cpu" 2>/dev/null
while read -r pid home; do kill "$pid" 2>/dev/null; done < "$PIDLIST"
sleep 3
rm -rf farron/state/sweep/stub_lat

# 2) 空闲基线 60s
echo "--- [2/6] 空闲基线 60s ---"
read -r _ u1 n1 s1 i1 w1 q1 sq1 st1 _ < /proc/stat
sleep 60
read -r _ u2 n2 s2 i2 w2 q2 sq2 st2 _ < /proc/stat
B=$(( (u2+n2+s2+q2+sq2+st2)-(u1+n1+s1+q1+sq1+st1) ))
T=$(( (u2+n2+s2+i2+w2+q2+sq2+st2)-(u1+n1+s1+i1+w1+q1+sq1+st1) ))
[ "$T" -gt 0 ] || fail "基线采样异常"
PCT=$(awk "BEGIN{printf \"%.3f\", $B*100/$T}")
echo "idle_busy_pct=$PCT" > "$OUT/idle.txt"
echo "空闲基线busy率: ${PCT}%"

# 3) 应用 + 探针
echo "--- [3/6] 启动 stress-ng + 4唤醒探针 + ping探针 ---"
nohup taskset -c 0-178,180-191 stress-ng --cpu 191 --timeout 8h -q > "$OUT/stress_ng.log" 2>&1 &
echo $! > farron/state/sweep/app.pid
disown
sleep 8
NW=$(pgrep -f "stress-ng --cpu" | wc -l)
[ "$NW" -ge 190 ] || fail "stress-ng 进程数异常: $NW (预期192)"
echo "stress-ng: pid=$(cat farron/state/sweep/app.pid) 进程数=$NW"
: > "$PIDLIST"
for i in 0 1 2 3; do
  S="CPU$((i+1))"
  nohup taskset -c "${PROBE_CORES[$i]}" python3 farron/latency_probe.py "$OUT/probe_$S.csv" "$S" >/dev/null 2>&1 &
  echo "$! $S" >> "$PIDLIST"
  disown
done
sleep 3
NP=$(grep -c . "$PIDLIST")
echo "唤醒探针: ${NP}个 (钉核 ${PROBE_CORES[*]}, 本座被测时随应用迁出)"
nohup ping -i 0.2 -D 127.0.0.1 > "$OUT/ping.log" 2>&1 &
disown
echo "ping探针: localhost 0.2s间隔"

# 4) FARRON 时延版扫描 + 双采样器
echo "--- [4/6] 启动 prod_sweep_lat + 采样器 ---"
nohup bash farron/prod_sweep_lat.sh $SWEEP_S prod6h_lat $PERIOD > "$OUT/sweep_console.log" 2>&1 &
disown
nohup bash farron/cpu_total_sampler.sh "$OUT" $DUR_S > /dev/null 2>&1 & disown
nohup bash farron/app_cpu_sampler.sh "$OUT" $DUR_S > /dev/null 2>&1 & disown
echo "prod_sweep_lat(6h, 周期${PERIOD}s) + CPU采样器 已启动"

# 5) 温度监控 + 看门狗
echo "--- [5/6] 温度监控 + 看门狗 ---"
nohup taskset -c 0 bash farron/temp_monitor_5s.sh "$OUT/temp_5s.log" $DUR_S > /dev/null 2>&1 & disown
nohup taskset -c 0 bash farron/watchdog_cont.sh "$OUT/temp_5s.log" > /dev/null 2>&1 & disown
echo "温度监控(5s)+看门狗(98°C x2连续)已启动"

echo "=== [6/6] 部署完成 $(date '+%F %T') | 6h后结束: $(date -d "+6 hour" '+%F %T') ==="
