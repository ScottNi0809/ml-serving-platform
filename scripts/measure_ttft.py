"""
TTFT 逐层测量 — 找出流式链路的延迟瓶颈
=========================================
分别测量：
1. vLLM 直连的 TTFT
2. LLM Worker 的 TTFT
3. Gateway 的 TTFT
看每一层加了多少延迟。
"""
import httpx
import asyncio
import json
import time


async def measure_ttft(
    url: str, payload: dict, label: str, n: int = 3
) -> list[float]:
    """测量指定 endpoint 的 TTFT"""
    ttfts = []
    async with httpx.AsyncClient(timeout=120.0) as client:
        for i in range(n):
            start = time.perf_counter()
            first_content_time = None

            async with client.stream("POST", url, json=payload) as resp:
                async for line in resp.aiter_lines():
                    if not line.strip() or not line.startswith("data: "):
                        continue
                    data_str = line[6:]
                    if data_str.strip() == "[DONE]":
                        break
                    try:
                        chunk = json.loads(data_str)
                        # 兼容两种格式
                        content = chunk.get("content") or ""
                        if not content:
                            choices = chunk.get("choices", [])
                            if choices:
                                delta = choices[0].get("delta", {})
                                content = delta.get("content", "")
                        if content and first_content_time is None:
                            first_content_time = time.perf_counter()
                            break  # 只要首字就够了
                    except json.JSONDecodeError:
                        continue

            ttft = (first_content_time or time.perf_counter()) - start
            ttfts.append(ttft)
            print(f"  {label} #{i+1}: TTFT = {ttft:.3f}s")

    return ttfts


async def main():
    question = "什么是SSE？"
    max_tokens = 50

    print("📊 TTFT 逐层测量\n")

    # Layer 1: vLLM 直连
    print("Layer 1: vLLM 直连 (localhost:8100)")
    vllm_ttfts = await measure_ttft(
        "http://localhost:8100/v1/chat/completions",
        {
            "model": "Qwen/Qwen2.5-1.5B-Instruct",
            "messages": [{"role": "user", "content": question}],
            "max_tokens": max_tokens,
            "stream": True,
        },
        "vLLM",
    )

    # Layer 2: LLM Worker
    print("\nLayer 2: LLM Worker (localhost:8003)")
    worker_ttfts = await measure_ttft(
        "http://localhost:8003/api/v1/chat/completions",
        {
            "messages": [{"role": "user", "content": question}],
            "max_tokens": max_tokens,
            "stream": True,
        },
        "Worker",
    )

    # Layer 3: Gateway
    print("\nLayer 3: Gateway (localhost:8002)")
    gw_ttfts = await measure_ttft(
        "http://localhost:8002/api/v1/gateway/chat/qwen2.5-1.5b/v1/stream",
        {
            "messages": [{"role": "user", "content": question}],
            "max_tokens": max_tokens,
        },
        "Gateway",
    )

    # 汇总
    avg = lambda xs: sum(xs) / len(xs)
    print(f"\n{'='*50}")
    print(f"📊 TTFT 汇总（{len(vllm_ttfts)} 次平均）:")
    print(f"  vLLM 直连:   {avg(vllm_ttfts):.3f}s")
    print(f"  LLM Worker:  {avg(worker_ttfts):.3f}s  (+ {avg(worker_ttfts)-avg(vllm_ttfts):.3f}s)")
    print(f"  Gateway:     {avg(gw_ttfts):.3f}s  (+ {avg(gw_ttfts)-avg(worker_ttfts):.3f}s)")
    print(f"\n  总代理开销:  {avg(gw_ttfts)-avg(vllm_ttfts):.3f}s")
    print(f"  GPU 推理占比: {avg(vllm_ttfts)/avg(gw_ttfts)*100:.0f}%")


if __name__ == "__main__":
    asyncio.run(main())