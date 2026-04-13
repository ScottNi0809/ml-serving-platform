"""
Prometheus 指标定义
==================

所有指标集中定义在这个模块，其他模块通过 import 使用。

设计原则：
- 指标对象是模块级别的单例（prometheus_client 要求同名指标不能重复创建）
- 标签按 Four Golden Signals 设计
- Gateway 和 Registry 共用请求指标，用 service 标签区分
"""

from prometheus_client import Counter, Gauge, Histogram

# ── 请求指标（Counter + Histogram + Gauge） ──

REQUEST_COUNT = Counter(
    "http_requests_total",
    "Total HTTP requests received",
    ["service", "method", "endpoint", "status"],
)

REQUEST_LATENCY = Histogram(
    "http_request_duration_seconds",
    "HTTP request duration in seconds",
    ["service", "endpoint"],
    buckets=[0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0],
)

ACTIVE_REQUESTS = Gauge(
    "http_active_requests",
    "Number of currently active HTTP requests",
    ["service"],
)


# ── 推理专用指标（Gateway 独有） ──
INFERENCE_COUNT = Counter(
    "inference_requests_total",
    "Total inference requests forwarded by gateway",
    ["model_name", "version", "status"],
)

INFERENCE_LATENCY = Histogram(
    "inference_duration_seconds",
    "End-to-end inference duration (gateway → worker → response)",
    ["model_name", "version"],
    buckets=[0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0],
)