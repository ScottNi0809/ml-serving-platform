"""
Registry 测试套件
=================

覆盖：
- 健康检查
- 模型 CRUD（创建、列表、详情、更新、删除）
- 版本管理（创建版本、设置默认版本）
- 异常场景（重复名称、不存在的模型、缺少认证）

运行：
    pytest tests/ -v
"""

import pytest
from fastapi.testclient import TestClient

from registry.app import app
from registry.database import _db_path, create_tables

# ============================================================
# Fixtures
# ============================================================

API_KEY = "dev-api-key"
HEADERS = {"X-API-Key": API_KEY}


@pytest.fixture(autouse=True)
def fresh_db(tmp_path, monkeypatch):
    """每个测试使用独立的临时数据库"""
    import registry.database as db_mod

    test_db = str(tmp_path / "test.db")
    monkeypatch.setattr(db_mod, "_db_path", test_db)
    create_tables()
    yield


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def sample_model():
    return {
        "name": "test-bert",
        "framework": "pytorch",
        "description": "A test model",
        "tags": ["nlp", "test"],
    }


@pytest.fixture
def created_model(client, sample_model):
    """创建一个模型并返回响应"""
    resp = client.post("/api/v1/models", json=sample_model, headers=HEADERS)
    assert resp.status_code == 201
    return resp.json()


@pytest.fixture(autouse=True)
def override_storage(tmp_path):
    """用 dependency_overrides 把 storage 指向临时目录"""
    from registry.dependencies import get_storage
    from registry.storage import LocalStorage
    
    test_storage = LocalStorage(base_path=str(tmp_path / "test_store"))
    app.dependency_overrides[get_storage] = lambda: test_storage
    yield
    app.dependency_overrides.clear()

# ============================================================
# 健康检查
# ============================================================

