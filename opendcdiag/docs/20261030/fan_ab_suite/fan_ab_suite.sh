#!/bin/bash
# Fan-state A/B suite across multiple high-rate test cases
# (user directive 2026-10-30 late evening: "多测机组对比试验——不同的高效
# 测试用例是否也有这种与节点功率正相关的特性").
# For each test: arm AUTO (15m) -> arm 100% (15m), CPU4-only (144-191 incl
# 179), -n 48, auto seed, baseline a05c1763.  Reference point: tonight's
# rowmajor A/B = 1.72x/min, 1.55x/loop (AUTO 55.3C/569W vs full 53.3C/715W).
# Per arm: temps 30s + voltage/power/CPU util (env logger) + run log.
# Samplers pinned off the test mask (cores 8/9).  Watchdog 95C.
# Ends in manual 99999s + 100% (standing config).
set -u
R=/home/sdc/root/arm64-sdc-fuzzing/opendcdiag
D=$R/docs/20261030/fan_ab_suite
BIN=$R/builddir/opendcdiag
SSHOPT="-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o ConnectTimeout=8"
TESTS="neon_rot_ldr_at_top_sub neon_rot_ldr_at_top_str3 mrn_reloaded_2src_alu movbe"

[ -n "${BMC_HOST:-}" ] && [ -n "${BMC_PASS:-}" ] || { echo "ABORT: BMC_HOST/BMC_PASS env missing"; exit 1; }
mkdir -p "$D"

bmc() { printf 'Y\n' | timeout 25 sshpass -p "$BMC_PASS" ssh $SSHOPT "${BMC_USER:-Administrator}@$BMC_HOST" "$@" 2>/dev/null; }
log() { echo "[$(date '+%F %T')] $*" | tee -a "$D/monitor.log"; }

if pgrep -x opendcdiag >/dev/null; then log "ABORT: opendcdiag already running"; exit 1; fi
[ "$(cat /sys/devices/system/cpu/cpu179/online 2>/dev/null)" = "1" ] || { log "ABORT: cpu179 offline"; exit 1; }
taskset -c 144-191 true 2>/dev/null || { log "ABORT: mask 144-191 unusable"; exit 1; }

set_auto() {
    bmc ipmcset -d fanmode -v 0
    sleep 3
    bmc ipmcget -d faninfo | grep -qi 'mode: *auto' || log "警告: AUTO 设置未确认"
}
set_full() {
    bmc ipmcset -d fanmode -v 1 99999
    bmc ipmcset -d fanlevel -v 100
    sleep 5
}

temp_sampler() {   # $1=logfile — 30s cadence, watchdog 95C
    # NOTE: background subshell stdout MUST be redirected away from the
    # command-substitution pipe (2026-10-30 deadlock lesson).
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
    label=$1; test=$2
    AD=$D/$test/$label
    mkdir -p "$AD"
    MONPID=$(temp_sampler "$AD/temp.log")
    taskset -pc 8 "$MONPID" >/dev/null 2>&1
    setsid nohup bash $R/scripts/sdc_env_logger.sh "$AD" 20 >> "$AD/env_logger.out" 2>&1 < /dev/null &
    start=$(date '+%F %T')
    taskset -c 144-191 "$BIN" -e "$test" -T 15m -n 48 --ignore-os-error --ignore-timeout -o "$AD/run.log" -q >/dev/null 2>&1
    rc=$?
    end=$(date '+%F %T')
    kill "$MONPID" 2>/dev/null
    sleep 35      # env logger 自止宽限
    read t_final t_avg v_avg p_avg <<< "$(summarize "$AD")"
    fails=$(grep -c 'result: fail' "$AD/run.log" 2>/dev/null); fails=${fails:-0}
    loops=$(grep -c '# Loop iteration' "$AD/run.log" 2>/dev/null); loops=${loops:-0}
    log "ARM[$label/$test] rc=$rc fails=$fails loops=$loops | CPU4 final=${t_final}C avg5=${t_avg}C | rail=${v_avg}V | Power=${p_avg}W | ${start} -> ${end}"
}

log "SUITE START | bin=$(sha256sum "$BIN" | cut -c1-16) | tests=[$TESTS] | mask=144-191 n=48 15m/arm | rowmajor参照=今晚A/B(1.72x/min 1.55x/loop)"

for T in $TESTS; do
    log "=== TEST $T: 设置 AUTO ==="
    set_auto
    run_arm auto "$T"
    [ -f "$D/ABORT" ] && { log "SUITE ABORTED (watchdog)"; exit 9; }
    log "=== TEST $T: 设置 manual 99999s + 100% ==="
    set_full
    run_arm full "$T"
    [ -f "$D/ABORT" ] && { log "SUITE ABORTED (watchdog)"; exit 9; }
done
log "SUITE COMPLETE (风扇终态: manual 99999s + 100%)"
