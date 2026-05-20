#!/bin/bash
# demo.sh - ML Model Serving Platform end-to-end demo
#
# Default path: CPU-only Registry + ML Worker + Gateway.
# Optional path: set RUN_GPU_DEMO=1 after starting docker-compose.gpu.yml.

set -euo pipefail

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

REGISTRY_BASE="${REGISTRY_BASE:-http://localhost:8000}"
SERVING_BASE="${SERVING_BASE:-http://localhost:8001}"
GATEWAY_BASE="${GATEWAY_BASE:-http://localhost:8002}"
LLM_WORKER_BASE="${LLM_WORKER_BASE:-http://localhost:8003}"

REGISTRY_API="$REGISTRY_BASE/api/v1"
GATEWAY_API="$GATEWAY_BASE/api/v1/gateway"
API_KEY="${API_KEY:-dev-api-key}"

MODEL_NAME="${MODEL_NAME:-iris-classifier}"
MODEL_V1="1.0.0"
MODEL_V2="2.0.0"
WORKER_URL="${WORKER_URL:-http://serving:8001}"
SERVING_CONTAINER="${SERVING_CONTAINER:-ml-serving}"
LOCAL_MODEL_PATH="${LOCAL_MODEL_PATH:-scripts/models/iris_classifier.joblib}"
CONTAINER_MODEL_PATH="${CONTAINER_MODEL_PATH:-/tmp/iris_classifier.joblib}"

LLM_MODEL_NAME="${LLM_MODEL_NAME:-qwen2.5-1.5b}"
LLM_MODEL_VERSION="${LLM_MODEL_VERSION:-1.0.0}"
LLM_WORKER_URL="${LLM_WORKER_URL:-http://llm-worker:8003}"

if command -v python3 >/dev/null 2>&1; then
  PYTHON_BIN="python3"
elif command -v python >/dev/null 2>&1; then
  PYTHON_BIN="python"
else
  PYTHON_BIN=""
fi

section() {
  echo -e "\n${GREEN}=== $1 ===${NC}"
}

warn() {
  echo -e "${YELLOW}$1${NC}"
}

fail() {
  echo -e "${RED}$1${NC}" >&2
  exit 1
}

pretty() {
  if [[ -n "$PYTHON_BIN" ]]; then
    "$PYTHON_BIN" -m json.tool
  else
    cat
  fi
}

wait_for_url() {
  local name="$1"
  local url="$2"
  local attempts="${3:-30}"

  for ((i = 1; i <= attempts; i++)); do
    if curl -fsS "$url" >/dev/null 2>&1; then
      echo "OK: $name is reachable at $url"
      return 0
    fi
    sleep 2
  done

  fail "$name is not reachable at $url. Start the stack first."
}

request_json() {
  curl -sS "$@" | pretty
}

ignore_delete() {
  curl -sS -o /dev/null -w "%{http_code}" "$@" >/dev/null || true
}

ensure_demo_model() {
  mkdir -p "$(dirname "$LOCAL_MODEL_PATH")"

  if docker ps --format '{{.Names}}' | grep -qx "$SERVING_CONTAINER"; then
    echo "Training demo model inside $SERVING_CONTAINER ..."
    docker exec -i "$SERVING_CONTAINER" python - <<'PY'
import joblib
from sklearn.datasets import load_iris
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import train_test_split

iris = load_iris()
X_train, _, y_train, _ = train_test_split(
    iris.data, iris.target, test_size=0.2, random_state=42
)
model = LogisticRegression(max_iter=200, random_state=42)
model.fit(X_train, y_train)
joblib.dump(model, "/tmp/iris_classifier.joblib")
print("saved /tmp/iris_classifier.joblib")
PY
    docker cp "$SERVING_CONTAINER:$CONTAINER_MODEL_PATH" "$LOCAL_MODEL_PATH"
  elif [[ -n "$PYTHON_BIN" ]]; then
    warn "Serving container not found; training demo model on the host."
    "$PYTHON_BIN" scripts/train_demo_model.py >/dev/null
    CONTAINER_MODEL_PATH="$LOCAL_MODEL_PATH"
  else
    fail "No serving container and no local Python interpreter found."
  fi

  [[ -f "$LOCAL_MODEL_PATH" ]] || fail "Demo model was not created at $LOCAL_MODEL_PATH"
  echo "Demo model artifact: $LOCAL_MODEL_PATH"
}

