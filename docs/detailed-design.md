# 详细设计 — Novel Agents 小说创作系统

> 概要见 [architecture.md](./architecture.md)。本文件给到可落地的字段级/端点级/节点级细节。
> 约定：后端全 async（SQLAlchemy async + asyncpg + `async def`）；所有业务表带 `owner_id`（租户隔离）；所有金额/密钥不进代码。

## 1. 数据库详细设计

> 全部主键 `BIGSERIAL id`；时间 `TIMESTAMPTZ DEFAULT now()`；通用列 `created_at/updated_at` 省略展示。JSONB 用于半结构化。追踪域铁律：`tracking_state` 及派生视图只能由 `TrackingService/ChapterService` 写入。

### 1.1 用户与模型配置

```sql
users(
  id BIGSERIAL PK,
  username VARCHAR(64) UNIQUE NOT NULL,
  email VARCHAR(255) UNIQUE,
  password_hash VARCHAR(255) NOT NULL,      -- argon2
  display_name VARCHAR(64),
  is_active BOOL DEFAULT true,
  created_at, updated_at
)

user_settings(
  id, user_id UNIQUE FK→users,
  tier_high VARCHAR(128),   -- "deepseek:deepseek-chat" 格式 provider:model
  tier_mid  VARCHAR(128),
  tier_low  VARCHAR(128),
  default_project_id BIGINT FK→projects
)

providers(                        -- 模型配置（首启由 config/models.yaml seed）
  id, name VARCHAR(32) UNIQUE,    -- deepseek / qwen / glm / kimi / doubao / minimax ...
  base_url VARCHAR(255) NOT NULL, -- OpenAI 兼容端点
  api_key_enc TEXT,               -- Fernet 加密
  models JSONB,                   -- {"high":"qwen-max","mid":"qwen-plus","low":"qwen-turbo"}
  enabled BOOL DEFAULT true,
  priority INT DEFAULT 0          -- 同档降级顺序
)

usage_logs(
  id, owner_id FK→users,
  provider VARCHAR(32), model VARCHAR(64),
  task_type VARCHAR(32),          -- write_chapter/analyze/review/...
  prompt_tokens INT, completion_tokens INT, cached_tokens INT,
  cost_estimate NUMERIC(12,6),
  latency_ms INT, created_at
)

tasks(
  id, owner_id, project_id NULL,
  type VARCHAR(32),               -- write_chapter/analyze/import/review/deslop/scan
  status VARCHAR(16),             -- pending/running/success/failed/cancelled
  progress VARCHAR(512),          -- 当前阶段描述
  payload JSONB, error TEXT,
  started_at, finished_at
)
```

### 1.2 项目域

```sql
projects(
  id, owner_id FK→users,
  slug VARCHAR(64),               -- 书名拼音/英文标识
  title VARCHAR(128), genre VARCHAR(64), platform VARCHAR(32),
  status VARCHAR(16) DEFAULT 'inactive',  -- active 标记当前书
  UNIQUE(owner_id, slug)
)
settings(          -- 设定（关系/题材定位/题材正文提示卡/世界观/金手指/势力）
  id, project_id FK, kind VARCHAR(32), title VARCHAR(128),
  content TEXT, updated_at,
  UNIQUE(project_id, kind, title)
)
volumes(
  id, project_id FK, no INT, title VARCHAR(128), synopsis TEXT,
  UNIQUE(project_id, no)
)
outline_chapters(
  id, volume_id FK, chapter_no INT, title VARCHAR(128),
  beats JSONB,                    -- 细纲情节点
  contract_status VARCHAR(16),    -- valid/invalid
  UNIQUE(volume_id, chapter_no)
)
chapters(
  id, project_id FK, volume_id FK NULL, chapter_no INT, title VARCHAR(128),
  content TEXT, wordcount INT DEFAULT 0,
  status VARCHAR(16) DEFAULT 'draft',   -- draft/committed
  revision INT DEFAULT 0,
  UNIQUE(project_id, chapter_no)
)
```

