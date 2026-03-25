"""验证 A/B 路由流量分布的脚本"""
import asyncio
import httpx

GATEWAY_URL = "http://localhost:8002"
MODEL_NAME = "iris-classifier"
N_REQUESTS = 300


async def main():
    async with httpx.AsyncClient(timeout=30.0) as client:
        # 配置 A/B 路由 70:30
        await client.post(f"{GATEWAY_URL}/api/v1/gateway/ab/configure", json={
            "model_name": MODEL_NAME,
            "backends": [
                {"version": "1", "worker_url": "http://localhost:8001", "weight": 70},
                {"version": "2", "worker_url": "http://localhost:8003", "weight": 30},
            ],
        })

        # 发送请求并统计
        counts = {}
        for i in range(N_REQUESTS):
            resp = await client.post(
                f"{GATEWAY_URL}/api/v1/gateway/ab/predict/{MODEL_NAME}",
                json={"inputs": [[5.1, 3.5, 1.4, 0.2]]},
            )
            if resp.status_code != 200:
                print(f"请求失败: {resp.status_code} - {resp.text}")
                continue
            data = resp.json()
            version = data.get("_routed_to", {}).get("version", "?")
            counts[version] = counts.get(version, 0) + 1

            if (i + 1) % 50 == 0:
                print(f"  已发送 {i + 1}/{N_REQUESTS} 请求...")

        # 输出结果
        print(f"\n{'='*40}")
        print(f"总请求数: {N_REQUESTS}")
        print(f"配置权重: v1=70, v2=30")
        print(f"{'='*40}")
        for version in sorted(counts.keys()):
            count = counts[version]
            pct = count / N_REQUESTS * 100
            bar = "█" * int(pct / 2)
            print(f"  v{version}: {count:>4} 次 ({pct:5.1f}%) {bar}")


if __name__ == "__main__":
    asyncio.run(main())