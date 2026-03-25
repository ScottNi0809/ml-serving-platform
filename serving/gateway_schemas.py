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