### 1.3 追踪域（唯一真值 + 派生视图）

```sql
tracking_state(
  id, project_id UNIQUE FK,
  state_revision INT DEFAULT 0,        -- 版本守卫，防串版本
  last_committed_chapter INT DEFAULT 0,
  state_jsonb JSONB                    -- 兼容原 _tracking-state.json 快照
)
characters(
  id, project_id FK, name VARCHAR(64), kind VARCHAR(32),
  profile JSONB, active_status VARCHAR(16),
  UNIQUE(project_id, name)
)
foreshadowing(
  id, project_id FK, content TEXT,
  planted_chapter INT, resolved_chapter INT NULL, status VARCHAR(16)
)
timeline_events(
  id, project_id FK, chapter_no INT, author_only BOOL DEFAULT false, content TEXT
)
chapter_records(          -- 派生：仅提交事务重建
  id, project_id FK, chapter_no INT,
  context JSONB, characters JSONB, events JSONB, foreshadowing JSONB,
  UNIQUE(project_id, chapter_no)
)
context_views(            -- 派生：固定 7 列 ≤12KB，键 {project_id, revision}
  id, project_id UNIQUE FK, revision INT, content TEXT, updated_at
)
author_memory(            -- 作者记忆（按用户，跨项目）
  id, owner_id FK, kind VARCHAR(32), content TEXT,
  scope VARCHAR(32), active BOOL DEFAULT true, created_at
)
benchmarks( id, project_id FK, book_title VARCHAR(128), content TEXT, is_primary BOOL )
reference_materials( id, project_id FK, title VARCHAR(128), content TEXT, kind VARCHAR(32) )
```

### 1.4 拆文 / 扫榜

```sql
analysis_books(
  id, owner_id FK, title VARCHAR(128), genre VARCHAR(64),
  source_text TEXT, status VARCHAR(16), created_at
)
analysis_chapters(
  id, book_id FK, chapter_no INT, summary TEXT, beats JSONB,
  UNIQUE(book_id, chapter_no)
)
analysis_aggregates(
  id, book_id FK, kind VARCHAR(32),   -- plot/rhythm/emotion/settings/characters/relations/report/style/golden
  content TEXT,
  UNIQUE(book_id, kind)
)
analysis_progress(
  id, book_id FK, stage VARCHAR(16), status VARCHAR(16), updated_at,
  UNIQUE(book_id, stage)
)
scan_results(
  id, owner_id FK, platform VARCHAR(32), snapshot_at TIMESTAMPTZ,
  raw JSONB, cleaned JSONB, report TEXT
)
```

**索引**：`chapters(project_id, chapter_no)` 唯一索引；`tracking_state(project_id)`；`foreshadowing(project_id, status)`；`usage_logs(owner_id, created_at)`。预留 pgvector（`analysis_aggregates` 文风/情绪模块语义召回）。

**迁移**：Alembic 版本管理；种子：`config/models.yaml` → providers。

## 2. API 详细设计

> 统一前缀 `/api`；鉴权 `Authorization: Bearer <access>`；错误统一 `{"detail": {"code": "...", "message": "..."}}`；资源不存在返回 404（不泄露租户存在性）。

