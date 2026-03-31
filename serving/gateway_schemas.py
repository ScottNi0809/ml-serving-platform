"""Gateway 请求/响应模型"""
from pydantic import BaseModel, Field


class WorkerRegistration(BaseModel):
    """Worker 注册请求"""
    worker_url: str = Field(
        ...,
        description="Worker 的基础 URL，如 http://localhost:8001",
        examples=["http://localhost:8001"],
    )
    model_name: str = Field(..., description="该 Worker 服务的模型名称")
    version: str = Field(..., description="该 Worker 服务的模型版本")


class RouteInfo(BaseModel):
    """路由信息"""
    model_name: str
    version: str
    worker_url: str
    healthy: bool = True


class GatewayPredictRequest(BaseModel):
    """Gateway 推理请求（与 Worker 的 PredictRequest 格式一致）"""
    inputs: list[list[float]] = Field(
        ...,
        description="输入特征矩阵",
        examples=[[[5.1, 3.5, 1.4, 0.2]]],
    )


class WeightedBackend(BaseModel):
    """A/B 路由中的一个后端"""
    version: str = Field(..., description="模型版本")
    worker_url: str = Field(..., description="Worker 地址")
    weight: int = Field(
        ..., ge=0, le=100,
        description="流量权重（相对值，所有后端权重之和不要求等于 100）",
    )


class ABRouteConfig(BaseModel):
    """A/B 路由配置请求"""
    model_name: str = Field(..., description="模型名称")
    backends: list[WeightedBackend] = Field(
        ..., min_length=1,
        description="后端列表，至少一个",
    )


class ABRouteInfo(BaseModel):
    """A/B 路由信息（响应）"""
    model_name: str
    backends: list[WeightedBackend]
    total_weight: int


class RollbackRequest(BaseModel):
    """回滚请求"""
    target_version: str = Field(..., description="要回滚到的目标版本")
    reason: str = Field("", description="回滚原因（可选，用于审计追溯）")


# ────────────────────── LLM 路由请求 ──────────────────────────
class GatewayChatRequest(BaseModel):
    """Gateway LLM 推理请求 — Chat Completions 格式"""
    messages: list[dict] = Field(
        ...,
        description="聊天消息列表",
        examples=[[
            {"role": "user", "content": "什么是KV Cache？"},
        ]],
    )
    max_tokens: int = Field(default=256, ge=1, le=4096, description="最大生成 token 数")
    temperature: float = Field(default=0.7, ge=0.0, le=2.0, description="采样温度，越高越随机")