"""
简单的 vLLM 性能基准测试
测量 TTFT（Time to First Token）和 TPOT（Time Per Output Token）
"""
import time
from openai import OpenAI

client = OpenAI(
    base_url="http://localhost:8100/v1",
    api_key="not-needed"
)

MODEL = "Qwen/Qwen2.5-1.5B-Instruct"

def measure_non_streaming(prompt: str, max_tokens: int = 200):
    """测量非 streaming 模式的端到端延迟"""
    start = time.perf_counter()
    response = client.chat.completions.create(
        model=MODEL,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=max_tokens,
        temperature=0.7,
    )
    end = time.perf_counter()
    
    total_time = end - start
    output_tokens = response.usage.completion_tokens
    tps = output_tokens / total_time if total_time > 0 else 0
    
    return {
        "total_time": round(total_time, 3),
        "output_tokens": output_tokens,
        "tokens_per_second": round(tps, 1),
        "content": response.choices[0].message.content[:100] + "..."
    }

def measure_streaming_ttft(prompt: str, max_tokens: int = 200):
    """测量 streaming 模式的 TTFT 和 TPOT"""
    start = time.perf_counter()
    first_token_time = None
    token_count = 0
    
    stream = client.chat.completions.create(
        model=MODEL,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=max_tokens,
        temperature=0.7,
        stream=True,
    )
    
    for chunk in stream:
        if chunk.choices[0].delta.content:
            if first_token_time is None:
                first_token_time = time.perf_counter()
            token_count += 1
    
    end = time.perf_counter()
    ttft = first_token_time - start if first_token_time else None
    total_time = end - start
    decode_time = end - first_token_time if first_token_time else 0
    tpot = (decode_time / (token_count - 1) * 1000) if token_count > 1 else None  # ms per token
    
    return {
        "ttft_ms": round(ttft * 1000, 1) if ttft else None,
        "tpot_ms": round(tpot, 1) if tpot else None,
        "total_time": round(total_time, 3),
        "token_count": token_count,
    }

# ========== 测试不同 prompt 长度 ==========
print("=" * 60)
print("测试 1：Non-Streaming 性能")
print("=" * 60)

prompts = [
    ("短 prompt", "你好"),
    ("中等 prompt", "请详细解释什么是微服务架构，以及它和单体架构的区别。"),
    ("长 prompt", "请从以下几个维度详细对比分析 vLLM、TGI 和 llama.cpp 三个推理框架："
     "1. 核心技术原理 2. 性能表现 3. 硬件要求 4. 适用场景 5. 易用性。"
     "每个维度请给出具体的例子和数据。"),
]

for name, prompt in prompts:
    result = measure_non_streaming(prompt, max_tokens=200)
    print(f"\n[{name}]")
    print(f"  总时间: {result['total_time']}s")
    print(f"  输出 tokens: {result['output_tokens']}")
    print(f"  生成速度: {result['tokens_per_second']} tokens/s")

# ========== 测试 Streaming TTFT ==========
print("\n" + "=" * 60)
print("测试 2：Streaming TTFT & TPOT")
print("=" * 60)

for name, prompt in prompts:
    result = measure_streaming_ttft(prompt, max_tokens=200)
    print(f"\n[{name}]")
    print(f"  TTFT: {result['ttft_ms']}ms")
    print(f"  TPOT: {result['tpot_ms']}ms/token")
    print(f"  总时间: {result['total_time']}s")
    print(f"  Token 数: {result['token_count']}")