reset_demo_state() {
  echo "Cleaning previous demo state if present ..."
  ignore_delete -X DELETE "$GATEWAY_API/ab/$MODEL_NAME"
  ignore_delete -X DELETE "$GATEWAY_API/routes/$MODEL_NAME/$MODEL_V1"
  ignore_delete -X DELETE "$GATEWAY_API/routes/$MODEL_NAME/$MODEL_V2"
  ignore_delete -X DELETE "$REGISTRY_API/models/$MODEL_NAME" -H "X-API-Key: $API_KEY"
}

section "Phase 1: Health Check"
wait_for_url "Registry" "$REGISTRY_BASE/health"
wait_for_url "ML Worker" "$SERVING_BASE/health"
wait_for_url "Gateway" "$GATEWAY_BASE/health"

echo "Registry:"
request_json "$REGISTRY_BASE/health"
echo "Gateway:"
request_json "$GATEWAY_BASE/health"

section "Phase 2: Prepare Demo Model"
ensure_demo_model
reset_demo_state

section "Phase 3: Register Model And Versions"
request_json -X POST "$REGISTRY_API/models" \
  -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d "{\"name\":\"$MODEL_NAME\",\"framework\":\"sklearn\",\"description\":\"Iris classifier demo model\",\"tags\":[\"demo\",\"sklearn\"]}"

request_json -X POST "$REGISTRY_API/models/$MODEL_NAME/versions" \
  -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d "{\"version\":\"$MODEL_V1\",\"description\":\"Stable baseline version\"}"

request_json -X POST "$REGISTRY_API/models/$MODEL_NAME/versions" \
  -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d "{\"version\":\"$MODEL_V2\",\"description\":\"Candidate rollout version\"}"

section "Phase 4: Upload Artifact To Registry"
request_json -X POST "$REGISTRY_API/models/$MODEL_NAME/versions/$MODEL_V1/upload" \
  -H "X-API-Key: $API_KEY" \
  -F "file=@$LOCAL_MODEL_PATH"

request_json -X POST "$REGISTRY_API/models/$MODEL_NAME/versions/$MODEL_V2/upload" \
  -H "X-API-Key: $API_KEY" \
  -F "file=@$LOCAL_MODEL_PATH"

section "Phase 5: Load Models Into ML Worker"
request_json -X POST "$SERVING_BASE/api/v1/models/load" \
  -H "Content-Type: application/json" \
  -d "{\"model_name\":\"$MODEL_NAME\",\"version\":\"$MODEL_V1\",\"framework\":\"sklearn\",\"file_path\":\"$CONTAINER_MODEL_PATH\"}"

request_json -X POST "$SERVING_BASE/api/v1/models/load" \
  -H "Content-Type: application/json" \
  -d "{\"model_name\":\"$MODEL_NAME\",\"version\":\"$MODEL_V2\",\"framework\":\"sklearn\",\"file_path\":\"$CONTAINER_MODEL_PATH\"}"

section "Phase 6: Register Gateway Routes"
request_json -X POST "$GATEWAY_API/register" \
  -H "Content-Type: application/json" \
  -d "{\"model_name\":\"$MODEL_NAME\",\"version\":\"$MODEL_V1\",\"worker_url\":\"$WORKER_URL\"}"

request_json -X POST "$GATEWAY_API/register" \
  -H "Content-Type: application/json" \
  -d "{\"model_name\":\"$MODEL_NAME\",\"version\":\"$MODEL_V2\",\"worker_url\":\"$WORKER_URL\"}"

request_json "$GATEWAY_API/routes"

section "Phase 7: Predict Through Gateway"
request_json -X POST "$GATEWAY_API/predict/$MODEL_NAME/$MODEL_V1" \
  -H "Content-Type: application/json" \
  -d '{"inputs":[[5.1,3.5,1.4,0.2]]}'

section "Phase 8: Configure A/B Routing"
request_json -X POST "$GATEWAY_API/ab/configure" \
  -H "Content-Type: application/json" \
  -d "{\"model_name\":\"$MODEL_NAME\",\"backends\":[{\"version\":\"$MODEL_V1\",\"worker_url\":\"$WORKER_URL\",\"weight\":90},{\"version\":\"$MODEL_V2\",\"worker_url\":\"$WORKER_URL\",\"weight\":10}]}"

for i in 1 2 3 4 5; do
  echo "A/B request $i:"
  request_json -X POST "$GATEWAY_API/ab/predict/$MODEL_NAME" \
    -H "Content-Type: application/json" \
    -d '{"inputs":[[6.2,2.9,4.3,1.3]]}'
done

section "Phase 9: One-click Rollback"
request_json -X POST "$GATEWAY_API/ab/rollback/$MODEL_NAME" \
  -H "Content-Type: application/json" \
  -d "{\"target_version\":\"$MODEL_V1\",\"reason\":\"demo rollback after candidate validation\"}"

