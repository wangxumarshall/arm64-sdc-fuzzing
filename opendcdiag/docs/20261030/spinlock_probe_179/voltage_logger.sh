#!/bin/bash
# Voltage/power sampler for the spinlock probe positive-control run.
# (User directive 2026-10-30: record voltage/current at SDC trigger
# moments. No current sensors on this BMC; Power/Power2 (W) are the
# proxy. Fast set ~4-8s: N_VDDAVS_CPU1-4 + Power/Power2; every 3rd
# cycle adds CPU4 VDDAVS + CPU4 HVCC.)
# Pinned to core 9 (outside test mask 144-191, away from 179).
# Self-terminates when the test process exits (5-consecutive-miss
# grace for startup race) or after 100min.
set -u
D=/home/sdc/root/arm64-sdc-fuzzing/opendcdiag/docs/20261030/spinlock_probe_179
VLOG=$D/voltage.log
deadline=$(( $(date +%s) + 6000 ))
n=0
miss=0
echo "[$(date '+%F %T')] VOLTAGE LOG START (from t0) | log=local(+8h=UTC) | fast@~4s: N_VDDAVS_CPU1-4+Power/Power2 | slow@every3rd: CPU4 VDDAVS+HVCC" >> "$VLOG"
while [ "$(date +%s)" -lt "$deadline" ]; do
  if ! pgrep -x opendcdiag >/dev/null; then
    miss=$((miss+1))
    if [ "$miss" -ge 5 ]; then
      echo "[$(date '+%F %T')] VOLTAGE LOG END (test exited)" >> "$VLOG"; exit 0
    fi
  else
    miss=0
  fi
  ts=$(date '+%F %T.%3N')
  fast=$(timeout 6 sudo ipmitool sensor reading N_VDDAVS_CPU1 N_VDDAVS_CPU2 N_VDDAVS_CPU3 N_VDDAVS_CPU4 Power Power2 2>/dev/null | tr -s ' ' | paste -sd';')
  slow=""
  n=$((n+1))
  if [ $((n % 3)) -eq 0 ]; then
    slow=$(timeout 9 sudo ipmitool sensor reading "CPU4 VDDAVS" "CPU4 HVCC" 2>/dev/null | tr -s ' ' | paste -sd';')
  fi
  echo "$ts | $fast | $slow" >> "$VLOG"
  sleep 2
done
echo "[$(date '+%F %T')] VOLTAGE LOG END (deadline)" >> "$VLOG"