class TestHealth:

    def test_health_returns_ok(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "healthy"
        assert data["service"] == "registry"


# ============================================================
# 认证
# ============================================================

class TestAuth:

    def test_missing_api_key_returns_401(self, client):
        resp = client.get("/api/v1/models")
        assert resp.status_code == 401

    def test_invalid_api_key_returns_401(self, client):
        resp = client.get("/api/v1/models", headers={"X-API-Key": "wrong"})
        assert resp.status_code == 401


# ============================================================
# 模型 CRUD
# ============================================================

class TestModelCRUD:

    def test_create_model(self, client, sample_model):
        resp = client.post("/api/v1/models", json=sample_model, headers=HEADERS)
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "test-bert"
        assert data["framework"] == "pytorch"
        assert data["status"] == "registered"
        assert data["version_count"] == 0

    def test_create_duplicate_model_returns_409(self, client, sample_model, created_model):
        resp = client.post("/api/v1/models", json=sample_model, headers=HEADERS)
        assert resp.status_code == 409

    def test_list_models(self, client, created_model):
        resp = client.get("/api/v1/models", headers=HEADERS)
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 1
        assert len(data["items"]) >= 1

    def test_get_model_by_name(self, client, created_model):
        name = created_model["name"]
        resp = client.get(f"/api/v1/models/{name}", headers=HEADERS)
        assert resp.status_code == 200
        assert resp.json()["name"] == name

    def test_get_nonexistent_model_returns_404(self, client):
        resp = client.get("/api/v1/models/no-such-model", headers=HEADERS)
        assert resp.status_code == 404

    def test_update_model(self, client, created_model):
        name = created_model["name"]
        resp = client.patch(
            f"/api/v1/models/{name}",
            json={"description": "Updated desc", "tags": ["updated"]},
            headers=HEADERS,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["description"] == "Updated desc"
        assert data["tags"] == ["updated"]

    def test_delete_model(self, client, created_model):
        name = created_model["name"]
        resp = client.delete(f"/api/v1/models/{name}", headers=HEADERS)
        assert resp.status_code == 204

        # 确认已删除
        resp = client.get(f"/api/v1/models/{name}", headers=HEADERS)
        assert resp.status_code == 404


# ============================================================
# 版本管理
# ============================================================

class TestVersionManagement:

    def test_create_version(self, client, created_model):
        name = created_model["name"]
        resp = client.post(
            f"/api/v1/models/{name}/versions",
            json={"version": "1.0.0", "description": "Initial version"},
            headers=HEADERS,
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["version"] == "1.0.0"
        assert data["is_default"] is True  # 第一个版本自动为默认

    def test_second_version_not_default(self, client, created_model):
        name = created_model["name"]
        client.post(
            f"/api/v1/models/{name}/versions",
            json={"version": "1.0.0"},
            headers=HEADERS,
        )
        resp = client.post(
            f"/api/v1/models/{name}/versions",
            json={"version": "2.0.0"},
            headers=HEADERS,
        )
        assert resp.status_code == 201
        assert resp.json()["is_default"] is False

    def test_list_versions(self, client, created_model):
        name = created_model["name"]
        client.post(f"/api/v1/models/{name}/versions", json={"version": "1.0.0"}, headers=HEADERS)
        client.post(f"/api/v1/models/{name}/versions", json={"version": "2.0.0"}, headers=HEADERS)

        resp = client.get(f"/api/v1/models/{name}/versions", headers=HEADERS)
        assert resp.status_code == 200
        assert len(resp.json()) == 2

    def test_set_default_version(self, client, created_model):
        name = created_model["name"]
        client.post(f"/api/v1/models/{name}/versions", json={"version": "1.0.0"}, headers=HEADERS)
        client.post(f"/api/v1/models/{name}/versions", json={"version": "2.0.0"}, headers=HEADERS)

        resp = client.put(f"/api/v1/models/{name}/versions/2.0.0/default", headers=HEADERS)
        assert resp.status_code == 200
        assert resp.json()["is_default"] is True

        # 验证模型的 default_version 也更新了
        model = client.get(f"/api/v1/models/{name}", headers=HEADERS).json()
        assert model["default_version"] == "2.0.0"

    def test_duplicate_version_returns_error(self, client, created_model):
        name = created_model["name"]
        client.post(f"/api/v1/models/{name}/versions", json={"version": "1.0.0"}, headers=HEADERS)
        resp = client.post(f"/api/v1/models/{name}/versions", json={"version": "1.0.0"}, headers=HEADERS)
        # DuplicateVersionError — 应返回错误（409 or 500 depending on handler）
        assert resp.status_code >= 400


# ============================================================
# 文件操作
# ============================================================

class TestFileOperations:
    """文件上传、下载、删除清理"""
    
    def _setup_model_with_version(self, client):
        """创建一个模型和版本，返回 (name, version)"""
        name = "file-ops-model"
        ver = "1.0.0"
        client.post("/api/v1/models", json={
            "name": name, "framework": "pytorch",
        }, headers=HEADERS)
        client.post(f"/api/v1/models/{name}/versions", json={
            "version": ver,
        }, headers=HEADERS)
        return name, ver

    # TODO: 在下面实现 5 个测试方法
    # 1. 上传文件
    def test_upload_file(self, client):
        name, ver = self._setup_model_with_version(client)
        file_content = b"dummy model data"
        files = {"file": ("model.bin", file_content)}
        resp = client.post(f"/api/v1/models/{name}/versions/{ver}/upload", files=files, headers=HEADERS)
        assert resp.status_code == 200

    # 2. 下载文件
    def test_download_file(self, client):
        name, ver = self._setup_model_with_version(client)
        file_content = b"dummy model data"
        files = {"file": ("model.bin", file_content)}
        client.post(f"/api/v1/models/{name}/versions/{ver}/upload", files=files, headers=HEADERS)

        resp = client.get(f"/api/v1/models/{name}/versions/{ver}/download", headers=HEADERS)
        assert resp.status_code == 200
        assert resp.content == file_content

    # 3. 删除文件
    def test_delete_file(self, client):
        name, ver = self._setup_model_with_version(client)
        file_content = b"dummy model data"
        files = {"file": ("model.bin", file_content)}
        client.post(f"/api/v1/models/{name}/versions/{ver}/upload", files=files, headers=HEADERS)

        resp = client.delete(f"/api/v1/models/{name}/versions/{ver}/file", headers=HEADERS)
        assert resp.status_code == 204

        # 确认文件已删除
        resp = client.get(f"/api/v1/models/{name}/versions/{ver}/download", headers=HEADERS)
        assert resp.status_code == 404  # 文件不存在

    # 4. 清理文件
    def test_cleanup_file(self, client):
        name, ver = self._setup_model_with_version(client)
        file_content = b"dummy model data"
        files = {"file": ("model.bin", file_content)}
        client.post(f"/api/v1/models/{name}/versions/{ver}/upload", files=files, headers=HEADERS)

        # 调用清理接口
        resp = client.post(f"/api/v1/models/{name}/versions/{ver}/cleanup", headers=HEADERS)
        assert resp.status_code == 200

        # 确认文件已删除
        resp = client.get(f"/api/v1/models/{name}/versions/{ver}/download", headers=HEADERS)
        assert resp.status_code == 404  # 文件不存在

    # 5. 清理所有文件
    def test_cleanup_all_files(self, client):
        name, ver = self._setup_model_with_version(client)
        file_content = b"dummy model data"
        files = {"file": ("model.bin", file_content)}
        client.post(f"/api/v1/models/{name}/versions/{ver}/upload", files=files, headers=HEADERS)

        # 调用清理所有文件接口
        resp = client.post("/api/v1/cleanup", headers=HEADERS)
        assert resp.status_code == 200

        # 确认文件已删除
        resp = client.get(f"/api/v1/models/{name}/versions/{ver}/download", headers=HEADERS)
        assert resp.status_code == 404  # 文件不存在


# ============================================================
# 版本管理进阶
# ============================================================

class TestVersionAdvanced:
    """自动版本号 + 删除版本 + 默认回退"""

    def _create_model(self, client, name = "adv-ver-model"):
        resp = client.post("/api/v1/models", json={
            "name": name,
            "framework": "pytorch",
        }, headers=HEADERS)
        assert resp.status_code == 201
        return name
    
    def test_auto_version_first(self, client):
        """创建版本时不指定版本号，自动分配 1.0.0"""
        name = self._create_model(client, "auto-ver-model-1")
        resp = client.post(f"/api/v1/models/{name}/versions", json={}, headers=HEADERS)
        assert resp.status_code == 201
        assert resp.json()["version"] == "1.0.0"

    def test_auto_version_increment(self, client):
        """连续创建版本，自动递增版本号"""
        name = self._create_model(client, "auto-ver-model-2")
        client.post(f"/api/v1/models/{name}/versions", json={}, headers=HEADERS)
        resp = client.post(f"/api/v1/models/{name}/versions", json={}, headers=HEADERS)
        assert resp.status_code == 201
        assert resp.json()["version"] == "1.0.1"

    def test_auto_after_manual_version(self, client):
        """在手动指定版本后，自动版本号继续递增"""
        name = self._create_model(client, "auto-ver-model-3")
        client.post(f"/api/v1/models/{name}/versions", json={"version": "2.0.0"}, headers=HEADERS)
        resp = client.post(f"/api/v1/models/{name}/versions", json={}, headers=HEADERS)
        assert resp.status_code == 201
        assert resp.json()["version"] == "2.0.1"

    def test_delete_non_default_version(self, client):
        """删除非默认版本，版本列表减少，默认不变"""
        name = self._create_model(client, "del-ver-model-1")
        client.post(f"/api/v1/models/{name}/versions", json={"version": "1.0.0"}, headers=HEADERS)
        client.post(f"/api/v1/models/{name}/versions", json={"version": "2.0.0"}, headers=HEADERS)

        resp = client.delete(f"/api/v1/models/{name}/versions/2.0.0", headers=HEADERS)
        assert resp.status_code == 204

        # 确认版本列表
        resp = client.get(f"/api/v1/models/{name}/versions", headers=HEADERS)
        assert len(resp.json()) == 1
        assert resp.json()[0]["version"] == "1.0.0"

    def test_delete_default_version_falls_back(self, client):
        """删除默认版本后，另一个版本成为新默认"""
        name = self._create_model(client, "del-ver-model-2")
        client.post(f"/api/v1/models/{name}/versions", json={"version": "1.0.0"}, headers=HEADERS)
        client.post(f"/api/v1/models/{name}/versions", json={"version": "2.0.0"}, headers=HEADERS)

        # 删除默认版本 1.0.0
        resp = client.delete(f"/api/v1/models/{name}/versions/1.0.0", headers=HEADERS)
        assert resp.status_code == 204

        # 确认 2.0.0 成为新默认
        resp = client.get(f"/api/v1/models/{name}", headers=HEADERS)
        assert resp.json()["default_version"] == "2.0.0"
