#!/bin/bash
# ============================================================
# 运行指定测试并记录温度（IPMI / sensors）
# 用法：./run_test_with_temp.sh [test_name] [core] [duration]
# 默认：test_name=eigen_sparse, core=179, duration=20s
# ============================================================

TEST_NAME="${1:-eigen_sparse}"
CORE="${2:-179}"
DURATION="${3:-20s}"
OPENDCDIAG="./builddir/opendcdiag"
LOG_DIR="./temp_test_$(date +%Y%m%d_%H%M%S)"
mkdir -p "$LOG_DIR"
TEMP_LOG="$LOG_DIR/temperature.log"
TEST_LOG="$LOG_DIR/opendcdiag.log"
FAIL_TEMP="$LOG_DIR/fail_temperature.txt"

echo "========== 测试配置 =========="
echo "测试用例: $TEST_NAME"
echo "核心:     $CORE"
echo "时长:     $DURATION"
echo "日志目录: $LOG_DIR"

# 检查 opendcdiag 是否存在
if [ ! -x "$OPENDCDIAG" ]; then
    echo "错误: $OPENDCDIAG 不存在或不可执行"
    exit 1
fi

# 检查温度读取命令（优先 ipmitool，备选 sensors）
if command -v ipmitool &> /dev/null; then
    TEMP_CMD="ipmitool sensor list 2>/dev/null | grep '^CPU4_TEMP' | awk '{print \$2}'"
    echo "使用 ipmitool 读取温度"
elif command -v sensors &> /dev/null; then
    TEMP_CMD="sensors | grep 'CPU4' | awk '{print \$2}' | tr -d '+°C'"
    echo "使用 sensors 读取温度"
else
    echo "错误: 未找到 ipmitool 或 sensors，无法记录温度"
    exit 1
fi

# ---------- 1. 启动温度记录（后台） ----------
record_temp() {
    while true; do
        now=$(date +%s%3N)
        temp=$(eval "$TEMP_CMD")
        if [[ -z "$temp" ]]; then
            temp="N/A"
        fi
        echo "$now $temp" >> "$TEMP_LOG"
        sleep 2
    done
}
record_temp &
TEMP_PID=$!
echo "温度记录进程 PID: $TEMP_PID"

# ---------- 2. 运行测试 ----------
echo ""
echo "启动测试..."
$OPENDCDIAG --enable="$TEST_NAME" --cpuset="$CORE" -t "$DURATION" -o "$TEST_LOG"
EXIT_CODE=$?

# ---------- 3. 停止温度记录 ----------
kill $TEMP_PID 2>/dev/null
wait $TEMP_PID 2>/dev/null
echo "温度记录已停止"

# ---------- 4. 分析结果并提取失败温度 ----------
echo ""
echo "========== 测试结果分析 =========="
if grep -q "result: fail" "$TEST_LOG"; then
    echo "检测到失败！正在提取温度..."
    # 提取所有失败时间
    grep -E "result: fail" -B 20 "$TEST_LOG" | grep "time-at-start" | sed 's/.*timestamp '\''\(.*\)Z'\''.*/\1/' | while read -r time_str; do
        ts=$(date -d "${time_str}Z" +%s%3N 2>/dev/null)
        if [ -n "$ts" ]; then
            closest=$(awk -v t="$ts" 'BEGIN{min=9999999; val="N/A"} {diff=t-$1; if(diff<0) diff=-diff; if(diff<min){min=diff; val=$2}} END{print val}' "$TEMP_LOG")
            echo "失败时间: $time_str -> 温度: $closest°C" | tee -a "$FAIL_TEMP"
        else
            echo "时间解析失败: $time_str" | tee -a "$FAIL_TEMP"
        fi
    done
else
    echo "测试通过，未触发失败。"
    echo "温度记录功能正常（但无关联数据）"
fi

echo ""
echo "日志文件:"
echo "  - 测试日志: $TEST_LOG"
echo "  - 温度日志: $TEMP_LOG"
if [ -f "$FAIL_TEMP" ]; then
    echo "  - 失败温度: $FAIL_TEMP"
fi
echo "测试退出码: $EXIT_CODE"
exit $EXIT_CODE
