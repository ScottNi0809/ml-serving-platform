"""
ML Serving Platform - Load Testing Suite

Usage:
    # Headless mode (CI-friendly) — --host 指向 Gateway (8002)
    # 环境变量 REGISTRY_HOST 指向 Registry (8000)
    REGISTRY_HOST=http://localhost:8000 \
    locust -f benchmarks/locustfile.py --host=http://localhost:8002 \
        --users 50 --spawn-rate 10 --run-time 60s --headless --csv=benchmarks/results

    # Web UI mode
    REGISTRY_HOST=http://localhost:8000 \
    locust -f benchmarks/locustfile.py --host=http://localhost:8002
"""

import os
import random
import string
from locust import HttpUser, task, between, events

# Registry 服务地址（/api/v1/models 路由在 Registry 上）
REGISTRY_HOST = os.environ.get("REGISTRY_HOST", "http://localhost:8000")

# Registry API Key（认证用）
REGISTRY_API_KEY = os.environ.get("REGISTRY_API_KEY", "dev-api-key")

# 发往 Registry 的请求公共 headers
_registry_headers = {"X-API-Key": REGISTRY_API_KEY}


def random_name(prefix: str = "bench") -> str:
    """生成唯一模型名，避免冲突"""
    suffix = "".join(random.choices(string.ascii_lowercase, k=6))
    return f"{prefix}-{suffix}"


class ReadHeavyUser(HttpUser):
    """
    场景 1：读密集型（模拟正常运行时的查询负载）

    流量分布：
    - 40% 列出模型        → Registry (8000)
    - 30% 查询路由        → Gateway  (8002)
    - 20% 健康检查        → Gateway  (8002)
    - 10% 获取模型详情    → Registry (8000)
    """

    wait_time = between(0.1, 0.5)
    weight = 3  # 3/4 的用户跑这个场景

    @task(4)
    def list_models(self):
        with self.client.get(
            f"{REGISTRY_HOST}/api/v1/models",
            headers=_registry_headers,
            name="/api/v1/models [LIST]",
            catch_response=True,
        ) as resp:
            if resp.status_code == 200:
                data = resp.json()
                # 缓存模型 ID，供后续查询使用
                if isinstance(data, list) and data:
                    self._model_ids = [m.get("id") or m.get("name") for m in data[:10]]
                resp.success()
            else:
                resp.failure(f"Status {resp.status_code}")

    @task(3)
    def get_routes(self):
        self.client.get("/api/v1/gateway/routes", name="/api/v1/gateway/routes")

    @task(2)
    def health_check(self):
        self.client.get("/health", name="/health")

    @task(1)
    def get_model_detail(self):
        model_ids = getattr(self, "_model_ids", [])
        if model_ids:
            model_id = random.choice(model_ids)
            self.client.get(
                f"{REGISTRY_HOST}/api/v1/models/{model_id}",
                headers=_registry_headers,
                name="/api/v1/models/[id]",
            )


class WriteMixedUser(HttpUser):
    """
    场景 2：写操作混合（模拟模型注册/管理负载）

    流量分布：
    - 40% 列出模型        → Registry (8000)
    - 30% 注册新模型      → Registry (8000)
    - 20% 获取路由        → Gateway  (8002)
    - 10% 健康检查        → Gateway  (8002)
    """

    wait_time = between(0.5, 1.5)
    weight = 1  # 1/4 的用户跑这个场景

    @task(4)
    def list_models(self):
        self.client.get(
            f"{REGISTRY_HOST}/api/v1/models",
            headers=_registry_headers,
            name="/api/v1/models [LIST]",
        )

    @task(3)
    def register_model(self):
        payload = {
            "name": random_name("bench"),
            "framework": random.choice(["pytorch", "onnx", "tensorflow"]),
            "description": "Benchmark test model",
        }
        self.client.post(
            f"{REGISTRY_HOST}/api/v1/models",
            headers=_registry_headers,
            json=payload,
            name="/api/v1/models [CREATE]",
        )

    @task(2)
    def get_routes(self):
        self.client.get("/api/v1/gateway/routes", name="/api/v1/gateway/routes")

    @task(1)
    def health_check(self):
        self.client.get("/health", name="/health")