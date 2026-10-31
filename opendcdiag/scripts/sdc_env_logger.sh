#!/bin/bash
# sdc_env_logger.sh — standing environmental logger for SDC test runs.
#
# User directive (2026-10-30): whenever test cases are running, continuously
# record VOLTAGE and CPU UTILIZATION.  Canonical script for all future runs.
#
# Usage:   setsid nohup bash scripts/sdc_env_logger.sh <logdir> [max_minutes] \
#              >> <logdir>/env_logger.out 2>&1 < /dev/null &
#
# Samples while an opendcdiag process exists (self-terminates 5 misses
# after it exits, or at the deadline):
#   fast, every cycle (~1.5s, single-word sensor names batch fine):
#     N_VDDAVS_CPU1-4 (core rails) + Power/Power2 (W, current proxy)
#   slow, every 3rd cycle (multi-word names, ~5s per batch):
#     CPU4 VDDAVS (secondary rail) + CPU4 HVCC
#   cpu,  every cycle (/proc/stat jiffy deltas — free, no BMC traffic):
#     per-socket + total utilization  (CPU1=cores 0-47 ... CPU4=144-191)
#
# Log line:  <ts> | <fast> | cpu: 1=% 2=% 3=% 4=% T=% | <slow>
# (cpu/extra fields appended AFTER Power — existing analysis regexes for
#  N_VDDAVS_CPU4 / Power keep working unchanged.)
#
# Known quirks (see memory): no current sensors on this BMC; multi-word
# sensor names are slow and large mixed batches can time out.
set -u
D=${1:?usage: sdc_env_logger.sh <logdir> [max_minutes]}
MAXMIN=${2:-120}
LOG=$D/env.log
deadline=$(( $(date +%s) + MAXMIN * 60 ))
n=0
miss=0
mkdir -p "$D"
echo "[$(date '+%F %T')] ENV LOG START | volt: N_VDDAVS_CPU1-4+Power/Power2(fast) CPU4 VDDAVS+HVCC(slow) | cpu: per-socket from /proc/stat | log=local(+8h=UTC)" >> "$LOG"

while [ "$(date +%s)" -lt "$deadline" ]; do
  if ! pgrep -x opendcdiag >/dev/null; then
    miss=$((miss + 1))
    if [ "$miss" -ge 5 ]; then
      echo "[$(date '+%F %T')] ENV LOG END (test exited)" >> "$LOG"; exit 0
    fi
  else
    miss=0
  fi

  ts=$(date '+%F %T.%3N')
  fast=$(timeout 6 sudo ipmitool sensor reading N_VDDAVS_CPU1 N_VDDAVS_CPU2 N_VDDAVS_CPU3 N_VDDAVS_CPU4 Power Power2 2>/dev/null | tr -s ' ' | paste -sd';')

  # per-socket + total CPU utilization from /proc/stat deltas
  cur=$D/.cpu_cur; prev=$D/.cpu_prev
  grep -E '^cpu[0-9]+ ' /proc/stat > "$cur" 2>/dev/null
  cpu=""
  if [ -s "$prev" ]; then
    cpu=$(awk '
      FNR==NR {
        if ($1 ~ /^cpu[0-9]+$/) {
          n = substr($1, 4) + 0; s = int(n / 48)
          b = $2 + $3 + $4 + $7 + $8 + $9
          pb[s] += b; pt[s] += b + $5 + $6; pbt += b; ptt += b + $5 + $6
        }
        next
      }
      {
        if ($1 ~ /^cpu[0-9]+$/) {
          n = substr($1, 4) + 0; s = int(n / 48)
          b = $2 + $3 + $4 + $7 + $8 + $9
          cb[s] += b; ct[s] += b + $5 + $6; cbt += b; ctt += b + $5 + $6
        }
      }
      END {
        printf "cpu:"
        for (s = 0; s < 4; s++) {
          d = ct[s] - pt[s]
          if (d > 0) printf " %d=%.0f%%", s + 1, 100 * (cb[s] - pb[s]) / d
        }
        d = ctt - ptt
        if (d > 0) printf " T=%.0f%%", 100 * (cbt - pbt) / d
      }' "$prev" "$cur")
  fi
  [ -s "$cur" ] && mv "$cur" "$prev"

  slow=""
  n=$((n + 1))
  if [ $((n % 3)) -eq 0 ]; then
    slow=$(timeout 9 sudo ipmitool sensor reading "CPU4 VDDAVS" "CPU4 HVCC" 2>/dev/null | tr -s ' ' | paste -sd';')
  fi

  echo "$ts | $fast | $cpu | $slow" >> "$LOG"
  sleep 2
done
echo "[$(date '+%F %T')] ENV LOG END (deadline)" >> "$LOG"
