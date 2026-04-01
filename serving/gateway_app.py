"""
Gateway Service — FastAPI 入口
===============================

提供统一的推理入口，将请求路由到对应的 Worker。

运行（开发模式）：
    uvicorn serving.gateway_app:app --reload --host 0.0.0.0 --port 8002
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Path
from fastapi.responses import StreamingResponse

from serving.gateway import GatewayRouter
from serving.gateway_schemas import (
    GatewayPredictRequest,
    WorkerRegistration,
    ABRouteConfig,
    RollbackRequest,
    GatewayChatRequest,
    GatewayChatStreamRequest,
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


# ── LLM Chat 入口 ───────────────────────────────────────────

@app.post("/api/v1/gateway/chat/{model_name}/{version}")
async def gateway_chat(
    body: GatewayChatRequest,
    model_name: str = Path(...),
    version: str = Path(...),
):
    """
    LLM 推理入口 — Gateway 的 Chat API。

    和 predict 入口的设计一致：
    客户端只需知道模型名和版本，不需要知道 LLM Worker 地址。
    Gateway 查路由表 → 转发给对应的 LLM Worker → 返回结果。
    """
    try:
        result = await router.forward_chat(
            model_name = model_name,
            version = version,
            payload = body.model_dump(),
        )
        return result
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=502,
            detail=f"Failed to forward request to worker: {e}",
        )

@app.post("/api/v1/gateway/chat/{model_name}/{version}/stream")
async def gateway_chat_stream(
    body: GatewayChatStreamRequest,
    model_name: str = Path(...),
    version: str = Path(...),
):
    """
    LLM 流式推理入口 — SSE 格式。

    和 /chat/{model_name}/{version} 的区别：
    - 非流式版本：返回 JSON，等全部生成完
    - 流式版本：返回 SSE 流，逐 token 推送
    """
    try:
        async def stream_generator():
            async for chunk in router.forward_chat_stream(
                model_name = model_name,
                version = version,
                payload = body.model_dump(),
            ):
                yield chunk

        return StreamingResponse(
            stream_generator(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )
    except KeyError as e:
            raise HTTPException(status_code=404, detail=str(e))

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


# ─────────────── A/B 路由配置 ───────────────────

@app.post("/api/v1/gateway/ab/configure")
async def configure_ab_route(body: ABRouteConfig):
    """
    设置模型的 A/B 路由配置。
    
    示例：iris-classifier 的流量 90% 走 v1，10% 走 v2
    """
    backends = [b.model_dump() for b in body.backends]
    result = router.set_ab_route(
        model_name=body.model_name,
        backends=backends,
    )
    return result

@app.delete("/api/v1/gateway/ab/{model_name}")
async def delete_ab_route(model_name: str = Path(...)):
    """删除模型的 A/B 路由配置"""
    result = router.remove_ab_route(model_name)
    if result["status"] == "not_found":
        raise HTTPException(
            status_code=404, 
            detail=f"A/B route not found: {model_name}"
        )
    return result

@app.get("/api/v1/gateway/ab")
async def list_ab_routes():
    """列出所有 A/B 路由配置"""
    routes = router.list_ab_routes()
    return {"ab_routes": routes}

@app.get("/api/v1/gateway/ab/{model_name}")
async def get_ab_route(model_name: str = Path(...)):
    """获取指定模型的 A/B 路由配置"""
    backends = router.get_ab_route(model_name)
    if backends is None:
        raise HTTPException(
            status_code=404,
            detail=f"No A/B route for model: {model_name}",
        )
    return {
        "model_name": model_name,
        "backends": backends,
        "total_weight": sum(b["weight"] for b in backends),
    }

@app.post("/api/v1/gateway/ab/rollback/{model_name}")
async def rollback_ab_route(
    body: RollbackRequest,
    model_name: str = Path(...),
):
    """
    一键回滚：将指定模型的全部流量切到目标版本。

    其他版本的权重自动归零，回滚操作记录到历史中。
    """
    result = router.rollback_ab_route(
        model_name = model_name,
        target_version = body.target_version,
        reason = body.reason,
    )
    if result["status"] == "not_found":
        raise HTTPException(status_code=404, detail=f"No A/B route: {model_name}")
    if result["status"] == "version_not_found":
        raise HTTPException(
            status_code=400,
            detail=f"Version '{body.target_version}' not in A/B config. "
                   f"Available: {result['available_versions']}",
        )
    return result

@app.get("/api/v1/gateway/ab/rollback-history/{model_name}")
async def get_rollback_history(model_name: str = Path(...)):
    """查看指定模型的回滚历史"""
    history = router.get_rollback_history(model_name)
    return {"model_name": model_name, "history": history}

@app.post("/api/v1/gateway/ab/predict/{model_name}")
async def ab_predict(
    body: GatewayPredictRequest,
    model_name: str = Path(...),
):
    """
    A/B 路由推理入口。
    
    客户端只需指定模型名，不需要指定版本。
    Gateway 根据配置的权重自动选择版本并转发。
    
    响应中的 _routed_to 字段告诉你请求实际发到了哪个版本。
    """
    try:
        result = await router.forward_predict_ab(
            model_name=model_name,
            inputs=body.inputs,
        )
        return result
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=502,
            detail=f"Failed to forward request: {e}",
        )