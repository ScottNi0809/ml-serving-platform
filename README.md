# ML Model Serving Platform

A production-grade platform for deploying and serving ML models — from model registration to real-time inference with monitoring.

## Architecture

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   Client     │────▶│   Gateway   │────▶│   Worker    │
│  (curl/UI)   │     │  (routing)  │     │ (inference) │
└─────────────┘     └─────────────┘     └─────────────┘
                           │
                    ┌──────┴──────┐
                    │  Registry   │
                    │  (metadata  │
                    │  + storage) │
                    └─────────────┘
```

### Components

| Component | Description | Status |
|-----------|-------------|--------|
| **Registry** | Model metadata, version management, file storage | ✅ Phase 1 |
| **Gateway** | Request routing, A/B traffic splitting, rollback | 🔲 Phase 2 |
| **Worker** | Model loading + inference execution | 🔲 Phase 2 |
| **LLM Worker** | vLLM integration for LLM serving | 🔲 Phase 3 |
| **Monitoring** | Prometheus + Grafana observability | 🔲 Phase 4 |

## Quick Start

### Prerequisites

- Python 3.11+
- Docker & Docker Compose

### Local Development (without Docker)

```bash
# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
.venv\Scripts\activate     # Windows

# Install dependencies
pip install -r requirements.txt

# Run the registry service
uvicorn registry.app:app --reload --host 0.0.0.0 --port 8000

# Run tests
pytest tests/ -v
```

### Docker Compose

```bash
# Production mode
docker compose up --build

# Development mode (with hot-reload)
docker compose -f docker-compose.yml -f docker-compose.dev.yml up --build
```

### Verify

```bash
# Health check
curl http://localhost:8000/health

# API docs (Swagger UI)
open http://localhost:8000/docs
```

## API Reference

### Models

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/models` | Register a new model |
| GET | `/api/v1/models` | List all models (with filtering) |
| GET | `/api/v1/models/{name}` | Get model details |
| PATCH | `/api/v1/models/{name}` | Update model metadata |
| DELETE | `/api/v1/models/{name}` | Delete model and all versions |

### Versions

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/models/{name}/versions` | Create a new version |
| GET | `/api/v1/models/{name}/versions` | List all versions |
| GET | `/api/v1/models/{name}/versions/{ver}` | Get version details |
| POST | `/api/v1/models/{name}/versions/{ver}/upload` | Upload model file |
| PUT | `/api/v1/models/{name}/versions/{ver}/default` | Set as default version |

### Authentication

All API endpoints (except `/health`) require the `X-API-Key` header.

```bash
curl -H "X-API-Key: dev-api-key" http://localhost:8000/api/v1/models
```

## Example Workflow

```bash
API_KEY="dev-api-key"
BASE="http://localhost:8000/api/v1"

# 1. Register a model
curl -X POST "$BASE/models" \
  -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"name": "bert-sentiment", "framework": "pytorch", "tags": ["nlp"]}'

# 2. Create a version
curl -X POST "$BASE/models/bert-sentiment/versions" \
  -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"version": "1.0.0", "description": "Initial release"}'

# 3. Upload model file
curl -X POST "$BASE/models/bert-sentiment/versions/1.0.0/upload" \
  -H "X-API-Key: $API_KEY" \
  -F "file=@model.pt"

# 4. Check model status
curl -H "X-API-Key: $API_KEY" "$BASE/models/bert-sentiment"
```

## Project Roadmap

- [x] **Phase 1** — Model Registry: metadata CRUD + version management + file upload
- [ ] **Phase 2** — Serving Worker: load models + execute inference
- [ ] **Phase 3** — Gateway: A/B routing + traffic splitting + rollback
- [ ] **Phase 4** — LLM Integration: vLLM backend + streaming output
- [ ] **Phase 5** — Monitoring: Prometheus metrics + Grafana dashboards
- [ ] **Phase 6** — K8s Deployment: Helm chart + HPA + GPU scheduling

## Tech Stack

| Layer | Technology |
|-------|------------|
| API Framework | FastAPI |
| Data Validation | Pydantic v2 |
| Database | SQLite (→ PostgreSQL) |
| Model Storage | Local FS (→ S3-compatible) |
| Containerization | Docker + Docker Compose |
| Testing | pytest |
| LLM Inference | vLLM (Phase 4) |
| Monitoring | Prometheus + Grafana (Phase 5) |
| Orchestration | Kubernetes (Phase 6) |

## License

MIT
