"""
对比 ML Worker 和 LLM Worker 的端到端延迟。
展示不同推理类型的性能特征。
"""
import httpx
import asyncio
import time

GATEWAY = "http://localhost:8002"


async def benchmark_llm(client: httpx.AsyncClient, n: int = 5) -> list[float]:
    """测量 LLM 推理延迟"""
    latencies = []
    for i in range(n):
        start = time.perf_counter()
        resp = await client.post(
            f"{GATEWAY}/api/v1/gateway/chat/qwen2.5-1.5b/v1",
            json={
                "messages": [{"role": "user", "content": "hi"}],
                "max_tokens": 20,
                "temperature": 0.0,
            },
        )
        elapsed = time.perf_counter() - start
        latencies.append(elapsed)
        status = "✅" if resp.status_code == 200 else "❌"
        print(f"  LLM #{i+1}: {elapsed:.3f}s {status}")
    return latencies


async def benchmark_ml(client: httpx.AsyncClient, n: int = 5) -> list[float]:
    """测量 ML 推理延迟（需要 iris 模型已加载）"""
    latencies = []
    for i in range(n):
        start = time.perf_counter()
        resp = await client.post(
            f"{GATEWAY}/api/v1/gateway/predict/iris-classifier/v1",
            json={"inputs": [[5.1, 3.5, 1.4, 0.2]]},
        )
        elapsed = time.perf_counter() - start
        latencies.append(elapsed)
        status = "✅" if resp.status_code == 200 else "❌"
        print(f"  ML  #{i+1}: {elapsed:.3f}s {status}")
    return latencies


async def main():
    async with httpx.AsyncClient(timeout=120.0) as client:
        print("📊 LLM 推理延迟（Gateway → LLM Worker → vLLM）")
        llm_lats = await benchmark_llm(client)

        print(f"\n📊 ML 推理延迟（Gateway → ML Worker → sklearn）")
        ml_lats = await benchmark_ml(client)

        print(f"\n{'='*50}")
        print(f"LLM 平均延迟: {sum(llm_lats)/len(llm_lats):.3f}s")
        print(f"ML  平均延迟: {sum(ml_lats)/len(ml_lats):.3f}s")
        print(f"差异倍数: {sum(llm_lats)/len(llm_lats) / (sum(ml_lats)/len(ml_lats) + 1e-9):.0f}x")

        print(f"\n💡 为什么 LLM 这么慢？")
        print(f"   - ML 推理：sklearn predict 是 CPU 矩阵运算，微秒级")
        print(f"   - LLM 推理：GPU 逐 token 自回归生成，GPU kernel launch + memory ops")
        print(f"   - LLM 多了一跳：Gateway → LLM Worker → vLLM（两次 HTTP）")


if __name__ == "__main__":
    asyncio.run(main())