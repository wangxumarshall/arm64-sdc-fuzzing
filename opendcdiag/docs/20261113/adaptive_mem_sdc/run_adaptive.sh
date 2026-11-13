#!/bin/bash
# adaptive_mem_sdc 首役 —— CPU3+CPU4 (96-189), 风扇AUTO (2026-11-13, 用户批准的 v2 设计)
# 设计: docs/ADAPTIVE_MEM_SDC_DESIGN_20261113.md (v2.1); 计划: docs/superpowers/plans/2026-11-13-adaptive-mem-sdc.md
# 协议:
#   阶段1 verify: 179下线, 30组合轮扫验证golden, 60s, 须 0fail!!! (两法交叉) 且 30/30 覆盖
#   阶段2 正式:  179上线, 墙钟组合扫描 30min/组合 × 30 = 最坏 15h (-T 16h 兜底), auto seed
#                看门狗轮询 run.log: 首个 result:fail 块 → 提取组合标签 → SIGKILL+pgrep 验证
#                (框架 fail 不停进程, 脚本负责即停即报)
# 监控钉0-7; 温度看门狗98°C×2; env logger 全程; 频率: governor 存在则 best-effort performance.
# PHASE1_ONLY=1 环境变量: 只跑阶段1 (门/复检用).
set -u
O=/home/sdc/root/arm64-sdc-fuzzing/opendcdiag
BIN=$O/builddir/opendcdiag
NAME=adaptive_mem_sdc
RR=/home/sdc/adaptive_mem_sdc
mkdir -p "$RR"
BINFP=$(sha256sum $BIN | cut -c1-12)
[ "$BINFP" = "4a4d12c8e5d3" ] || { echo "ABORT: 指纹 $BINFP ≠ 4a4d12c8e5d3" > $RR/ABORT; exit 1; }
online(){ echo 1 | sudo tee /sys/devices/system/cpu/cpu$1/online >/dev/null; }
offline(){ echo 0 | sudo tee /sys/devices/system/cpu/cpu$1/online >/dev/null; }
KEY=$(date +%s)_$$

# 频率最高环境 (可移植分支): governor 存在则 performance (本机无 DVFS 恒2.6GHz, 路径不存在自动跳过)
if [ -e /sys/devices/system/cpu/cpu0/cpufreq/scaling_governor ]; then
  echo performance | sudo tee /sys/devices/system/cpu/cpu0/cpufreq/scaling_governor >/dev/null 2>&1 || true
  echo "[$(date '+%F %T')] governor=performance (best-effort)" >> "$RR/monitor.log"
fi

# ---------------- 阶段1: verify (30组合 golden 自检) ----------------
P1=$RR/phase1; mkdir -p "$P1"
echo "[$(date '+%F %T')] == 阶段1 verify: 179下线, 30组合轮扫 60s, bin=$BINFP ==" >> "$P1/monitor.log"
pkill -f 'temp_monitor_5s[.]sh' 2>/dev/null || true
pkill -f 'sdc_env_logger[.]sh' 2>/dev/null || true
pkill -f 'farron/watchdog_cont[.]sh' 2>/dev/null || true
pgrep -x opendcdiag >/dev/null && { echo "smoke_abort" > "$P1/STATUS"; echo "[$(date '+%F %T')] 已有 opendcdiag 在跑, 作废" >> "$P1/monitor.log"; exit 1; }
online 178; online 179; offline 190; offline 191; offline 179; sleep 2
s179=$(cat /sys/devices/system/cpu/cpu179/online); s190=$(cat /sys/devices/system/cpu/cpu190/online); s191=$(cat /sys/devices/system/cpu/cpu191/online)
echo "[$(date '+%F %T')] 核心配置: 179=$s179(冒烟下线) 190=$s190 191=$s191 | 在线核数=$(grep -c processor /proc/cpuinfo)" >> "$P1/monitor.log"
[ "$s179" = "0" ] && [ "$s190" = "0" ] && [ "$s191" = "0" ] || { echo "core_state_abort" > "$P1/STATUS"; exit 1; }
nohup taskset -c 0-7 bash $O/farron/temp_monitor_5s.sh "$P1/temp_all.log" 4500 >/dev/null 2>&1 & disown
setsid nohup taskset -c 0-7 bash $O/scripts/sdc_env_logger.sh "$P1" 6 >> "$P1/env_logger.out" 2>&1 < /dev/null & disown
ADAPTIVE_MEM_SDC_VERIFY=1 ADAPTIVE_MEM_SDC_KEY=${KEY}_p1 ADAPTIVE_MEM_SDC_COVFILE=$P1/covfile.txt \
  timeout 200 taskset -c 96-178,180-189 $BIN -e $NAME -n 93 -T 60s \
  --ignore-os-error --ignore-timeout -o "$P1/run.log" -q >/dev/null 2>&1
f1=$(grep -c 'result: fail' "$P1/run.log" 2>/dev/null); f1=${f1:-0}
mc1=$(grep -c 'miscompare' "$P1/run.log" 2>/dev/null); mc1=${mc1:-0}
cov1=$(awk '$4=="verify"{print $5}' "$P1/covfile.txt" 2>/dev/null | sort -u | wc -l); cov1=${cov1:-0}
echo "[$(date '+%F %T')] 阶段1 结果: fail=$f1 mc=$mc1 覆盖=$cov1/30" >> "$P1/monitor.log"
if [ "$f1" -ne 0 ] || [ "$mc1" -ne 0 ] || [ "$cov1" -ne 30 ]; then
  echo "[$(date '+%F %T')] 阶段1 不达标 (须 0fail!!! + 30/30), 作废" >> "$P1/monitor.log"
  echo verify_fail > "$P1/STATUS"; pkill -f 'farron/watchdog_cont[.]sh' 2>/dev/null; exit 1
