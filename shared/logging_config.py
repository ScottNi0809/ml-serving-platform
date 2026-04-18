import json
import logging
import sys
import os
from contextvars import ContextVar

# ============ ContextVar ============
request_id_var: ContextVar[str] = ContextVar("request_id", default="-")

# ============ JSON Formatter ============
class JSONFormatter(logging.Formatter):
    """输出单行 JSON 日志，方便 ELK / Loki 解析"""

    def format(self, record: logging.LogRecord) -> str:
        log_data = {
            "timestamp": self.formatTime(record, datefmt="%Y-%m-%dT%H:%M:%S"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": getattr(record, "request_id", "-"),
        }
        # 合并 extra 中的自定义字段
        for key in ("model_name", "model_id", "version", "service", "status_code", "duration"):
            val = getattr(record, key, None)
            if val is not None:
                log_data[key] = val
        if record.exc_info and record.exc_info[0]:
            log_data["exception"] = self.formatException(record.exc_info)
        return json.dumps(log_data, ensure_ascii=False)

# ============ Request ID Filter ============
class RequestIDFilter(logging.Filter):
    """自动把 ContextVar 里的 request_id 注入每条日志"""

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_var.get("-")
        return True

# ============ Setup 函数 ============
def setup_logging(service_name: str, level: str = "INFO") -> logging.Logger:
    """
    统一初始化日志。每个服务启动时调用一次。
    
    用法：
        from shared.logging_config import setup_logging
        logger = setup_logging("gateway")
    """
    level = level or os.getenv("LOG_LEVEL", "INFO")
    logger = logging.getLogger(service_name)
    logger.setLevel(getattr(logging, level.upper(), logging.INFO))

    # 避免重复添加 handler
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(JSONFormatter())
        logger.addHandler(handler)

    logger.addFilter(RequestIDFilter())
    return logger