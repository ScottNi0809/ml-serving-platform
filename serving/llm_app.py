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
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException

from serving.llm_schemas import ChatCompletionRequest, ChatCompletionResponse, TokenUsage
from serving.llm_worker import LLMWorker

# 从环境变量读取配置（12-Factor App 原则）
VLLM_BASE_URL = os.getenv("VLLM_BASE_URL", "http://localhost:8100")
VLLM_DEFAULT_MODEL = os.getenv("VLLM_DEFAULT_MODEL", "Qwen/Qwen2.5-1.5B-Instruct")

# 全局 LLM Worker 实例
llm_worker = LLMWorker(
    vllm_base_url=VLLM_BASE_URL,
    default_model=VLLM_DEFAULT_MODEL,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    print(f"✅ LLM Worker started on port 8003")
    print(f"   vLLM backend: {VLLM_BASE_URL}")
    print(f"   Default model: {VLLM_DEFAULT_MODEL}")
    yield
    await llm_worker.close()
    print("🔴 LLM Worker shutting down.")


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
    if body.stream:
        raise HTTPException(
            status_code=501,
            detail="Streaming not implemented yet — Day21 will add this.",
        )

    try:
        messages = [msg.model_dump() for msg in body.messages]
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
    except Exception as e:
        raise HTTPException(
            status_code=502,
            detail=f"vLLM backend error: {e}",
        )