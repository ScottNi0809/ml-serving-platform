# ML Model Serving Platform

![CI](https://github.com/ScottNi0809/ml-serving-platform/actions/workflows/ci.yml/badge.svg)

A production-grade ML model serving platform — from model registration to real-time LLM inference with A/B routing, streaming output, and GPU containerization.

**Key features:** Model registry & versioning · Weighted A/B traffic routing with one-click rollback · vLLM integration via thin HTTP proxy · SSE streaming through full proxy chain · GPU Docker containers with multi-stage builds

---

## Architecture

```
┌──────────┐
│  Client  │
│(curl/UI) │
└────┬─────┘
     │
     ▼
┌──────────────────────────────────────────┐
│           Gateway  :8002                 │
│  ┌─────────────┐  ┌──────────────────┐   │
│  │ ML Routing   │  │ LLM Routing     │   │
│  │ A/B Testing  │  │ SSE Streaming   │   │
│  │ Rollback     │  │ Chat Forwarding │   │
│  └──────┬──────┘  └───────┬──────────┘   │
└─────────┼──────────────────┼─────────────┘
          │                  │
     ┌────▼────┐       ┌────▼──────┐     ┌───────────┐
     │ML Worker│       │LLM Worker │────▶│   vLLM    │
     │  :8001  │       │   :8003   │     │   :8100   │
     │ sklearn │       │ HTTP Proxy│     │Qwen2.5-1.5B│
     └─────────┘       └───────────┘     │   (GPU)   │
                                         └───────────┘
     ┌─────────┐
     │Registry │
     │  :8000  │
     │ SQLite  │
     │ + Files │
     └─────────┘
```

| Component       | Description                                        | Status      |
|-----------------|----------------------------------------------------|-------------|
| **Registry**    | Model metadata, version management, file storage   | ✅ Complete |
| **ML Worker**   | sklearn model loading + in-process inference       | ✅ Complete |
| **Gateway**     | Request routing, A/B traffic splitting, rollback   | ✅ Complete |
| **LLM Worker**  | vLLM HTTP proxy with streaming support             | ✅ Complete |
| **vLLM Engine** | GPU inference backend (Qwen2.5-1.5B-Instruct)     | ✅ Complete |
| **CI/CD**       | GitHub Actions: pytest + Docker build verification | ✅ Complete |
| **Monitoring**  | Prometheus + Grafana observability                 | 🔲 Planned  |
| **K8s Deploy**  | Helm chart + HPA + GPU scheduling                  | 🔲 Planned  |

---

## Quick Start

```bash
# Local development
pip install -r requirements.txt
uvicorn registry.app:app --reload --port 8000   # Registry
uvicorn serving.app:app --reload --port 8001     # ML Worker
uvicorn serving.gateway_app:app --reload --port 8002  # Gateway

# Docker (CPU services)
docker compose up -d

# Docker (full stack with GPU)
docker compose -f docker-compose.yml -f docker-compose.gpu.yml up -d

# Run tests
pytest tests/ -v
```

> **Swagger UI** available at `http://localhost:8000/docs`, `http://localhost:8001/docs`, `http://localhost:8002/docs`

---

## Quick Demo

<details>
<summary><b>1. Register a model and run prediction</b></summary>

```bash
GATEWAY="http://localhost:8002/api/v1/gateway"

# Register worker in Gateway
curl -X POST "$GATEWAY/register" \
  -H "Content-Type: application/json" \
  -d '{"model_name": "iris-classifier", "version": "v1", "worker_url": "http://serving:8001"}'

# Run prediction through Gateway
curl -X POST "$GATEWAY/predict/iris-classifier/v1" \
  -H "Content-Type: application/json" \
  -d '{"inputs": [[5.1, 3.5, 1.4, 0.2]]}'
# → {"prediction": [0], "model": "iris-classifier", "version": "v1"}
```
</details>

<details>
<summary><b>2. Configure A/B testing with rollback</b></summary>

```bash
# Set 90/10 traffic split between v1 and v2
curl -X POST "$GATEWAY/ab/configure" \
  -H "Content-Type: application/json" \
  -d '{
    "model_name": "iris-classifier",
    "backends": [
      {"version": "v1", "weight": 90, "worker_url": "http://serving:8001"},
      {"version": "v2", "weight": 10, "worker_url": "http://serving:8001"}
    ]
  }'

# Predict — Gateway automatically routes by weight
curl -X POST "$GATEWAY/ab/predict/iris-classifier" \
  -H "Content-Type: application/json" \
  -d '{"inputs": [[5.1, 3.5, 1.4, 0.2]]}'
# → {"prediction": [0], "_routed_to": {"version": "v1", ...}}

# One-click rollback: send 100% traffic to v1
curl -X POST "$GATEWAY/ab/rollback/iris-classifier" \
  -H "Content-Type: application/json" \
  -d '{"target_version": "v1", "reason": "v2 accuracy regression"}'
```
</details>

<details>
<summary><b>3. Chat with LLM — streaming & non-streaming (requires GPU)</b></summary>

```bash
# Register LLM worker
curl -X POST "$GATEWAY/register" \
  -H "Content-Type: application/json" \
  -d '{"model_name": "qwen2.5-1.5b", "version": "v1", "worker_url": "http://llm-worker:8003"}'

# Non-streaming chat
curl -X POST "$GATEWAY/chat/qwen2.5-1.5b/v1" \
  -H "Content-Type: application/json" \
  -d '{"messages": [{"role": "user", "content": "What is Docker?"}], "max_tokens": 100}'

# Streaming chat (SSE) — tokens arrive incrementally
curl -N "$GATEWAY/chat/qwen2.5-1.5b/v1/stream" \
  -H "Content-Type: application/json" \
  -d '{"messages": [{"role": "user", "content": "Explain KV Cache in 3 sentences"}], "max_tokens": 150}'
# → data: {"choices": [{"delta": {"content": "KV"}}]}
# → data: {"choices": [{"delta": {"content": " Cache"}}]}
# → ...
# → data: [DONE]
```
</details>

---

## Key Design Decisions

| Decision | Choice | Why |
|----------|--------|-----|
| Architecture | 4 microservices + vLLM | Different scaling profiles: Registry is low-frequency, ML Worker is CPU-bound, LLM Worker is I/O-bound, vLLM is GPU-bound |
| LLM integration | Thin HTTP proxy | Decouples Gateway from vLLM specifics; swap to TensorRT-LLM or Triton without touching Gateway |
| Traffic management | Weighted A/B routing | Gradual rollout (90/10 → 50/50) with rollback history, not binary blue-green |
| Streaming | SSE end-to-end | `async for` + `yield` at every layer; zero buffering from vLLM to client |
| Error mapping | Custom exceptions | `VLLMConnectionError` → 503, `VLLMTimeoutError` → 504, `VLLMResponseError` → 502 |
| Storage | Local FS + S3 interface | Abstract `StorageBackend` base; production swap = config change |
| Database | SQLite | Zero-dependency dev; schema portable to PostgreSQL |

---

## API Reference

> All Registry endpoints (except `/health`) require `X-API-Key` header: `-H "X-API-Key: dev-api-key"`

<details>
<summary><b>Registry — Models & Versions</b></summary>

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST   | `/api/v1/models` | Register a new model |
| GET    | `/api/v1/models` | List all models (with filtering) |
| GET    | `/api/v1/models/{name}` | Get model details |
| PATCH  | `/api/v1/models/{name}` | Update model metadata |
| DELETE | `/api/v1/models/{name}` | Delete model and all versions |
| POST   | `/api/v1/models/{name}/versions` | Create a new version |
| GET    | `/api/v1/models/{name}/versions` | List all versions |
| GET    | `/api/v1/models/{name}/versions/{ver}` | Get version details |
| POST   | `/api/v1/models/{name}/versions/{ver}/upload` | Upload model file |
| PUT    | `/api/v1/models/{name}/versions/{ver}/default` | Set as default version |
</details>

<details>
<summary><b>Gateway — Routing, A/B Testing & LLM</b></summary>

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST   | `/api/v1/gateway/register` | Register a worker |
| DELETE | `/api/v1/gateway/routes/{model}/{version}` | Remove a worker |
| GET    | `/api/v1/gateway/routes` | List all routes |
| POST   | `/api/v1/gateway/predict/{model}/{version}` | Forward prediction |
| POST   | `/api/v1/gateway/chat/{model}/{version}` | Forward LLM chat |
| POST   | `/api/v1/gateway/chat/{model}/{version}/stream` | Forward LLM chat (SSE) |
| POST   | `/api/v1/gateway/ab/configure` | Set A/B routing weights |
| POST   | `/api/v1/gateway/ab/predict/{model}` | Predict with A/B routing |
| POST   | `/api/v1/gateway/ab/rollback/{model}` | One-click rollback |
| GET    | `/api/v1/gateway/ab` | List all A/B configs |
| GET    | `/api/v1/gateway/ab/{model}` | Get A/B config |
| DELETE | `/api/v1/gateway/ab/{model}` | Remove A/B config |
| GET    | `/api/v1/gateway/ab/rollback-history/{model}` | View rollback history |
| GET    | `/api/v1/gateway/health/{model}/{version}` | Check worker health |
</details>

<details>
<summary><b>LLM Worker</b></summary>

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET    | `/health` | Health check (includes vLLM backend status) |
| POST   | `/api/v1/chat/completions` | Chat completion (stream or non-stream) |
</details>

---

## CI/CD

GitHub Actions runs on every push and PR ([`.github/workflows/ci.yml`](.github/workflows/ci.yml)):

- **Test** — `pytest tests/ -v` on Python 3.11 with pip caching
- **Docker Build** — validates `Dockerfile.registry` builds successfully
- **Concurrency** — auto-cancels stale runs on the same branch

---

## Roadmap

- [x] **Phase 1** — Model Registry: metadata CRUD + version management + file storage
- [x] **Phase 2** — Serving: sklearn model loading + Gateway request routing
- [x] **Phase 3** — A/B Testing: weighted traffic splitting + one-click rollback
- [x] **Phase 4** — LLM Integration: vLLM backend + streaming output + GPU containers
- [ ] **Phase 5** — Monitoring: Prometheus metrics + Grafana dashboards
- [ ] **Phase 6** — K8s Deployment: Helm chart + HPA + GPU scheduling

---

## What I Learned

I built this project as part of my transition from C# backend engineering (DevProd / Build Infrastructure) to AI Infrastructure. Key lessons:

1. **LLM serving ≠ traditional ML serving.** sklearn prediction is microsecond-level CPU math; LLM generation is seconds-long GPU autoregression. This 1000x latency gap drives every architectural decision — streaming, timeouts, error handling.

2. **The thin proxy pattern pays off.** Keeping LLM Worker as a pure HTTP proxy means Gateway is completely unaware of vLLM internals (tokenization, KV Cache, model weights). A/B routing between sklearn and LLM models works with zero Gateway code changes.

3. **GPU containerization has sharp edges.** NVIDIA Container Toolkit compatibility, 15GB+ base images, 10-minute health check start periods for model loading — none of this is in Docker's getting started guide.

4. **SSE through a proxy chain is harder than it looks.** Each layer (vLLM → LLM Worker → Gateway → Client) needs `async for` + `yield`, `Transfer-Encoding: chunked`, and `X-Accel-Buffering: no`. One synchronous read anywhere in the chain defeats streaming entirely.

---

## Tech Stack

| Layer | Technology |
|-------|------------|
| API Framework | FastAPI |
| Data Validation | Pydantic v2 |
| Database | SQLite (→ PostgreSQL) |
| Model Storage | Local FS (→ S3-compatible) |
| Containerization | Docker + Docker Compose |
| Testing | pytest |
| LLM Inference | vLLM |
| Monitoring | Prometheus + Grafana (Planned) |
| Orchestration | Kubernetes (Planned) |

## License

MIT
