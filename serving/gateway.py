"""
Gateway — 请求路由层
====================

维护「模型:版本 → Worker URL」路由表，
接收推理请求并异步转发给对应 Worker。
"""
import httpx
from typing import Optional


class GatewayRouter:
    """Gateway 路由管理器"""

    def __init__(self):
        # key: "model_name:version" → value: worker_url
        self._routes: dict[str, str] = {}
        self._client = httpx.AsyncClient(timeout=30.0)

    def _key(self, model_name: str, version: str) -> str:
        return f"{model_name}:{version}"

    def register_worker(
        self, model_name: str, version: str, worker_url: str
    ) -> dict:
        """注册一个 Worker：将模型+版本绑定到 Worker 地址"""
        key = self._key(model_name, version)
        self._routes[key] = worker_url
        return {
            "status": "registered",
            "key": key,
            "worker_url": worker_url,
            "total_routes": len(self._routes),
        }

    def deregister_worker(self, model_name: str, version: str) -> dict:
        """注销一个 Worker"""
        key = self._key(model_name, version)
        if key not in self._routes:
            return {"status": "not_found", "key": key}
        del self._routes[key]
        return {"status": "deregistered", "key": key}

    def get_worker_url(self, model_name: str, version: str) -> Optional[str]:
        """查询路由表，返回 Worker URL"""
        key = self._key(model_name, version)
        return self._routes.get(key)

    def list_routes(self) -> list[dict]:
        """列出所有路由"""
        return [
            {"key": k, "worker_url": v}
            for k, v in self._routes.items()
        ]

    async def forward_predict(
        self, model_name: str, version: str, inputs: list[list[float]]
    ) -> dict:
        """
        核心方法：将推理请求转发给对应 Worker。

        1. 查路由表找到 Worker URL
        2. 构造 Worker 的 predict 接口 URL
        3. 用 httpx 异步 POST 转发
        4. 返回 Worker 的响应
        """
        worker_url = self.get_worker_url(model_name, version)
        if not worker_url:
            raise KeyError(
                f"No worker registered for {model_name}:{version}"
            )

        predict_url = (
            f"{worker_url}/api/v1/models/{model_name}"
            f"/versions/{version}/predict"
        )

        response = await self._client.post(
            predict_url, json={"inputs": inputs}
        )
        response.raise_for_status()
        return response.json()

    async def check_worker_health(self, worker_url: str) -> bool:
        """检查 Worker 是否存活"""
        try:
            response = await self._client.get(
                f"{worker_url}/health", timeout=5.0
            )
            return response.status_code == 200
        except (httpx.RequestError, httpx.HTTPStatusError):
            return False

    async def close(self):
        """关闭 HTTP 客户端"""
        await self._client.aclose()