fi
echo "[$(date '+%F %T')] 阶段1: 0 fail!!! (两法交叉) + 30/30 组合覆盖" >> "$P1/monitor.log"
echo done > "$P1/STATUS"
rm -f /dev/shm/adaptive_mem_sdc_${KEY}_p1
if [ "${PHASE1_ONLY:-0}" = "1" ]; then
  echo "[$(date '+%F %T')] PHASE1_ONLY=1, 到此为止" >> "$P1/monitor.log"
  exit 0
fi

# ---------------- 阶段2: 正式扫描 (墙钟组合, 30min/组合, SDC 即停) ----------------
P2=$RR/phase2; mkdir -p "$P2"
sleep 60
online 179; sleep 2
# 清阶段1监控栈 (温度/env logger 换到 P2 落盘)
pkill -f 'temp_monitor_5s[.]sh' 2>/dev/null || true
pkill -f 'sdc_env_logger[.]sh' 2>/dev/null || true
echo "[$(date '+%F %T')] == 阶段2 正式: 179上线, 96-189 (-n 94) 墙钟扫描 30min/组合, -T 16h ==" >> "$P2/monitor.log"
nohup taskset -c 0-7 bash $O/farron/temp_monitor_5s.sh "$P2/temp_all.log" 4500 >/dev/null 2>&1 & disown
nohup taskset -c 0-7 bash $O/farron/watchdog_cont.sh "$P2/temp_all.log" >/dev/null 2>&1 & disown
setsid nohup taskset -c 0-7 bash $O/scripts/sdc_env_logger.sh "$P2" 75 >> "$P2/env_logger.out" 2>&1 < /dev/null & disown

ADAPTIVE_MEM_SDC_KEY=${KEY}_p2 ADAPTIVE_MEM_SDC_COVFILE=$P2/covfile.txt \
  taskset -c 96-189 $BIN -e $NAME -n 94 -T 16h \
  --ignore-os-error --ignore-timeout -o "$P2/run.log" -q >/dev/null 2>&1 &
MAINPID=$!
echo "[$(date '+%F %T')] 主进程 pid=$MAINPID 启动, 看门狗进入轮询 (10s/次)" >> "$P2/monitor.log"

# 看门狗: 首个 fail 块 → SIGKILL (铁律) + 组合标签提取 + 总结
while kill -0 $MAINPID 2>/dev/null; do
  if grep -q 'result: fail' "$P2/run.log" 2>/dev/null; then
    TAG=$(grep -m1 -oE 'combo#[0-9]+ \[[^]]+\]' "$P2/run.log" | head -1)
    echo "[$(date '+%F %T')] !!! SDC 检出: $TAG" >> "$P2/monitor.log"
    grep -m1 -B2 -A2 'combo#' "$P2/run.log" >> "$P2/monitor.log" 2>/dev/null
    kill -9 $MAINPID 2>/dev/null
    sleep 2
    if pgrep -x opendcdiag >/dev/null; then
      pkill -9 -x opendcdiag 2>/dev/null; sleep 1
    fi
    pgrep -x opendcdiag >/dev/null && echo "[$(date '+%F %T')] ⚠ SIGKILL 后仍有残留!" >> "$P2/monitor.log"
    echo "[$(date '+%F %T')] SDC_CAUGHT | $TAG | fail块=$(grep -c 'result: fail' "$P2/run.log") miscompare=$(grep -c 'miscompare' "$P2/run.log")" >> "$RR/series_summary.txt"
    echo sdc_caught > "$P2/STATUS"
    pkill -f 'farron/watchdog_cont[.]sh' 2>/dev/null || true
    exit 0
  fi
  sleep 10
done

# -T 自然到期 / 全扫完退出
wait $MAINPID 2>/dev/null
f=$(grep -c 'result: fail' "$P2/run.log" 2>/dev/null); f=${f:-0}
mc=$(grep -c 'miscompare' "$P2/run.log" 2>/dev/null); mc=${mc:-0}
covn=$(awk '$4=="normal"{print $5}' "$P2/covfile.txt" 2>/dev/null | sort -u | wc -l); covn=${covn:-0}
lastc=$(awk '$4=="normal"{print $5}' "$P2/covfile.txt" 2>/dev/null | tail -1)
tmax=$(grep -oE 'CPU[1-4]_TEMP=[0-9]+' "$P2/temp_all.log" 2>/dev/null | awk -F= '{if($2>m[$1])m[$1]=$2} END{printf "CPU1=%s CPU2=%s CPU3=%s CPU4=%s", m["CPU1_TEMP"],m["CPU2_TEMP"],m["CPU3_TEMP"],m["CPU4_TEMP"]}')
echo "[$(date '+%F %T')] 阶段2 结束: fails=$f mc=$mc 覆盖组合数=$covn 末组合=$lastc | Tmax: $tmax" >> "$P2/monitor.log"
if [ "$f" -eq 0 ]; then
  echo "[$(date '+%F %T')] ADAPTIVE 全扫完: 0 fail!!! (miscompare=$mc) — 30 组合均无效或触发窗口休眠" >> "$P2/monitor.log"
  echo "[$(date '+%F %T')] ALL_DONE | 全扫 0!!! | mc=$mc | cov=$covn | Tmax: $tmax" >> "$RR/series_summary.txt"
else
  echo "[$(date '+%F %T')] ALL_DONE | fails=$f (未即停异常, 人工检查) | mc=$mc | Tmax: $tmax" >> "$RR/series_summary.txt"
fi
echo done > "$P2/STATUS"
pkill -f 'farron/watchdog_cont[.]sh' 2>/dev/null || true
rm -f /dev/shm/adaptive_mem_sdc_${KEY}_p2
