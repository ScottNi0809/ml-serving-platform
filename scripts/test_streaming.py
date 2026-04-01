"""
测试 SSE 流式输出 — 打字机效果演示
==================================
三种测试方式：
1. 直接调用 LLM Worker
2. 通过 Gateway 调用
3. 非流式 vs 流式延迟对比
"""
import httpx
import asyncio
import json
import time


async def test_llm_worker_stream():
    """测试 1：直接调用 LLM Worker 的流式输出"""
    print("=" * 60)
    print("测试 1：LLM Worker 直接流式调用")
    print("=" * 60)

    async with httpx.AsyncClient(timeout=120.0) as client:
        start = time.perf_counter()
        first_token_time = None

        async with client.stream(
            "POST",
            "http://localhost:8003/api/v1/chat/completions",
            json={
                "messages": [{"role": "user", "content": "什么是SSE？一句话解释。"}],
                "max_tokens": 100,
                "temperature": 0.7,
                "stream": True,
            },
        ) as response:
            async for line in response.aiter_lines():
                if not line.strip():
                    continue
                if line.startswith("data: "):
                    data_str = line[6:]
                    if data_str.strip() == "[DONE]":
                        break
                    try:
                        chunk = json.loads(data_str)
                        content = chunk.get("content", "")
                        if content:
                            if first_token_time is None:
                                first_token_time = time.perf_counter()
                            print(content, end="", flush=True)  # 逐字打印！
                    except json.JSONDecodeError:
                        continue

        total = time.perf_counter() - start
        ttft = first_token_time - start if first_token_time else total
        print(f"\n\n⏱️ TTFT (首字延迟): {ttft:.3f}s")
        print(f"⏱️ 总耗时: {total:.3f}s")


async def test_gateway_stream():
    """测试 2：通过 Gateway 的流式调用"""
    print("\n" + "=" * 60)
    print("测试 2：Gateway 流式调用")
    print("=" * 60)

    async with httpx.AsyncClient(timeout=120.0) as client:
        # 先注册（幂等操作）
        await client.post(
            "http://localhost:8002/api/v1/gateway/register",
            json={
                "model_name": "qwen2.5-1.5b",
                "version": "v1",
                "worker_url": "http://localhost:8003",
            },
        )

        start = time.perf_counter()
        first_token_time = None

        async with client.stream(
            "POST",
            "http://localhost:8002/api/v1/gateway/chat/qwen2.5-1.5b/v1/stream",
            json={
                "messages": [
                    {"role": "system", "content": "你是AI基础设施专家。"},
                    {"role": "user", "content": "KV Cache为什么重要？两句话回答。"},
                ],
                "max_tokens": 100,
                "temperature": 0.7,
            },
        ) as response:
            async for line in response.aiter_lines():
                if not line.strip():
                    continue
                if line.startswith("data: "):
                    data_str = line[6:]
                    if data_str.strip() == "[DONE]":
                        break
                    try:
                        chunk = json.loads(data_str)
                        content = chunk.get("content", "")
                        if content:
                            if first_token_time is None:
                                first_token_time = time.perf_counter()
                            print(content, end="", flush=True)
                    except json.JSONDecodeError:
                        continue

        total = time.perf_counter() - start
        ttft = first_token_time - start if first_token_time else total
        print(f"\n\n⏱️ TTFT: {ttft:.3f}s")
        print(f"⏱️ 总耗时: {total:.3f}s")


async def test_stream_vs_nonstream():
    """测试 3：非流式 vs 流式的感知延迟对比"""
    print("\n" + "=" * 60)
    print("测试 3：Non-Streaming vs Streaming 延迟对比")
    print("=" * 60)

    question = "用Python写一个冒泡排序"
    max_tokens = 200

    async with httpx.AsyncClient(timeout=120.0) as client:
        # 非流式
        print("\n📦 Non-Streaming（等全部完成）...")
        start = time.perf_counter()
        resp = await client.post(
            "http://localhost:8003/api/v1/chat/completions",
            json={
                "messages": [{"role": "user", "content": question}],
                "max_tokens": max_tokens,
                "stream": False,
            },
        )
        non_stream_time = time.perf_counter() - start
        data = resp.json()
        print(f"   延迟: {non_stream_time:.3f}s（用户看到回复的时间）")
        print(f"   回复长度: {len(data.get('content', ''))} 字符")

        # 流式
        print("\n🌊 Streaming（逐 token 推送）...")
        start = time.perf_counter()
        first_token_time = None
        char_count = 0

        async with client.stream(
            "POST",
            "http://localhost:8003/api/v1/chat/completions",
            json={
                "messages": [{"role": "user", "content": question}],
                "max_tokens": max_tokens,
                "stream": True,
            },
        ) as response:
            async for line in response.aiter_lines():
                if not line.strip() or not line.startswith("data: "):
                    continue
                data_str = line[6:]
                if data_str.strip() == "[DONE]":
                    break
                try:
                    chunk = json.loads(data_str)
                    content = chunk.get("content", "")
                    if content:
                        char_count += len(content)
                        if first_token_time is None:
                            first_token_time = time.perf_counter()
                except json.JSONDecodeError:
                    continue

        stream_total = time.perf_counter() - start
        ttft = first_token_time - start if first_token_time else stream_total

        print(f"   TTFT (首字延迟): {ttft:.3f}s ← 用户开始看到内容的时间！")
        print(f"   总耗时: {stream_total:.3f}s")
        print(f"   回复长度: {char_count} 字符")

        print(f"\n{'='*60}")
        print(f"📊 对比总结：")
        print(f"   Non-Streaming 用户等待: {non_stream_time:.3f}s")
        print(f"   Streaming 首字到达:     {ttft:.3f}s")
        print(f"   用户感知提升:           {non_stream_time/ttft:.1f}x 更快看到内容！")


async def main():
    await test_llm_worker_stream()
    await test_gateway_stream()
    await test_stream_vs_nonstream()


if __name__ == "__main__":
    asyncio.run(main())