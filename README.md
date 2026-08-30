# Novel Agents

An AI-driven **multi-agent long-form novel writing system** — a multi-user web app
that orchestrates specialized agents (writer, reviewer, de-slop editor, story
deconstructor, trending scanner) with **FastAPI + LangGraph**, streaming agent
activity to a **Vue 3** frontend in real time.

> The full 12-day MVP (D1–D12) is complete. `docker compose up` runs the whole stack.

## Modules

| Module | Description |
|--------|-------------|
| 📝 Writing | Writer agent generates chapter-by-chapter from outline + tracking context; SSE streams tokens + tool calls; asymmetric word-count gate |
| 🔍 Review | Full (4 parallel reviewers) / lean / solo modes; findings + per-axis scores + summary |
| 🧹 De-slop | Gate A–G grading → scan → rewrite; original/rewritten diff; accept writes back to committed chapter |
| 📚 Deconstruction | Upload a whole book → auto chapter split → per-axis analysis → one-click import as a writable project |
| 📊 Trending | Qidian/Fanqie rankings → collect/clean → genre distribution / hot tags / growth top → topic decision |
| 💰 Usage | token / cost / cache-hit-rate, aggregated by day, task type, and provider |

## Tech Stack

- **Backend**: Python 3.14 · FastAPI · SQLAlchemy 2 (async) · LangGraph · PostgreSQL 16 (Redis reserved)
- **Frontend**: Vue 3 · TypeScript · Vite · Element Plus · Pinia
- **Core mechanisms**:
  - File-based prompts + **KV cache reuse assembly** (stable prefix → vendor prefix-cache hits, observed in `usage_logs.cached_tokens`)
  - **Output-contract post-validation + error-feedback retry** (bad JSON → wrap error → re-feed → model corrects)
  - **Three-tier multi-model** (fast/normal/high; DeepSeek/Qwen/GLM/Kimi/Doubao/MiniMax) with API-level timeout retry + cross-provider fallback
  - **Chapter-commit concurrency**: project-level `pg_advisory_xact_lock` serialization + `expected_revision` optimistic lock; optional Redis lock double-insurance
  - **Reserved Redis interface**: `MemoryStore` protocol + PG fallback (disableable); switching to Redis only changes `get_store()`
  - **request-id end-to-end logging** + unified 500 for unhandled errors
- **Domestic LLM friendly**: provider keys stored encrypted; `config/models.yaml` drives configuration

## Quick Start

### Docker one-click (recommended)

```bash
cp .env.example .env        # set JWT_SECRET in production
docker compose up --build -d
# → http://localhost:8080   (nginx front, /api proxied to backend)
```

See [docs/deploy.md](docs/deploy.md).

### Local development

```bash
# Backend (DB via docker, or point DATABASE_URL at your own PG)
cd backend
cp .env.example .env
docker compose up -d postgres   # from repo root; requires the compose file
pip install -e . -i https://pypi.tuna.tsinghua.edu.cn/simple
python -m app.db.init_db        # idempotent table creation
uvicorn app.main:app --port 8000

# Frontend
cd frontend
npm install
npm run dev                     # http://localhost:5173, /api proxied to :8000
```

### Tests

```bash
cd backend
python -m pytest        # 82 cases (in-memory SQLite, covers all modules)
```

## Repository Layout

```
├── backend/
│   ├── app/
│   │   ├── api/           # FastAPI routes (auth/projects/writing/analysis/quality/scan/usage…)
│   │   ├── core/          # config / logging(request-id) / KV store(Redis+PG fallback) / commit lock
│   │   ├── graphs/        # LangGraph: write / review / deslop / scan (+ stub implementations)
│   │   ├── llm/           # ModelFactory (tiers / retry / fallback / usage logging)
│   │   ├── models/        # SQLAlchemy models (incl. kv_cache / kv_locks)
│   │   ├── schemas/       # Pydantic contracts (post-validation)
│   │   ├── services/      # tracking / quality / context / cost / task_service …
│   │   └── db/            # engine / session / init_db
│   ├── prompts/           # Jinja2 prompt files (hot-reloaded)
│   ├── tests/             # pytest (incl. per-day MVP acceptance)
│   ├── Dockerfile
│   └── pyproject.toml
├── frontend/
│   ├── src/
│   │   ├── api/           # axios wrapper
│   │   ├── stores/        # Pinia
│   │   ├── views/         # feature pages
│   │   └── components/    # Agent activity panel / SSE stream
│   ├── Dockerfile
│   └── nginx.conf         # static hosting + /api reverse proxy (incl. SSE)
├── docs/                  # architecture / detailed design / dev plan / deploy
├── docker-compose.yml     # postgres + backend + frontend full stack
└── README.zh-CN.md
```

## Docs

- [docs/architecture.md](docs/architecture.md)
- [docs/detailed-design.md](docs/detailed-design.md) (Redis §9, deployment §10)
- [docs/development-plan.md](docs/development-plan.md) (12-day plan + acceptance)
- [docs/deploy.md](docs/deploy.md)

## License

[Apache License 2.0](LICENSE)
