#!/bin/bash
# ============================================================
# 在核心 179 上运行 eigen 测试（每个 30 分钟）
# 同时在所有其他核心上运行 stress-ng 升温（无限运行，直到测试结束）
# 所有日志永久保留
# ============================================================

# ---------- 配置 ----------
OPENDCDIAG="./builddir/opendcdiag"
STRESS_NG="stress-ng"
LOG_DIR="./eigen_core179_30m_stress_logs"
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
TEST_DURATION="30m"
MAX_TOTAL_TIME="6h"          # 10个测试 × 30m = 5h，留 1h 缓冲

# ---------- 获取除 179 外的所有核心 ----------
get_other_cores() {
    local other=()
    for ((c=0; c<TOTAL_CORES; c++)); do
        if [ $c -ne 179 ]; then
            other+=($c)
        fi
    done
    IFS=, echo "${other[*]}"
}

OTHER_CORES=$(get_other_cores)
OTHER_COUNT=$((TOTAL_CORES - 1))

# ---------- 主流程 ----------
mkdir -p "$LOG_DIR"

echo "========== 核心 179 eigen 测试（每个 30 分钟，全核 stress-ng 升温） =========="
echo "总核心: $TOTAL_CORES | 测试核心: 179"
echo "压力核心: 除 179 外的所有核心 (共 $OTHER_COUNT 个)"
echo "测试数: ${#ENABLE_TESTS[@]} | 每测试: $TEST_DURATION | 总时间上限: $MAX_TOTAL_TIME"
echo "日志目录: $LOG_DIR"
echo "开始: $(date)"
echo ""

# 构建 --enable 参数
ENABLE_ARGS=""
for test in "${ENABLE_TESTS[@]}"; do
    ENABLE_ARGS="$ENABLE_ARGS --enable=$test"
done

LOG_FILE="$LOG_DIR/core179_eigen_30m_$(date +%Y%m%d_%H%M%S).log"
echo "日志文件: $LOG_FILE"
echo ""

# ---------- 启动 stress-ng（所有非179核心） ----------
echo "启动 stress-ng 升温负载（所有非179核心）..."
$STRESS_NG --taskset "$OTHER_CORES" \
    --cpu $OTHER_COUNT --cpu-method all \
    --matrix $OTHER_COUNT --matrix-method all \
    --cache $OTHER_COUNT --cache-level 3 \
    --vm 4 --vm-bytes 80% \
    --hdd 2 --hdd-bytes 1G \
    --timeout 6h \
    --metrics-brief &
STRESS_PID=$!
echo "stress-ng PID: $STRESS_PID"
sleep 3

# ---------- 运行 opendcdiag（核心179） ----------
echo "启动 opendcdiag 测试 (核心179) ..."
taskset -c 179 $OPENDCDIAG $ENABLE_ARGS -t $TEST_DURATION -T $MAX_TOTAL_TIME --strict-runtime -o "$LOG_FILE"
TEST_EXIT=$?

# ---------- 停止 stress-ng ----------
echo "测试结束，停止 stress-ng ..."
kill $STRESS_PID 2>/dev/null
wait $STRESS_PID 2>/dev/null

# ---------- 显示结果（不删除任何日志） ----------
if grep -qi "result: fail" "$LOG_FILE"; then
    echo -e "\033[31m❌ 检测到 FAIL\033[0m (日志已保存: $LOG_FILE)"
else
    echo -e "\033[32m✅ 全部 PASS\033[0m (日志已保存: $LOG_FILE)"
fi

echo ""
echo "========== 测试完成 =========="
echo "结束: $(date)"
echo "所有日志保存在: $LOG_DIR（未删除任何文件）"
