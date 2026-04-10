# fucking_alive

## 项目介绍

`fucking_alive Agent` 是一个部署在云服务器上的飞书私聊机器人。

它的核心能力很简单：
- 接收用户在飞书中的私聊消息
- 调用 LLM 生成回复
- 记录用户最后活跃时间
- 当用户长时间未互动时，向预设联系人发送提醒邮件

当前技术栈：
- Python
- FastAPI
- PostgreSQL
- Docker Compose
- 飞书长连接
- OpenAI 兼容 LLM 接口

## 风险提示

- 这是一个“长时间未活跃提醒”工具，不是医疗、安防或紧急救援系统。
- 邮件提醒只代表“超过阈值未互动”，不代表系统确认了真实异常。
- LLM 回复可能出现误解、幻觉或不稳定输出，因此关键判断不能交给模型。
- 当前项目已要求 LLM 只输出纯文本，但模型内容本身仍然不应视为权威事实。
- SMTP、飞书凭据、API Key、`ADMIN_TOKEN` 都属于敏感信息，不能写入仓库。

## 飞书交互

当前项目通过飞书长连接接收私聊消息，不使用 webhook。

普通用户可用命令：
- `/help`
- `/alive`

管理员额外可用命令：
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
- 未知斜杠命令默认可进入命令纠错场景
- 可通过运行时设置关闭命令纠错，回退到普通聊天场景

## 部署教程

### 1. 准备配置

先复制环境变量模板：

```bash
cp .env.example .env
```

然后编辑 `.env`，至少填写这些字段：
- `DATABASE_URL`
- `FEISHU_APP_ID`
- `FEISHU_APP_SECRET`
- `FEISHU_LONG_CONNECTION_ENABLED=true`
- `OPENAI_API_KEY`
- `OPENAI_BASE_URL`
- `ADMIN_TOKEN`

如果要启用邮件提醒，再补这些字段：
- `SMTP_HOST`
- `SMTP_PORT`
- `SMTP_USERNAME`
- `SMTP_PASSWORD`
- `SMTP_FROM`

详细配置说明见：
- [docs/configuration.md](docs/configuration.md)

### 2. 启动数据库

先只启动 PostgreSQL：

```bash
docker compose up -d postgres
```

建议确认数据库容器已经正常运行：

```bash
docker compose ps
```

### 3. 执行迁移

数据库起来后，执行 Alembic 迁移：

```bash
docker compose run --rm api alembic upgrade head
```

如果迁移成功，数据库表结构就已经初始化完成。

### 4. 启动服务

然后启动全部服务：

```bash
docker compose up --build -d
```

默认会启动：
- `postgres`
- `api`
- `scheduler`

如果你暂时不想启用定时告警扫描，可以在 `.env` 中把：

```env
ALERT_SCHEDULER_ENABLED=false
```

保留为默认值。

### 5. 验证服务

先检查容器状态：

```bash
docker compose ps
```

再检查健康接口：

```bash
curl http://localhost:8000/healthz
```

预期返回：

```json
{"status":"ok","app_env":"dev"}
```

如果这里不通，再看 API 日志：

```bash
docker compose logs -f api
```

### 6. 飞书侧检查

在飞书开放平台确认：
- 企业自建应用已创建
- 机器人能力已开启
- 已订阅 `im.message.receive_v1`
- 应用已发布
- 应用对你本人可用

同时确认你在 `.env` 中填写的：
- `FEISHU_APP_ID`
- `FEISHU_APP_SECRET`

与飞书开放平台里的应用一致。

完成后，可以直接在飞书里给机器人发送：
- `/help`
- `/alive`

来验证长连接和消息回复是否已经打通。

### 7. 常用排查命令

查看所有服务状态：

```bash
docker compose ps
```

查看 API 日志：

```bash
docker compose logs -f api
```

查看调度器日志：

```bash
docker compose logs -f scheduler
```

重新执行数据库迁移：

```bash
docker compose run --rm api alembic upgrade head
```

重启服务：

