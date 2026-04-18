"""
LLM Worker Service — FastAPI 入口
=================================

LLM 推理服务，代理请求到 vLLM 后端。
独立于 ML Worker 运行在端口 8003。

运行：
    uvicorn serving.llm_app:app --reload --host 0.0.0.0 --port 8003

环境变量：
    VLLM_BASE_URL: vLLM 服务地址（默认 http://localhost:8100）
    VLLM_DEFAULT_MODEL: 默认模型名（默认 Qwen/Qwen2.5-1.5B-Instruct）
"""
import os
import json
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse

from serving.llm_schemas import ChatCompletionRequest, ChatCompletionResponse, TokenUsage
from serving.llm_worker import LLMWorker, LLMWorkerError
from shared.logging_config import setup_logging

# 从环境变量读取配置（12-Factor App 原则）
VLLM_BASE_URL = os.getenv("VLLM_BASE_URL", "http://localhost:8100")
VLLM_DEFAULT_MODEL = os.getenv("VLLM_DEFAULT_MODEL", "Qwen/Qwen2.5-1.5B-Instruct")

# 全局 LLM Worker 实例
llm_worker = LLMWorker(
    vllm_base_url=VLLM_BASE_URL,
    default_model=VLLM_DEFAULT_MODEL,
)
logger = setup_logging("llm-worker")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("llm_worker_started", extra={
        "service": "llm-worker",
        "vllm_base_url": VLLM_BASE_URL,
        "default_model": VLLM_DEFAULT_MODEL,
    })
    yield
    await llm_worker.close()
    logger.info("llm_worker_shutting_down", extra={"service": "llm-worker"})


app = FastAPI(
    title="ML Model Serving Platform — LLM Worker",
    description="LLM 推理服务：代理请求到 vLLM 后端。",
    version="0.1.0",
    lifespan=lifespan,
)


# ── 健康检查 ──────────────────────────────────────────────────

@app.get("/health")
async def health():
    """
    健康检查 — 同时检查 LLM Worker 自身和 vLLM 后端。
    
    Gateway 通过这个接口判断 LLM Worker 是否可用。
    """
    check = await llm_worker.health_check()
    status = "healthy" if check["vllm_healthy"] else "degraded"
    return {
        "status": status,
        "service": "llm-worker",
        **check,
    }


# ── LLM 推理入口 ─────────────────────────────────────────────

@app.post(
    "/api/v1/chat/completions",
    response_model=ChatCompletionResponse,
)
async def chat_completions(body: ChatCompletionRequest):
    """
    Chat Completions API — LLM Worker 的核心 endpoint。
    
    接收标准化的 Chat 请求，转发给 vLLM，返回标准化的响应。
    Gateway 通过这个接口调用 LLM 推理。
    """
    messages = [msg.model_dump() for msg in body.messages]

    # ── 流式模式 ──
    if body.stream:
        async def event_generator():
            """将 LLMWorker 的 async generator 包装成 SSE 流"""
            try:
                async for chunk in llm_worker.chat_stream(
                    messages = messages,
                    max_tokens = body.max_tokens,
                    temperature = body.temperature,
                ):
                    yield chunk
            except Exception as e:
                # 流中发生错误，发送错误事件后结束
                error_chunk = {"error": str(e)}
                yield f"data: {json.dumps(error_chunk)}\n\n"
                yield "data: [DONE]\n\n"

        return StreamingResponse(
            event_generator(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Access-Buffering": "no", # 禁用Nginx缓冲
            }
        )

    # ── 非流式模式 ──
    try:
        result = await llm_worker.chat(
            messages=messages,
            max_tokens=body.max_tokens,
            temperature=body.temperature,
        )

        usage = None
        if "usage" in result:
            usage = TokenUsage(**result["usage"])

        return ChatCompletionResponse(
            model=result["model"],
            content=result["content"],
            usage=usage,
            finish_reason=result.get("finish_reason"),
        )
    except LLMWorkerError as e:
        # 自定义异常：按 status_code 返回对应的 HTTP 状态
        raise HTTPException(status_code=e.status_code, detail=e.message)
    except Exception as e:
        # 未预期异常：兜底 500
        raise HTTPException(status_code=500, detail=f"Unexpected error: {e}")