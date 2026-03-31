"""
LLM Worker — vLLM 代理层
========================
接收标准化的 Chat 请求，转发给 vLLM 的 OpenAI-compatible API，
返回标准化的响应。

本质：thin HTTP proxy，不直接管理模型，而是委托给 vLLM。
"""
import httpx
from typing import Any


class LLMWorker:
    """LLM 推理工作器 — 代理到 vLLM 后端"""

    def __init__(self, vllm_base_url: str, default_model: str):
        """
        Args:
            vllm_base_url: vLLM 服务地址，如 "http://localhost:8100"
            default_model: 默认模型名，如 "Qwen/Qwen2.5-1.5B-Instruct"
        """
        self.vllm_base_url = vllm_base_url.rstrip("/")
        self.default_model = default_model
        self._client = httpx.AsyncClient(timeout=120.0)  # LLM 推理耗时长，超时设 2 分钟

    async def chat(
        self,
        messages: list[dict[str, str]],
        max_tokens: int = 256,
        temperature: float = 0.7,
        model: str | None = None,
    ) -> dict[str, Any]:
        """
        发送 Chat Completions 请求到 vLLM。

        Args:
            messages: [{"role": "user", "content": "..."}]
            max_tokens: 最大生成 token 数
            temperature: 采样温度
            model: 模型名（不传则用 default_model）

        Returns:
            标准化的响应字典
        """
        model_name = model or self.default_model

        # 构造 vLLM 的 OpenAI-compatible 请求
        payload = {
            "model": model_name,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }

        url = f"{self.vllm_base_url}/v1/chat/completions"
        response = await self._client.post(url, json=payload)
        response.raise_for_status()

        data = response.json()

        # 标准化响应：从 OpenAI 格式提取关键信息
        choice = data["choices"][0]
        result = {
            "model": data.get("model", model_name),
            "content": choice["message"]["content"],
            "finish_reason": choice.get("finish_reason"),
        }

        if "usage" in data:
            result["usage"] = {
                "prompt_tokens": data["usage"]["prompt_tokens"],
                "completion_tokens": data["usage"]["completion_tokens"],
                "total_tokens": data["usage"]["total_tokens"],
            }

        return result

    async def health_check(self) -> dict[str, Any]:
        """检查 vLLM 后端是否健康"""
        try:
            response = await self._client.get(f"{self.vllm_base_url}/health")
            vllm_healthy = response.status_code == 200
        except httpx.HTTPError:
            vllm_healthy = False

        # 查询已加载的模型
        models = []
        if vllm_healthy:
            try:
                resp = await self._client.get(f"{self.vllm_base_url}/v1/models")
                if resp.status_code == 200:
                    models = [m["id"] for m in resp.json().get("data", [])]
            except httpx.HTTPError:
                pass

        return {
            "vllm_backend": self.vllm_base_url,
            "vllm_healthy": vllm_healthy,
            "loaded_models": models,
            "default_model": self.default_model,
        }

    async def close(self):
        """关闭 HTTP 客户端"""
        await self._client.aclose()