### 2.1 认证

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/auth/register` | `{username,email,password}` → 建用户 + 返回 token |
| POST | `/api/auth/login` | `{username,password}` → `{access, refresh}` |
| POST | `/api/auth/refresh` | `{refresh}` → 新 access |
| GET | `/api/auth/me` | 当前用户信息 |

### 2.2 项目与写作

| 方法 | 路径 | 说明 |
|------|------|------|
| GET/POST | `/api/projects` | 列表 / 新建（`{slug,title,genre,platform}`） |
| GET/PATCH | `/api/projects/{pid}` | 详情 / 更新 |
| POST | `/api/projects/{pid}/activate` | 设为活跃书 |
| GET | `/api/projects/{pid}/chapters` | 章节列表（含 wordcount/status） |
| GET | `/api/projects/{pid}/chapters/{no}` | 章节内容 |
| POST | `/api/projects/{pid}/chapters/next` | **发起写下一章任务** → `{task_id}` |
| POST | `/api/projects/{pid}/chapters/{no}/commit` | 直接提交已存在 draft（质量校验+追踪） |
| POST | `/api/projects/{pid}/chapters/{no}/accept-length` | 接受自然长度 |
| GET | `/api/projects/{pid}/tracking/context` | 上下文视图（7 列 ≤12KB） |
| GET | `/api/projects/{pid}/tracking` | 追踪实体（角色/伏笔/时间线） |

### 2.3 任务（长操作统一走这里）

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/tasks` | 我的任务（分页/按状态过滤） |
| GET | `/api/tasks/{tid}` | 任务详情（status/progress/error） |
| GET | `/api/tasks/{tid}/events` | **SSE 事件流**（见 2.5） |
| POST | `/api/tasks/{tid}/cancel` | 取消（触发图中断） |

### 2.4 拆文 / 审查 / 去味 / 扫榜 / 设置 / 用量

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/analyze/books` | 上传书文本（title+content）→ 建 analysis_books |
| POST | `/api/analyze/books/{bid}/run` | 发起拆解任务 |
| GET | `/api/analyze/books` / `.../{bid}/progress` / `.../{bid}/report` | 列表/进度/报告 |
| POST | `/api/import` | 发起导入任务 `{analysis_book_id, project_id?}` |
| POST | `/api/review/projects/{pid}/chapters/{no}` | 发起审查 `{mode: full/lean/solo}` |
| GET | `/api/review/projects/{pid}/chapters/{no}/findings` | 审查结果 |
| POST | `/api/deslop/chapters/{cid}` | 发起去味任务 |
| POST | `/api/scan/run` | `{platform}` → 采集任务 |
| GET | `/api/scan/results?platform=` | 扫榜结果 |
| POST | `/api/scan/{sid}/decision` | 选题决策落库 |
| GET/PUT | `/api/settings/providers` | 模型配置管理（管理端） |
| GET/PUT | `/api/settings/tiers` | 当前用户三档模型选择 |
| POST | `/api/settings/providers/test` | `{provider_id, model}` → 连通性测试 |
| GET | `/api/usage?days=30` | 用量/成本汇总 |

### 2.5 SSE 事件协议（`GET /api/tasks/{tid}/events`）

```
data: {"type":"stage","stage":"write_prep","message":"召回情绪模块…"}\n\n
data: {"type":"tool","id":"t1","tool":"TrackingService.check","input":"{project_id:7}","status":"running"}\n\n
data: {"type":"tool","id":"t1","tool":"TrackingService.check","status":"done","duration_ms":8}\n\n
data: {"type":"token","content":"<正文增量>"}\n\n
data: {"type":"checkpoint","wordcount":1850,"remaining":[150,250]}\n\n
data: {"type":"status","status":"committing"}\n\n
data: {"type":"done","result":{...}}\n\n
data: {"type":"error","message":"..."}\n\n
```
前端按 `type` 分流：`token` 追加到正文区；**`tool` 进 AgentActivityPanel（工具调用日志：名称 / input 摘要 / running·done·fail 状态）**；`stage/status` 更新进度条；`done/error` 收尾并刷新追踪侧栏。`tool` 事件的 `input/output` 截断到 ≤200 字符，避免大内容阻塞 SSE 通道。

### 2.6 示例：写下一章

```
POST /api/projects/7/chapters/next  → {task_id: 1024}
GET  /api/tasks/1024/events         (SSE, 保持连接)
   → write_prep → token流 → checkpoint → committing → done
