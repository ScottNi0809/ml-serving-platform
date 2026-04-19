"""
模型加载器（工厂模式）
====================
根据 framework 字段选择对应的加载/推理方式。
"""
from abc import ABC, abstractmethod
from typing import Any


class BaseModelRunner(ABC):
    """已加载模型的统一推理接口"""

    @abstractmethod
    def predict(self, inputs: list[list[float]]) -> dict[str, Any]:
        """执行推理，返回结果字典"""
        ...

    @abstractmethod
    def metadata(self) -> dict:
        """返回模型元信息（类别、输入维度等）"""
        ...


class SklearnRunner(BaseModelRunner):
    """sklearn 模型运行器"""

    def __init__(self, model, model_name: str, version: str):
        self.model = model
        self.model_name = model_name
        self.version = version

    def predict(self, inputs: list[list[float]]) -> dict[str, Any]:
        import numpy as np
        X = np.array(inputs)
        predictions = self.model.predict(X).tolist()

        result = {"predictions": predictions}

        # 如果模型支持 predict_proba，也返回概率
        if hasattr(self.model, "predict_proba"):
            probabilities = self.model.predict_proba(X).tolist()
            result["probabilities"] = probabilities

        return result

    def metadata(self) -> dict:
        meta = {
            "model_name": self.model_name,
            "version": self.version,
            "framework": "sklearn",
            "model_type": type(self.model).__name__,
        }
        if hasattr(self.model, "classes_"):
            meta["classes"] = self.model.classes_.tolist()
        if hasattr(self.model, "n_features_in_"):
            meta["n_features"] = self.model.n_features_in_
        return meta


def load_model(framework: str, file_path: str, model_name: str, version: str) -> BaseModelRunner:
    """工厂函数：根据 framework 加载模型并返回对应的 Runner"""
    if framework == "sklearn":
        import joblib
        model = joblib.load(file_path)
        return SklearnRunner(model, model_name, version)
    elif framework == "pytorch":
        raise NotImplementedError("Pytorch loader")
    elif framework == "onnx":
        raise NotImplementedError("ONNX loader")
    else:
        raise ValueError(f"Unsupported framework: {framework}")