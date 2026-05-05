# ML Serving Platform Helm Chart

This chart deploys the ML Serving Platform application stack:

- Registry (`8000`)
- Classic ML worker / serving service (`8001`)
- Gateway (`8002`)
- LLM worker proxy (`8003`)
- vLLM backend (`8100`, optional GPU workload)

## Quick Start

```bash
# Local minikube/dev mode
helm install ml-dev ./chart -f chart/values-dev.yaml

# Production-style rendering
helm template ml-prod ./chart -f chart/values-prod.yaml
```

## Configuration

See [values.yaml](values.yaml) for all available options.

### Key Parameters

| Parameter | Description | Default |
|-----------|-------------|---------|
| `registry.replicas` | Registry service replicas | `1` |
| `mlWorker.replicas` | Classic ML worker replicas | `1` |
| `llmWorker.enabled` | Enable LLM worker proxy | `true` |
| `gateway.replicas` | Gateway service replicas | `1` |
| `vllm.enabled` | Enable vLLM service | `true` |
| `autoscaling.enabled` | Enable HPA | `false` |
| `ingress.enabled` | Enable Ingress | `false` |

## Validation

```bash
helm lint chart/
helm lint chart/ -f chart/values-dev.yaml
helm lint chart/ -f chart/values-prod.yaml

helm template dev chart/ -f chart/values-dev.yaml
helm template prod chart/ -f chart/values-prod.yaml
```

## Important Notes

- Local development defaults to `imagePullPolicy: Never`; build and load images into minikube first.
- Production values assume images are pushed to a real registry. Update `global.imageRegistry` before installing.
- HPA requires Metrics Server.
- Registry HPA is disabled in production-style values because the default registry storage uses SQLite on a ReadWriteOnce PVC. Enable it only after moving Registry state to HA storage.
- Ingress requires an Ingress Controller such as ingress-nginx.
- TLS requires the referenced secret to exist before enabling `ingress.tls`.
- vLLM requires a GPU node and NVIDIA Device Plugin when `vllm.gpu.enabled=true`.
