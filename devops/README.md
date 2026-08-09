# 本地目标库与集成测试

## 默认起什么

| 服务 | 端口 | 说明 |
|------|------|------|
| ArangoDB 3.12.4 | `18529` | `--experimental-vector-index`，覆盖本 Bundle Arango ANN 全路径 |

Astra 云 / 自建 HCD Data API：**不在默认 compose 里**（镜像源通常拉不到 HCD）。  
配好 `devops/.env.integration` 后，同一套 `pytest -m integration` 会跑 Astra 用例。

## 命令

```bash
./devops/db-up.sh                 # 拉镜像（必要时 DaoCloud）并启动
./devops/test-integration.sh      # 真库测试（先 up）
./devops/test-integration.sh --skip-up   # 库已起时
./devops/db-down.sh               # 停并删 volume
./devops/db-down.sh --keep-data   # 停但保留数据
```

单元测试（不碰库）：

```bash
mise exec -- uv run pytest -m "not integration"
```

## 环境变量

见 `env.integration.example`。
