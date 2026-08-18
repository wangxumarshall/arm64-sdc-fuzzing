#!/bin/bash
# ============================================================
# 对核心179和180进行逐个测试用例运行（每个5分钟）
# 记录完整日志、温度（CPU4_TEMP）和电压（CPU Core Voltage）
# 超时测试自动跳过，最终汇总失败/超时信息
# 用法：./test_core179.sh
# ============================================================

CPUSET="179,180"
OPENDCDIAG="./builddir/opendcdiag"
BASE_DIR="./core179_180_per_test_$(date +%Y%m%d_%H%M%S)"
mkdir -p "$BASE_DIR"
OPENDCDIAG_LOG="$BASE_DIR/opendcdiag.log"
TEMP_LOG="$BASE_DIR/temperature.log"
VOLT_LOG="$BASE_DIR/voltage.log"
FAIL_LOG="$BASE_DIR/fail_summary.log"

echo "========== 核心 $CPUSET 逐测试用例运行（每个5分钟）=========="
echo "日志目录: $BASE_DIR"
echo "opendcdiag 日志: $OPENDCDIAG_LOG"
echo "温度日志: $TEMP_LOG"
echo "电压日志: $VOLT_LOG"
echo "失败汇总: $FAIL_LOG"

# ---------- 1. 后台记录温度和电压（每2秒） ----------
record_sensors() {
    while true; do
        now=$(date +%s%3N)
        # 温度（CPU4_TEMP）
        if command -v ipmitool &> /dev/null; then
            temp=$(ipmitool sensor list 2>/dev/null | grep "^CPU4_TEMP" | awk '{print $2}')
            volt=$(ipmitool sensor list 2>/dev/null | grep "CPU Core Voltage" | awk '{print $2}')
        fi
        # 如果值无效设为 N/A
        [[ ! "$temp" =~ ^[0-9.]+$ ]] && temp="N/A"
        [[ ! "$volt" =~ ^[0-9.]+$ ]] && volt="N/A"
        echo "$now $temp" >> "$TEMP_LOG"
        echo "$now $volt" >> "$VOLT_LOG"
        sleep 2
    done
}
record_sensors &
SENSOR_PID=$!
echo "传感器记录进程 PID: $SENSOR_PID"

# ---------- 2. 运行 opendcdiag（每个测试用例5分钟，无总时间限制） ----------
echo "启动 opendcdiag ..."
$OPENDCDIAG --cpuset=$CPUSET -t 5m -o "$OPENDCDIAG_LOG"
TEST_EXIT=$?
echo "opendcdiag 退出码: $TEST_EXIT"

# ---------- 3. 停止传感器记录 ----------
kill $SENSOR_PID 2>/dev/null
wait $SENSOR_PID 2>/dev/null

# ---------- 4. 分析失败和超时 ----------
echo ""
echo "========== 失败/超时汇总 =========="
grep -E "result: fail|result: timed out" "$OPENDCDIAG_LOG" | while read -r line; do
    # 提取测试名称（前面几行有 test:）
    test_name=$(grep -B 10 "$line" "$OPENDCDIAG_LOG" | grep -E "^test:" | tail -1 | awk '{print $2}')
    [ -z "$test_name" ] && test_name="Unknown"
    
    # 提取失败时间（time-at-start）
    time_line=$(grep -B 20 "$line" "$OPENDCDIAG_LOG" | grep "time-at-start" | tail -1)
    if [[ $time_line =~ now:\ \!\!timestamp\ \'([0-9T:-]+)Z\' ]]; then
        time_str="${BASH_REMATCH[1]}"
        ts=$(date -d "${time_str}Z" +%s%3N 2>/dev/null)
    else
        ts=""
        time_str="Unknown"
    fi
    
    # 从温度/电压日志中找最接近的值
    if [ -n "$ts" ]; then
        temp=$(awk -v t="$ts" 'BEGIN{min=9999999; val="N/A"} {diff=t-$1; if(diff<0) diff=-diff; if(diff<min){min=diff; val=$2}} END{print val}' "$TEMP_LOG")
        volt=$(awk -v t="$ts" 'BEGIN{min=9999999; val="N/A"} {diff=t-$1; if(diff<0) diff=-diff; if(diff<min){min=diff; val=$2}} END{print val}' "$VOLT_LOG")
    else
        temp="N/A"
        volt="N/A"
    fi
    
    echo "测试: $test_name  状态: $(echo "$line" | awk '{print $2}')  时间: $time_str  温度: $temp°C  电压: $volt V" | tee -a "$FAIL_LOG"
done

echo ""
echo "========== 测试完成 =========="
echo "所有日志保存在: $BASE_DIR"
echo "失败/超时汇总: $FAIL_LOG"
