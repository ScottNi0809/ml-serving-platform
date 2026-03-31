"""
vLLM OpenAI-compatible API 调用示例
演示如何用标准 OpenAI SDK 调用本地 vLLM 服务
"""
from openai import OpenAI

# 创建客户端 —— 唯一的区别是 base_url 指向本地 vLLM
client = OpenAI(
    base_url="http://localhost:8000/v1",
    api_key="not-needed"  # vLLM 本地不需要真正的 API key
)

# ========== 测试 1：Chat Completions ==========
print("=" * 50)
print("测试 1：Chat Completions")
print("=" * 50)

response = client.chat.completions.create(
    model="Qwen/Qwen2.5-1.5B-Instruct",
    messages=[
        {"role": "system", "content": "你是一个AI基础设施专家。请简洁回答。"},
        {"role": "user", "content": "请解释什么是PagedAttention，以及它为什么重要？"}
    ],
    max_tokens=300,
    temperature=0.7,
)

print(f"模型回复：\n{response.choices[0].message.content}")
print(f"\nToken 用量：")
print(f"  Prompt tokens: {response.usage.prompt_tokens}")
print(f"  Completion tokens: {response.usage.completion_tokens}")
print(f"  Total tokens: {response.usage.total_tokens}")

# ========== 测试 2：流式输出（Streaming） ==========
print("\n" + "=" * 50)
print("测试 2：Streaming（流式输出）")
print("=" * 50)

stream = client.chat.completions.create(
    model="Qwen/Qwen2.5-1.5B-Instruct",
    messages=[
        {"role": "user", "content": "用Python写一个快速排序，加上注释。"}
    ],
    max_tokens=500,
    temperature=0.3,
    stream=True,  # 开启流式输出
)

# 逐 token 打印（打字机效果）
for chunk in stream:
    if chunk.choices[0].delta.content is not None:
        print(chunk.choices[0].delta.content, end="", flush=True)
print()  # 换行

# ========== 测试 3：多轮对话 ==========
print("\n" + "=" * 50)
print("测试 3：多轮对话")
print("=" * 50)

messages = [
    {"role": "system", "content": "你是一个AI基础设施专家。"},
    {"role": "user", "content": "vLLM是什么？"}
]

# 第一轮
response1 = client.chat.completions.create(
    model="Qwen/Qwen2.5-1.5B-Instruct",
    messages=messages,
    max_tokens=200,
)
assistant_reply = response1.choices[0].message.content
print(f"[用户] vLLM是什么？")
print(f"[AI]   {assistant_reply}\n")

# 第二轮 —— 把上一轮的回复加入消息历史
messages.append({"role": "assistant", "content": assistant_reply})
messages.append({"role": "user", "content": "它和TGI（Text Generation Inference）相比有什么优势？"})

response2 = client.chat.completions.create(
    model="Qwen/Qwen2.5-1.5B-Instruct",
    messages=messages,
    max_tokens=300,
)
print(f"[用户] 它和TGI相比有什么优势？")
print(f"[AI]   {response2.choices[0].message.content}")

# ========== 测试 4：调节生成参数 ==========
print("\n" + "=" * 50)
print("测试 4：Temperature 对比")
print("=" * 50)

prompt_msg = [{"role": "user", "content": "给AI Infra工程师一条职业建议。"}]

for temp in [0.1, 0.7, 1.2]:
    resp = client.chat.completions.create(
        model="Qwen/Qwen2.5-1.5B-Instruct",
        messages=prompt_msg,
        max_tokens=100,
        temperature=temp,
    )
    print(f"\n[Temperature={temp}]")
    print(f"  {resp.choices[0].message.content[:150]}...")