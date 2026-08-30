# 概要设计 — Novel Agents 小说创作系统

> 对应需求：Vue + FastAPI + asyncio + LangGraph + PostgreSQL（Redis 预留）+ 国内多模型 + 提示词文件化 + 服务器多用户 + 每日可运行 MVP。
> 参考来源：[oh-story-langgraph-mcp-decomposition.md](./oh-story-langgraph-mcp-decomposition.md)（oh-story-claudecode 拆解）。

## 1. 背景与目标

把 oh-story-claudecode 的网文写作能力重构为一个 **B/S 架构的多智能体小说创作系统**：

- **多智能体**：7 个角色 agent（情节架构 / 文笔 / 人物 / 研究 / 单章提取 / 一致性 / 状态查询）编排在 LangGraph 图中，协同完成开书、日更、拆文、审查、去味、扫榜、导入。
- **Web 应用**：Vue 前端 + FastAPI 后端，服务器多用户部署，登录鉴权 + 项目级租户隔离。
- **国内大模型优先**：配置驱动接入 DeepSeek / 通义千问 / 智谱 GLM / Kimi / 豆包 / MiniMax 等 OpenAI 兼容 API，按 high/mid/low 三档模型分级路由。
- **提示词工程化**：所有提示词从代码剥离，放单独文件（`prompts/`），可维护、可版本化、可热更新。
- **存储**：PostgreSQL 为唯一权威（业务数据 + 追踪状态 + 派生视图）；Redis 预留为长期记忆热层（可禁用，回源 PG）。

## 2. 技术选型

| 层 | 选型 | 理由 |
|----|------|------|
| 前端 | Vue 3 + Vite + TypeScript + Pinia + Vue Router + Element Plus | 用户选定；组件库选 Element Plus |
| 后端 | Python 3.12 + FastAPI + **asyncio** | 异步 I/O 天然适配 LLM 长调用与并发任务 |
| 智能体编排 | LangGraph | 显式图节点/条件边/`Send` 并行/`interrupt_before` 人机协同，`create_agent` 内嵌 7 角色 |
| ORM/迁移 | SQLAlchemy 2.0（async）+ asyncpg + Alembic | 异步驱动、迁移可控 |
| 数据库 | PostgreSQL 16 | 追踪提交的多表原子性、卷↔章↔正文强结构、JSONB、pgvector 预留（理由见拆解文档 §6.7） |
| 缓存/记忆热层 | Redis（**预留**） | 长期记忆热层（上下文/召回包/锁），通过接口抽象，可禁用 |
| LLM | `langchain-openai`（OpenAI 兼容）| 国内主流模型全部提供 OpenAI 兼容端点，一套代码接入 |
| 认证 | JWT（pyjwt）+ argon2 | 无状态鉴权、多用户隔离 |
| 部署 | docker-compose + nginx（反代 + 静态资源） | 一键起 PG + 后端 + 前端 |

## 3. 系统架构

```
                    ┌────────────────────────────────────────────┐
   浏览器 ─────────► │            Vue 3 SPA (Element Plus)         │
   (Vite/TS)        │  登录/工作台/拆文/审查/扫榜/设置/用量        │
                    └───────────────┬────────────────────────────┘
                                    │  HTTPS/JSON + SSE(流式)
                    ┌───────────────▼────────────────────────────┐
                    │              FastAPI (asyncio)              │
                    │  ┌────────┐ ┌──────────┐ ┌────────────────┐ │
                    │  │ 鉴权    │ │ 任务管理  │ │  SSE 事件总线    │ │
                    │  │ JWT    │ │ tasks表   │ │  (asyncio.Queue)│ │
                    │  └────┬───┘ └────┬─────┘ └────────┬───────┘ │
                    │       └──────────┼────────────────┘         │
                    │            ┌─────▼─────┐                    │
                    │            │ LangGraph │  RouterGraph        │
                    │            │  7 agent  │  Write/Analyze/     │
                    │            │  节点      │  Review/Deslop/     │
                    │            │           │  Scan/Import        │
                    │            └─────┬─────┘                    │
                    │        ┌─────────┼──────────┐               │
                    │  ┌─────▼────┐ ┌───▼────┐ ┌──▼─────┐         │
                    │  │  服务层   │ │ LLM 抽象 │ │Prompt  │         │
                    │  │ Tracking │ │ factory │ │Registry│         │
                    │  │ Word/Chpt│ │ providers│ │ Jinja2 │         │
                    │  │ Quality/ │ │ tier路由 │ │        │         │
                    │  │ Context  │ └────────┘ └────────┘         │
                    │  └─────┬────┘                                │
                    │        └── repository/DAO（用户作用域）         │
                    └───────────────┬────────────────────────────┘
                          ┌─────────▼───────────┐
                          │ PostgreSQL (权威)     │   Redis（预留热层）
                          │  + Alembic 迁移       │ ◄── 可禁用
                          └─────────────────────┘
```

