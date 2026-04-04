"""
LLM Worker 单元测试
===================
用 mock 模拟 vLLM 后端，不需要 GPU 或真实的 vLLM 服务。
"""
import pytest
from unittest.mock import AsyncMock, patch
from httpx import Response, ConnectError, TimeoutException, Request

from serving.llm_worker import (
    LLMWorker,
    VLLMConnectionError,
    VLLMTimeoutError,
    VLLMResponseError,
)


@pytest.fixture
def worker():
    """创建 LLM Worker 实例（不连接真实 vLLM）"""
    return LLMWorker(
        vllm_base_url="http://fake-vllm:8100",
        default_model="test-model",
    )


def _mock_chat_response() -> dict:
    """构造一个模拟的 vLLM Chat Completions 响应"""
    return {
        "id": "chatcmpl-test123",
        "model": "test-model",
        "choices": [
            {
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": "KV Cache 是一种缓存机制。",
                },
                "finish_reason": "stop",
            }
        ],
        "usage": {
            "prompt_tokens": 10,
            "completion_tokens": 8,
            "total_tokens": 18,
        },
    }


class TestLLMWorkerChat:
    """chat() 方法的测试"""

    @pytest.mark.anyio
    async def test_chat_success(self, worker):
        """正常情况：vLLM 正常返回"""
        mock_response = Response(
            status_code=200,
            json=_mock_chat_response(),
            request=Request("POST", f"{worker.vllm_base_url}/v1/chat/completions"),
        )

        with patch.object(worker._client, "post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_response

            result = await worker.chat(
                messages=[{"role": "user", "content": "什么是 KV Cache？"}],
                max_tokens=100,
            )

        assert result["content"] == "KV Cache 是一种缓存机制。"
        assert result["model"] == "test-model"
        assert result["finish_reason"] == "stop"
        assert result["usage"]["total_tokens"] == 18

    @pytest.mark.anyio
    async def test_chat_uses_default_model(self, worker):
        """不传 model 参数时使用默认模型"""
        mock_response = Response(
            status_code=200,
            json=_mock_chat_response(),
            request=Request("POST", f"{worker.vllm_base_url}/v1/chat/completions"),
        )

        with patch.object(worker._client, "post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_response

            await worker.chat(
                messages=[{"role": "user", "content": "test"}],
            )

            # 验证发给 vLLM 的 payload 中 model 是默认值
            call_kwargs = mock_post.call_args
            sent_payload = call_kwargs.kwargs.get("json") or call_kwargs[1].get("json")
            assert sent_payload["model"] == "test-model"

    @pytest.mark.anyio
    async def test_chat_connection_error(self, worker):
        """vLLM 不可达时抛出 VLLMConnectionError"""
        with patch.object(worker._client, "post", new_callable=AsyncMock) as mock_post:
            mock_post.side_effect = ConnectError("Connection refused")

            with pytest.raises(VLLMConnectionError) as exc_info:
                await worker.chat(
                    messages=[{"role": "user", "content": "test"}],
                )
            assert exc_info.value.status_code == 503
            assert "Cannot connect" in exc_info.value.message

    @pytest.mark.anyio
    async def test_chat_timeout_error(self, worker):
        """vLLM 推理超时时抛出 VLLMTimeoutError"""
        with patch.object(worker._client, "post", new_callable=AsyncMock) as mock_post:
            mock_post.side_effect = TimeoutException("Read timed out")

            with pytest.raises(VLLMTimeoutError) as exc_info:
                await worker.chat(
                    messages=[{"role": "user", "content": "test"}],
                )
            assert exc_info.value.status_code == 504

    @pytest.mark.anyio
    async def test_chat_vllm_error_response(self, worker):
        """vLLM 返回非 2xx 时抛出 VLLMResponseError"""
        error_response = Response(
            status_code=400,
            text="Invalid model name",
            request=Request("POST", f"{worker.vllm_base_url}/v1/chat/completions"),
        )

        with patch.object(worker._client, "post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = error_response

            with pytest.raises(VLLMResponseError) as exc_info:
                await worker.chat(
                    messages=[{"role": "user", "content": "test"}],
                )
            assert exc_info.value.status_code == 502
            assert "400" in exc_info.value.message


class TestLLMWorkerHealthCheck:
    """health_check() 方法的测试"""

    @pytest.mark.anyio
    async def test_health_check_healthy(self, worker):
        """vLLM 健康时返回 healthy"""
        health_response = Response(status_code=200)
        models_response = Response(
            status_code=200,
            json={"data": [{"id": "test-model"}]},
        )

        with patch.object(worker._client, "get", new_callable=AsyncMock) as mock_get:
            mock_get.side_effect = [health_response, models_response]

            result = await worker.health_check()

        assert result["vllm_healthy"] is True
        assert "test-model" in result["loaded_models"]

    @pytest.mark.anyio
    async def test_health_check_unhealthy(self, worker):
        """vLLM 不可达时返回 unhealthy"""
        with patch.object(worker._client, "get", new_callable=AsyncMock) as mock_get:
            mock_get.side_effect = ConnectError("Connection refused")

            result = await worker.health_check()

        assert result["vllm_healthy"] is False
        assert result["loaded_models"] == []