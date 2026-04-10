# Alive Agent

存活提醒 Agent，运行在 `Docker Compose + PostgreSQL + Python` 上，接入飞书长连接与 OpenAI 兼容 LLM，并支持未活跃邮件告警。

## 当前状态

当前已完成阶段 0 到阶段 7，并已进入阶段 8 的第一批增强：

- Python 项目骨架与 Docker Compose
- SQLAlchemy / Alembic 与初始数据库迁移
- 飞书长连接接收消息
- `/alive`、`/help` 与消息落库
- OpenAI 兼容格式 LLM 接入
- SMTP 邮件发送与未活跃告警扫描
- HTTP 管理接口：`settings`、`contacts`、`email-template`、`test-alert`
- 飞书内配置管理：联系人命令、模板命令、二次确认流转
- 阶段 7 回归测试、结构化日志与运维说明
- Prompt 版本化、命令纠错场景拆分、运行时开关与回滚能力

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

## 测试

在容器内运行当前回归测试：

```bash
docker compose up -d postgres
docker run --rm \
  --network fucking_alive_default \
  --env-file .env \
  -e PYTHONPATH=/app \
  -v "$PWD":/app \
  -w /app \
  fucking_alive-api \
  python -m unittest discover -s tests -v
```

## 运维注意事项

- `api` 容器负责 FastAPI 与飞书长连接
- `scheduler` 容器负责未活跃扫描
- 生产环境建议使用 `docker compose up -d`
- 修改 `.env` 中的飞书、SMTP、LLM 凭据后需要重启相关容器
- 日志已带基础上下文字段，可直接通过 `docker logs` 排查
- 建议定期备份 PostgreSQL 数据卷
- `app_settings.admin_feishu_user_id` 应设置为你的真实飞书账号，否则飞书内管理员命令不会生效

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

## 文档

- [docs/README.md](/home/heavenlysu/fucking_alive/docs/README.md)
- [docs/configuration.md](/home/heavenlysu/fucking_alive/docs/configuration.md)

## 阶段 8 进展

当前已完成：

- `chat_v1` / `chat_v2` 两个聊天 Prompt 版本
- `command_repair_v1` 命令纠错 Prompt
- `command_repair_v1` 的少量 few-shot 示例
- 运行时设置项：
  - `chat_prompt_version`
  - `command_repair_prompt_version`
  - `command_repair_enabled`
- 未知斜杠命令可按开关在“命令纠错”和“普通聊天”之间回退
- Prompt 已收紧为纯文本输出，避免飞书文本消息中的 Markdown 渲染问题
- Prompt 场景与版本进入结构化日志
- Prompt 样例回归集与单元测试
- 已完成真实飞书联调，对比验证 `command_repair_enabled=true/false` 两种行为

后续仍可继续：

- 记录真实联调效果与回滚结论
- 视需要增加更多 Prompt 版本
