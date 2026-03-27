# Alive Agent

存活提醒 Agent 的最小项目骨架。

## 当前状态

当前仅完成阶段 0：

- Python 项目骨架
- FastAPI 入口与健康检查
- Dockerfile
- Docker Compose
- `.env.example`

## 本地启动

1. 复制环境变量样例：

```bash
cp .env.example .env
```

2. 启动基础服务：

```bash
docker compose up --build
```

3. 验证 API：

```bash
curl http://localhost:8000/healthz
```

预期返回：

```json
{"status":"ok","app_env":"dev"}
```

## 当前目录

```text
app/
  api/
  core/
docker/
docker-compose.yml
pyproject.toml
README.md
```

## 下一阶段

阶段 1 将补充：

- SQLAlchemy
- Alembic
- PostgreSQL 数据表
- 配置持久化

