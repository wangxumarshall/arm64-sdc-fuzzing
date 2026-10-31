#!/bin/bash
# FARRON 生产节奏部署 (2026-10-26): 6h 无人值守, 含部署前 stub 自检
#   应用: stress-ng 191 worker 满载于可靠池 0-178,180-191 (排除已知缺陷核179; 179由FARRON在CPU4窗覆盖)
#   FARRON: 每30min一轮逐插槽独占扫描 (prod_sweep.sh, 与3h/5h评估同构口径)
#   采样: 全机CPU+应用CPU (15s) / 温度 (5s) / 98°C看门狗
# 用法: bash farron/deploy_prod6h.sh   (子进程 nohup+disown, 不依赖会话存活; 总耗时~5min含自检)
set -u
REPO="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO"
OUT="farron/state/sweep/prod6h"
SWEEP_S=21600      # 6h 扫描时长
PERIOD=1800        # 30min 一轮
DUR_S=22200        # 采样器/监控时长 = 6h + 10min 余量

mkdir -p "$OUT" farron/state/sweep
echo "=== FARRON 生产节奏部署开始 $(date '+%F %T') ==="
fail(){ echo "!! 部署中止: $*"; exit 1; }

# 0) 清理盯旧日志(eval3h)的残留看门狗
pkill -f "watchdog_cont.sh.*eval3h" 2>/dev/null && echo "旧看门狗(eval3h)已清理" || echo "无旧看门狗残留"

# 1) stub 自检 (~3.5min): 198s迷你run, 周期170s, 验证新循环逻辑(周期休眠/到点退出/窗口记账/检出路径)
echo "--- [1/5] prod_sweep stub 自检 ---"
STUB=stub_prod
timeout 400 bash farron/prod_sweep.sh 198 $STUB 170 > "$OUT/stub_console.log" 2>&1
SRC=$?
sleep 2
ROWS=$(( $(wc -l < "farron/state/sweep/$STUB/sweeps.csv" 2>/dev/null || echo 1) - 1 ))
[ $SRC -eq 0 ] || fail "stub 未正常退出(exit=$SRC), 详见 $OUT/stub_console.log"
[ "$ROWS" -ge 5 ] || fail "stub 窗口数不足($ROWS<5), 轮循环异常"
grep -q "休眠" "farron/state/sweep/$STUB/events.log" || fail "stub 未走到周期休眠分支"
grep -q "评估结束, 共 2 轮" "farron/state/sweep/$STUB/events.log" || fail "stub 轮数异常(预期2轮)"
STUB_F=$(awk -F, 'NR>1{s+=$4} END{print s+0}' "farron/state/sweep/$STUB/sweeps.csv")
echo "stub 通过: ${ROWS}窗, fail块${STUB_F}(CPU4检出路径已走通)"
pkill -f stress-ng 2>/dev/null && echo "stub 的 stress-ng 已清理" || true
sleep 3
rm -rf "farron/state/sweep/$STUB"

# 2) 空闲基线 60s (供最终 CPU 占比分解扣系统本底)
echo "--- [2/5] 空闲基线 60s ---"
read -r _ u1 n1 s1 i1 w1 q1 sq1 st1 _ < /proc/stat
sleep 60
read -r _ u2 n2 s2 i2 w2 q2 sq2 st2 _ < /proc/stat
B=$(( (u2+n2+s2+q2+sq2+st2)-(u1+n1+s1+q1+sq1+st1) ))
T=$(( (u2+n2+s2+i2+w2+q2+sq2+st2)-(u1+n1+s1+i1+w1+q1+sq1+st1) ))
[ "$T" -gt 0 ] || fail "基线采样异常"
PCT=$(awk "BEGIN{printf \"%.3f\", $B*100/$T}")
echo "idle_busy_pct=$PCT" > "$OUT/idle.txt"
echo "空闲基线busy率: ${PCT}%"

# 3) 应用: stress-ng 全机满载 (8h超时兜底覆盖6h+分析窗口)
echo "--- [3/5] 启动 stress-ng ---"
nohup taskset -c 0-178,180-191 stress-ng --cpu 191 --timeout 8h -q > "$OUT/stress_ng.log" 2>&1 &
echo $! > farron/state/sweep/app.pid
disown
sleep 8
NW=$(pgrep -f stress-ng | wc -l)
[ "$NW" -ge 190 ] || fail "stress-ng 进程数异常: $NW (预期192)"
echo "stress-ng: pid=$(cat farron/state/sweep/app.pid) 进程数=$NW (主+191worker)"

# 4) FARRON 生产节奏扫描 + 双采样器 (15s)
echo "--- [4/5] 启动 prod_sweep + CPU采样器 ---"
nohup bash farron/prod_sweep.sh $SWEEP_S prod6h $PERIOD > "$OUT/sweep_console.log" 2>&1 &
disown
nohup bash farron/cpu_total_sampler.sh "$OUT" $DUR_S > /dev/null 2>&1 & disown
nohup bash farron/app_cpu_sampler.sh "$OUT" $DUR_S > /dev/null 2>&1 & disown
echo "prod_sweep(6h, 周期${PERIOD}s, 预计~12轮) + CPU采样器 已启动"

# 5) 温度监控(5s) + 98°C看门狗
echo "--- [5/5] 温度监控 + 看门狗 ---"
nohup taskset -c 0 bash farron/temp_monitor_5s.sh "$OUT/temp_5s.log" $DUR_S > /dev/null 2>&1 & disown
nohup taskset -c 0 bash farron/watchdog_cont.sh "$OUT/temp_5s.log" > /dev/null 2>&1 & disown
echo "温度监控(5s)+看门狗(98°C x2连续)已启动"

echo "=== 部署完成 $(date '+%F %T') | 6h后结束: $(date -d "+6 hour" '+%F %T') ==="
