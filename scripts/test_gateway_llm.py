"""
测试 Gateway → LLM Worker → vLLM 完整链路
"""
import httpx
import asyncio


async def main():
    async with httpx.AsyncClient(timeout=120.0) as client:
        # 1. 注册 LLM Worker
        print("📌 注册 LLM Worker 到 Gateway...")
        reg = await client.post(
            "http://localhost:8002/api/v1/gateway/register",
            json={
                "model_name": "qwen2.5-1.5b",
                "version": "v1",
                "worker_url": "http://localhost:8003",
            },
        )
        print(f"   注册结果: {reg.json()}")

        # 2. 发送 Chat 请求
        print("\n💬 发送 Chat 请求...")
        resp = await client.post(
            "http://localhost:8002/api/v1/gateway/chat/qwen2.5-1.5b/v1",
            json={
                "messages": [
                    {"role": "user", "content": "什么是 Continuous Batching？一句话解释。"},
                ],
                "max_tokens": 100,
                "temperature": 0.7,
            },
        )

        if resp.status_code == 200:
            data = resp.json()
            print(f"   模型: {data.get('model')}")
            print(f"   回复: {data.get('content')}")
            if data.get("usage"):
                usage = data["usage"]
                print(f"   Token 用量: prompt={usage['prompt_tokens']}, "
                      f"completion={usage['completion_tokens']}, "
                      f"total={usage['total_tokens']}")
        else:
            print(f"   ❌ 错误: {resp.status_code} — {resp.text}")

        # 3. 检查路由表
        print("\n📋 Gateway 当前路由表:")
        routes = await client.get("http://localhost:8002/api/v1/gateway/routes")
        for route in routes.json()["routes"]:
            print(f"   {route['key']} → {route['worker_url']}")


if __name__ == "__main__":
    asyncio.run(main())