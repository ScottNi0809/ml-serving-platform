"""
Serving Service — FastAPI 入口
==============================

提供模型推理 API，独立于 Registry 服务运行在端口 8001。

运行（开发模式）：
    uvicorn serving.app:app --reload --host 0.0.0.0 --port 8001
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Path

from serving.schemas import LoadModelRequest, PredictRequest, PredictResponse
from serving.worker import ServingWorker

# 全局 Worker 实例
worker = ServingWorker()


@asynccontextmanager
async def lifespan(app: FastAPI):
    print("✅ Serving worker started.")
    yield
    print("🔴 Serving worker shutting down.")


app = FastAPI(
    title="ML Model Serving Platform — Inference",
    description="模型推理服务：加载模型、执行预测。",
    version="0.1.0",
    lifespan=lifespan,
)


@app.get("/health")
async def health():
    loaded = worker.list_loaded()
    return {"status": "healthy", "loaded_models": len(loaded)}


@app.post("/api/v1/models/load")
async def load_model(body: LoadModelRequest):
    """加载模型到内存"""
    try:
        result = worker.load_model(
            model_name=body.model_name,
            version=body.version,
            framework=body.framework,
            file_path=body.file_path,
        )
        return result
    except NotImplementedError as e:
        raise HTTPException(status_code=501, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to load model: {e}")


@app.post(
    "/api/v1/models/{model_name}/versions/{version}/predict",
    response_model=PredictResponse,
)
async def predict(
    body: PredictRequest,
    model_name: str = Path(...),
    version: str = Path(...),
):
    """执行推理"""
    try:
        result = worker.predict(model_name, version, body.inputs)
        return PredictResponse(
            model_name=model_name,
            version=version,
            predictions=result["predictions"],
            probabilities=result.get("probabilities"),
        )
    except KeyError:
        raise HTTPException(
            status_code=404,
            detail=f"Model {model_name}:{version} not loaded. "
                   f"Call /api/v1/models/load first.",
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Inference failed: {e}")


@app.delete("/api/v1/models/{model_name}/versions/{version}/unload")
async def unload_model(
    model_name: str = Path(...),
    version: str = Path(...),
):
    """从内存卸载模型"""
    result = worker.unload_model(model_name, version)
    if result["status"] == "not_found":
        raise HTTPException(
            status_code=404, detail=f"Model not loaded: {result['key']}"
        )
    return result


@app.get("/api/v1/serving/models")
async def list_loaded_models():
    """列出所有已加载的模型"""
    return {"models": worker.list_loaded()}