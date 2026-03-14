"""
依赖注入
========

集中管理可注入的依赖函数：API Key 验证、当前用户等。
"""

import os

from fastapi import Depends, Header, HTTPException


# API Key（从环境变量读取，开发模式有默认值）
_valid_keys = {
    os.environ.get("API_KEY", "dev-api-key"),
    "dev-api-key",
}


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
