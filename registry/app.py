"""
ML Model Serving Platform — Registry Service
=============================================

模型注册中心：管理模型的元数据、版本和文件存储。

主入口，负责：
- 创建 FastAPI 实例
- 注册中间件（CORS、请求日志）
- 注册异常处理器
- 挂载路由
- 生命周期管理（数据库初始化）

运行（开发模式）：
    uvicorn registry.app:app --reload --host 0.0.0.0 --port 8000
"""

import time
import uuid
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from registry.database import create_tables, get_db
from registry.exceptions import (
    DuplicateModelError,
    DuplicateVersionError,
    ModelNotFoundError,
    ModelVersionNotFoundError,
)
from registry.routers import models


# ============================================================
# 生命周期
# ============================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期：启动时初始化数据库表"""
    create_tables()
    print("✅ Registry service started. Database initialized.")
    yield
    print("🔴 Registry service shutting down.")


# ============================================================
# 创建应用
# ============================================================

app = FastAPI(
    title="ML Model Serving Platform — Registry",
    description=(
        "模型注册中心 API：管理模型元数据、版本和文件存储。\n\n"
        "Phase 1 of ML Model Serving Platform."
    ),
    version="0.1.0",
    lifespan=lifespan,
)

# CORS（开发阶段允许所有来源）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================
# 请求日志中间件
# ============================================================

@app.middleware("http")
async def log_requests(request: Request, call_next):
    request_id = str(uuid.uuid4())[:8]
    request.state.request_id = request_id
    start = time.perf_counter()
    response = await call_next(request)
    elapsed_ms = (time.perf_counter() - start) * 1000
    print(
        f"[{request_id}] {request.method} {request.url.path} "
        f"→ {response.status_code} ({elapsed_ms:.1f}ms)"
    )
    response.headers["X-Request-ID"] = request_id
    return response


# ============================================================
# 异常处理器
# ============================================================

@app.exception_handler(ModelNotFoundError)
async def model_not_found_handler(request: Request, exc: ModelNotFoundError):
    return JSONResponse(
        status_code=404,
        content={"error": "model_not_found", "message": str(exc)},
    )


@app.exception_handler(ModelVersionNotFoundError)
async def version_not_found_handler(request: Request, exc: ModelVersionNotFoundError):
    return JSONResponse(
        status_code=404,
        content={"error": "version_not_found", "message": str(exc)},
    )


@app.exception_handler(DuplicateModelError)
async def duplicate_model_handler(request: Request, exc: DuplicateModelError):
    return JSONResponse(
        status_code=409,
        content={"error": "duplicate_model", "message": str(exc)},
    )


@app.exception_handler(DuplicateVersionError)
async def duplicate_version_handler(request: Request, exc: DuplicateVersionError):
    return JSONResponse(
        status_code=409,
        content={"error": "duplicate_version", "message": str(exc)},
    )


# ============================================================
# 路由挂载
# ============================================================

app.include_router(models.router)


# ============================================================
# 全局清理
# ============================================================

@app.post("/api/v1/cleanup", tags=["Cleanup"])
async def cleanup_all_files(
    user: dict = Depends(models.get_current_user),
):
    """清理所有版本的模型文件"""
    from registry.database import get_db
    from registry.dependencies import get_storage

    store = get_storage()
    with get_db() as conn:
        rows = conn.execute(
            "SELECT id, file_path FROM model_versions WHERE file_path IS NOT NULL"
        ).fetchall()
        for row in rows:
            store.delete(row["file_path"])
        conn.execute(
            "UPDATE model_versions SET file_path = NULL, status = 'registered' WHERE file_path IS NOT NULL"
        )
    return {"message": f"cleanup completed, {len(rows)} files removed"}


# ============================================================
# 健康检查
# ============================================================

@app.get("/health", tags=["Health"])
async def health():
    return {
        "status": "healthy",
        "service": "registry",
        "version": "0.1.0",
    }
