"""
依赖注入
========

集中管理可注入的依赖函数：API Key 验证、当前用户等。
"""

from fastapi import Depends, Header, HTTPException

from registry.config import settings

from functools import lru_cache
from registry.storage import BaseStorage, create_storage

# API Key（从集中配置读取，开发模式可选保留默认 key）
_valid_keys = {settings.api_key, "dev-api-key"}


async def verify_api_key(x_api_key: str = Header(default=None)):
    """验证 API Key"""
    if x_api_key is None:
        raise HTTPException(status_code=401, detail="Missing X-API-Key header")
    if x_api_key not in _valid_keys:
        raise HTTPException(status_code=401, detail="Invalid API key")
    return x_api_key


async def get_current_user(api_key: str = Depends(verify_api_key)):
    """根据 API Key 获取当前用户（简化实现）"""
    return {"username": "developer", "role": "admin"}

@lru_cache()
def get_storage() -> BaseStorage:
    return create_storage(
        backend = settings.storage_backend,
        base_path = settings.model_store_path,
    )
