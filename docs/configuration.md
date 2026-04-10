# 配置与接入清单

本文档只整理当前项目真实需要的配置，不包含任何私密值。

## 1. 配置分层

当前配置分 3 层：

1. `.env`
- 基础设施和敏感配置
- 如数据库、飞书凭据、LLM API Key、SMTP、`ADMIN_TOKEN`

2. HTTP 管理接口
- 运行时业务配置
- 通过 `Bearer Token` 保护的 `/admin/*` 接口修改

3. 飞书内管理命令
- 受限子集
- 只允许修改联系人和邮件模板
- 需要管理员身份和二次确认

## 2. `.env` 必填项

来源：
- [config.py](/home/heavenlysu/fucking_alive/app/core/config.py)
- [.env.example](/home/heavenlysu/fucking_alive/.env.example)

### 2.1 应用与数据库

```env
APP_NAME=alive-agent
APP_ENV=dev
APP_HOST=0.0.0.0
APP_PORT=8000
APP_TIMEZONE=Asia/Shanghai
LOG_LEVEL=INFO

DATABASE_URL=postgresql+psycopg://alive_agent:change_me@postgres:5432/alive_agent
```

### 2.2 飞书

当前实现使用长连接接收事件。

```env
FEISHU_APP_ID=
FEISHU_APP_SECRET=
FEISHU_VERIFICATION_TOKEN=
FEISHU_ENCRYPT_KEY=
FEISHU_DOMAIN=https://open.feishu.cn
FEISHU_LONG_CONNECTION_ENABLED=true
```

说明：
- 长连接模式下，实际接收消息只依赖 `FEISHU_APP_ID`、`FEISHU_APP_SECRET`
- `FEISHU_VERIFICATION_TOKEN` 和 `FEISHU_ENCRYPT_KEY` 当前不参与长连接消息接收
- 如果未来切回 webhook，可以继续复用这两个字段

### 2.3 LLM

```env
DEFAULT_LLM_PROVIDER=openai
DEFAULT_LLM_MODEL=gpt-4.1-mini
CHAT_CONTEXT_MESSAGES=10
CHAT_PROMPT_VERSION=chat_v2
COMMAND_REPAIR_PROMPT_VERSION=command_repair_v1
COMMAND_REPAIR_ENABLED=true
```

```env
OPENAI_API_KEY=
OPENAI_BASE_URL=https://api.openai.com/v1

ANTHROPIC_API_KEY=
ANTHROPIC_BASE_URL=https://api.anthropic.com

GEMINI_API_KEY=
GEMINI_BASE_URL=https://generativelanguage.googleapis.com/v1beta
```

说明：
- 当前真实接入的是 OpenAI 兼容格式
- Anthropic / Gemini 当前保留占位 adapter
- `CHAT_PROMPT_VERSION` 当前支持：
  - `chat_v1`
  - `chat_v2`
- `COMMAND_REPAIR_PROMPT_VERSION` 当前支持：
  - `command_repair_v1`
- `COMMAND_REPAIR_ENABLED=true` 时，未知斜杠命令优先进入命令纠错场景
- `COMMAND_REPAIR_ENABLED=false` 时，未知斜杠命令回退到普通聊天场景

### 2.4 告警与管理

```env
ALERT_DEFAULT_HOURS=72
ALERT_SCAN_INTERVAL_MINUTES=10
ADMIN_FEISHU_USER_ID=
ADMIN_TOKEN=change_me
ALERT_SCHEDULER_ENABLED=false
```

说明：
- `ADMIN_FEISHU_USER_ID` 用于飞书内管理员命令鉴权
- `ADMIN_TOKEN` 用于 HTTP 管理接口鉴权
- `ALERT_SCHEDULER_ENABLED=true` 时启用定时扫描

### 2.5 SMTP

```env
SMTP_HOST=
SMTP_PORT=587
SMTP_USERNAME=
SMTP_PASSWORD=
SMTP_FROM=
SMTP_USE_TLS=true
SMTP_USE_SSL=false
```

说明：
- 常见 `465` 端口配置：
  - `SMTP_USE_SSL=true`
  - `SMTP_USE_TLS=false`
- 常见 `587` 端口配置：
  - `SMTP_USE_TLS=true`
  - `SMTP_USE_SSL=false`
- `SMTP_FROM` 建议直接使用发件邮箱地址

