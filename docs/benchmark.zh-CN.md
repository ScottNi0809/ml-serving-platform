# 性能压测报告

[![English](https://img.shields.io/badge/lang-English-blue)](benchmark.md)

> 最后更新：2026-04-21  
> 测试工具：Locust 2.x  
> 测试环境：DELL Precision 5570

## 测试环境

| 组件 | 规格 |
|------|------|
| 机器 | DELL Precision 5570 |
| CPU | 14 核 |
| 内存 | 64GB |
| 操作系统 | Windows 11 |
| Docker | 29.4.0 |
| Python | 3.11 |
| 架构 | Registry + Serving + Gateway（docker compose） |
| 数据库 | SQLite |

## 测试场景

两种场景，按加权任务分布：

**读密集型（75% 用户）：** 40% 列出模型、30% 获取路由、20% 健康检查、10% 详情查询  
**读写混合型（25% 用户）：** 40% 列表、30% 注册模型、20% 路由操作、10% 健康检查

## 结果摘要

### 吞吐量扩展

| 并发用户 | 总 RPS | P50 (ms) | P95 (ms) | P99 (ms) | 错误率 |
|:---:|:---:|:---:|:---:|:---:|:---:|
| 10（基线） | 23.88 | 5 | 9 | 16 | 0% |
| 50（负载） | 120.79 | 5 | 11 | 18 | 0% |
| 100（压力） | 239.00 | 4 | 12 | 22 | 0% |
| 200（压力） | 453.77 | 4 | 17 | 30 | 0% |

### 各端点明细（50 用户）

| 端点 | RPS | P50 (ms) | P95 (ms) | P99 (ms) |
|------|:---:|:---:|:---:|:---:|
| GET /api/v1/models | 53.66 | 6 | 12 | 18 |
| GET /api/v1/gateway/routes | 37.80 | 4 | 7 | 11 |
| POST /api/v1/models | 3.82 | 12 | 21 | 26 |
| GET /health | 25.52 | 4 | 7 | 11 |

## 分析

### 观测结论
1. QPS 在 200 并发用户内近线性扩展（23.88 → 120.79 → 239.00 → 453.77 RPS）
2. 超过 100 用户后，P99 延迟增长更明显（22ms → 30ms），但 QPS 仍在持续增长
3. 所有测试梯度（10 / 50 / 100 / 200 用户）错误率均为 0%

### 瓶颈
- 主要瓶颈：SQLite 写竞争 + 单 Uvicorn Worker
- 证据：POST /api/v1/models [CREATE] P99 从 21ms（10 用户）→ 26ms（50）→ 43ms（100）→ 54ms（200），是所有端点中延迟增幅最大的

### 优化方向
1. **增加 Uvicorn Worker 数量**（1→4）：预期在多核下吞吐提升约 3 倍
2. **为模型列表添加 Redis 缓存**：预期读端点性能提升约 5 倍
3. **通过 K8s HPA 水平扩展**：吞吐随副本数线性增长

## 如何复现

```bash
# 启动服务
docker compose up -d

# 运行压测
./benchmarks/run_benchmark.sh

# 或使用自定义参数
USERS=50 SPAWN_RATE=10 RUN_TIME=120s ./benchmarks/run_benchmark.sh
```
