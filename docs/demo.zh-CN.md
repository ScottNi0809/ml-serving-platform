# 演示指南

[![English](https://img.shields.io/badge/lang-English-blue)](demo.md)

本指南将项目展示为一个 AI 基础设施工作流，而非一组独立 API。默认演示仅需 CPU，可在笔记本电脑上运行；GPU/vLLM 路径为可选。

## 演示证明了什么

主演示走过一个生产级服务生命周期：

1. 启动服务栈
2. 在 Registry 注册模型
3. 创建两个模型版本
4. 上传 sklearn 模型文件
5. 将版本加载到 ML Worker
6. 在 Gateway 注册路由
7. 通过 Gateway 发送预测流量
8. 配置 A/B 路由
9. 将全部流量回滚到稳定版本
10. 查看监控仪表盘

可选 GPU 步骤添加 vLLM 支持的 Chat Completions 和 SSE 流式输出。

## 前置条件

| 要求 | 说明 |
|------|------|
| Docker + Docker Compose | 服务栈必需 |
| Python 3.11 | 仅在 Docker 外运行服务时需要 |
| Python 依赖 | 在容器外运行辅助脚本时执行 `pip install -r requirements.txt` |
| Bash shell | 演示脚本基于 bash 编写 |
| NVIDIA Container Toolkit | 仅可选 GPU/vLLM 演示需要 |

本地 Registry 演示使用开发 API Key：

```bash
export API_KEY=dev-api-key
```

## CPU 演示

启动 CPU 栈：

```bash
docker compose up --build -d
```

运行演示：

```bash
bash scripts/demo.sh
```

预期阶段：

```text
=== Phase 1: Health Check ===
=== Phase 2: Prepare Demo Model ===
=== Phase 3: Register Model And Versions ===
=== Phase 4: Upload Artifact To Registry ===
=== Phase 5: Load Models Into ML Worker ===
=== Phase 6: Register Gateway Routes ===
=== Phase 7: Predict Through Gateway ===
=== Phase 8: Configure A/B Routing ===
=== Phase 9: One-click Rollback ===
=== Phase 10: Monitoring Pointers ===
```

预测响应应包含模型名称、版本和预测结果：

```json
{
  "model_name": "iris-classifier",
  "version": "1.0.0",
  "predictions": [0]
}
```

A/B 路由响应应包含 `_routed_to`，证明 Gateway 按权重选择了后端：

```json
{
  "model_name": "iris-classifier",
  "version": "1.0.0",
  "predictions": [0],
  "_routed_to": {
    "version": "1.0.0",
    "worker_url": "http://serving:8001",
    "weight": 90
  }
}
```

回滚响应应显示版本 `1.0.0` 权重 100，版本 `2.0.0` 权重 0。

## 监控演示

启动监控栈：

```bash
docker compose -f docker-compose.yml -f docker-compose.monitor.yml up --build -d
bash scripts/demo.sh
```

打开：

| 工具 | URL | 检查内容 |
|------|-----|----------|
| Prometheus | http://localhost:9090 | Targets `gateway` 和 `serving` 状态为 UP |
| Grafana | http://localhost:3000 | ML Platform 仪表盘展示 QPS、延迟、错误、活跃请求 |

常用 Prometheus 查询：

```promql
sum(rate(http_requests_total[1m])) by (service)
histogram_quantile(0.95, sum(rate(http_request_duration_seconds_bucket[5m])) by (le, service))
sum(http_active_requests) by (service)
sum(rate(inference_requests_total[1m])) by (model_name, version, status)
```

仪表盘截图：

![Grafana 仪表盘演示](../demo/grafana-dashboard.png)

## GPU / LLM 演示

启动 GPU 栈：

```bash
docker compose -f docker-compose.yml -f docker-compose.gpu.yml up --build -d
```

首次 vLLM 启动可能需要数分钟，因为需要下载和加载配置的模型。

运行可选 LLM 流程：

```bash
RUN_GPU_DEMO=1 bash scripts/demo.sh
```

脚本将：

1. 检查 LLM Worker 健康状态。
2. 在 Gateway 注册 `qwen2.5-1.5b:1.0.0`。
3. 通过 Gateway 调用非流式聊天。
4. 调用流式聊天并打印 SSE 块。

手动非流式请求：

```bash
curl -sS -X POST http://localhost:8002/api/v1/gateway/register \
  -H "Content-Type: application/json" \
  -d '{"model_name":"qwen2.5-1.5b","version":"1.0.0","worker_url":"http://llm-worker:8003"}'

curl -sS -X POST http://localhost:8002/api/v1/gateway/chat/qwen2.5-1.5b/1.0.0 \
  -H "Content-Type: application/json" \
  -d '{"messages":[{"role":"user","content":"Explain KV Cache in two sentences."}],"max_tokens":120}'
```

手动流式请求：

```bash
curl -N -X POST http://localhost:8002/api/v1/gateway/chat/qwen2.5-1.5b/1.0.0/stream \
  -H "Content-Type: application/json" \
  -d '{"messages":[{"role":"user","content":"Explain continuous batching in three bullets."}],"max_tokens":160}'
```

预期流式输出：

```text
data: {"content":"Continuous","finish_reason":null,"model":"Qwen/Qwen2.5-1.5B-Instruct"}
data: {"content":" batching","finish_reason":null,"model":"Qwen/Qwen2.5-1.5B-Instruct"}
...
data: [DONE]
```

## 压测演示

安装压测依赖：

```bash
pip install -r benchmarks/requirements.txt
```

运行负载测试：

```bash
docker compose up --build -d
USERS=50 SPAWN_RATE=10 RUN_TIME=120s ./benchmarks/run_benchmark.sh
```

已发布的压测报告见 [benchmark.zh-CN.md](benchmark.zh-CN.md)。记录的测试在 200 并发用户下达到约 454 RPS，0% 错误率。

## 故障排查

| 症状 | 可能原因 | 解决方法 |
|------|----------|----------|
| `Registry is not reachable` | Docker 栈未运行 | `docker compose up --build -d` |
| Gateway 预测返回 404 | Worker 路由未注册或演示被部分中断 | 重新运行 `bash scripts/demo.sh`；脚本会重置演示模型路由 |
| ML Worker 加载失败，文件缺失 | 演示模型文件未复制到容器内 | 重新运行脚本；它会训练并复制 `scripts/models/iris_classifier.joblib` |
| Prometheus target 为 DOWN | 监控栈未启动或服务名不匹配 | 使用 `docker compose -f docker-compose.yml -f docker-compose.monitor.yml up -d` |
| vLLM 健康状态持续 unhealthy | 模型仍在下载/加载或 GPU 运行时缺失 | 检查 `docker logs vllm-engine` 并验证 NVIDIA Container Toolkit |
| SSE 返回一次性缓冲响应 | 代理正在缓冲流 | 保持 `X-Accel-Buffering: no` 并使用 `curl -N` |

## 重置

移除容器和本地卷：

```bash
docker compose -f docker-compose.yml -f docker-compose.monitor.yml -f docker-compose.gpu.yml down -v
```

仅 CPU 栈：

```bash
docker compose down -v
```
