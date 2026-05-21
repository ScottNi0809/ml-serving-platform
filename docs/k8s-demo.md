# K8s 命令参考

## 前置条件

```bash
# 确认 minikube 运行中
minikube status

# 如果未启动
minikube start --cpus=4 --memory=8192

# 启用必要插件
minikube addons enable ingress
minikube addons enable metrics-server
```

---

## 方式一：原生 K8s Manifests（k8s/ 目录）

### 部署

```bash
# 构建镜像到 minikube 的 Docker 环境（不用推远程仓库）
eval $(minikube docker-env)
docker build -t ml-registry:v1 -f Dockerfile.registry .
docker build -t ml-serving:v1 -f Dockerfile.serving .
docker build -t ml-gateway:v1 -f Dockerfile.serving .
docker build -t ml-llm-worker:v1 -f Dockerfile.llm-worker .

# 一次性部署所有资源
kubectl apply -f k8s/

# 或逐步部署
kubectl apply -f k8s/pvc-registry-data.yaml
kubectl apply -f k8s/pvc-model-store.yaml
kubectl apply -f k8s/configmap-registry.yaml
kubectl apply -f k8s/deployment-registry.yaml
kubectl apply -f k8s/service-registry.yaml
kubectl apply -f k8s/deployment-ml-worker.yaml
kubectl apply -f k8s/service-ml-worker.yaml
kubectl apply -f k8s/deployment-gateway.yaml
kubectl apply -f k8s/service-gateway.yaml
```

### 查看状态

```bash
# 所有 Pod 状态
kubectl get pods -o wide

# 所有 Service
kubectl get svc

# 所有 Deployment
kubectl get deploy

# 查看 PVC 状态
kubectl get pvc
```

### 清理

```bash
kubectl delete -f k8s/
```

---

## 方式二：Helm Chart（chart/ 目录）

### 部署

```bash
# 预览渲染结果（不实际部署，展示模板能力）
helm template ml-platform ./chart

# 用开发配置部署
helm install ml-platform ./chart -f chart/values-dev.yaml

# 用生产配置部署
helm install ml-platform ./chart -f chart/values-prod.yaml

# 升级（修改配置后）
helm upgrade ml-platform ./chart -f chart/values-dev.yaml
```

### 查看 Helm Release 状态

```bash
# 列出所有 release
helm list

# 查看当前 release 的状态
helm status ml-platform

# 查看 release 历史（可展示 rollback 能力）
helm history ml-platform
```

### Helm Rollback

```bash
# 回滚到上一个版本
helm rollback ml-platform

# 回滚到指定版本号
helm rollback ml-platform 1
```

### 清理

```bash
helm uninstall ml-platform
```

---

## 核心 K8s 操作

### 1. 查看 Pod 详情和日志

```bash
# 查看某个 Pod 的详细信息（events、状态、调度）
kubectl describe pod -l app.kubernetes.io/component=gateway

# 查看 Gateway 日志
kubectl logs -l app.kubernetes.io/component=gateway --tail=50

# 实时跟踪日志
kubectl logs -l app.kubernetes.io/component=gateway -f
```

### 2. 端口转发（访问集群内服务）

```bash
# 转发 Gateway 到本地 8002
kubectl port-forward svc/ml-platform-gateway 8002:8002

# 转发 Registry 到本地 8000
kubectl port-forward svc/ml-platform-registry 8000:8000

# 转发 Prometheus（如果部署了）
kubectl port-forward svc/prometheus 9090:9090
```

### 3. 扩缩容演示

```bash
# 手动扩容 ML Worker 到 3 副本
kubectl scale deployment ml-platform-ml-worker --replicas=3

# 查看扩容过程
kubectl get pods -w

# 缩回 1 副本
kubectl scale deployment ml-platform-ml-worker --replicas=1
```

### 4. HPA 自动伸缩

```bash
# 查看 HPA 状态
kubectl get hpa

# 详细查看 HPA 指标和决策
kubectl describe hpa ml-platform-gateway

# 启用 autoscaling（通过 Helm values）
helm upgrade ml-platform ./chart --set autoscaling.enabled=true

# 观察 HPA 在压测下的扩容行为
kubectl get hpa -w
```

**要点：**
- Gateway HPA: min=1, max=5, CPU target=70%, Memory target=80%
- ML Worker HPA: min=1, max=10, CPU target=70%
- scaleDown 稳定窗口 300s（避免抖动）
- scaleUp 最快 30s 反应，每次最多翻倍或加 2 pod

### 5. 滚动更新演示

```bash
# 更新镜像触发滚动更新
kubectl set image deployment/ml-platform-gateway \
  gateway=ml-gateway:v2

# 查看滚动更新状态
kubectl rollout status deployment/ml-platform-gateway

# 查看更新历史
kubectl rollout history deployment/ml-platform-gateway

# 回滚到上一版本
kubectl rollout undo deployment/ml-platform-gateway
```

### 6. ConfigMap 热更新

```bash
# 查看当前 ConfigMap
kubectl get configmap ml-platform-registry -o yaml

# 编辑 ConfigMap（修改环境变量）
kubectl edit configmap ml-platform-registry

# 重启 Pod 使新配置生效
kubectl rollout restart deployment/ml-platform-registry
```

### 7. 资源使用情况

```bash
# 查看 Node 资源使用
kubectl top nodes

# 查看 Pod 资源使用
kubectl top pods

# 按 CPU 排序
kubectl top pods --sort-by=cpu
```

### 8. 健康检查验证

```bash
# 查看 Pod 的 liveness/readiness probe 状态
kubectl describe pod -l app.kubernetes.io/component=gateway | grep -A5 "Liveness\|Readiness"

# 模拟服务不健康（删掉 Pod 看自愈）
kubectl delete pod -l app.kubernetes.io/component=gateway
kubectl get pods -w  # 观察 K8s 自动重建
```

---

## 完整流程脚本

```bash
# ① 构建镜像
eval $(minikube docker-env)
docker build -t ml-registry:v1 -f Dockerfile.registry .
docker build -t ml-serving:v1 -f Dockerfile.serving .
docker build -t ml-gateway:v1 -f Dockerfile.serving .

# ② Helm 部署
helm install ml-platform ./chart -f chart/values-dev.yaml

# ③ 等待就绪
kubectl get pods -w
# 等到所有 Pod 状态为 Running

# ④ 端口转发
kubectl port-forward svc/ml-platform-gateway 8002:8002 &
kubectl port-forward svc/ml-platform-registry 8000:8000 &

# ⑤ 运行 demo
bash scripts/demo.sh

# ⑥ 展示扩容
kubectl scale deployment ml-platform-ml-worker --replicas=3
kubectl get pods -w

# ⑦ 展示自愈
kubectl delete pod -l app.kubernetes.io/component=gateway
kubectl get pods -w

# ⑧ 清理
helm uninstall ml-platform
```

---

## 关键文件位置速查

| 内容 | 路径 |
|------|------|
| 原生 Manifests | `k8s/` |
| Helm Chart | `chart/` |
| 默认 Values | `chart/values.yaml` |
| 开发环境覆盖 | `chart/values-dev.yaml` |
| 生产环境覆盖 | `chart/values-prod.yaml` |
| HPA 模板 | `chart/templates/hpa-gateway.yaml` |
| Ingress 模板 | `chart/templates/ingress.yaml` |
