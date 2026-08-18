#!/bin/bash
# 试跑: 估算不同 K 维度下 eigen_gemm_double_dynamic_square 的 fail 复现率
# 条件与历史完全一致: taskset -c 179 + 其余191核 stress-ng 全方位升压
# 用法: ./gemm_k_estrate.sh <K_DIM> <duration_seconds>

K_DIM="${1:-256}"
DUR="${2:-120}"
OPENDCDIAG="./builddir/opendcdiag"
TOTAL_CORES=$(nproc)

get_other_cores() {
    local other=()
    for ((c=0; c<TOTAL_CORES; c++)); do
        if [ $c -ne 179 ]; then other+=($c); fi
    done
    IFS=, echo "${other[*]}"
}
OTHER_CORES=$(get_other_cores)
OTHER_COUNT=$((TOTAL_CORES - 1))

LOG_DIR="./gemm_k_estrate_logs"
mkdir -p "$LOG_DIR"
LOG_FILE="$LOG_DIR/gemm_k${K_DIM}_${DUR}s_$(date +%Y%m%d_%H%M%S).log"

echo "[estrate] K=$K_DIM dur=${DUR}s log=$LOG_FILE"

# 启动 stress-ng (与历史一致)
stress-ng --taskset "$OTHER_CORES" \
    --cpu $OTHER_COUNT --cpu-method all \
    --matrix $OTHER_COUNT --matrix-method all \
    --cache $OTHER_COUNT --cache-level 3 \
    --vm 4 --vm-bytes 80% \
    --hdd 2 --hdd-bytes 1G \
    --timeout $((DUR + 60))s --metrics-brief >/dev/null 2>&1 &
STRESS_PID=$!
sleep 3

# 跑 opendcdiag (core 179, 只 enable gemm_double, 短时)
GEMM_K_DIM=$K_DIM taskset -c 179 $OPENDCDIAG \
    --enable=eigen_gemm_double_dynamic_square \
    -t ${DUR}s -T $((DUR + 30))s --strict-runtime \
    -o "$LOG_FILE" >/dev/null 2>&1

kill $STRESS_PID 2>/dev/null
wait $STRESS_PID 2>/dev/null

# 统计 fail 数
FAILS=$(grep -c "result: fail" "$LOG_FILE" 2>/dev/null)
ITERS=$(grep "iteration:" "$LOG_FILE" 2>/dev/null | tail -1)
echo "[estrate] K=$K_DIM: fail次数=$FAILS / ${DUR}s  =>  $(echo "scale=2; $FAILS*60/$DUR" | bc 2>/dev/null) fail/min"
echo "  最后迭代: $ITERS"
echo "  日志: $LOG_FILE"
