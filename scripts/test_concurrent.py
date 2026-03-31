"""
并发请求测试 —— 观察 vLLM 的 Continuous Batching 效果
"""
import time
import asyncio
from openai import AsyncOpenAI
from pathlib import Path

client = AsyncOpenAI(
    base_url="http://localhost:8100/v1",
    api_key="not-needed"
)

base_dir = Path(__file__).resolve().parent  # tests/
model_dir = base_dir.parent / "model_store" / "Qwen2.5-1.5B-Instruct"
print(model_dir)

# NOTE: 服务器 model 名称需要与当前可用模型一致。
# 本脚本会自动查询 vLLM /v1/models 并选第一个可用 model id。
MODEL = None

async def resolve_model():
    """从 vLLM /v1/models 获取可用 model_id（首个），为后续 API 调用提供模型名。"""
    global MODEL
    try:
        resp = await client.models.list()
        if resp.data:
            MODEL = resp.data[0].id
            print(f"选择模型: {MODEL}")
            return MODEL
    except Exception as e:
        print(f"无法通过 client.models.list() 获取模型列表，原因：{e}")

    # 回退设置（一般无效，除非 vLLM 直接支持此名称）
    MODEL = model_dir.name
    print(f"回退模型：{MODEL}")
    return MODEL

async def send_request(request_id: int, prompt: str, max_tokens: int, model: str):
    """发送单个请求并记录时间"""
    start = time.perf_counter()
    response = await client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=max_tokens,
        temperature=0.7,
    )
    end = time.perf_counter()
    
    output_tokens = response.usage.completion_tokens
    total_time = end - start
    
    print(f"  请求 {request_id}: {total_time:.2f}s, "
          f"{output_tokens} tokens, "
          f"{output_tokens/total_time:.1f} tok/s")
    
    return {"id": request_id, "time": total_time, "tokens": output_tokens}

async def run_concurrent_test(num_requests: int, max_tokens: int = 100, model: str | None = None):
    """并发发送多个请求"""
    if model is None:
        raise ValueError("必须传入 model 参数")

    prompts = [
        "用一句话解释什么是Docker。",
        "Python和C++的主要区别是什么？",
        "什么是KV Cache？",
        "微服务架构的优缺点是什么？",
        "什么是CI/CD？",
        "解释一下什么是GPU并行计算。",
        "什么是Kubernetes？",
        "如何优化数据库查询性能？",
    ]
    
    print(f"\n发送 {num_requests} 个并发请求（max_tokens={max_tokens}，model={model}）...")
    
    start = time.perf_counter()
    tasks = [
        send_request(i, prompts[i % len(prompts)], max_tokens, model)
        for i in range(num_requests)
    ]
    results = await asyncio.gather(*tasks)
    end = time.perf_counter()
    
    total_time = end - start
    total_tokens = sum(r["tokens"] for r in results)
    avg_latency = sum(r["time"] for r in results) / len(results)
    
    print(f"\n  --- 汇总 ---")
    print(f"  总耗时: {total_time:.2f}s")
    print(f"  总生成 tokens: {total_tokens}")
    print(f"  整体吞吐: {total_tokens/total_time:.1f} tokens/s")
    print(f"  平均延迟: {avg_latency:.2f}s")
    print(f"  QPS: {num_requests/total_time:.2f}")

async def main():
    model = await resolve_model()

    # 先测单个请求作为基线
    print("=" * 60)
    print("基线：单个请求")
    print("=" * 60)
    await run_concurrent_test(1, max_tokens=100, model=model)
    
    # 逐步增加并发
    for n in [2, 4, 8]:
        print(f"\n{'=' * 60}")
        print(f"并发数: {n}")
        print(f"{'=' * 60}")
        await run_concurrent_test(n, max_tokens=100, model=model)

asyncio.run(main())