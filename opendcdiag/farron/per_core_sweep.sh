#!/bin/bash
# FARRON 逐核独占轮测 —— 校准/原型 (2026-10-25)
# 方案(用户规格): 逐核暂停应用(stress-ng)15s -> 活跃级测试 -> 无发现续基础级 -> 恢复
# 机制: taskset -apc 改应用全体线程亲和(摘除被测核 -> 应用线程即迁走 -> 测试独占该核 -> 恢复)
# 前提: 应用本身只跑可靠池(0-191 除 179), 179 为已知缺陷核(阳性对照)
#
# 用法:
#   per_core_sweep.sh gate  <app_pid> [窗口数=10] [窗口秒=15]   # Phase A: 179 门控校准
#   per_core_sweep.sh sweep <app_pid> [起始核=0] [结束核=191]   # Phase B: 全协议扫描
set -u
REPO="$(cd "$(dirname "$0")/.." && pwd)"
BIN="$REPO/builddir/opendcdiag"
OUT="$REPO/farron/state/sweep"
mkdir -p "$OUT"
ACTIVE_CASE="neon_rot_ldr_at_top_rowmajor"          # P0 #1 最强检测器
BASIC_CASES=(adcx cbw_arm tlbstress stress_sub mfence mrn_flags)  # 基础级轮换代表
APP_BASE_MASK="0-178,180-191"                        # 应用池(排除179)
SWEEP_LOG="$OUT/sweep.log"

mask_minus() {  # $1=N -> 应用掩码 = 0-191 减 {179, N}
  python3 -c "
n=$1
cs=[c for c in range(192) if c!=179 and c!=n]
out=[]; i=0
while i<len(cs):
    j=i
    while j+1<len(cs) and cs[j+1]==cs[j]+1: j+=1
    out.append(f'{cs[i]}-{cs[j]}' if j>i else str(cs[i]))
    i=j+1
print(','.join(out))"
}

run_test() {  # $1=core $2=case $3=dur秒 $4=tag -> echo fail数
  local core=$1 case=$2 dur=$3 tag=$4 n
  taskset -c "$core" "$BIN" -e "$case" -n 1 -T "${dur}s" \
    --ignore-os-error --ignore-timeout \
    -o "$OUT/${tag}.log" > "$OUT/${tag}.stdout" 2>&1
  n=$(grep -c 'result: fail' "$OUT/${tag}.log" 2>/dev/null)
  echo "${n:-0}"
}

fail_core_check() {  # $1=tag -> 确认失败块里的逻辑核
  grep -o 'logical: [0-9]*' "$OUT/${1}.stdout" 2>/dev/null | sort -u | tr '\n' ' '
}

pause_app()   {  # 摘除被测核: 对主进程+全部worker子进程逐个改亲和(stress-ng worker是fork子进程)
  for p in $APP_PID $(pgrep -P $APP_PID); do taskset -pc "$1" "$p" >/dev/null 2>&1; done
}
resume_app()  { pause_app "$APP_BASE_MASK"; }

CMD=$1; APP_PID=$2

case "$CMD" in
gate)
  NW=${3:-10}; WD=${4:-15}
  echo "=== Phase A: 179 门控校准 (应用=$APP_PID 于 $APP_BASE_MASK; $NW 窗 x ${WD}s + 3 窗 x 60s) ==="
  total=0
  for i in $(seq 1 "$NW"); do
    f=$(run_test 179 "$ACTIVE_CASE" "$WD" "gate179_${WD}s_$i")
    cores=$(fail_core_check "gate179_${WD}s_$i")
    total=$((total+f))
    echo "$(date '+%T') 窗口$i/${WD}s: ${f} fail (核: ${cores:-无})"
  done
  echo "--- ${WD}s 窗合计: $total ---"
  for i in 1 2 3; do
    f=$(run_test 179 "$ACTIVE_CASE" 60 "gate179_60s_$i")
    cores=$(fail_core_check "gate179_60s_$i")
    echo "$(date '+%T') 长窗$i/60s: ${f} fail (核: ${cores:-无})"
  done
  ;;
sweep)
  START=${3:-0}; END=${4:-191}
  echo "=== Phase B: 全协议扫描 核$START-$END (暂停->活跃15s->无发现续基础15s->恢复) 开始 $(date '+%F %T') ===" | tee -a "$SWEEP_LOG"
  bi=0
  for N in $(seq "$START" "$END"); do
    t0=$(date +%s)
    if [ "$N" -ne 179 ]; then pause_app "$(mask_minus "$N")"; fi
    af=$(run_test "$N" "$ACTIVE_CASE" 15 "c${N}_active")
    if [ "$af" -gt 0 ]; then
      cores=$(fail_core_check "c${N}_active")
      echo "$(date '+%T') 🚨 核$N 活跃级检出 ${af} fail (核: $cores) 用时$(( $(date +%s)-SWEEP_T0 ))s" | tee -a "$SWEEP_LOG"
    else
      bc=${BASIC_CASES[$((bi % ${#BASIC_CASES[@]}))]}; bi=$((bi+1))
      bf=$(run_test "$N" "$bc" 15 "c${N}_basic")
      if [ "$bf" -gt 0 ]; then
        cores=$(fail_core_check "c${N}_basic")
        echo "$(date '+%T') 🚨 核$N 基础级($bc)检出 ${bf} fail (核: $cores)" | tee -a "$SWEEP_LOG"
      else
        echo "$(date '+%T') 核$N: 活跃0 基础($bc)0 [+$(( $(date +%s)-t0 ))s]" >> "$SWEEP_LOG"
      fi
    fi
    if [ "$N" -ne 179 ]; then resume_app; fi
  done
  echo "=== Phase B 扫描结束 $(date '+%F %T') ===" | tee -a "$SWEEP_LOG"
  ;;
*)
  echo "用法: $0 gate|sweep <app_pid> [参数]"; exit 1;;
esac
