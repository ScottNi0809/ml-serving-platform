"""Serving Worker 单元测试"""
import pytest
import joblib
import numpy as np
from sklearn.linear_model import LogisticRegression

from serving.worker import ServingWorker


@pytest.fixture
def trained_model_path(tmp_path):
    """训练一个临时模型并保存"""
    X = np.array([[1, 2, 3, 4], [5, 6, 7, 8], [1, 1, 1, 1], [9, 9, 9, 9]])
    y = np.array([0, 1, 0, 1])
    model = LogisticRegression(max_iter=200)
    model.fit(X, y)
    path = tmp_path / "test_model.joblib"
    joblib.dump(model, path)
    return str(path)


@pytest.fixture
def worker():
    return ServingWorker()


class TestServingWorker:
    def test_load_model(self, worker, trained_model_path):
        result = worker.load_model("test-model", "1.0.0", "sklearn", trained_model_path)
        assert result["status"] == "loaded"
        assert "metadata" in result

    def test_load_model_duplicate(self, worker, trained_model_path):
        worker.load_model("test-model", "1.0.0", "sklearn", trained_model_path)
        result = worker.load_model("test-model", "1.0.0", "sklearn", trained_model_path)
        assert result["status"] == "already_loaded"

    def test_predict(self, worker, trained_model_path):
        worker.load_model("test-model", "1.0.0", "sklearn", trained_model_path)
        result = worker.predict("test-model", "1.0.0", [[1, 2, 3, 4]])
        assert "predictions" in result
        assert len(result["predictions"]) == 1

    def test_predict_not_loaded(self, worker):
        with pytest.raises(KeyError):
            worker.predict("missing", "1.0.0", [[1, 2, 3, 4]])

    def test_unload_model(self, worker, trained_model_path):
        worker.load_model("test-model", "1.0.0", "sklearn", trained_model_path)
        result = worker.unload_model("test-model", "1.0.0")
        assert result["status"] == "unloaded"

    def test_list_loaded(self, worker, trained_model_path):
        assert worker.list_loaded() == []
        worker.load_model("test-model", "1.0.0", "sklearn", trained_model_path)
        loaded = worker.list_loaded()
        assert len(loaded) == 1
        assert loaded[0]["model_name"] == "test-model"

    def test_unsupported_framework(self, worker):
        with pytest.raises(ValueError, match="Unsupported framework"):
            worker.load_model("test", "1.0.0", "unknown", "fake_path")