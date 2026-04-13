"""
Prometheus HTTP 中间件
=====================

自动为每个 HTTP 请求记录指标，挂载到 FastAPI 后无需逐路由埋点。
跳过 /metrics、/health 等路径，避免自我监控噪音。
"""

import time

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from serving.metrics import ACTIVE_REQUESTS, REQUEST_COUNT, REQUEST_LATENCY

# 不需要监控的路径
SKIP_PATHS = {"/metrics", "/health", "/docs", "/openapi.json"}


class PrometheusMiddleware(BaseHTTPMiddleware):
    """自动记录 HTTP 请求的 Counter + Histogram + Gauge 指标"""

    def __init__(self, app, service_name: str = "unknown"):
        super().__init__(app)
        self.service_name = service_name

    async def dispatch(self, request: Request, call_next):
        if request.url.path in SKIP_PATHS:
            return await call_next(request)
        
        endpoint = self._normalize_path(request.url.path)
        ACTIVE_REQUESTS.labels(service=self.service_name).inc()
        start = time.perf_counter()

        try:
            response = await call_next(request)
            status = str(response.status_code)
        except Exception:
            status = "500"
            raise
        finally:
            elapsed = time.perf_counter() - start
            REQUEST_COUNT.labels(
                service = self.service_name,
                method = request.method,
                endpoint = endpoint,
                status = status,
            ).inc()
            REQUEST_LATENCY.labels(
                service = self.service_name,
                endpoint = endpoint,
            ).observe(elapsed)
            ACTIVE_REQUESTS.labels(service = self.service_name).dec()

        return response
    
    @staticmethod
    def _normalize_path(path: str) -> str:
        """
        将动态 URL 路径参数替换为占位符，防止 label cardinality 爆炸。

        /api/v1/models/resnet50/versions/3
        → /api/v1/models/{name}/versions/{version}
        """
        parts = path.strip("/").split("/")
        normalized = []
        i = 0
        while i < len(parts):
            part = parts[i]
            if part in ("models", "routes") and i + 1 < len(parts):
                normalized.append(part)
                normalized.append("{name}")
                i += 2
                if i + 1 < len(parts) and parts[i] == "versions":
                    normalized.append("versions")
                    normalized.append("{version}")
                    i += 2
                continue
            normalized.append(part)
            i += 1
        return "/" + "/".join(normalized)

        