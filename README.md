# Alive Agent

存活提醒 Agent 的最小项目骨架。

## 当前状态

当前仅完成阶段 0：

- Python 项目骨架
- FastAPI 入口与健康检查
- Dockerfile
- Docker Compose
- `.env.example`
- SQLAlchemy 与 Alembic 基础配置
- 初始数据库迁移与种子数据

## 本地启动

1. 复制环境变量样例：

```bash
cp .env.example .env
```

2. 启动基础服务：

```bash
docker compose up --build
```

3. 执行数据库迁移：

```bash
docker compose run --rm api alembic upgrade head
```

4. 验证 API：

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

阶段 2 将补充：

- 飞书 webhook
- 消息接收
- `/alive`
- `/help`
