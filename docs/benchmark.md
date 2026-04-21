# Performance Benchmark Report

> Last updated: 2026-04-21  
> Test tool: Locust 2.x  
> Environment: [DELL Precision 5570]

## Test Environment

| Component | Specification |
|-----------|--------------|
| Machine | [DELL Precision 5570] |
| CPU | [14] cores |
| Memory | [64GB] |
| OS | [Windows11] |
| Docker | [29.4.0] |
| Python | 3.11 |
| Architecture | Registry + Serving + Gateway (docker compose) |
| Database | SQLite |

## Test Scenarios

Two scenarios with weighted task distribution:

**Read-Heavy (75% of users):** 40% List Models, 30% Get Routes, 20% Health, 10% Detail  
**Write-Mixed (25% of users):** 40% List, 30% Register, 20% Routes, 10% Health

## Results Summary

### Throughput Scaling

| Concurrent Users | Total RPS | P50 (ms) | P95 (ms) | P99 (ms) | Error Rate |
|:---:|:---:|:---:|:---:|:---:|:---:|
| 10 (baseline) | 23.88 | 5 | 9 | 16 | 0% |
| 50 (load) | 120.79 | 5 | 11 | 18 | 0% |
| 100 (stress) | 239.00 | 4 | 12 | 22 | 0% |
| 200 (stress) | 453.77 | 4 | 17 | 30 | 0% |

### Per-Endpoint Breakdown (50 users)

| Endpoint | RPS | P50 (ms) | P95 (ms) | P99 (ms) |
|----------|:---:|:---:|:---:|:---:|
| GET /api/v1/models | 53.66 | 6 | 12 | 18 |
| GET /api/v1/gateway/routes | 37.80 | 4 | 7 | 11 |
| POST /api/v1/models | 3.82 | 12 | 21 | 26 |
| GET /health | 25.52 | 4 | 7 | 11 |

## Analysis

### Observations
1. QPS scales near-linearly up to 200 concurrent users (23.88 → 120.79 → 239.00 → 453.77 RPS)
2. Beyond 100 users, P99 latency increases more noticeably (22ms → 30ms) while QPS continues scaling
3. Error rate remains 0% across all test tiers (10 / 50 / 100 / 200 users)

### Bottleneck
- Primary bottleneck: SQLite write contention + single Uvicorn worker
- Evidence: POST /api/v1/models [CREATE] P99 grows from 21ms (10 users) → 26ms (50) → 43ms (100) → 54ms (200), the steepest latency increase among all endpoints

### Optimization Opportunities
1. **Increase Uvicorn workers** (1→4): Expected ~3x throughput with multi-core
2. **Add Redis cache** for model list: Expected ~5x improvement for read endpoints  
3. **Horizontal scaling** via K8s HPA: Linear scaling with replica count

## How to Reproduce

```bash
# Start services {#start-services  data-source-line="286"}
docker compose up -d

# Run benchmark {#run-benchmark  data-source-line="289"}
./benchmarks/run_benchmark.sh

# Or with custom parameters {#or-with-custom-parameters  data-source-line="292"}
USERS=50 SPAWN_RATE=10 RUN_TIME=120s ./benchmarks/run_benchmark.sh
``` {data-source-line="294"}