```bash
docker compose up --build -d
```

如果要长期运行，建议额外做两件事：
- 配置 Docker 或宿主机开机自启
- 备份 PostgreSQL 数据卷

## 项目结构

### 文件结构

```text
fucking_alive/
├── app/                         # 应用主目录
│   ├── main.py                  # FastAPI 入口，启动飞书长连接
│   ├── worker.py                # 调度器入口，负责未活跃扫描
│   ├── alerts/                  # 告警模块
│   │   └── service.py           # 告警扫描、去重、状态流转
│   ├── api/                     # HTTP API
│   │   ├── deps/                # 依赖注入
│   │   │   └── admin.py         # ADMIN_TOKEN 鉴权
│   │   └── routes/              # 路由定义
│   │       ├── admin_alerts.py  # 管理接口
│   │       └── health.py        # 健康检查
│   ├── core/                    # 核心基础设施
│   │   ├── config.py            # 环境变量加载
│   │   └── logging.py           # 结构化日志配置
│   ├── db/                      # 数据库层
│   │   ├── base.py              # SQLAlchemy Base
│   │   ├── session.py           # 数据库会话
│   │   └── models/              # 数据模型
│   ├── llm/                     # LLM 抽象层
│   │   ├── factory.py           # Provider 工厂
│   │   ├── prompts.py           # Prompt 定义与版本
│   │   ├── service.py           # 上下文拼装与模型调用
│   │   ├── types.py             # ChatRequest / ChatResponse
│   │   └── providers/           # Provider 实现
│   ├── mail/                    # 邮件模块
│   │   ├── sender.py            # SMTP 发信
│   │   └── template.py          # 邮件模板校验与渲染
│   └── services/                # 业务服务层
│       ├── admin_config_service.py   # 运行时配置读写
│       ├── feishu_admin_service.py   # 飞书内配置管理
│       ├── feishu_client.py          # 飞书客户端构造
│       ├── feishu_longconn.py        # 飞书长连接
│       └── feishu_message_service.py # 飞书消息处理主链路
├── alembic/                     # 数据库迁移
│   └── versions/                # 迁移版本文件
├── docker/                      # Docker 相关文件
│   └── Dockerfile               # 应用镜像构建
├── docs/                        # 可提交文档
│   ├── README.md                # docs 目录索引
│   └── configuration.md         # 必要配置说明
├── tests/                       # 回归测试
├── docker-compose.yml           # 本地与服务器部署入口
├── pyproject.toml               # Python 依赖与项目配置
└── README.md                    # 项目说明
```

### 核心组件

- [app/main.py](app/main.py)
  - FastAPI 应用入口
  - 启动飞书长连接

- [app/worker.py](app/worker.py)
  - 告警调度器入口

- [app/services/feishu_longconn.py](app/services/feishu_longconn.py)
  - 飞书长连接客户端

- [app/services/feishu_message_service.py](app/services/feishu_message_service.py)
  - 飞书消息解析
  - `/alive`、`/help`
  - 管理员命令入口
  - LLM 调用路由

- [app/services/feishu_admin_service.py](app/services/feishu_admin_service.py)
  - 飞书内联系人和模板管理
  - 二次确认流

- [app/llm/service.py](app/llm/service.py)
  - 统一 LLM 抽象
  - 上下文拼装
  - Prompt 版本选择

- [app/llm/prompts.py](app/llm/prompts.py)
  - `chat_v1`
  - `chat_v2`
  - `command_repair_v1`

- [app/alerts/service.py](app/alerts/service.py)
  - 未活跃扫描
  - 告警去重
  - 状态流转

- [app/mail/sender.py](app/mail/sender.py)
  - SMTP 发信

- [app/api/routes/admin_alerts.py](app/api/routes/admin_alerts.py)
  - `/admin/settings`
  - `/admin/contacts`
  - `/admin/email-template`
  - `/admin/test-alert`

- [app/db/models](app/db/models)
  - 用户、消息、联系人、模板、告警、待确认变更等数据模型

## TODO