**模块划分**

| 模块 | 说明 |
|------|------|
| `backend/api` | REST 路由 + SSE 流式端点（auth/projects/writing/analyze/review/scan/settings/usage） |
| `backend/core` | 配置、JWT 安全、当前用户依赖、Redis 封装（预留） |
| `backend/db` | 异步 engine/session、Alembic |
| `backend/models` | SQLAlchemy 模型（users/projects/chapters/tracking_state/…） |
| `backend/repositories` | 异步 DAO，**所有查询强制 owner 作用域** |
| `backend/services` | Tracking/Wordcount/Chapter/Quality/Context/Memory/Scan 确定性服务 |
| `backend/llm` | 多模型 provider 配置 + factory + tier 路由 + 重试降级 + 用量 |
| `backend/graph` | LangGraph 各图 + 7 agent（`create_agent`）+ 执行器 |
| `backend/prompts` | **提示词文件**（agents/ nodes/ system/，Jinja2 模板） |
| `frontend/src` | 页面/组件/store/router/SSE 客户端（含 Agent 活动面板：流式正文 + 工具调用日志） |

## 4. 核心业务流

### 4.1 写章节（日常核心，P0）
```
前端「写下一章」 ──► POST /chapters/next ──► 任务管理建 tasks 记录
   ──► WriteGraph 异步执行:
        route_scenario → write_prep(召回包+Reference Gate)
        → write_prose(narrative-writer 流式输出) → wordcount_checkpoint
        → quality_scan → tracking_commit(PG 单事务) → 完成
   ──► 全程 SSE 推流: {stage}/{tool}/{token}/{done}
        —— token 实时进正文区；tool（LLM 调用工具）进 Agent 活动面板
   ──► 提交后前端拉取最新 tracking 上下文
```

### 4.2 开书（三阶段）
`route_scenario=open_book`：phase1 选题+对标 → phase2 设定（关系/题材定位/题材卡）→ phase3 卷纲+逐章细纲 → `validate_outline`。

### 4.3 拆文
上传书文本 → AnalyzeGraph：stage0 概览 → stage1 黄金三章 → stage2 逐章提取（`Send` map 并行 5-8 章/批）→ stage3-6 聚合（剧情/节奏/情绪/设定/角色/关系/报告/文风）→ 全部入 `analysis_*` 表，`analysis_progress` 断点恢复。

### 4.4 导入（逆向）
ImportGraph：拆解（复用 AnalyzeGraph）→ 拆文库映射到项目结构（设定/卷纲/细纲/正文表）→ `TrackingService.init` 一次性生成追踪 → `activate_project`。

### 4.5 审查 & 去味
ReviewGraph：full/lean/solo → 4 reviewer（`Send` 并行）→ 聚合 findings。
DeslopGraph：AI 味扫描 → 六指标定级 → Gate A-G 处理 → 确定性兜底（标点/AI 句式/退化复扫）。

### 4.6 扫榜
ScanGraph：平台采集 → 清洗 → 趋势分析 → 选题决策。

### 4.7 多租户
所有业务表带 `owner_id`；`current_user` 依赖解析 JWT → repository 层强制 owner 过滤；API 级 `404`（而非 403）避免项目存在性泄露。

## 5. 数据架构总览

- **用户**：`users`（登录）+ `user_settings`（该用户三档模型选择）+ `usage_logs`（用量/成本）。
- **项目域**（owner_id 隔离）：`projects` → `settings` / `volumes`→`outline_chapters` / `chapters`。
- **追踪域**（单项目唯一真值）：`tracking_state`（JSONB 快照 + `state_revision`）+ 可查询实体 `characters` / `foreshadowing` / `timeline_events` + 派生 `chapter_records` / `context_views`。
- **拆文域**：`analysis_books` → `analysis_chapters` / `analysis_aggregates` / `analysis_progress`。
- **记忆域**：`author_memory`（按用户）；`benchmarks` / `reference_materials`（按项目）。
- **扫榜/任务/模型**：`scan_results`；`tasks`；`providers`（模型配置）。

**铁律（DB 版）**：`tracking_state` 及派生视图（`chapter_records`/`context_views`/角色/伏笔/时间线联动）唯一写入口是 `TrackingService.commit` / `ChapterService.commit`（单 PG 事务，revision 递增），**LLM 节点不得直写**。

## 6. 横切设计