GET  /api/projects/7/tracking/context  → 更新侧栏
```

## 3. LangGraph 详细设计

### 3.1 共享状态

```python
class StoryState(TypedDict):
    user_id: int
    project_id: int
    task_id: int
    intent: str
    scenario: str                  # open_book/write_chapter/daily/revision
    chapter_no: int
    draft_content: str
    wordcount_target: int
    wordcount_status: str
    tracking_ok: bool
    quality_report: dict
    findings: list[dict]           # review
    stage_progress: dict           # analyze
    book_id: int                   # analyze/import
    errors: list[str]
```

### 3.2 图与节点（异步化拆解文档 §3，节点逻辑同源）

| 图 | 节点（节选） | 关键边 |
|----|-------------|--------|
| RouterGraph | `intent_router` → 条件路由 | 路由到各子图 |
| WriteGraph | `route_scenario`→`phase1/2/3`(开书) 或 `write_prep`→`write_prose`→`wordcount_checkpoint`→`quality_scan`→`quality_review`→`tracking_commit`→`snapshot_checkpoint` | 日更循环条件边（2-3 章/批） |
| AnalyzeGraph | `stage0`→`stage1`→`stage1_checkpoint`→`stage2_extract`(map)→`stage2_validate`→`stage2_merge`→`stage3`‖`stage4a`→`stage4b`→`stage4c`→`stage5`→`stage6` | `Send` map 5-8 章/批 |
| ReviewGraph | `preflight`→`deterministic_precheck`→`fan_out_reviewers`(map)→`aggregate_findings`→`output_report`→`tracking_maintenance` | `Send` 4 reviewer |
| DeslopGraph | `ai_scan`→`classify_severity`→`gate_processing`→`deterministic_finish`→`output_report` | 分级条件边 |
| ImportGraph | `confirm_source`→`length_routing`→`run_analyze`(子图)→`migrate_structure`→`migrate_chapters`→`reverse_outline`→`init_tracking`→`activate_project` | 子图调用 |
| ScanGraph | `collect_rankings`→`clean_data`→`validate_quality`→`analyze_trends`→`generate_report`→`topic_decision` | 平台分支 |

### 3.3 执行器与事件总线

```python
class TaskExecutor:
    async def run(self, graph: CompiledGraph, state: StoryState, task_id: int):
        events = asyncio.Queue[Event]()
        bus = EventBus(events)                      # emit(stage/token/tool/checkpoint)
        # 自研服务节点：cfg["bus"] 传入节点，节点内 emit(stage/checkpoint)
        # LLM agent 节点的 token 与工具调用：astream_events(v2) 捕获
        try:
            async for ev in graph.astream_events(
                state, config={"recursion_limit": 100}, version="v2",
            ):
                if ev["event"] == "on_chat_model_stream":
                    await bus.token(ev["data"]["chunk"].content)        # → SSE token
                elif ev["event"] == "on_tool_start":
                    await bus.tool_start(ev["name"], ev["data"]["input"])  # → SSE tool(running)
                elif ev["event"] == "on_tool_end":
                    await bus.tool_end(ev["name"], ev["data"]["output"])   # → SSE tool(done/fail)
            await bus.done(result)
        except Exception as e:
            await bus.error(str(e))
            raise
```
- SSE 端点 `StreamingResponse(consume(events))`，每事件 `data: {json}\n\n`。
- **停靠点**：`interrupt_before` + `Command(resume=...)` 实现日更批次/拆文预览确认。
- **checkpoint**：`AsyncPostgresSaver`（复用业务 PG，表 `checkpoints`）按 `(user_id, task_id)` 保存，支持断点续跑。

### 3.4 7 个 agent 节点

`create_agent(model=ModelFactory.get(tier, user_id), system=PromptRegistry.render("agents/xxx", **vars), tools=[...])`
- `story-architect`(high) / `narrative-writer`(mid) / `character-designer`(mid) / `story-researcher`(mid) / `chapter-extractor`(low, 只读) / `consistency-checker`(low, 只读) / `story-explorer`(low)。
- 工具白名单来自 repository/服务层（`repo_*` / `TrackingService.check` / `MemoryService.query`），**不给写追踪的工具**。

## 4. 服务层详细设计

```python
class TrackingService:            # 唯一写入口（铁律）
    async def init(self, project_id, input_json) -> state_revision
    async def commit(self, project_id, transaction_json) -> state_revision   # 单事务
    async def check(self, project_id) -> {last_committed_chapter, state_revision, views_consistent}

