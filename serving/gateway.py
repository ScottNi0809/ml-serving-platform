"""
Gateway — 请求路由层
====================

维护「模型:版本 → Worker URL」路由表，
接收推理请求并异步转发给对应 Worker。
"""
import random

import httpx
from typing import Optional


class GatewayRouter:
    """Gateway 路由管理器"""

    def __init__(self):
        # key: "model_name:version" → value: worker_url
        self._routes: dict[str, str] = {}
        # key: A/B 路由：key: "model_name" → value: [{"version", "worker_url", "weight"}]
        self._ab_routes: dict[str, list[dict]] = {}
        self._rollback_history: list[dict] = []  # 用于回滚的历史记录
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
    
    def set_ab_route(
            self, model_name: str, backends: list[dict]
    ) -> dict:
        """
        设置 A/B 路由配置。
        backends 格式：[{"version": "1", "worker_url": "...", "weight": 90}, ...]
        """
        self._ab_routes[model_name] = backends
        total_weight = sum(b['weight'] for b in backends)
        return {
            "status": "ab_route_set",
            "model_name": model_name,
            "backends": backends,
            "total_weight": total_weight,
        }
    
    def remove_ab_route(self, model_name: str) -> dict:
        """移除某个模型的 A/B 路由配置"""
        if model_name not in self._ab_routes:
            return {"status": "not_found", "model_name": model_name}
        del self._ab_routes[model_name]
        return {"status": "ab_route_removed", "model_name": model_name}
    
    def rollback_ab_route(self, model_name: str, target_version: str, reason: str = "") -> dict:
        """
        一键回滚：将指定模型的全部流量切换到 target_version。

        逻辑：
        1. 查找 A/B 配置中是否存在 target_version
        2. 将 target_version 的权重设为 100，其他版本归零
        3. 记录到 _rollback_history
        """
        backends = self._ab_routes.get(model_name)
        if not backends:
            return {"status": "not_found", "model_name": model_name}
        
        # 检查target version是否在配置中
        version_exists = any(b['version'] == target_version for b in backends)
        if not version_exists:
            return {
                "status": "version_not_found",
                "model_name": model_name,
                "target_version": target_version,
                "available_versions": [b["version"] for b in backends]
            }
        
        # 记录回滚前的快照
        snapshot_before = [
            {"version": b["version"], "weight": b["weight"]}
            for b in backends
        ]

        # 执行回滚：目标版本100，其他归零
        for b in backends:
            b["weight"] = 100 if b["version"] == target_version else 0

        # 记录回滚历史
        from datetime import datetime, timezone
        record = {
            "model_name": model_name,
            "target_version": target_version,
            "reason": reason,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "before": snapshot_before,
            "after": [
                {"version": b["version"], "weight": b["weight"]}
                for b in backends
            ]
        }
        self._rollback_history.append(record)

        return {
            "status": "rolled_back",
            "model_name": model_name,
            "target_version": target_version,
            "before": snapshot_before,
            "after": record["after"],
        }

    def get_rollback_history(self, model_name: str | None = None) -> list[dict]:
        """获取回滚历史，可选按模型名过滤"""
        if model_name:
            return [r for r in self._rollback_history if r["model_name"] == model_name]
        return list(self._rollback_history)

    def get_ab_route(self, model_name: str) -> Optional[list[dict]]:
        """查询 A/B 路由配置"""
        return self._ab_routes.get(model_name)
    
    def list_ab_routes(self) -> list[dict]:
        """列出所有 A/B 路由配置"""
        return {
            name: {
                "backends": backends,
                "total_weight": sum(b["weight"] for b in backends),
            }
            for name, backends in self._ab_routes.items()
        }
    
    def _weighted_select(self, backends: list[dict]) -> dict:
        """
        加权随机选择一个后端。
        
        算法：累加权重，生成 [0, total) 的随机数，
        落在哪个区间就选哪个后端。
        """
        total = sum(b["weight"] for b in backends)
        r = random.uniform(0, total)
        cumulative = 0
        for backend in backends:
            cumulative += backend["weight"]
            if r < cumulative:
                return backend
        return backends[-1]  # 理论上不会到这行，但加个兜底

    async def forward_predict_ab(
        self, model_name: str, inputs: list[list[float]]
    ) -> dict:
        """
        A/B 路由转发。
        
        1. 查 A/B 路由表找到后端列表
        2. 按权重随机选择一个后端
        3. 转发推理请求
        4. 在响应中附带路由信息（方便调试和统计）
        """
        backends = self.get_ab_route(model_name)
        if not backends:
            raise KeyError(f"No A/B route configured for {model_name}")

        # 过滤掉权重为 0 的后端
        active_backends = [b for b in backends if b["weight"] > 0]
        if not active_backends:
            raise KeyError(f"All backends for '{model_name}' have zero weight")
        
        selected = self._weighted_select(active_backends)
        version = selected["version"]
        worker_url = selected["worker_url"]

        predict_url = (
            f"{worker_url}/api/v1/models/{model_name}"
            f"/versions/{version}/predict"
        )

        response = await self._client.post(
            predict_url, json={"inputs": inputs}
        )
        response.raise_for_status()

        result = response.json()
        # 附带路由元信息，方便调试
        result["_routed_to"] = {
            "version": version,
            "worker_url": worker_url,
            "weight": selected["weight"],
        }
        return result

    async def check_worker_health(self, worker_url: str) -> bool:
        """检查 Worker 是否存活"""
        try:
            response = await self._client.get(
                f"{worker_url}/health", timeout=5.0
            )
            return response.status_code == 200
        except (httpx.RequestError, httpx.HTTPStatusError):
            return False
        
    async def forward_chat(
        self, model_name: str, version: str, payload: dict
    ) -> dict:
        """
        转发 LLM Chat 请求到 LLM Worker。

        与 forward_predict 类似，但目标 URL 和请求格式不同：
        - ML Worker:  POST {worker_url}/api/v1/models/{name}/versions/{ver}/predict
        - LLM Worker: POST {worker_url}/api/v1/chat/completions

        Args:
            model_name: 模型名（路由查找用）
            version: 版本号
            payload: Chat 请求体 {"messages": [...], "max_tokens": ..., ...}
        """
        worker_url = self.get_worker_url(model_name, version)
        if not worker_url:
            raise KeyError(f"No worker registered for {model_name}:{version}")

        chat_url = f"{worker_url}/api/v1/chat/completions"

        response = await self._client.post(chat_url, json=payload)
        response.raise_for_status()
        return response.json()
        
    async def close(self):
        """关闭 HTTP 客户端"""
        await self._client.aclose()