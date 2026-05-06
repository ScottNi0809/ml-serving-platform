# ML Model Serving Platform

[![中文文档](https://img.shields.io/badge/lang-中文-red)](README.zh-CN.md)

![CI](https://github.com/ScottNi0809/ml-serving-platform/actions/workflows/ci.yml/badge.svg)

An AI infrastructure portfolio project that turns trained ML and LLM models into versioned, observable, containerized inference services. It covers the production-serving path from model registry and worker routing to A/B rollout, rollback, vLLM proxying, SSE streaming, Prometheus/Grafana monitoring, load testing, and Kubernetes deployment templates.

**Core capabilities:** Model registry and versioning · sklearn inference worker · Gateway routing · Weighted A/B traffic splitting · One-click rollback · vLLM-backed chat completions · End-to-end SSE streaming · Docker/GPU containers · Prometheus/Grafana · Helm/K8s manifests

### Quick Links

| Resource | Path |
|----------|------|
| End-to-end demo | [docs/demo.md](docs/demo.md) |
| Benchmark report | [docs/benchmark.md](docs/benchmark.md) |
| Helm chart | [chart/](chart/) |
| CI pipeline | [.github/workflows/ci.yml](.github/workflows/ci.yml) |
| Grafana dashboard | [monitoring/grafana/](monitoring/grafana/) |

### Run Modes

| Mode | Command | What it starts |
|------|---------|----------------|
| CPU | `docker compose up --build -d` | Registry, ML Worker, Gateway |
| Monitoring | `docker compose -f docker-compose.yml -f docker-compose.monitor.yml up --build -d` | + Prometheus, Grafana |
| GPU / LLM | `docker compose -f docker-compose.yml -f docker-compose.gpu.yml up --build -d` | + LLM Worker, vLLM (requires NVIDIA GPU) |

---

## Why This Project

This project is built as a backend-to-AI-infra transition case study. It focuses on problems AI infrastructure teams actually own: safely shipping model versions, routing inference traffic, isolating GPU-backed LLM serving behind a stable API, measuring latency and errors, and preparing services for container orchestration.

Resume-ready proof points:

| Area | Evidence |
|------|----------|
| End-to-end serving | Registry -> ML Worker -> Gateway prediction path with versioned sklearn models |
| Safe rollout | Dynamic A/B route configuration, weighted selection, and rollback history |
| Real LLM serving | vLLM OpenAI-compatible backend behind a thin LLM Worker proxy |
| Streaming | SSE chunks flow through vLLM -> LLM Worker -> Gateway -> client without buffering |
| Observability | Prometheus HTTP/inference metrics, Grafana dashboard, alert rules |
| Performance | Locust benchmark reaches ~454 RPS at 200 concurrent users with 0% errors |
| Deployment | Docker Compose for CPU/GPU stacks, Helm chart with HPA, Ingress, PVC, GPU scheduling templates |
| Quality gates | pytest, Docker build validation, Helm lint/template, kubeconform in GitHub Actions |

---

## Architecture

```text
┌──────────┐
│  Client  │
│ curl/API │
└────┬─────┘
     │
     ▼
┌──────────────────────────────────────────┐
│              Gateway :8002               │
│  ┌───────────────┐  ┌─────────────────┐  │
│  │ ML Routing    │  │ LLM Routing     │  │
│  │ A/B Testing   │  │ SSE Streaming   │  │
│  │ Rollback      │  │ Chat Forwarding │  │
│  └───────┬───────┘  └───────┬─────────┘  │
└──────────┼───────────────────┼───────────┘
           │                   │
      ┌────▼────┐       ┌──────▼──────┐     ┌───────────┐
      │ML Worker│       │ LLM Worker  │────▶│   vLLM    │
      │  :8001  │       │   :8003     │     │   :8100   │
      │ sklearn │       │ HTTP Proxy  │     │ Qwen 1.5B │
      └─────────┘       └─────────────┘     │   GPU     │
                                            └───────────┘
      ┌─────────┐
      │Registry │
      │  :8000  │
      │ SQLite  │
      │ + Files │
      └─────────┘

      Prometheus :9090  +  Grafana :3000
```

| Component | Description | Status |
|-----------|-------------|--------|
| **Registry** | Model metadata, semantic versions, default version, file upload/download | Complete |
| **ML Worker** | sklearn model loading, in-process prediction, model unload/list APIs | Complete |
| **Gateway** | Worker registration, route lookup, prediction forwarding, health checks | Complete |
| **A/B Router** | Weighted backend selection, dynamic rollout config, rollback history | Complete |
| **LLM Worker** | Thin HTTP proxy to vLLM with custom timeout/connection/error mapping | Complete |
| **vLLM Engine** | GPU container for Qwen2.5-1.5B-Instruct via OpenAI-compatible API | Complete |
| **Monitoring** | Prometheus middleware, inference metrics, Grafana dashboard, alerts | Complete |
| **CI/CD** | pytest, Docker build, Helm lint/template, kubeconform validation | Complete |
| **K8s/Helm** | Deployments, Services, PVCs, HPA, Ingress, GPU resource templates | Production-style templates |

---

## Quick Start

### CPU Stack

```bash
# Start Registry, ML Worker, and Gateway
docker compose up --build -d

# Run the end-to-end CPU demo
bash scripts/demo.sh

# Run tests
pytest tests/ -v
```

Services:

| Service | URL |
|---------|-----|
| Registry | http://localhost:8000 |
| ML Worker | http://localhost:8001 |
| Gateway | http://localhost:8002 |
| Swagger UI | http://localhost:8000/docs, http://localhost:8001/docs, http://localhost:8002/docs |

### Monitoring Stack

```bash
docker compose -f docker-compose.yml -f docker-compose.monitor.yml up --build -d
bash scripts/demo.sh
```

Then open:

| Tool | URL | Default login |
|------|-----|---------------|
| Prometheus | http://localhost:9090 | none |
| Grafana | http://localhost:3000 | admin / admin |

### GPU / LLM Stack

Requires NVIDIA Container Toolkit and a GPU with enough VRAM for the configured model.

```bash
docker compose -f docker-compose.yml -f docker-compose.gpu.yml up --build -d
RUN_GPU_DEMO=1 bash scripts/demo.sh
```

The GPU stack adds:

| Service | URL |
|---------|-----|
| LLM Worker | http://localhost:8003 |
| vLLM | http://localhost:8100 |

Full demo notes are in [docs/demo.md](docs/demo.md).

---

## Demo Flow

The runnable demo script covers the resume-facing CPU path:

1. Verify Registry, ML Worker, and Gateway health.
2. Train or reuse a local Iris sklearn model artifact.
3. Register `iris-classifier` in the Registry and create versions `1.0.0` and `2.0.0`.
4. Upload the model artifact to Registry metadata/file storage.
5. Load both versions into the ML Worker.
6. Register both worker routes in the Gateway.
7. Send prediction traffic through the Gateway.
8. Configure 90/10 A/B routing and show routed responses.
9. Roll back to version `1.0.0` and print rollback history.
10. Optionally register the LLM worker and call non-streaming plus streaming chat.

```bash
bash scripts/demo.sh
```

The demo is intentionally CPU-first so it can be run quickly by reviewers without a GPU. The LLM path is enabled separately with `RUN_GPU_DEMO=1`.

---

## Monitoring

The platform exposes service and inference metrics through Prometheus middleware:

| Metric | Type | Purpose |
|--------|------|---------|
| `http_requests_total` | Counter | Request volume by service, method, endpoint, status |
| `http_request_duration_seconds` | Histogram | HTTP latency distribution by service and endpoint |
| `http_active_requests` | Gauge | Current in-flight requests by service |
| `inference_requests_total` | Counter | Gateway inference forwarding outcomes by model/version/status |
| `inference_duration_seconds` | Histogram | End-to-end Gateway -> Worker inference latency |

Alert rules cover high 5xx error rate, scrape target downtime, P95 latency spikes, throughput drops, and high active request saturation.

![Grafana Dashboard Demo](./demo/grafana-dashboard.png)

---

## Performance

Benchmark results from Locust load testing are documented in [docs/benchmark.md](docs/benchmark.md).

| Concurrent Users | Total RPS | P50 | P95 | P99 | Error Rate |
|------------------|-----------|-----|-----|-----|------------|
| 10 | 23.88 | 5ms | 9ms | 16ms | 0% |
| 50 | 120.79 | 5ms | 11ms | 18ms | 0% |
| 100 | 239.00 | 4ms | 12ms | 22ms | 0% |
| 200 | 453.77 | 4ms | 17ms | 30ms | 0% |

Observed bottleneck: SQLite write contention plus a single Uvicorn worker affects write-heavy model registration latency first. This is why PostgreSQL and connection pooling are the next production-hardening step.

---

## Kubernetes And Helm

The chart deploys Registry, ML Worker, Gateway, optional LLM Worker, and optional vLLM. It includes resource requests/limits, PVCs, HPA templates, Ingress, and GPU resource limits for vLLM.

> **`chart/` vs `k8s/`:** The `chart/` directory is the Helm chart (templated, parameterized). The `k8s/` directory contains plain Kubernetes manifests for quick `kubectl apply` without Helm.

```bash
# Local/minikube-style rendering
helm lint chart/ -f chart/values-dev.yaml
helm template ml-dev chart/ -f chart/values-dev.yaml

# Production-style rendering
helm lint chart/ -f chart/values-prod.yaml
helm template ml-prod chart/ -f chart/values-prod.yaml
```

Important production notes:

- `registry.persistence` uses PVCs for SQLite data and model files in the default chart.
- Registry HPA is disabled in `values-prod.yaml` because SQLite on a ReadWriteOnce PVC is not HA storage.
- Enable Registry horizontal scaling only after moving metadata to PostgreSQL and artifacts to S3/MinIO-compatible storage.
- vLLM GPU scheduling requires NVIDIA Device Plugin on the cluster.
- Ingress TLS requires a pre-created certificate secret or cert-manager integration.

---

## API Reference

Registry endpoints require `X-API-Key`. The development default accepts `dev-api-key` for local demos.

<details>
<summary><b>Registry - Models & Versions</b></summary>

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/models` | Register a model |
| GET | `/api/v1/models` | List models |
| GET | `/api/v1/models/{name}` | Get model details |
| PATCH | `/api/v1/models/{name}` | Update model metadata |
| DELETE | `/api/v1/models/{name}` | Delete model and versions |
| POST | `/api/v1/models/{name}/versions` | Create a version |
| GET | `/api/v1/models/{name}/versions` | List versions |
| GET | `/api/v1/models/{name}/versions/{ver}` | Get version details |
| POST | `/api/v1/models/{name}/versions/{ver}/upload` | Upload model artifact |
| GET | `/api/v1/models/{name}/versions/{ver}/download` | Download model artifact |
| PUT | `/api/v1/models/{name}/versions/{ver}/default` | Set default version |

</details>

<details>
<summary><b>Gateway - Routing, A/B Testing & LLM</b></summary>

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/gateway/register` | Register a worker route |
| DELETE | `/api/v1/gateway/routes/{model}/{version}` | Remove a worker route |
| GET | `/api/v1/gateway/routes` | List routes |
| POST | `/api/v1/gateway/predict/{model}/{version}` | Forward ML prediction |
| POST | `/api/v1/gateway/chat/{model}/{version}` | Forward LLM chat |
| POST | `/api/v1/gateway/chat/{model}/{version}/stream` | Forward LLM chat as SSE |
| POST | `/api/v1/gateway/ab/configure` | Configure weighted A/B routing |
| POST | `/api/v1/gateway/ab/predict/{model}` | Predict through A/B router |
| POST | `/api/v1/gateway/ab/rollback/{model}` | Shift 100% traffic to one version |
| GET | `/api/v1/gateway/ab` | List A/B configs |
| GET | `/api/v1/gateway/ab/{model}` | Get A/B config |
| DELETE | `/api/v1/gateway/ab/{model}` | Remove A/B config |
| GET | `/api/v1/gateway/ab/rollback-history/{model}` | View rollback history |
| GET | `/api/v1/gateway/health/{model}/{version}` | Check registered worker health |

</details>

<details>
<summary><b>LLM Worker</b></summary>

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Health check including vLLM backend status |
| POST | `/api/v1/chat/completions` | Chat completion, streaming or non-streaming |

</details>

---

## Key Design Decisions

| Decision | Choice | Why |
|----------|--------|-----|
| Service split | Registry, ML Worker, Gateway, LLM Worker, vLLM | Different state, scaling, and hardware profiles |
| LLM integration | Thin HTTP proxy over vLLM OpenAI API | Gateway stays independent from engine-specific details |
| Rollout model | Weighted A/B routing with rollback history | Supports gradual rollout and quick recovery |
| Streaming | SSE end-to-end | Simple client support and incremental token delivery |
| Error mapping | 503 connection, 504 timeout, 502 backend response | Makes infrastructure failure modes visible to callers |
| Observability | Prometheus middleware plus Grafana dashboard | Captures traffic, latency, errors, saturation |
| Local database | SQLite | Zero-dependency development path; explicit PostgreSQL next step |
| Artifact storage | Local FS abstraction with S3 extension point | Keeps local demo simple while preserving production direction |

---

## CI/CD

GitHub Actions runs on every push and pull request through [.github/workflows/ci.yml](.github/workflows/ci.yml):

- `pytest tests/ -v` on Python 3.11 with pip caching.
- Helm lint and template validation for dev/prod values.
- kubeconform validation for rendered and raw Kubernetes manifests.
- Docker build validation for the Registry image.
- Concurrency cancellation for stale workflow runs on the same branch.

---

## Roadmap

- [x] **Phase 1** - Model Registry: metadata CRUD, versions, default version, file storage
- [x] **Phase 2** - Serving: sklearn loading, prediction, Gateway routing
- [x] **Phase 3** - Traffic Management: weighted A/B split, rollback, history
- [x] **Phase 4** - LLM Integration: vLLM backend, LLM proxy, streaming output, GPU containers
- [x] **Phase 5** - Observability: Prometheus metrics, Grafana dashboard, alert rules, benchmark report
- [x] **Phase 6** - Deployment Templates: Docker Compose, Helm chart, HPA, Ingress, GPU scheduling templates
- [ ] **Next** - PostgreSQL metadata store, Redis cache, OpenTelemetry tracing, S3/MinIO artifact backend, rate limiting, vLLM circuit breaker

---

## Production Boundaries

This repository is intentionally optimized for local reproducibility and interview discussion. The current defaults are enough to demonstrate system design and serving workflows, but these changes are recommended before a real production deployment:

| Boundary | Current state | Production direction |
|----------|---------------|----------------------|
| Registry metadata | SQLite | PostgreSQL with migrations and connection pooling |
| Model artifacts | Local filesystem | S3/MinIO-compatible object storage |
| Registry scaling | Single writer, HPA disabled in prod values | Enable after HA metadata/artifact storage is introduced |
| Authentication | Development API key | External secret management, scoped keys or JWT/RBAC |
| Tracing | Metrics and logs only | OpenTelemetry spans across Gateway, Worker, and vLLM |
| Resilience | Explicit vLLM error mapping | Retry budget, circuit breaker, backpressure/rate limiting |

---

## What I Learned

1. **LLM serving is a different latency class from classic ML serving.** sklearn prediction is millisecond-level CPU work; LLM generation is GPU-bound autoregressive decoding. That difference drives streaming, timeout, and observability design.
2. **A thin proxy keeps infrastructure flexible.** The Gateway does not need to know vLLM tokenization or scheduler details, so the backend can later move to TensorRT-LLM, Triton, or another engine.
3. **Safe rollout is an infrastructure feature.** A/B routing and rollback are not product polish; they are how model teams ship new versions without turning every release into a flag day.
4. **Observability turns a demo into an engineering system.** QPS, latency percentiles, 5xx rate, and active requests make performance and failure modes discussable with concrete evidence.
5. **Kubernetes support is more than YAML.** HPA, PVCs, GPU scheduling, ingress, and storage caveats all have to line up with the actual state model.

---

## Tech Stack

| Layer | Technology |
|-------|------------|
| API Framework | FastAPI |
| Data Validation | Pydantic v2 |
| Metadata Store | SQLite local default, PostgreSQL planned |
| Model Storage | Local FS default, S3/MinIO planned |
| Classic ML | scikit-learn, joblib |
| LLM Inference | vLLM |
| Streaming | Server-Sent Events |
| Observability | prometheus-client, Prometheus, Grafana |
| Load Testing | Locust |
| Containerization | Docker, Docker Compose, NVIDIA runtime |
| Orchestration | Kubernetes manifests, Helm |
| Testing | pytest, httpx ASGITransport |

## License

MIT
