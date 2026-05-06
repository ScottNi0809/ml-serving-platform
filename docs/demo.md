# Demo Guide

[![中文文档](https://img.shields.io/badge/lang-中文-red)](demo.zh-CN.md)

This guide shows the project as an AI infrastructure workflow rather than a collection of standalone APIs. The default demo is CPU-only so it can run on a laptop; the GPU/vLLM path is optional.

## What The Demo Proves

The main demo walks through a production-style serving lifecycle:

1. Start the service stack.
2. Register a model in the Registry.
3. Create two model versions.
4. Upload a sklearn artifact.
5. Load the versions into the ML Worker.
6. Register routes in the Gateway.
7. Send prediction traffic through the Gateway.
8. Configure A/B routing.
9. Roll back all traffic to a stable version.
10. Inspect monitoring dashboards.

Optional GPU steps add vLLM-backed chat completions and SSE streaming.

## Prerequisites

| Requirement | Notes |
|-------------|-------|
| Docker + Docker Compose | Required for the service stack |
| Python 3.11 | Required only when running services outside Docker |
| Python dependencies | `pip install -r requirements.txt` if running helper scripts outside containers |
| Bash shell | The demo script is written for bash |
| NVIDIA Container Toolkit | Only required for the optional GPU/vLLM demo |

The local Registry demo uses the development API key:

```bash
export API_KEY=dev-api-key
```

## CPU Demo

Start the CPU stack:

```bash
docker compose up --build -d
```

Run the demo:

```bash
bash scripts/demo.sh
```

Expected phases:

```text
=== Phase 1: Health Check ===
=== Phase 2: Prepare Demo Model ===
=== Phase 3: Register Model And Versions ===
=== Phase 4: Upload Artifact To Registry ===
=== Phase 5: Load Models Into ML Worker ===
=== Phase 6: Register Gateway Routes ===
=== Phase 7: Predict Through Gateway ===
=== Phase 8: Configure A/B Routing ===
=== Phase 9: One-click Rollback ===
=== Phase 10: Monitoring Pointers ===
```

The prediction response should include the model name, version, and predictions:

```json
{
  "model_name": "iris-classifier",
  "version": "1.0.0",
  "predictions": [0]
}
```

The A/B route response should include `_routed_to`, which proves the Gateway selected a backend by weight:

```json
{
  "model_name": "iris-classifier",
  "version": "1.0.0",
  "predictions": [0],
  "_routed_to": {
    "version": "1.0.0",
    "worker_url": "http://serving:8001",
    "weight": 90
  }
}
```

The rollback response should show version `1.0.0` at weight 100 and version `2.0.0` at weight 0.

## Monitoring Demo

Start the monitoring stack:

```bash
docker compose -f docker-compose.yml -f docker-compose.monitor.yml up --build -d
bash scripts/demo.sh
```

Open:

| Tool | URL | What to check |
|------|-----|---------------|
| Prometheus | http://localhost:9090 | Targets `gateway` and `serving` are UP |
| Grafana | http://localhost:3000 | ML Platform dashboard shows QPS, latency, errors, active requests |

Useful Prometheus queries:

```promql
sum(rate(http_requests_total[1m])) by (service)
histogram_quantile(0.95, sum(rate(http_request_duration_seconds_bucket[5m])) by (le, service))
sum(http_active_requests) by (service)
sum(rate(inference_requests_total[1m])) by (model_name, version, status)
```

Dashboard proof screenshot:

![Grafana Dashboard Demo](../demo/grafana-dashboard.png)

## GPU / LLM Demo

Start the GPU stack:

```bash
docker compose -f docker-compose.yml -f docker-compose.gpu.yml up --build -d
```

The first vLLM startup can take several minutes because it may download and load the configured model.

Run the optional LLM flow:

```bash
RUN_GPU_DEMO=1 bash scripts/demo.sh
```

The script will:

1. Check LLM Worker health.
2. Register `qwen2.5-1.5b:1.0.0` in the Gateway.
3. Call non-streaming chat through the Gateway.
4. Call streaming chat and print SSE chunks.

Manual non-streaming request:

```bash
curl -sS -X POST http://localhost:8002/api/v1/gateway/register \
  -H "Content-Type: application/json" \
  -d '{"model_name":"qwen2.5-1.5b","version":"1.0.0","worker_url":"http://llm-worker:8003"}'

curl -sS -X POST http://localhost:8002/api/v1/gateway/chat/qwen2.5-1.5b/1.0.0 \
  -H "Content-Type: application/json" \
  -d '{"messages":[{"role":"user","content":"Explain KV Cache in two sentences."}],"max_tokens":120}'
```

Manual streaming request:

```bash
curl -N -X POST http://localhost:8002/api/v1/gateway/chat/qwen2.5-1.5b/1.0.0/stream \
  -H "Content-Type: application/json" \
  -d '{"messages":[{"role":"user","content":"Explain continuous batching in three bullets."}],"max_tokens":160}'
```

Expected stream shape:

```text
data: {"content":"Continuous","finish_reason":null,"model":"Qwen/Qwen2.5-1.5B-Instruct"}
data: {"content":" batching","finish_reason":null,"model":"Qwen/Qwen2.5-1.5B-Instruct"}
...
data: [DONE]
```

## Benchmark Demo

Install benchmark dependencies:

```bash
pip install -r benchmarks/requirements.txt
```

Run a load test:

```bash
docker compose up --build -d
USERS=50 SPAWN_RATE=10 RUN_TIME=120s ./benchmarks/run_benchmark.sh
```

The published benchmark report is in [benchmark.md](benchmark.md). The recorded run reached ~454 RPS at 200 concurrent users with 0% errors.

## Troubleshooting

| Symptom | Likely cause | Fix |
|---------|--------------|-----|
| `Registry is not reachable` | Docker stack is not running | `docker compose up --build -d` |
| Gateway prediction returns 404 | Worker route not registered or demo was partially interrupted | Re-run `bash scripts/demo.sh`; it resets the demo model routes |
| ML Worker load fails with missing file | Demo artifact was not copied into the container | Re-run the script; it trains and copies `scripts/models/iris_classifier.joblib` |
| Prometheus target is DOWN | Monitoring stack not started or service name mismatch | Use `docker compose -f docker-compose.yml -f docker-compose.monitor.yml up -d` |
| vLLM health remains unhealthy | Model is still downloading/loading or GPU runtime is missing | Check `docker logs vllm-engine` and verify NVIDIA Container Toolkit |
| SSE returns one buffered response | A proxy is buffering the stream | Keep `X-Accel-Buffering: no` and use `curl -N` |

## Reset

Remove containers and local volumes:

```bash
docker compose -f docker-compose.yml -f docker-compose.monitor.yml -f docker-compose.gpu.yml down -v
```

For the CPU-only stack:

```bash
docker compose down -v
```
