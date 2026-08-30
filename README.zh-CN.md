# Novel Agents（小说代理）

AI 驱动的多智能体长篇小说创作系统：**多用户 Web 应用**，由 FastAPI + LangGraph 编排多个专业智能体（写手、审查、去味、拆文、扫榜），前端 Vue 3 实时流式展示 Agent 活动。

> 12 天 MVP 已全部完成（D1–D12），可 `docker compose up` 一键跑通全栈。

## 功能模块

| 模块 | 说明 |
|------|------|
| 📝 写作 | 写手 Agent 依大纲/追踪上下文逐章生成；SSE 流式输出 token + 工具调用；非对称字数收口 |
| 🔍 审查 | 全量（4 评审并行）/ 精简 / 单评审；findings + 分项打分 + 汇总 |
| 🧹 去味 | Gate A-G 分级 → 扫描 → 改写，原文/改写对照，接受后写回提交 |
| 📚 拆文库 | 上传整本书 → 自动切章 → 分维拆解 → 一键导入为可写项目 |
| 📊 扫榜 | 起点/番茄榜单采集 → 清洗 → 题材分布/热词/头部增速 → 选题决策 |
| 💰 用量 | token / 成本 / 缓存命中率，按天、任务类型、Provider 聚合 |

## 技术栈

- **后端**：Python 3.14 · FastAPI · SQLAlchemy 2 (async) · LangGraph · PostgreSQL 16（预留 Redis）
- **前端**：Vue 3 · TypeScript · Vite · Element Plus · Pinia
- **核心机制**：
  - 提示词文件化 + **KV 缓存复用装配**（稳定前缀 → 命中厂商前缀缓存，`usage_logs.cached_tokens` 观测）
  - **输出契约后校验 + 错误反馈重试**（坏 JSON → 封装错误回喂 → 模型修正）
  - **多模型三档**（fast/normal/high，DeepSeek/Qwen/GLM/Kimi/豆包/MiniMax），API 级超时重试 + 跨 Provider 降级回退
  - **章节提交并发锁**：项目级 `pg_advisory_xact_lock` 串行化 + `expected_revision` 乐观锁；Redis 可选双重保险
  - **Redis 预留接口**：`MemoryStore` 协议 + PG 回源实现（可禁用），切 Redis 只换 `get_store()`
  - **request-id 全链路日志** + 未捕获异常统一 500
- **支持国产大模型**：供应商密钥加密存储，`config/models.yaml` 配置驱动

## 快速开始

### Docker 一键部署（推荐）

```bash
cp .env.example .env        # 生产务必修改 JWT_SECRET
docker compose up --build -d
# → http://localhost:8080   （前端 nginx :8080，/api 反代后端）
```

详见 [docs/deploy.md](docs/deploy.md)。

### 本地开发

```bash
# 后端（数据库用 docker）
cd backend
cp .env.example .env
docker compose up -d postgres    # 根目录执行；或已有 PG 则改 DATABASE_URL
pip install -e . -i https://pypi.tuna.tsinghua.edu.cn/simple
python -m app.db.init_db        # 建表（幂等）
uvicorn app.main:app --port 8000

# 前端
cd frontend
npm install
npm run dev        # http://localhost:5173，/api 代理到 :8000
```

### 测试

```bash
cd backend
python -m pytest        # 77 个用例（内存 SQLite，覆盖全部模块）
```

## 项目结构

```
├── backend/
│   ├── app/
│   │   ├── api/           # FastAPI 路由（auth/projects/writing/analysis/quality/scan/usage…）
│   │   ├── core/          # 配置 / 日志(request-id) / KV 存储(Redis+PG回源) / 提交锁
│   │   ├── graphs/        # LangGraph 图：write / review / deslop / scan + stub 实现
│   │   ├── llm/           # ModelFactory（三档/重试/回退/用量落库）
│   │   ├── models/        # SQLAlchemy 模型（含 kv_cache/kv_locks）
│   │   ├── schemas/       # Pydantic 契约（输出后校验）
│   │   ├── services/      # 服务层（tracking/quality/context/cost/task_service…）
│   │   └── db/            # engine / session / init_db
│   ├── prompts/           # 提示词文件（Jinja2，热重载）
│   ├── tests/             # pytest（含每日本 MVP 验收）
│   ├── Dockerfile
│   └── pyproject.toml
├── frontend/
│   ├── src/
│   │   ├── api/           # axios 封装
│   │   ├── stores/        # Pinia
│   │   ├── views/         # 各功能页
│   │   └── components/    # Agent 活动面板 / SSE 流式
│   ├── Dockerfile
│   └── nginx.conf         # 静态托管 + /api 反代（含 SSE）
├── docs/                  # 架构 / 详细设计 / 开发计划 / 部署
├── docker-compose.yml     # postgres + backend + frontend 全栈
└── README.md
```

## 文档

- [docs/architecture.md](docs/architecture.md) — 总体架构
- [docs/detailed-design.md](docs/detailed-design.md) — 详细设计（含 Redis §9、部署 §10）
- [docs/development-plan.md](docs/development-plan.md) — 12 天开发计划与验收标准
- [docs/deploy.md](docs/deploy.md) — 部署指南

## License

[Apache License 2.0](LICENSE)
