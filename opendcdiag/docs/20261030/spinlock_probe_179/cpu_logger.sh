#!/bin/bash
# cpu-util-only patch logger for the RUNNING spinlock_probe_179 experiment.
# Voltage/power are already covered by voltage_logger.sh (avoid duplicate
# BMC polling); this adds /proc-stat-based per-socket CPU utilization.
# Reads only /proc/stat — zero BMC traffic.  Self-terminates with the test.
set -u
D=/home/sdc/root/arm64-sdc-fuzzing/opendcdiag/docs/20261030/spinlock_probe_179
LOG=$D/cpu_util.log
deadline=$(( $(date +%s) + 3600 ))
miss=0
prev=$D/.cpu_prev_p
echo "[$(date '+%F %T')] CPU UTIL LOG START (patch for running probe run; per-socket 1-4 + T)" >> "$LOG"
while [ "$(date +%s)" -lt "$deadline" ]; do
  if ! pgrep -x opendcdiag >/dev/null; then
    miss=$((miss + 1))
    if [ "$miss" -ge 5 ]; then
      echo "[$(date '+%F %T')] CPU UTIL LOG END (test exited)" >> "$LOG"; exit 0
    fi
  else
    miss=0
  fi
  ts=$(date '+%F %T.%3N')
  cur=$D/.cpu_cur_p
  grep -E '^cpu[0-9]+ ' /proc/stat > "$cur" 2>/dev/null
  cpu=""
  if [ -s "$prev" ]; then
    cpu=$(awk '
      FNR==NR {
        if ($1 ~ /^cpu[0-9]+$/) {
          n = substr($1, 4) + 0; s = int(n / 48)
          b = $2 + $3 + $4 + $7 + $8 + $9
          pb[s] += b; pt[s] += b + $5 + $6
        }
        next
      }
      {
        if ($1 ~ /^cpu[0-9]+$/) {
          n = substr($1, 4) + 0; s = int(n / 48)
          b = $2 + $3 + $4 + $7 + $8 + $9
          cb[s] += b; ct[s] += b + $5 + $6
        }
      }
      END {
        printf "cpu:"
        for (s = 0; s < 4; s++) {
          d = ct[s] - pt[s]
          if (d > 0) printf " %d=%.0f%%", s + 1, 100 * (cb[s] - pb[s]) / d
        }
      }' "$prev" "$cur")
  fi
  [ -s "$cur" ] && mv "$cur" "$prev"
  echo "$ts | $cpu" >> "$LOG"
  sleep 3
done
echo "[$(date '+%F %T')] CPU UTIL LOG END (deadline)" >> "$LOG"