## 3. 飞书后台配置

### 3.1 应用类型

- 企业自建应用
- 开启机器人能力

### 3.2 当前推荐权限

当前最小推荐权限：

```json
{
  "scopes": {
    "tenant": [
      "contact:user.base:readonly",
      "im:chat.access_event.bot_p2p_chat:read",
      "im:message.p2p_msg:readonly",
      "im:message:send_as_bot"
    ],
    "user": []
  }
}
```

说明：
- 当前项目只处理 bot 私聊文本消息
- 长连接不会改变这组权限需求

### 3.3 事件模式

当前使用：
- 长连接订阅事件

需要在飞书端确认：
- 已订阅 `im.message.receive_v1`
- 应用已发布
- 应用对你本人可用

当前不依赖：
- `Request URL`
- `url_verification`
- `Verification Token`
- `Encrypt Key`

这些只在未来切回 webhook 时才需要。

## 4. HTTP 管理接口

来源：
- [admin_alerts.py](/home/heavenlysu/fucking_alive/app/api/routes/admin_alerts.py)

鉴权方式：

```http
Authorization: Bearer <ADMIN_TOKEN>
```

当前接口：

- `GET /admin/settings`
- `PATCH /admin/settings`
- `GET /admin/contacts`
- `PUT /admin/contacts`
- `GET /admin/email-template`
- `PUT /admin/email-template`
- `POST /admin/test-alert`

### 4.1 `PATCH /admin/settings` 可修改项

- `default_llm_provider`
- `default_llm_model`
- `alert_default_hours`
- `chat_context_messages`
- `chat_prompt_version`
- `command_repair_prompt_version`
- `command_repair_enabled`
- `admin_feishu_user_id`

示例：

```json
{
  "default_llm_provider": "openai",
  "default_llm_model": "gemini-3-flash-preview",
  "chat_prompt_version": "chat_v2",
  "command_repair_prompt_version": "command_repair_v1",
  "command_repair_enabled": true,
  "chat_context_messages": 10,
  "alert_default_hours": 72
}
```

## 5. 飞书内管理命令

普通用户可用：

- `/help`
- `/alive`

管理员额外可用：

- `/contacts list`
- `/contacts add <name> <email> [relation]`
- `/contacts update <email> <name> [relation] [enabled]`
- `/contacts remove <email>`
- `/template show`
- `/template subject set <text>`
- `/template body set`
- `/config confirm`
- `/config cancel`

说明：
- 飞书内只允许改联系人和邮件模板
- 所有修改先进入 `pending_admin_changes`
- 只有 `/config confirm` 后才正式生效

## 6. 当前 Prompt 运行方式

来源：
- [prompts.py](/home/heavenlysu/fucking_alive/app/llm/prompts.py)

当前 prompt：

- `chat_v1`
- `chat_v2`
- `command_repair_v1`

当前约束：

- 默认输出简洁中文
- 不暴露系统实现细节
- 不伪造系统状态
- 只输出纯文本
- 不使用 Markdown、代码块、标题或列表格式

当前真实联调已确认：

1. `COMMAND_REPAIR_ENABLED=true`
- `/contact list` 会进入 `command_repair_v1`

2. `COMMAND_REPAIR_ENABLED=false`
- `/contact list` 会回退到 `chat_v2`

## 7. 启动前检查清单

- [ ] `.env` 已填写数据库连接
- [ ] `FEISHU_APP_ID` 与 `FEISHU_APP_SECRET` 已填写
- [ ] 飞书端已开启机器人能力
- [ ] 飞书端已订阅 `im.message.receive_v1`
- [ ] 飞书端应用已发布且对本人可用
- [ ] `OPENAI_API_KEY` 与 `OPENAI_BASE_URL` 已填写
- [ ] 如需邮件功能，已填写 SMTP 配置
- [ ] 如需 HTTP 管理接口，已设置 `ADMIN_TOKEN`
- [ ] 如需飞书管理员命令，已设置 `ADMIN_FEISHU_USER_ID`
- [ ] 已执行 Alembic 迁移

## 8. 当前不应写入仓库的内容

不要提交：

- 真实 `.env`
- 飞书 `APP_SECRET`
- LLM API Keys
- SMTP 密码
- `ADMIN_TOKEN`
- 任何测试邮箱验证码或授权码
