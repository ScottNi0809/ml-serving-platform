#!/bin/bash
set -euo pipefail

# ============ 配置 ============
HOST="${HOST:-http://localhost:8002}"
REGISTRY_HOST="${REGISTRY_HOST:-http://localhost:8000}"
USERS="${USERS:-50}"
SPAWN_RATE="${SPAWN_RATE:-10}"
RUN_TIME="${RUN_TIME:-60s}"
OUTPUT_DIR="benchmarks/results"

# ============ 准备 ============
echo "🔧 ML Serving Platform - Benchmark Suite"
echo "========================================="
echo "Gateway:    $HOST"
echo "Registry:   $REGISTRY_HOST"
echo "Users:      $USERS"
echo "Spawn rate: $SPAWN_RATE users/s"
echo "Duration:   $RUN_TIME"
echo ""

# 检查服务是否可达
echo "⏳ Checking service availability..."
if ! curl -sf "$HOST/health" > /dev/null 2>&1; then
    echo "❌ Gateway at $HOST is not reachable. Start it first:"
    echo "   docker compose up -d"
    exit 1
fi
echo "✅ Gateway is healthy"

if ! curl -sf "$REGISTRY_HOST/health" > /dev/null 2>&1; then
    echo "❌ Registry at $REGISTRY_HOST is not reachable. Start it first:"
    echo "   docker compose up -d"
    exit 1
fi
echo "✅ Registry is healthy"
echo ""

# 创建输出目录
mkdir -p "$OUTPUT_DIR"

# ============ 运行测试 ============
echo "🚀 Starting load test..."
REGISTRY_HOST="$REGISTRY_HOST" \
locust -f benchmarks/locustfile.py \
    --host="$HOST" \
    --users "$USERS" \
    --spawn-rate "$SPAWN_RATE" \
    --run-time "$RUN_TIME" \
    --headless \
    --csv="$OUTPUT_DIR/benchmark" \
    --html="$OUTPUT_DIR/report.html" \
    2>&1 | tee "$OUTPUT_DIR/output.log"

echo ""
echo "✅ Benchmark complete!"
echo "📊 Results:"
echo "   CSV:  $OUTPUT_DIR/benchmark_stats.csv"
echo "   HTML: $OUTPUT_DIR/report.html"
echo "   Log:  $OUTPUT_DIR/output.log"