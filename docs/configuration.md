# 必要配置说明

本文档只保留项目启动和联调所需的必要设置。

## 1. 启动前必须准备

你至少需要准备这 5 类信息：

1. PostgreSQL 连接
2. 飞书应用 `APP_ID` 和 `APP_SECRET`
3. 一个可用的 OpenAI 兼容接口 `API Key` 和 `Base URL`
4. HTTP 管理接口的 `ADMIN_TOKEN`
5. 如果要启用邮件提醒，还需要 SMTP 配置

## 2. `.env` 最小必填项

参考：
- [.env.example](../.env.example)

### 2.1 数据库

```env
DATABASE_URL=postgresql+psycopg://alive_agent:change_me@postgres:5432/alive_agent
```

### 2.2 飞书

当前项目使用长连接接收事件，至少需要：

```env
FEISHU_APP_ID=
FEISHU_APP_SECRET=
FEISHU_LONG_CONNECTION_ENABLED=true
```

说明：
- `FEISHU_VERIFICATION_TOKEN` 和 `FEISHU_ENCRYPT_KEY` 当前长连接模式下不是必填
- 只有未来切回 webhook 才需要

### 2.3 LLM

当前真实接入的是 OpenAI 兼容格式，至少需要：

```env
DEFAULT_LLM_PROVIDER=openai
DEFAULT_LLM_MODEL=gpt-4.1-mini
OPENAI_API_KEY=
OPENAI_BASE_URL=https://api.openai.com/v1
```

### 2.4 管理接口

```env
ADMIN_TOKEN=change_me
ADMIN_FEISHU_USER_ID=
```

说明：
- `ADMIN_TOKEN` 用于 `/admin/*` HTTP 接口
- `ADMIN_FEISHU_USER_ID` 用于飞书内管理员命令

### 2.5 邮件提醒

如果要启用邮件能力，再补：

```env
SMTP_HOST=
SMTP_PORT=587
SMTP_USERNAME=
SMTP_PASSWORD=
SMTP_FROM=
SMTP_USE_TLS=true
SMTP_USE_SSL=false
```

常见情况：
- `465` 端口：`SMTP_USE_SSL=true`、`SMTP_USE_TLS=false`
- `587` 端口：`SMTP_USE_TLS=true`、`SMTP_USE_SSL=false`

## 3. 飞书端最少配置

你需要在飞书开放平台完成这些设置：

1. 创建企业自建应用
2. 开启机器人能力
3. 订阅 `im.message.receive_v1`
4. 发布应用
5. 确保应用对你本人可用

当前推荐最小权限：

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

## 4. 运行时可调设置

这些不是部署必填，但启动后常会调整：

- `default_llm_provider`
- `default_llm_model`
- `chat_context_messages`
- `chat_prompt_version`
- `command_repair_prompt_version`
- `command_repair_enabled`
- `alert_default_hours`

它们可以通过：
- `PATCH /admin/settings`

当前 prompt 相关默认值：

```env
CHAT_PROMPT_VERSION=chat_v2
COMMAND_REPAIR_PROMPT_VERSION=command_repair_v1
COMMAND_REPAIR_ENABLED=true
```

## 5. 飞书内管理命令

普通用户：
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

## 6. 不要提交到仓库

不要提交这些真实值：

- `.env`
- 飞书 `APP_SECRET`
- LLM API Key
- SMTP 密码或授权码
- `ADMIN_TOKEN`
