"""
并发流式请求测试 — 多个客户端同时发送流式请求
"""
import httpx
import asyncio
import json
import time


async def single_stream(client: httpx.AsyncClient, client_id: int) -> dict:
    """单个客户端的流式请求"""
    start = time.perf_counter()
    first_token_time = None
    token_count = 0

    try:
        async with client.stream(
            "POST",
            "http://localhost:8003/api/v1/chat/completions",
            json={
                "messages": [{"role": "user", "content": f"数到{client_id + 3}"}],
                "max_tokens": 30,
                "temperature": 0.0,
                "stream": True,
            },
        ) as resp:
            async for line in resp.aiter_lines():
                if not line.strip() or not line.startswith("data: "):
                    continue
                data_str = line[6:]
                if data_str.strip() == "[DONE]":
                    break
                try:
                    chunk = json.loads(data_str)
                    if chunk.get("content"):
                        token_count += 1
                        if first_token_time is None:
                            first_token_time = time.perf_counter()
                except json.JSONDecodeError:
                    continue
    except Exception as e:
        return {"client_id": client_id, "error": str(e)}

    total = time.perf_counter() - start
    ttft = (first_token_time or time.perf_counter()) - start
    return {
        "client_id": client_id,
        "ttft": ttft,
        "total": total,
        "tokens": token_count,
    }


async def main():
    concurrency = 5
    print(f"🚀 并发 {concurrency} 个流式请求\n")

    async with httpx.AsyncClient(timeout=120.0) as client:
        tasks = [single_stream(client, i) for i in range(concurrency)]
        results = await asyncio.gather(*tasks)

    print(f"\n{'Client':<10} {'TTFT':<10} {'Total':<10} {'Tokens':<8}")
    print("-" * 40)
    for r in results:
        if "error" in r:
            print(f"#{r['client_id']:<9} ERROR: {r['error']}")
        else:
            print(f"#{r['client_id']:<9} {r['ttft']:.3f}s    {r['total']:.3f}s    {r['tokens']}")

    valid = [r for r in results if "error" not in r]
    if valid:
        avg_ttft = sum(r["ttft"] for r in valid) / len(valid)
        max_ttft = max(r["ttft"] for r in valid)
        print(f"\n📊 平均 TTFT: {avg_ttft:.3f}s, 最大 TTFT: {max_ttft:.3f}s")
        print(f"💡 并发增加后 TTFT 会升高，因为 vLLM 的 Continuous Batching")
        print(f"   需要在 GPU 上同时处理多个请求的 Prefill + Decode")


if __name__ == "__main__":
    asyncio.run(main())