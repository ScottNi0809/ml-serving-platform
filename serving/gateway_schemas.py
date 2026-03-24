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