#!/bin/bash
# demo.sh — ML Model Serving Platform 完整演示
# 前置条件：docker compose up -d (基础服务已启动)

set -e
GREEN='\033[0;32m'
NC='\033[0m'

REGISTRY="http://localhost:8000/api/v1"
GATEWAY="http://localhost:8002/api/v1/gateway"
API_KEY="dev-api-key"

echo -e "${GREEN}=== Phase 1: Health Check ===${NC}"
curl -s http://localhost:8000/health | python3 -m json.tool
curl -s http://localhost:8002/health | python3 -m json.tool

echo -e "\n${GREEN}=== Phase 2: Register Model ===${NC}"
curl -s -X POST "$REGISTRY/models" \
  -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"name": "iris-classifier", "framework": "sklearn"}' | python3 -m json.tool

echo -e "\n${GREEN}=== Phase 3: sklearn Prediction ===${NC}"
# ... (注册 worker, 加载模型, 推理)

echo -e "\n${GREEN}=== Phase 4: A/B Routing ===${NC}"
# ... (配置 A/B, 多次请求展示分流, 回滚)

echo -e "\n${GREEN}=== Phase 5: LLM Chat (需要 GPU) ===${NC}"
# ... (注册 LLM worker, 非流式对话, 流式对话)

echo -e "\n${GREEN}=== Phase 6: Error Handling ===${NC}"
# ... (请求不存在的模型, 展示 404; 停掉 vLLM, 展示 503)