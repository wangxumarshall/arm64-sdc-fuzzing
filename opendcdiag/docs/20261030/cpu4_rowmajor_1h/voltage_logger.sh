#!/bin/bash
# Voltage/power sampler for SDC-trigger correlation (2026-10-30, user directive)
# Logs BMC voltage rails + node power with ms timestamps so fail-block
# timestamps (UTC in test log, +8h = local) can be joined in analysis.
# NOTE: no current sensors on this BMC (sdr type current empty, DCMI
# unsupported); Power/Power2 (Watts) serve as the current proxy.
# Read quirk: single-word sensor names batch fine (~1.5s); multi-word
# names are slow (~5s) and large mixed batches can time out — hence the
# fast/slow split below.
# Pinned to core 9 (outside test mask 144-191, away from 179).
# Self-terminates when the test process exits or after 45min.
set -u
D=/home/sdc/root/arm64-sdc-fuzzing/opendcdiag/docs/20261030/cpu4_rowmajor_1h
VLOG=$D/voltage.log
deadline=$(( $(date +%s) + 2700 ))
n=0
echo "[$(date '+%F %T')] VOLTAGE LOG START | log=local(+8h=UTC) | fast@~4s: N_VDDAVS_CPU1-4+Power/Power2 | slow@every3rd: CPU4 VDDAVS+HVCC" >> "$VLOG"
while [ "$(date +%s)" -lt "$deadline" ]; do
  if ! pgrep -x opendcdiag >/dev/null; then
    echo "[$(date '+%F %T')] VOLTAGE LOG END (test exited)" >> "$VLOG"; exit 0
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
