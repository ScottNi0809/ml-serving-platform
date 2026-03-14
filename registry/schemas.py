"""
Pydantic 数据模型（Schemas）
============================

请求体 / 响应体的数据验证与序列化。
"""

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


# ============================================================
# 枚举
# ============================================================

class ModelFramework(str, Enum):
    pytorch = "pytorch"
    tensorflow = "tensorflow"
    onnx = "onnx"
    sklearn = "sklearn"


class ModelStatus(str, Enum):
    registered = "registered"
    loading = "loading"
    ready = "ready"
    failed = "failed"
    archived = "archived"


# ============================================================
# 请求模型
# ============================================================

class ModelCreate(BaseModel):
    """创建模型时的请求体"""
    name: str = Field(
        ..., min_length=1, max_length=100,
        examples=["bert-sentiment"],
        description="模型名称（全局唯一标识）",
    )
    framework: ModelFramework
    description: Optional[str] = None
    tags: list[str] = Field(default_factory=list)


class ModelVersionCreate(BaseModel):
    """创建模型版本时的请求体"""
    version: str = Field(
        ..., pattern=r"^\d+\.\d+\.\d+$",
        examples=["1.0.0"],
        description="语义化版本号",
    )
    description: Optional[str] = None


class ModelUpdate(BaseModel):
    """更新模型元数据"""
    description: Optional[str] = None
    tags: Optional[list[str]] = None


# ============================================================
# 响应模型
# ============================================================

class ModelVersionResponse(BaseModel):
    id: str
    model_name: str
    version: str
    status: ModelStatus
    description: Optional[str]
    file_path: Optional[str]
    created_at: str
    is_default: bool


class ModelResponse(BaseModel):
    id: str
    name: str
    framework: ModelFramework
    status: ModelStatus
    description: Optional[str]
    tags: list[str]
    created_at: str
    default_version: Optional[str]
    version_count: int


class ModelListResponse(BaseModel):
    items: list[ModelResponse]
    total: int
    skip: int
    limit: int


class ErrorResponse(BaseModel):
    error: str
    message: str
    detail: Optional[str] = None