class WordcountService:
    async def measure(self, chapter_id) -> {metric, actual}
    async def checkpoint(self, chapter_id, target) -> {actual, remaining_user_range}
    async def evaluate(self, chapter_id, target) -> in_range/under/over

class ChapterService:
    async def draft(self, project_id, chapter_no, content)          # 存草稿+字数
    async def check(self, project_id, chapter_no) -> in_range/under/over
    async def commit(self, project_id, chapter_no, tx) -> chapter    # 原子提交
    async def accept_length(self, project_id, chapter_no)

class QualityService:
    async def ai_patterns(self, chapter_id, fail_on="blocking") -> findings
    async def degeneration(self, chapter_id) -> findings
    async def punctuation(self, chapter_id, check=True) -> findings
    async def banned_words(self, chapter_id) -> hits
    async def outline_contract(self, project_id) -> {valid, errors}

class ContextService:             # 写前召回包装配
    async def recall_pack(self, project_id) -> {context_view, emotion_module, rhythm, style, topic_card}
    async def build_context_view(self, project_id) -> str   # 7 列 ≤12KB

class MemoryService:
    async def record(self, owner_id, kind, content, scope)
    async def query(self, owner_id, kinds, limit_kb=2)

class ScanService:
    async def collect(self, platform, owner_id) -> scan_id
    async def clean(self, scan_id) ...
```

事务示例（`TrackingService.commit`）：`BEGIN → upsert tracking_state(revision+1) → 联动 characters/foreshadowing/timeline_events → 重建 chapter_records/context_views → COMMIT`，全程 `SELECT ... FOR UPDATE` 锁项目行。

## 5. LLM 抽象详细设计

```python
# llm/providers.py
@dataclass
class ProviderConfig:
    name: str; base_url: str; api_key: str
    models: dict[str, str]   # {high, mid, low}
    enabled: bool; priority: int

# llm/factory.py
class ModelFactory:
    def __init__(self, db, cache=None): ...
    async def get(self, tier: str, user_id: int) -> ChatOpenAI:
        """tier → (provider, model)：用户设置 > 服务端默认 > 同档降级"""
    async def stream(self, tier, messages) -> AsyncIterator[str]:
        """异步流式；返回 token 生成器"""
    async def invoke_with_retry(self, tier, messages, *, task_type, max_retries=2):
        """重试 + 跨 provider 降级 + 记录 usage_logs（OpenAI 兼容的 usage 字段）"""
```

- 认证：`api_key` 从 providers 表解密（Fernet，secret 来自 env），请求头 `Authorization: Bearer`。
- 超时：连接 30s / 读写 120s；`max_retries=2` + 指数退避；同档全部失败 → 抛 `ModelUnavailable`，任务置 failed 并提示。
- 三档模型默认表（`config/models.yaml` seed，可覆盖）：

| tier | deepseek | qwen | glm | kimi | minimax |
|------|----------|------|-----|------|---------|
| high | deepseek-reasoner | qwen-max | glm-4-plus | moonshot-v1-128k | MiniMax-Text-01 |
| mid | deepseek-chat | qwen-plus | glm-4-flash | moonshot-v1-32k | abab6.5s-chat |
| low | deepseek-chat | qwen-turbo | glm-4-flash | moonshot-v1-8k | abab6.5s-chat |

### 5.1 输出契约 · 后校验 · 反馈式重试

**铁律：所有 LLM 返回的 JSON 一律后校验，禁止直接信任。**

```python
# llm/contracts.py
@dataclass
class OutputContract:
    schema: type[BaseModel]            # Pydantic 输出契约
    max_retries: int = 2               # 校验失败重试次数
    tier_escalate: bool = True         # 失败升档 low→mid→high
    extractor: Callable | None = None  # 从 markdown 提取 JSON 块（容错解析）

