import time
import uuid
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from shared.logging_config import setup_logging, request_id_var

logger = setup_logging("middleware")

class RequestIDMiddleware(BaseHTTPMiddleware):
    """为每个请求生成一个唯一的 request_id，并存储在 ContextVar 中，供日志使用"""

    async def dispatch(self, request: Request, call_next) -> Response:
        # 优先使用客户端传入的 X-Request-ID
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4())[:8])

        if not request_id:
            # 生成一个新的 request_id
            request_id = str(uuid.uuid4())
        
        # 同时存在 request.state 和 ContextVar，方便不同中间件读取
        request.state.request_id = request_id
        request_id_var.set(request_id)

        # 继续处理请求
        start = time.time()
        response = await call_next(request)
        duration = time.time() - start

        logger.info("http_request", extra={
            "method": request.method,
            "path": request.url.path,
            "status_code": response.status_code,
            "duration": round(duration, 4),
        })
        # 在响应头中添加 request_id，方便追踪
        response.headers["X-Request-ID"] = request_id
        return response