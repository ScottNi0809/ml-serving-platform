"""LLM Worker 请求/响应模型 — ChatCompletions 格式"""
from typing import Optional
from pydantic import BaseModel, Field


class ChatMessage(BaseModel):
    """单条聊天消息"""
    role: str = Field(
        ...,
        description="角色：system / user / assistant",
        examples=["user"],
    )
    content: str = Field(
        ...,
        description="消息内容",
        examples=["什么是KV Cache？"],
    )


class ChatCompletionRequest(BaseModel):
    """LLM 推理请求 — 遵循 OpenAI Chat Completions 格式"""
    messages: list[ChatMessage] = Field(
        ...,
        description="聊天消息列表",
        min_length=1,
    )
    max_tokens: int = Field(
        default=256,
        ge=1,
        le=4096,
        description="最大生成 token 数",
    )
    temperature: float = Field(
        default=0.7,
        ge=0.0,
        le=2.0,
        description="采样温度，越高越随机",
    )
    stream: bool = Field(
        default=False,
        description="是否流式输出（Day21 实现）",
    )


class TokenUsage(BaseModel):
    """Token 用量统计"""
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int


class ChatCompletionResponse(BaseModel):
    """LLM 推理响应"""
    model: str
    content: str = Field(..., description="模型生成的回复内容")
    usage: Optional[TokenUsage] = None
    finish_reason: Optional[str] = None