# llm/retry.py
async def generate_checked(factory, tier, prompt, contract, *, task_type) -> BaseModel:
    feedback: list[str] = []
    for attempt in range(contract.max_retries + 1):
        try:
            text = await factory.invoke_with_retry(tier, prompt, task_type=task_type)
            data = parse_json_strict(text, contract.extractor)     # 容错解析
            return contract.schema.model_validate(data)            # Pydantic 后校验
        except (JSONParseError, ValidationError, ModelUnavailable) as e:
            feedback.append(format_feedback(e))                    # 统一封装错误
            prompt += "\n\n[纠错反馈]\n" + "\n".join(feedback)
            if contract.tier_escalate: tier = escalate(tier)       # 升档重试
    raise OutputValidationFailed(feedback)
```

**统一错误反馈格式**（回喂给模型）：

```
[输出校验失败 · 第 2/3 次]
错误类型: SchemaValidationError          # JSONParseError | SchemaValidationError | ...
原因: 字段 chapter_no 必填但缺失
出错片段: {"chapter_no": ..., "标题": "..."}    # 截断 ≤200 字符
期望格式: {"chapter_no": int, "summary": str, "beats": [...]}
请修正后重新输出完整 JSON，不要附加解释。
```

**两类重试分工**：

| 错误类型 | 处理 | 是否改 prompt |
|---------|------|--------------|
| API 级（限流/超时/5xx） | `ModelFactory.invoke_with_retry`：指数退避 + 跨 provider 降级 | **不改**（服务问题，prompt 无辜） |
| 内容级（JSON 解析失败 / schema 校验失败） | `generate_checked`：错误类型+原因+片段+期望格式封装回喂，可升档 | **改**（追加纠错反馈段） |

**契约清单**（所有 JSON 输出节点统一走 `generate_checked`）：

| 节点/用途 | 契约 schema | 校验要点 |
|-----------|------------|---------|
| intent_router | `IntentResult{intent, project_ref?}` | intent 枚举合法 |
| outline beats | `OutlineBeats{chapter_no, beats:[{no,type,summary}]}` | beats 非空 |
| chapter_extractor | `ChapterExtraction{chapter_no, summary, beats, mood, hooks}` | 情节点数一致性 |
| quality_review | `ReviewFindings{issues:[{level,type,quote,reason}]}` | 引用须出自原文 |
| reviewer findings | `AgentFindings{verdict, findings:[...]}` | S1-S4 排序 |
| tracking transaction | `TrackingTx{append:[...], revisions:[...]}` | 提交前校验（配合 §3.3 提交守卫） |
| length_routing | `LengthDecision{book_type: long/short, chapters}` | 规则一致性 |
| stage0 boundaries | `ChapterBoundaries[{no,title,start,end}]` | 边界单调递增 |

### 5.2 提示词装配与 KV Cache 复用

**铁律：prompt 前缀按固定顺序装配、任务内逐字节复用，触发厂商前缀缓存；上下文摘要与反馈式重试都不动前缀。**

**装配顺序（固定）：**

```
[1 system/base.md 共享规则]             ┐
[2 project 设定 + 大纲 + 题材卡]         ├─ 稳定前缀（任务内不变）
[3 tracking 上下文视图 + 召回包]          │
[4 任务指令 + 输出契约格式]              ┘
[5 可变尾部：本章原文 / 会话历史 / 纠错反馈]
```

**规则：**
1. 段 1-4 在一次任务内逐字节相同 → 命中 KV 前缀缓存（写作任务多轮工具调用 + 重试收益最大）。
2. **显式断点**：支持 `cache_control` 的提供商（Kimi/Moonshot 等）在段 4/5 交界打断点（`extra_body={"cache_control": {"type": "ephemeral"}}`）；DeepSeek/Qwen/GLM 为自动前缀缓存，按厂商阈值生效，无需标记。
3. **上下文摘要**：对话过长触发 LangGraph 历史摘要时，只把"段 5 会话历史"整体替换为摘要文本，段 1-4 不动 → 前缀缓存不失效；摘要置于尾部并标注"以下为历史摘要"。
4. **反馈式重试**（§5.1）：[纠错反馈] 只追加在段 5 末尾，段 1-4 不变 → 重试调用命中缓存。
5. **可观测**：usage_logs 记录 `cached_tokens`，`usage` 页展示缓存命中率。

**实现**：`PromptRegistry.build_prompt(segments: dict[str, str]) -> str` 保证段顺序与分隔符固定；段 1-4 渲染结果按 `(provider, model, tier, prefix_hash)` 做观测键（仅观测，不改变调用路径）。

## 6. 提示词管理详细设计

```
backend/prompts/
├── system/base.md                 # 共享规则：输出格式、追踪铁律、参考契约
├── agents/
│   ├── story-architect.md
│   ├── narrative-writer.md
│   ├── character-designer.md
│   ├── story-researcher.md
│   ├── chapter-extractor.md
│   ├── consistency-checker.md
│   └── story-explorer.md
└── nodes/
    ├── intent-router.md
    ├── route-scenario.md
    ├── write-prep.md
    ├── quality-review.md
    ├── stage0-overview.md … stage6-style.md
    └── gate-processing.md
