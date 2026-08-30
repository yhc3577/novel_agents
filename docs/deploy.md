# 部署指南（D11：US-30）

novel-agents 采用 **docker compose 全栈部署**：`postgres:16` + `backend`（FastAPI/uvicorn）+ `frontend`（nginx 托管静态 + 反代 `/api`，含 SSE）。

## 快速开始

```bash
# 1. 准备环境变量（生产务必修改密钥）
cp .env.example .env
vim .env          # 设置 JWT_SECRET；FERNET_KEY 可选（见 backend/.env.example）

# 2. 构建并启动全栈（postgres 健康检查通过后 backend 才启动）
docker compose up --build -d

# 3. 验证
curl http://localhost:8080/health          # {"status":"ok","app":"novel-agents"}
curl http://localhost:8080/api/auth/me     # 未带 token → 401（预期）
```

打开 http://localhost:8080 注册 → 登录 → 进入工作台。

## 端口与拓扑

| 端口 | 服务 | 说明 |
|------|------|------|
| 8080 | frontend (nginx) | 前端静态 + `/api` 反代到 backend |
| 8000 | backend (uvicorn) | 仅容器内 `expose`，经 nginx 访问 |
| 5432 | postgres | 数据库（映射到宿主机便于调试） |

- nginx 将 `/api/*` 反代到 `backend:8000`，并关闭缓冲以支持 **SSE 流式**（`/api/tasks/{id}/events`）。
- SPA 路由由 `try_files ... /index.html` 回退。

## 环境变量

| 变量 | 默认 | 说明 |
|------|------|------|
| `JWT_SECRET` | dev 值 | 生产必须改 |
| `FERNET_KEY` | 空 | provider 密钥加密（Fernet base64），生成见 `backend/.env.example` |
| `REDIS_URL` | 空 | 非空启用 Redis（KV 缓存 + 章节锁），否则 **PG 回源**，功能等价 |
| `KV_CACHE_ENABLED` | `true` | `false` 时禁用缓存/锁（功能等价，无缓存） |

## 数据库

- 启动时 backend 执行 `python -m app.db.init_db`（`Base.metadata.create_all`，幂等，仅补缺失表）。
- 有 Alembic 迁移目录（`backend/migrations/`），可 `alembic upgrade head` 接管；当前两种方式并存。

## 生产化清单

- 换 `JWT_SECRET` / `FERNET_KEY`；`DEBUG=false`。
- 反向代理再加一层 TLS（证书挂到 nginx 或前置网关）。
- 高并发场景启用 Redis（`REDIS_URL=redis://...`），章节提交加 `lock:chapter:{pid}:{no}` 双重保险（US-29）。
- 日志含 `request-id`（`X-Request-ID` 响应头），排障时用 id 串联一条请求的全链路。

## 本地开发（非容器）

```bash
# 后端
cd backend
cp .env.example .env
docker compose up -d postgres          # 仅数据库
uvicorn app.main:app --port 8000

# 前端
cd frontend
npm install
npm run dev                             # :5173，/api 代理到 :8000
```
