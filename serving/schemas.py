"""Serving 服务的请求 / 响应模型"""
from typing import Any, Optional
from pydantic import BaseModel, Field


class PredictRequest(BaseModel):
    """推理请求"""
    inputs: list[list[float]] = Field(
        ...,
        description="输入特征矩阵，每个元素是一个样本的特征向量",
        examples=[[[5.1, 3.5, 1.4, 0.2], [6.2, 2.9, 4.3, 1.3]]],
    )


class PredictResponse(BaseModel):
    """推理响应"""
    model_name: str
    version: str
    predictions: list[Any]
    probabilities: Optional[list[list[float]]] = None


class LoadModelRequest(BaseModel):
    """加载模型请求"""
    model_name: str
    version: str
    framework: str = Field(..., description="模型框架：sklearn, pytorch, onnx")
    file_path: str = Field(..., description="模型文件路径")


class ModelInfo(BaseModel):
    """已加载模型的信息"""
    model_name: str
    version: str
    framework: str
    model_type: str