```

```python
# services/prompt_registry.py
class PromptRegistry:
    def __init__(self, dir: Path): self._templates = {}
    def load_all(self):                              # 启动时扫描 *.md
    def render(self, name: str, **vars) -> str:      # Jinja2 渲染
        tpl = self._templates[name]
        tpl.globals["base"] = self._templates["system/base.md"]
        return tpl.render(**vars)
```
- 模板变量约定：`{{ project }}`、`{{ chapter_no }}`、`{{ context_view }}`、`{{ recall_pack }}`、`{{ findings }}` 等，每个提示词文件头部用注释声明所需变量。
- **修改提示词不用改代码、不用重启**（热重载：按 mtime 失效），便于调优。

## 7. 前端详细设计

### 7.1 路由与页面

| 路由 | 页面 | 说明 |
|------|------|------|
| `/login` `/register` | 登录/注册 | Element Plus form |
| `/` | Dashboard | 项目卡片、活跃书入口、任务列表 |
| `/project/:pid` | Workspace | **核心页**：左章节树 / 中流式编辑器 / 右追踪侧栏 / 底部 Agent 活动面板（工具调用流） |
| `/project/:pid/analyze` | Analyze | 上传书文本、拆解进度、报告查看 |
| `/project/:pid/review` | Review | 审查模式选择、findings 列表、去味操作 |
| `/scan` | Scan | 平台榜单、趋势、选题决策 |
| `/settings` | Settings | 三档模型选择、provider 测试（管理员） |
| `/usage` | Usage | token/成本统计 |

### 7.2 关键组件

- `StreamEditor.vue`：接收 SSE `token` 增量追加到正文，Cursor 定位；支持整章回显（GET chapters/{no}）。
- `AgentActivityPanel.vue`：**Agent 活动流**——实时渲染 `stage` 阶段切换与 `tool` 工具调用（名称 / input 摘要 / running·done·fail 状态 / 耗时），按 agent 节点分组、可折叠、自动滚动，让用户看清模型在做什么。
- `TrackingPanel.vue`：渲染 context_view（7 列）+ 角色/伏笔/时间线折叠面板。
- `ChapterTree.vue`：卷→章树，状态徽标（draft/committed/字数）。
- `TaskProgress.vue`：全局任务条（阶段/进度/取消）。
- `ReportViewer.vue`：拆文报告/审查 findings 渲染。

### 7.3 Store（Pinia）

`auth`（token 持久化 + 刷新）、`project`（当前项目/章节）、`chapter`（正文 + 流式状态）、`task`（任务轮询 + SSE 连接管理）、`settings`（tier 选择）。

### 7.4 SSE 客户端

```ts
// api/sse.ts — 用 fetch + ReadableStream 支持 POST/header
export async function consumeSSE(
  url: string, token: string,
  onEvent: (ev: ServerEvent) => void, signal?: AbortSignal,
) { /* 解析 data: 行，按 type 分发 */ }
```

## 8. 异步执行与流式详细设计

- **任务生命周期**：`pending → running → success | failed | cancelled`。创建即落库（`pending`），后台 `asyncio.create_task` 执行，防进程崩溃时丢任务（重启扫描 pending→failed 可重试）。
- **并发与锁**：同一项目的章节提交用 **PG advisory lock**（`pg_advisory_xact_lock(hash(project_id))`）在事务内串行化；Redis 启用后可选 `SET NX lock:chapter:{pid}:{no}` 双重保险。
- **取消**：`POST /tasks/{id}/cancel` → 置 status=cancelled → 取消 asyncio task → LangGraph 内节点感知 `asyncio.CancelledError` 回滚草稿标记。
- **超时**：整图 `asyncio.wait_for`（写章 15min / 拆文 60min）；单 LLM 调用超时在 ModelFactory。

## 9. Redis 预留接口

```python
# core/redis.py
class MemoryStore(Protocol):          # 抽象，PG 实现 = RedisStore 关闭时回源
    async def get(self, key: str) -> str | None
    async def set(self, key: str, value: str, ttl: int | None = None)
    async def delete_prefix(self, prefix: str) -> int
    async def acquire_lock(self, key: str, token: str, ttl: int) -> bool
    async def release_lock(self, key: str, token: str) -> None