### 6.1 LLM 多模型抽象
- `providers` 表（或首启 seed）配置每家的 `base_url` / `api_key`（Fernet 加密）/ `models: {high, mid, low}`。
- `ModelFactory.get(tier, user_id)` → 异步 Chat 模型（`langchain-openai`，OpenAI 兼容端点）；tier 解析优先级：用户设置 > 服务端默认。
- 三档映射（默认）：high=架构/大纲类（如 deepseek-reasoner / qwen-max / glm-4-plus / MiniMax-Text-01）；mid=正文/人物类；low=单章提取/一致性（如 qwen-turbo / abab6.5s-chat）。
- 失败自动降级到同档其他 provider；超时/重试/用量记录。
- **输出契约与后校验（铁律）**：所有需返回 JSON 的 LLM 节点声明 Pydantic 输出契约，生成后统一校验（容错解析 + schema 校验），禁止直接信任。
- **反馈式重试**：解析/校验失败时把「错误类型 + 原因 + 出错片段 + 期望格式」统一封装回喂给模型自我修正（可升档）；API 级错误（限流/超时/5xx）走退避重试 + 跨 provider 降级，**不改 prompt**。
- **KV Cache 复用（提示词装配）**：prompt 前缀按固定顺序装配（system/base → 项目设定 → 追踪上下文 → 任务指令 → 可变尾部），任务内逐字节复用触发厂商前缀缓存（DeepSeek/Qwen 自动、Kimi 显式 cache_control）；**上下文摘要只替换尾部会话历史、反馈式重试只追加尾部**，前缀不动缓存不失效；usage_logs 记录 cached_tokens。

### 6.2 提示词文件化
全部提示词在 `prompts/`（`agents/*.md`、`nodes/*.md`、`system/base.md`），Jinja2 模板，`PromptRegistry` 启动加载缓存、`render(name, **vars)` 渲染；`base.md` 用 `{% include %}` 注入共享规则（输出格式、追踪铁律）。

### 6.3 异步与流式
- FastAPI 全 async；LLM 调用走异步流式。
- 长任务（写章/拆文/审查）不进请求线程：`tasks` 表 + asyncio 后台任务 + SSE 事件总线（`asyncio.Queue`/redis 预留）。
- **工具调用可见**：LangGraph `astream_events`(v2) 捕获 `on_tool_start/end` → SSE `tool` 事件 → 前端 Agent 活动面板实时展示"模型正在调用哪个工具、入参、成败"。
- SSE 事件协议见详细设计 §8。

### 6.4 鉴权与安全
JWT（access 15min + refresh 7d）、argon2 密码哈希、CORS 白名单、登录限流、`api_key` 加密存储、密钥走环境变量、request-id 日志。

### 6.5 Redis 预留
`core/redis.py` 定义 `RedisStore` 接口 + 无 Redis 时的 PG 回源实现；配置 `redis.url` 为空即禁用。启用后承担上下文/召回包缓存、章节提交锁、作者记忆热集（详见拆解文档 §2.2 的键设计）。

### 6.6 可观测性
`usage_logs`（token/成本/耗时）、请求日志、任务失败捕获、`GET /usage` 页面。

## 7. 目录结构

```
novel_agents/
├── backend/
│   ├── app/
│   │   ├── main.py               # app 工厂 + 路由挂载 + 启动
│   │   ├── api/                  # auth/projects/writing/analyze/review/scan/settings/usage
│   │   ├── core/                 # config.py security.py deps.py redis.py
│   │   ├── db/                   # engine.py session.py base.py
│   │   ├── models/               # SQLAlchemy 模型（对应 §5 各域）
│   │   ├── repositories/         # async DAO（owner 作用域）
│   │   ├── services/             # tracking/wordcount/chapter/quality/context/memory/scan
│   │   ├── llm/                  # providers.py factory.py tiers.py usage.py
│   │   ├── graph/                # state.py router.py write/analyze/review/deslop/scan/import_graph.py
│   │   │                         # agents.py executor.py events.py
│   │   └── tasks.py              # 任务生命周期
│   ├── migrations/               # Alembic
│   ├── prompts/                  # agents/ nodes/ system/（提示词文件）
│   ├── tests/
│   └── pyproject.toml
├── frontend/
│   ├── src/
│   │   ├── api/                  # http.ts sse.ts
│   │   ├── stores/               # auth/project/chapter/task/settings
│   │   ├── router/index.ts
│   │   ├── views/                # Login/Register/Dashboard/Workspace/Analyze/Review/Scan/Settings/Usage
│   │   ├── components/           # ChapterTree/StreamEditor/TrackingPanel/ReportViewer...
│   │   └── App.vue
│   └── vite.config.ts
├── docker-compose.yml            # postgres + backend + frontend(nginx)
├── config/models.yaml            # 服务端默认 provider 配置（seed）
├── docs/                         # 本组设计文档
└── README.md
```

## 8. 非功能需求

| 项 | 目标 |
|----|------|
| 并发 | 多用户并发写不同书；同一书章节提交用 PG advisory lock 串行化 |
| 一致性 | 追踪提交原子；派生视图与 `state_revision` 绑定 |
| 可用性 | LLM 提供商故障自动降级；任务失败可重试 |
| 成本 | `usage_logs` 记录 token/成本，三档模型分级降低高频调用成本 |
| 安全 | 租户隔离、密钥加密、登录限流、CORS |
| 可移植 | Redis 可禁用；模型可热切换；所有配置 env/DB 化 |
