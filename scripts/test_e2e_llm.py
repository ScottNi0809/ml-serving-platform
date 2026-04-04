"""
端到端测试脚本 — 验证 vLLM → LLM Worker → Gateway 全链路
========================================================

前提：以下服务已启动：
  1. vLLM       (port 8100)
  2. LLM Worker (port 8003)
  3. Gateway    (port 8002)

用法：
  python scripts/test_e2e_llm.py

测试覆盖（共 12 个测试）：
  ✅ Phase 1: 各服务健康检查 (3 个)
  ✅ Phase 2: Worker 注册到 Gateway (1 个)
  ✅ Phase 3: 非流式 Chat 请求（Gateway → LLM Worker → vLLM）(2 个)
  ✅ Phase 4: 流式 Chat 请求（SSE）(3 个)
  ✅ Phase 5: 错误场景验证 (3 个)
"""
import httpx
import asyncio
import sys
import json

# 服务地址
VLLM_URL = "http://localhost:8100"
LLM_WORKER_URL = "http://localhost:8003"
GATEWAY_URL = "http://localhost:8002"

# 测试结果统计
passed = 0
failed = 0
errors = []


def report(test_name: str, success: bool, detail: str = ""):
    global passed, failed
    if success:
        passed += 1
        print(f"  ✅ {test_name}")
    else:
        failed += 1
        errors.append(f"{test_name}: {detail}")
        print(f"  ❌ {test_name} — {detail}")


async def run_tests():
    
    async with httpx.AsyncClient(timeout=120.0) as client:

        # ── Phase 1: 健康检查 ─────────────────────────────
        print("\n📋 Phase 1: 服务健康检查")

        # 1.1 vLLM 健康
        try:
            resp = await client.get(f"{VLLM_URL}/health")
            report("vLLM 健康检查", resp.status_code == 200)
        except Exception as e:
            report("vLLM 健康检查", False, f"连接失败: {e}")

        # 1.2 LLM Worker 健康
        try:
            resp = await client.get(f"{LLM_WORKER_URL}/health")
            data = resp.json()
            report(
                "LLM Worker 健康检查",
                data.get("status") in ("healthy", "degraded"),
                f"status={data.get('status')}",
            )
        except Exception as e:
            report("LLM Worker 健康检查", False, f"连接失败: {e}")

        # 1.3 Gateway 健康
        try:
            resp = await client.get(f"{GATEWAY_URL}/health")
            report("Gateway 健康检查", resp.status_code == 200)
        except Exception as e:
            report("Gateway 健康检查", False, f"连接失败: {e}")

        # ── Phase 2: 注册 ────────────────────────────────
        print("\n📋 Phase 2: Worker 注册")

        try:
            resp = await client.post(
                f"{GATEWAY_URL}/api/v1/gateway/register",
                json={
                    "model_name": "qwen2.5-1.5b",
                    "version": "v1",
                    "worker_url": LLM_WORKER_URL,
                },
            )
            data = resp.json()
            report("注册 LLM Worker", data.get("status") == "registered")
        except Exception as e:
            report("注册 LLM Worker", False, str(e))

        # ── Phase 3: 非流式 Chat ─────────────────────────
        print("\n📋 Phase 3: 非流式 Chat 请求")

        try:
            resp = await client.post(
                f"{GATEWAY_URL}/api/v1/gateway/chat/qwen2.5-1.5b/v1",
                json={
                    "messages": [
                        {"role": "user", "content": "用一句话解释什么是 KV Cache。"}
                    ],
                    "max_tokens": 100,
                    "temperature": 0.7,
                },
            )
            data = resp.json()
            has_content = bool(data.get("content"))
            has_usage = data.get("usage") is not None
            report(
                "非流式 Chat 响应",
                resp.status_code == 200 and has_content,
                f"content长度={len(data.get('content', ''))}",
            )
            report("响应包含 usage", has_usage)
        except Exception as e:
            report("非流式 Chat 响应", False, str(e))

        # ── Phase 4: 流式 Chat ───────────────────────────
        print("\n📋 Phase 4: 流式 Chat 请求（SSE）")

        try:
            chunks_received = 0
            content_pieces = []
            got_done = False

            async with client.stream(
                "POST",
                f"{GATEWAY_URL}/api/v1/gateway/chat/qwen2.5-1.5b/v1/stream",
                json={
                    "messages": [
                        {"role": "user", "content": "Hello!"}
                    ],
                    "max_tokens": 50,
                    "temperature": 0.7,
                },
            ) as resp:
                async for line in resp.aiter_lines():
                    if not line.strip():
                        continue
                    if line.startswith("data: "):
                        data_str = line[6:]
                        if data_str == "[DONE]":
                            got_done = True
                            break
                        try:
                            chunk = json.loads(data_str)
                            if chunk.get("content"):
                                content_pieces.append(chunk["content"])
                            chunks_received += 1
                        except json.JSONDecodeError:
                            pass

            report("SSE 流收到 chunks", chunks_received > 0, f"chunks={chunks_received}")
            report("SSE 流收到 [DONE]", got_done)
            report("流式内容非空", len(content_pieces) > 0, f"pieces={len(content_pieces)}")
        except Exception as e:
            report("流式 Chat 请求", False, str(e))

        # ── Phase 5: 错误场景 ────────────────────────────
        print("\n📋 Phase 5: 错误场景验证")

        # 5.1 未注册的模型应返回 404
        try:
            resp = await client.post(
                f"{GATEWAY_URL}/api/v1/gateway/chat/nonexistent-model/v1",
                json={
                    "messages": [{"role": "user", "content": "test"}],
                },
            )
            report("未注册模型返回 404", resp.status_code == 404)
        except Exception as e:
            report("未注册模型返回 404", False, str(e))

        # 5.2 空消息应返回 422（Pydantic 校验）
        try:
            resp = await client.post(
                f"{GATEWAY_URL}/api/v1/gateway/chat/qwen2.5-1.5b/v1",
                json={
                    "messages": [],
                },
            )
            report("空消息返回 422", resp.status_code == 422)
        except Exception as e:
            report("空消息返回 422", False, str(e))

        # 5.3 超出 max_tokens 上限应返回 422
        try:
            resp = await client.post(
                f"{GATEWAY_URL}/api/v1/gateway/chat/qwen2.5-1.5b/v1",
                json={
                    "messages": [{"role": "user", "content": "test"}],
                    "max_tokens": 99999,
                },
            )
            report("超限 max_tokens 返回 422", resp.status_code == 422)
        except Exception as e:
            report("超限 max_tokens 返回 422", False, str(e))


async def main():
    print("=" * 60)
    print("🧪 ML Serving Platform — 端到端测试")
    print("=" * 60)

    await run_tests()

    print("\n" + "=" * 60)
    print(f"📊 结果：{passed} passed, {failed} failed")
    if errors:
        print("\n❌ 失败详情：")
        for err in errors:
            print(f"   - {err}")
    print("=" * 60)

    sys.exit(0 if failed == 0 else 1)


if __name__ == "__main__":
    asyncio.run(main())