class RedisStore:                     # 启用条件: config.redis_url 非空
    # 键空间（对应拆解文档 §2.2）：
    #   ctx:view:{pid}:{rev} / ctx:recall:{pid}:{rev} / mem:author:{uid}:{kind}
    #   emb:{hash} / scan:{platform}:{ts} / lock:chapter:{pid}:{no} / sess:{sid}
class PGMemoryStore:                  # 默认实现：全部操作直接走 PG（可禁用 Redis）
```
- 切 Redis：只换 `get_store()` 的返回，业务零改动；`FLUSHDB` 永远安全（可回填）。
- 版本守卫：ContextService 读 `ctx:view:{pid}:{rev}` 时用 `TrackingService.check().state_revision` 比对 key 版本，不匹配即回源重建。

## 10. 错误处理、安全与部署

- **错误模型**：`{"code","message"}`；LLM 层 `ModelUnavailable` → 任务 failed + 前端提示切换模型。
- **安全清单**：JWT 无状态鉴权；refresh 轮换；argon2 哈希；Fernet 加密 provider 密钥；CORS 白名单；登录限流（5 次/分/IP）；request-id 中间件；生产 `DEBUG=false`。
- **部署**：`docker-compose.yml`：`postgres:16` + `backend`（uvicorn, /api）+ `frontend`（nginx 服务静态 + 反代 /api 与 /api/tasks/*/events）。环境变量：`DATABASE_URL`、`JWT_SECRET`、`ENCRYPTION_KEY`、`REDIS_URL`(可选)。
- **观测**：uvicorn access log + structlog；`usage_logs` 页；任务失败 `error` 字段 + 日志。

## 11. 每日 MVP 与实现顺序（详见 development-plan.md）

实现顺序对应 US：**D1 骨架+鉴权 → D2 模型+LLM+提示词 → D3 服务层 → D4 写作后端 → D5 写作前端 → D6 拆文后端 → D7 拆文前端+导入+设置 → D8 审查+去味 → D9 扫榜 → D10 多模型增强+用量 → D11 Redis+部署 → D12 缓冲**。
