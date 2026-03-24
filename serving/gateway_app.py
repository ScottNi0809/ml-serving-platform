"""
Gateway Service — FastAPI 入口
===============================

提供统一的推理入口，将请求路由到对应的 Worker。

运行（开发模式）：
    uvicorn serving.gateway_app:app --reload --host 0.0.0.0 --port 8002
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Path

from serving.gateway import GatewayRouter
from serving.gateway_schemas import (
    GatewayPredictRequest,
    WorkerRegistration,
)

# 全局 Gateway Router 实例
router = GatewayRouter()


@asynccontextmanager
async def lifespan(app: FastAPI):
    print("✅ Gateway started on port 8002")
    yield
    await router.close()
    print("🔴 Gateway shutting down.")


app = FastAPI(
    title="ML Model Serving Platform — Gateway",
    description="推理网关：统一接收请求，路由到对应的模型 Worker。",
    version="0.1.0",
    lifespan=lifespan,
)


# ── 健康检查 ──────────────────────────────────────────────────

@app.get("/health")
async def health():
    routes = router.list_routes()
    return {
        "status": "healthy",
        "service": "gateway",
        "registered_routes": len(routes),
    }


# ── Worker 注册 / 注销 ───────────────────────────────────────

@app.post("/api/v1/gateway/register")
async def register_worker(body: WorkerRegistration):
    """注册一个 Worker 到路由表"""
    result = router.register_worker(
        model_name=body.model_name,
        version=body.version,
        worker_url=body.worker_url,
    )
    return result


@app.delete("/api/v1/gateway/routes/{model_name}/{version}")
async def deregister_worker(
    model_name: str = Path(...),
    version: str = Path(...),
):
    """从路由表中移除一个 Worker"""
    result = router.deregister_worker(model_name, version)
    if result["status"] == "not_found":
        raise HTTPException(status_code=404, detail=f"Route not found: {model_name}:{version}")
    return result


# ── 路由查询 ──────────────────────────────────────────────────

@app.get("/api/v1/gateway/routes")
async def list_routes():
    """查看当前所有路由"""
    return {"routes": router.list_routes()}


# ── 推理入口（核心） ──────────────────────────────────────────

@app.post("/api/v1/gateway/predict/{model_name}/{version}")
async def gateway_predict(
    body: GatewayPredictRequest,
    model_name: str = Path(...),
    version: str = Path(...),
):
    """
    统一推理入口 —— Gateway 的核心 API。
    
    客户端只需要知道模型名和版本，不需要知道 Worker 的地址。
    Gateway 查路由表，将请求转发给对应的 Worker。
    """
    try:
        result = await router.forward_predict(
            model_name=model_name,
            version=version,
            inputs=body.inputs,
        )
        return result
    except KeyError as e:
        raise HTTPException(
            status_code=404,
            detail=str(e),
        )
    except Exception as e:
        raise HTTPException(
            status_code=502,
            detail=f"Failed to forward request to worker: {e}",
        )


# ── Worker 健康检查 ───────────────────────────────────────────

@app.get("/api/v1/gateway/health/{model_name}/{version}")
async def check_worker_health(
    model_name: str = Path(...),
    version: str = Path(...),
):
    """检查指定模型的 Worker 是否存活"""
    worker_url = router.get_worker_url(model_name, version)
    if not worker_url:
        raise HTTPException(
            status_code=404,
            detail=f"No route for {model_name}:{version}",
        )
    healthy = await router.check_worker_health(worker_url)
    return {
        "model_name": model_name,
        "version": version,
        "worker_url": worker_url,
        "healthy": healthy,
    }