request_json "$GATEWAY_API/ab/$MODEL_NAME"
request_json "$GATEWAY_API/ab/rollback-history/$MODEL_NAME"

section "Phase 10: Traffic Simulation (30s for Monitoring)"
echo "Sending sustained traffic so Prometheus/Grafana dashboards have visible data..."
TRAFFIC_DURATION=${TRAFFIC_DURATION:-30}
TRAFFIC_END=$((SECONDS + TRAFFIC_DURATION))
TRAFFIC_COUNT=0

while [ $SECONDS -lt $TRAFFIC_END ]; do
  # Mix of direct predictions and A/B routed requests
  curl -sS -o /dev/null -X POST "$GATEWAY_API/predict/$MODEL_NAME/$MODEL_V1" \
    -H "Content-Type: application/json" \
    -d '{"input":[[5.1,3.5,1.4,0.2]]}'
  curl -sS -o /dev/null -X POST "$GATEWAY_API/predict/ab/$MODEL_NAME" \
    -H "Content-Type: application/json" \
    -d '{"input":[[6.2,3.4,5.4,2.3]]}'
  curl -sS -o /dev/null -X POST "$GATEWAY_API/predict/$MODEL_NAME/$MODEL_V1" \
    -H "Content-Type: application/json" \
    -d '{"input":[[5.9,3.0,4.2,1.5]]}'
  TRAFFIC_COUNT=$((TRAFFIC_COUNT + 3))
  sleep 0.1
done

echo "Sent $TRAFFIC_COUNT requests in ${TRAFFIC_DURATION}s."
echo "Wait a few seconds for Prometheus to scrape, then check Grafana."

section "Phase 11: Monitoring Pointers"
echo "Gateway metrics:    $GATEWAY_BASE/metrics"
echo "ML Worker metrics:  $SERVING_BASE/metrics"
echo "Prometheus:         http://localhost:9090"
echo "Grafana:            http://localhost:3000 (admin/admin)"

if [[ "${RUN_GPU_DEMO:-0}" == "1" ]]; then
  section "Optional Phase 12: LLM Chat Via vLLM"
  wait_for_url "LLM Worker" "$LLM_WORKER_BASE/health" 120

  request_json -X POST "$GATEWAY_API/register" \
    -H "Content-Type: application/json" \
    -d "{\"model_name\":\"$LLM_MODEL_NAME\",\"version\":\"$LLM_MODEL_VERSION\",\"worker_url\":\"$LLM_WORKER_URL\"}"

  echo "Non-streaming chat:"
  request_json -X POST "$GATEWAY_API/chat/$LLM_MODEL_NAME/$LLM_MODEL_VERSION" \
    -H "Content-Type: application/json" \
    -d '{"messages":[{"role":"user","content":"Explain KV Cache in two sentences."}],"max_tokens":120,"temperature":0.2}'

  echo ""
  echo "Streaming chat (token-by-token):"
  echo -e "${YELLOW}> Explain continuous batching in three bullets.${NC}"
  echo ""

  # Stream and display tokens in real-time, then show raw SSE sample
  STREAM_TMPFILE=$(mktemp)
  curl -sS -N -X POST "$GATEWAY_API/chat/$LLM_MODEL_NAME/$LLM_MODEL_VERSION/stream" \
    -H "Content-Type: application/json" \
    -d '{"messages":[{"role":"user","content":"Explain continuous batching in three bullets."}],"max_tokens":160,"temperature":0.2}' \
    | tee "$STREAM_TMPFILE" \
    | while IFS= read -r line; do
        # Extract content field and print without newline for typewriter effect
        if [[ "$line" == data:\ * ]]; then
          json="${line#data: }"
          if [[ "$json" == "[DONE]" ]]; then
            break
          fi
          if [[ -n "$PYTHON_BIN" ]]; then
            token=$("$PYTHON_BIN" -c "import sys,json; d=json.loads(sys.argv[1]); print(d.get('content',''),end='')" "$json" 2>/dev/null)
            printf '%s' "$token"
          fi
        fi
      done
  echo ""
  echo ""

  # Show a few raw SSE lines as proof of protocol
  echo -e "${GREEN}Raw SSE sample (first 5 events):${NC}"
  grep '^data: {' "$STREAM_TMPFILE" | head -5
  echo "..."
  grep '^data: \[DONE\]' "$STREAM_TMPFILE" | head -1
  rm -f "$STREAM_TMPFILE"
else
  warn "Skipping GPU/LLM demo. Set RUN_GPU_DEMO=1 after starting docker-compose.gpu.yml to enable it."
fi

section "Demo Complete"
echo "The platform served a versioned model, routed traffic through Gateway, configured A/B rollout, and performed rollback."
