"""
Serving Worker
==============
管理已加载模型的缓存，提供加载/卸载/推理接口。
"""
from typing import Any, Optional
from serving.loaders import BaseModelRunner, load_model


class ServingWorker:
    """模型推理工作器 — 管理内存中的模型实例"""

    def __init__(self):
        # key: "model_name:version"
        self._models: dict[str, BaseModelRunner] = {}

    def _key(self, model_name: str, version: str) -> str:
        return f"{model_name}:{version}"

    def load_model(
        self, model_name: str, version: str, framework: str, file_path: str
    ) -> dict:
        """加载模型到内存"""
        key = self._key(model_name, version)
        if key in self._models:
            return {"status": "already_loaded", "key": key}

        runner = load_model(framework, file_path, model_name, version)
        self._models[key] = runner
        return {"status": "loaded", "key": key, "metadata": runner.metadata()}

    def unload_model(self, model_name: str, version: str) -> dict:
        """从内存卸载模型"""
        key = self._key(model_name, version)
        if key not in self._models:
            return {"status": "not_found", "key": key}
        del self._models[key]
        return {"status": "unloaded", "key": key}

    def predict(
        self, model_name: str, version: str, inputs: list[list[float]]
    ) -> dict[str, Any]:
        """执行推理"""
        key = self._key(model_name, version)
        runner = self._models.get(key)
        if runner is None:
            raise KeyError(f"Model not loaded: {key}")
        return runner.predict(inputs)

    def list_loaded(self) -> list[dict]:
        """列出所有已加载的模型"""
        return [runner.metadata() for runner in self._models.values()]

    def get_model_metadata(self, model_name: str, version: str) -> Optional[dict]:
        """获取已加载模型的元数据"""
        key = self._key(model_name, version)
        runner = self._models.get(key)
        return runner.metadata() if runner else None