#!/bin/bash
# Fan-state A/B: AUTO vs 100% under identical CPU4-only rowmajor load
# (user directive 2026-10-30 evening; BMC fan authority re-invoked).
#   Arm 1: fan AUTO  -> neon_rot_ldr_at_top_rowmajor 15m (mask 144-191, -n 48)
#   Arm 2: fan 100%  -> same 15m
# Records per arm: CPU1-4 temps (30s), voltage+power+CPU util
# (scripts/sdc_env_logger.sh), run log.  Summary per arm: final value +
# last-5min averages (established steady-state protocol).
# Samplers pinned off the test mask (cores 8/9).  Watchdog 95C.
# Credentials via env BMC_HOST/BMC_USER/BMC_PASS (not stored on disk).
# Ends in manual 99999s + 100% (standing config).
set -u
R=/home/sdc/root/arm64-sdc-fuzzing/opendcdiag
D=$R/docs/20261030/fan_auto_vs_100
BIN=$R/builddir/opendcdiag
TEST=neon_rot_ldr_at_top_rowmajor
SSHOPT="-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o ConnectTimeout=8"

[ -n "${BMC_HOST:-}" ] && [ -n "${BMC_PASS:-}" ] || { echo "ABORT: BMC_HOST/BMC_PASS env missing"; exit 1; }
mkdir -p "$D"

bmc() { printf 'Y\n' | timeout 25 sshpass -p "$BMC_PASS" ssh $SSHOPT "${BMC_USER:-Administrator}@$BMC_HOST" "$@" 2>/dev/null; }
log() { echo "[$(date '+%F %T')] $*" | tee -a "$D/monitor.log"; }

if pgrep -x opendcdiag >/dev/null; then log "ABORT: opendcdiag already running"; exit 1; fi
[ "$(cat /sys/devices/system/cpu/cpu179/online 2>/dev/null)" = "1" ] || { log "ABORT: cpu179 offline"; exit 1; }
taskset -c 144-191 true 2>/dev/null || { log "ABORT: mask 144-191 unusable"; exit 1; }

temp_sampler() {   # $1=logfile — 30s cadence, watchdog 95C
    # NOTE: the background subshell MUST have its stdout/stderr redirected
    # away from the command-substitution pipe, or $(temp_sampler ...) never
    # returns (the infinite loop holds the pipe open — 2026-10-30 deadlock).
    (
      while true; do
        ts=$(date '+%F %T')
        t=$(timeout 12 sudo ipmitool sensor reading CPU1_TEMP CPU2_TEMP CPU3_TEMP CPU4_TEMP 2>/dev/null | grep -oE 'CPU[0-9]_TEMP[ |]+[0-9]+' | tr -s ' ' | tr '\n' ';')
        echo "$ts | $t" >> "$1"
        hot=$(echo "$t" | grep -oE '[0-9]+' | sort -rn | head -1)
        if [ -n "$hot" ] && [ "$hot" -gt 95 ]; then
            echo "$ts WATCHDOG ABORT: max CPU temp ${hot}C > 95C" >> "$1"
            touch "$D/ABORT"
            pkill -x opendcdiag 2>/dev/null
            exit 9
        fi
        sleep 30
      done
    ) > /dev/null 2>&1 &
    echo $!
}

summarize() {   # $1=arm dir -> "final_temp last5min_temp_avg last5min_v_avg last5min_power_avg"
    AD=$1
    t_final=$(awk -F'[ ;|]+' '$3=="CPU1_TEMP"{v=$10} END{print v}' "$AD/temp.log" 2>/dev/null)
    t_avg=$(tail -10 "$AD/temp.log" 2>/dev/null | awk -F'[ ;|]+' '$3=="CPU1_TEMP"{s+=$10;n++} END{if(n)printf "%.1f",s/n}')
    v_avg=$(tail -40 "$AD/env.log" 2>/dev/null | awk '{ if (match($0, /N_VDDAVS_CPU4 \| [0-9.]+/)) {x=substr($0,RSTART,RLENGTH); sub(/.*\| /,"",x); s+=x; n++} } END{if(n)printf "%.3f",s/n}')
    p_avg=$(tail -40 "$AD/env.log" 2>/dev/null | awk '{ if (match($0, /Power \| [0-9]+/)) {x=substr($0,RSTART,RLENGTH); sub(/.*\| /,"",x); s+=x; n++} } END{if(n)printf "%.0f",s/n}')
    echo "$t_final $t_avg $v_avg $p_avg"
}

run_arm() {
    label=$1
    AD=$D/$label
    mkdir -p "$AD"
    MONPID=$(temp_sampler "$AD/temp.log")
    taskset -pc 8 "$MONPID" >/dev/null 2>&1
    setsid nohup bash $R/scripts/sdc_env_logger.sh "$AD" 20 >> "$AD/env_logger.out" 2>&1 < /dev/null &
    start=$(date '+%F %T')
    taskset -c 144-191 "$BIN" -e "$TEST" -T 15m -n 48 --ignore-os-error --ignore-timeout -o "$AD/run.log" -q >/dev/null 2>&1
    rc=$?
    end=$(date '+%F %T')
    kill "$MONPID" 2>/dev/null
    sleep 35      # env logger 自止宽限
    read t_final t_avg v_avg p_avg <<< "$(summarize "$AD")"
    fails=$(grep -c 'result: fail' "$AD/run.log" 2>/dev/null); fails=${fails:-0}
    log "ARM[$label] rc=$rc fails=$fails | CPU4: final=${t_final}C last5min_avg=${t_avg}C | N_VDDAVS_CPU4(last5min)=${v_avg}V | Power(last5min)=${p_avg}W | ${start} -> ${end}"
}

log "EXPERIMENT START | bin=$(sha256sum "$BIN" | cut -c1-16) | test=$TEST mask=144-191 n=48 15m/arm | arm1=auto arm2=100%"

# ---- Arm 1: AUTO ----
if ! bmc ipmcget -d faninfo | grep -qi 'mode: *auto'; then
    log "设置风扇 AUTO"
    bmc ipmcset -d fanmode -v 0
    sleep 3
fi
run_arm auto
[ -f "$D/ABORT" ] && { log "EXPERIMENT ABORTED (watchdog)"; exit 9; }

# ---- Arm 2: 100% ----
log "设置风扇 manual 99999s + level 100"
bmc ipmcset -d fanmode -v 1 99999
bmc ipmcset -d fanlevel -v 100
sleep 5
run_arm full
[ -f "$D/ABORT" ] && { log "EXPERIMENT ABORTED (watchdog)"; exit 9; }
log "EXPERIMENT COMPLETE (风扇终态: manual 99999s + 100%)"
