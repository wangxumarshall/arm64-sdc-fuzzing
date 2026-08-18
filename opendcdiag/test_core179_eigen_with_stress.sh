#!/bin/bash
# ============================================================
# 在核心 179 上运行 eigen 测试（每个 1 分钟）
# 同时用 stress-ng 加热所有 CPU（CPU4 额外加重）
# 所有日志全部保留（不删除）
# ============================================================

# ---------- 配置 ----------
OPENDCDIAG="./builddir/opendcdiag"
STRESS_NG="stress-ng"
LOG_DIR="./eigen_core179_stress_logs"
TOTAL_CORES=$(nproc)

# eigen 测试列表
ENABLE_TESTS=(
    "eigen_gemm_double14"
    "eigen_gemm_cdouble_dynamic_square"
    "eigen_gemm_double_dynamic_square"
    "eigen_gemm_float_dynamic_square"
    "eigen_sparse"
    "eigen_svd"
    "eigen_svd_cdouble_noavx512"
    "eigen_svd_double2"
    "eigen_svd_double"
    "eigen_svd_fvectors"
)

# 时长
TEST_DURATION="1m"
MAX_TOTAL_TIME="15m"        # 10个测试 × 1m + 缓冲
STRESS_TIMEOUT="20m"        # 大于总测试时间

# ---------- 获取除 179 外的核心 ----------
get_other_cores() {
    local other=()
    for ((c=0; c<TOTAL_CORES; c++)); do
        if [ $c -ne 179 ]; then
            other+=($c)
        fi
    done
    IFS=, echo "${other[*]}"
}

# ---------- 主流程 ----------
mkdir -p "$LOG_DIR"

echo "========== 核心 179 eigen 测试（stress-ng 全CPU升温） =========="
echo "总核心: $TOTAL_CORES | 测试核心: 179"
echo "测试数: ${#ENABLE_TESTS[@]} | 每测试: $TEST_DURATION | 总时间上限: $MAX_TOTAL_TIME"
echo "stress-ng 超时: $STRESS_TIMEOUT"
echo "日志目录: $LOG_DIR"
echo "开始: $(date)"
echo ""

OTHER_CORES=$(get_other_cores)
OTHER_COUNT=$((TOTAL_CORES - 1))
CPU4_OTHER="168-178,180-191"
CPU4_COUNT=$(echo $CPU4_OTHER | tr ',' '\n' | wc -l)

echo "除179外的核心: $OTHER_CORES (共 $OTHER_COUNT 个)"
echo "CPU4额外加压: $CPU4_OTHER (共 $CPU4_COUNT 个)"
echo ""

# 构建 --enable 参数
ENABLE_ARGS=""
for test in "${ENABLE_TESTS[@]}"; do
    ENABLE_ARGS="$ENABLE_ARGS --enable=$test"
done

LOG_FILE="$LOG_DIR/core179_eigen_stress_$(date +%Y%m%d_%H%M%S).log"
echo "日志文件: $LOG_FILE"
echo ""

# ---------- 启动 stress-ng（两组） ----------
echo "启动 stress-ng 升温负载 ..."

# 第一组：除179外所有核心
$STRESS_NG --taskset "$OTHER_CORES" \
    --matrix $OTHER_COUNT --matrix-method prod \
    --vm 2 --vm-bytes 80% \
    --cache $OTHER_COUNT --cache-level 3 \
    --timeout "$STRESS_TIMEOUT" \
    --metrics-brief &
PID_STRESS1=$!

# 第二组：CPU4 其他核心（额外加压）
if [ $CPU4_COUNT -gt 0 ]; then
    $STRESS_NG --taskset "$CPU4_OTHER" \
        --matrix $CPU4_COUNT --matrix-method prod \
        --cache $CPU4_COUNT --cache-level 3 \
        --vm 1 --vm-bytes 60% \
        --timeout "$STRESS_TIMEOUT" \
        --metrics-brief &
    PID_STRESS2=$!
fi

echo "stress-ng PID1: $PID_STRESS1" 
[ -n "$PID_STRESS2" ] && echo "stress-ng PID2: $PID_STRESS2"
sleep 3

# ---------- 运行 opendcdiag（核心179） ----------
echo "启动 opendcdiag 测试 (核心179) ..."
taskset -c 179 $OPENDCDIAG $ENABLE_ARGS -t $TEST_DURATION -T $MAX_TOTAL_TIME --strict-runtime -o "$LOG_FILE"
TEST_EXIT=$?

# ---------- 停止 stress-ng ----------
echo "测试结束，停止 stress-ng ..."
kill $PID_STRESS1 2>/dev/null
[ -n "$PID_STRESS2" ] && kill $PID_STRESS2 2>/dev/null
wait $PID_STRESS1 2>/dev/null
[ -n "$PID_STRESS2" ] && wait $PID_STRESS2 2>/dev/null

# ---------- 显示结果（不删除任何日志） ----------
if grep -qi "result: fail" "$LOG_FILE"; then
    echo -e "\033[31m❌ 检测到 FAIL\033[0m (日志已保存: $LOG_FILE)"
else
    echo -e "\033[32m✅ 全部 PASS\033[0m (日志已保存: $LOG_FILE)"
fi

echo ""
echo "========== 测试完成 =========="
echo "结束: $(date)"
echo "所有日志保存在: $LOG_DIR (未删除任何文件)"
