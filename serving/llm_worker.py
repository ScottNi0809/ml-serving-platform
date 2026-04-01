"""
LLM Worker — vLLM 代理层
========================
接收标准化的 Chat 请求，转发给 vLLM 的 OpenAI-compatible API，
返回标准化的响应。

本质：thin HTTP proxy，不直接管理模型，而是委托给 vLLM。
"""
import httpx
import json
from typing import Any
from collections.abc import AsyncGenerator


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

    async def chat_stream(
            self,
            messages: list[dict[str, str]],
            max_tokens: int = 256,
            temperature: float = 0.7,
            model: str | None = None,
    ) -> AsyncGenerator[str, None]:
        """
        流式 Chat — 逐 chunk 从 vLLM 接收 SSE 数据并 yield。

        Yields:
            SSE 格式的字符串，如 'data: {"content": "你"}\n\n'
        """        
        model_name = model or self.default_model

        payload = {
            "model": model_name,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "stream": True, # 开启流式输出
        }
        
        url = f"{self.vllm_base_url}/v1/chat/completions"

        async with self._client.stream("POST", url, json=payload) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                # vLLM返回的每行格式： data: {"content": "你"}\n\n 或 data: [DONE]
                if not line.strip():
                    continue # 空行忽略

                if line.startswith("data: "):
                    data_str = line[len("data: "):]

                    if data_str == "[DONE]":
                        # 流结束，发送Done信号
                        yield "data: [DONE]\n\n"
                        return

                    # 解析 vLLM 的 SSE chunk，提取 delta.content
                    try:
                        chunk = json.loads(data_str)
                        delta = chunk["choices"][0].get("delta", {})
                        content = delta.get("content")
                        finish_reason = chunk["choices"][0].get("finish_reason")

                        # 跳过 content 为 None 的 chunk（如第一个 role 宣告 chunk）
                        if content is None and finish_reason is None:
                            continue

                        # 构造我们自己的SSE格式（标准化）
                        our_chunk = {
                            "content": content,
                            "finish_reason": finish_reason,
                            "model": chunk.get("model", model_name),
                        }
                        yield f"data: {json.dumps(our_chunk, ensure_ascii=False)}\n\n"
                    except (json.JSONDecodeError, KeyError, IndexError):
                        # 解析失败的 chunk 跳过，不中断流
                        continue

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