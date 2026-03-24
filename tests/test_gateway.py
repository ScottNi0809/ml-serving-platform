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