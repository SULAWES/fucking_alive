# Alive Agent

存活提醒 Agent，运行在 `Docker Compose + PostgreSQL + Python` 上，接入飞书长连接与 OpenAI 兼容 LLM，并支持未活跃邮件告警。

## 当前状态

当前已完成阶段 0 到阶段 6：

- Python 项目骨架与 Docker Compose
- SQLAlchemy / Alembic 与初始数据库迁移
- 飞书长连接接收消息
- `/alive`、`/help` 与消息落库
- OpenAI 兼容格式 LLM 接入
- SMTP 邮件发送与未活跃告警扫描
- HTTP 管理接口：`settings`、`contacts`、`email-template`、`test-alert`
- 飞书内配置管理：联系人命令、模板命令、二次确认流转

## 本地启动

1. 复制环境变量样例：

```bash
cp .env.example .env
```

2. 启动服务：

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

5. 单独执行数据库迁移：

```bash
docker compose run --rm api alembic upgrade head
```

6. 触发测试邮件接口：

```bash
curl -X POST http://localhost:8000/admin/test-alert \
  -H 'Authorization: Bearer change_me' \
  -H 'Content-Type: application/json' \
  -d '{
    "recipients": ["someone@example.com"],
    "subject": "test mail",
    "body": "test body"
  }'
```

注意：
- 真实发信前需要在 `.env` 中配置 `SMTP_HOST`、`SMTP_PORT`、`SMTP_USERNAME`、`SMTP_PASSWORD`、`SMTP_FROM`
- 如使用 `465` 端口，一般应设置 `SMTP_USE_SSL=true`、`SMTP_USE_TLS=false`

## 当前目录

```text
app/
  api/
  alerts/
  core/
  llm/
  mail/
docker/
docker-compose.yml
pyproject.toml
README.md
```

## 下一阶段

阶段 7 将补充：

- 稳定性与验收
- 回归测试与边界用例
- 部署与运维整理
