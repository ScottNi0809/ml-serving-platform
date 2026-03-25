"""Gateway 单元测试"""
import pytest
from httpx import AsyncClient, ASGITransport

from serving.gateway_app import app, router


@pytest.fixture(autouse=True)
def clean_routes():
    """每个测试前清空路由表"""
    router._routes.clear()
    yield
    router._routes.clear()


@pytest.mark.anyio
async def test_health():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["service"] == "gateway"
    assert data["registered_routes"] == 0


@pytest.mark.anyio
async def test_register_and_list_routes():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # 注册
        resp = await ac.post("/api/v1/gateway/register", json={
            "model_name": "test-model",
            "version": "1",
            "worker_url": "http://localhost:9999",
        })
        assert resp.status_code == 200
        assert resp.json()["status"] == "registered"

        # 查看路由
        resp = await ac.get("/api/v1/gateway/routes")
        routes = resp.json()["routes"]
        assert len(routes) == 1
        assert routes[0]["key"] == "test-model:1"


@pytest.mark.anyio
async def test_deregister_route():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # 先注册
        await ac.post("/api/v1/gateway/register", json={
            "model_name": "test-model",
            "version": "1",
            "worker_url": "http://localhost:9999",
        })

        # 注销
        resp = await ac.delete("/api/v1/gateway/routes/test-model/1")
        assert resp.status_code == 200
        assert resp.json()["status"] == "deregistered"

        # 确认已清空
        resp = await ac.get("/api/v1/gateway/routes")
        assert len(resp.json()["routes"]) == 0


@pytest.mark.anyio
async def test_predict_no_route_returns_404():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.post(
            "/api/v1/gateway/predict/nonexistent/1",
            json={"inputs": [[1.0, 2.0, 3.0, 4.0]]},
        )
        assert resp.status_code == 404


@pytest.mark.anyio
async def test_deregister_nonexistent_returns_404():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.delete("/api/v1/gateway/routes/no-such/1")
        assert resp.status_code == 404


# ───────────────── A/B 路由测试 ──────────────────────

@pytest.mark.anyio
async def test_configure_ab_route():
    """测试配置 A/B 路由"""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.post("/api/v1/gateway/ab/configure", json={
            "model_name": "test-model",
            "backends": [
                {"version": "1", "worker_url": "http://localhost:9001", "weight": 90},
                {"version": "2", "worker_url": "http://localhost:9002", "weight": 10},
            ],
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ab_route_set"
        assert len(data["backends"]) == 2
        assert data["total_weight"] == 100


@pytest.mark.anyio
async def test_list_ab_routes():
    """测试查看 A/B 路由列表"""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # 先配置
        await ac.post("/api/v1/gateway/ab/configure", json={
            "model_name": "model-a",
            "backends": [
                {"version": "1", "worker_url": "http://localhost:9001", "weight": 80},
                {"version": "2", "worker_url": "http://localhost:9002", "weight": 20},
            ],
        })

        # 查看列表
        resp = await ac.get("/api/v1/gateway/ab")
        assert resp.status_code == 200
        data = resp.json()
        assert "model-a" in data["ab_routes"]


@pytest.mark.anyio
async def test_get_ab_route_detail():
    """测试查看某模型的 A/B 配置"""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        await ac.post("/api/v1/gateway/ab/configure", json={
            "model_name": "model-b",
            "backends": [
                {"version": "1", "worker_url": "http://localhost:9001", "weight": 70},
                {"version": "3", "worker_url": "http://localhost:9003", "weight": 30},
            ],
        })

        resp = await ac.get("/api/v1/gateway/ab/model-b")
        assert resp.status_code == 200
        data = resp.json()
        assert data["model_name"] == "model-b"
        assert len(data["backends"]) == 2
        assert data["total_weight"] == 100


@pytest.mark.anyio
async def test_ab_predict_no_config_returns_404():
    """没有 A/B 配置时返回 404"""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.post(
            "/api/v1/gateway/ab/predict/nonexistent",
            json={"inputs": [[1.0, 2.0, 3.0, 4.0]]},
        )
        assert resp.status_code == 404


@pytest.mark.anyio
async def test_remove_ab_route():
    """测试移除 A/B 路由配置"""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # 先配置
        await ac.post("/api/v1/gateway/ab/configure", json={
            "model_name": "model-c",
            "backends": [
                {"version": "1", "worker_url": "http://localhost:9001", "weight": 100},
            ],
        })

        # 移除
        resp = await ac.delete("/api/v1/gateway/ab/model-c")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ab_route_removed"

        # 再查应该 404
        resp = await ac.get("/api/v1/gateway/ab/model-c")
        assert resp.status_code == 404


@pytest.mark.anyio
async def test_remove_nonexistent_ab_route_returns_404():
    """移除不存在的 A/B 配置返回 404"""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.delete("/api/v1/gateway/ab/no-such-model")
        assert resp.status_code == 404


def test_weighted_select_distribution():
    """验证加权选择算法的统计正确性"""
    from serving.gateway import GatewayRouter

    gw = GatewayRouter()
    backends = [
        {"version": "1", "worker_url": "http://a", "weight": 90},
        {"version": "2", "worker_url": "http://b", "weight": 10},
    ]

    counts = {"1": 0, "2": 0}
    n = 10000
    for _ in range(n):
        selected = gw._weighted_select(backends)
        counts[selected["version"]] += 1

    # 90% ± 3% 的容差（10000 次足够收敛）
    ratio_v1 = counts["1"] / n
    assert 0.87 < ratio_v1 < 0.93, f"v1 ratio = {ratio_v1}, expected ~0.90"