# oh-story-claudecode → LangGraph + 服务层/MCP 拆解设计

> 目标：把 [oh-story-claudecode](https://github.com/zenstory-ai/oh-story-claudecode)（网文写作 Claude Code skill 包）重构为 **LangGraph 图 + 服务层** 架构。
>
> **本文件是"拆什么"的参考；目标系统的工程化设计见 [architecture.md](./architecture.md)（概要）、[detailed-design.md](./detailed-design.md)（详细）、[development-plan.md](./development-plan.md)（US 拆分 + 每日 MVP）。**
>
> 核心思路：原系统里 LLM（Claude）是编排者，`SKILL.md` 是带流程的人肉 prompt，`scripts/*` 是确定性自动化，7 个 subagent 是分角色 LLM，`hooks` 是生命周期硬守卫。拆解后：
> - **LangGraph 节点** = 流程步骤（LLM 推理节点 + 服务节点 + 路由节点）
> - **服务层** = 确定性能力（Python service 函数，图节点直接调用）
> - **MCP** = 可选封装层（同一服务对外暴露，供外部工具复用）
> - **Agent 节点** = 原 7 个 subagent 角色，作为可复用的 LLM 节点（`create_agent`）

## 0. 本系统边界（相对原系统的两个调整）

1. **不需要部署**：原 `story-setup` 负责把 agents/hooks/settings 部署到外部 CLI（claude-code/codex/antigravity…）。本系统是自包含的 Python + LangGraph 应用，**不对外部环境部署任何东西**——SetupGraph 及其部署工具全部移除；7 个 agent 直接内嵌为图内 agent 节点。
2. **存储改为数据库（PostgreSQL + Redis）**：文件系统不再是数据库。**PostgreSQL 为唯一权威（系统真值）**，**Redis 为长期记忆热层**（只缓存派生读取结果，可从 PG 重建，可随时回填），通过 repository/service 层访问；派生视图由服务确定性重建，**LLM 一律不得直写数据表**。文件系统仅保留外部二进制资产（封面图）。

---

## 1. 原系统结构盘点

### 13 个 skill（工作流）

| Skill | 作用 | 关键流程 |
|------|------|---------|
| `story` | 路由入口 + 作者记忆 + Dashboard + 版本检查 | 意图分类 → 路由 |
| `story-setup` | 部署基础设施（hooks/agents/rules/AGENTS） | **不在本系统内实现**（见 §0） |
| `story-long-scan` | 长篇扫榜 | 采集 → 清洗 → 分析 → 报告 → 选题决策 |
| `story-long-analyze` | 长篇拆文 | Stage 0-6 拆解管道 |
| `story-long-write` | 长篇写作 | 开书(3阶段) → 单章写作 → 日更循环 |
| `story-short-scan` | 短篇扫榜 | 同 long-scan |
| `story-short-analyze` | 短篇拆文 | Stage 2-6 拆解管道 |
| `story-short-write` | 短篇写作 | 情绪目标 → 核心框架 → 成稿 |
| `story-review` | 多视角对抗审查 | full/lean/solo → 并行 reviewers → 综合 |
| `story-deslop` | 去 AI 味 | 扫描 → 分级 → 7 Gate → 确定性收尾 |
| `story-import` | 逆向导入 | 拆解管道 + 结构迁移 + 追踪初始化 |
| `story-cover` | 封面生成 | GPT-Image-2 |
| `browser-cdp` | 浏览器自动化 | CDP 抓取/登录态 |

### 7 个 agent（分角色 LLM）

| Agent | 模型档 | 职责 |
|-------|-------|------|
| `story-architect` | opus/高端 | 题材、世界观、大纲、钩子/反转、情绪弧线 |
| `narrative-writer` | sonnet/中端 | 正文写作、去 AI 味执行 |
| `character-designer` | sonnet/中端 | 角色、对话、人物弧线 |
| `story-researcher` | sonnet/中端 | 外部资料研究 |
| `chapter-extractor` | haiku/低端 | 单章情节点提取（只读） |
| `consistency-checker` | haiku/低端 | 事实一致性（只读） |
| `story-explorer` | haiku/低端 | 查询故事工程状态（只读） |

### 确定性能力（原 `scripts/*`，改为 Python service）

追踪（`tracking_commit.py` init/commit/check）、字数（`storyctl.py` wordcount/chapter）、AI 检测（`check-ai-patterns.js`）、退化检测（`check-degeneration.js`）、标点归一（`normalize-punctuation.js`）、作者记忆（`author_memory_commit.py`）、大纲契约校验（`check-outline-contract.js`）、榜单采集器（qidian/fanqie/qimao/jjwxc/ciweimao）、Dashboard（`dashboard-server.mjs`）。全部改写/封装为 DB 驱动的 Python service（§4），不再操作文件。

### hooks（生命周期守卫）

`SessionStart/End`、`PreCompact/PostCompact`、`PreToolUse`（写正文前必须有大纲）、`PostToolUse`（写后质量扫描）——这些在 LangGraph 里变成**图内守卫节点**（写正文前校验、写后质量扫描），不再部署为文件 hooks。

---

## 2. 总体架构

```
                         ┌─────────────────────────────────┐
   用户输入 ───────────► │  RouterGraph (对应 story skill)  │
                         │  intent_router → 条件路由         │
                         └──────┬──────┬──────┬──────┬──────┘
                                ▼      ▼      ▼      ▼
                        ScanGraph Analyze  WriteGraph  import/cover
                                          │
                             ┌────────────┼────────────┐
                             ▼            ▼            ▼
                        ChapterWrite   ReviewGraph   DeslopGraph
                             │
                             ▼
                     TrackingService.commit (DB 事务)
```

**服务层**：所有确定性能力实现为 Python service（DB 事务 / 字数 / 质量门禁 / 采集 / 记忆装配），图节点直接函数调用；对外可选 MCP 封装（§4）。
**存储层**：PostgreSQL（系统真值）+ Redis（长期记忆热层）双层，repository 层负责所有读写，Graph state 只保存 ID 与中间产物（§2.1、§2.2）。

### 2.1 存储层设计（文件系统 → PostgreSQL）

> 数据模型分层：**规范化可查询表**（项目/卷/章/角色/伏笔/时间线）+ **JSONB 快照列**（追踪状态原样兼容）。派生视图由服务确定性重建。**PostgreSQL 是唯一权威**；Redis 作为长期记忆热层只缓存派生读取结果（§2.2）。

| 数据域 | 原文件系统 | 数据库表 | 说明 |
|--------|-----------|---------|------|
| 项目 | `{书名}/` + `.active-book` | `projects(id, slug, title, genre, platform, status, created_at, updated_at)` | `status='active'` 标记当前书 |
| 设定 | `设定/*.md` | `settings(project_id, kind, title, content, updated_at)` | kind ∈ {关系, 题材定位, 题材正文提示卡, 世界观, 金手指, 势力} |
| 大纲 | `大纲/` 卷纲+逐章细纲 | `volumes(project_id, no, title, synopsis)` + `outline_chapters(volume_id, chapter_no, title, beats_jsonb, contract_status)` | 卷↔章外键 |
| 正文 | `正文/{chapter}.md` | `chapters(project_id, chapter_no, volume_id, title, content, wordcount, status, revision, created_at, updated_at)` | UNIQUE(project_id, chapter_no)；status ∈ {draft, committed}；wordcount 提交时校验 |
| 追踪权威状态 | `追踪/_tracking-state.json` | `tracking_state(project_id, state_revision, last_committed_chapter, state_jsonb)` | **JSONB 原样兼容原格式**，唯一真值源 |
| 角色状态 | `追踪/角色状态/*.md` | `characters(project_id, name, kind, profile_jsonb, active_status)` | 提交事务联动 |
| 伏笔 | `追踪/伏笔.md` | `foreshadowing(project_id, id, content, planted_chapter, resolved_chapter, status)` | |
| 时间线 | `追踪/时间线/作者真相.md` + `读者已知.md` | `timeline_events(project_id, chapter_no, author_only, content)` | `author_only` 区分作者真相/读者已知 |
| 逐章记录 | `追踪/逐章记录/` | `chapter_records(project_id, chapter_no, context, characters, events, foreshadowing)` | 派生，仅由提交事务重建 |
| 上下文视图 | `追踪/上下文.md`（固定 7 列 ≤12KB） | 视图/物化表 `context_views` | 确定性函数 `build_context_view(project_id)` |
| 拆文库（单章） | `拆文库/{书名}/第N章_摘要.md` | `analysis_chapters(book_id, chapter_no, summary, beats_jsonb)` | stage2_extract 输出，按章 upsert |
| 拆文库（聚合） | `拆文库/{书名}/剧情|节奏|情绪|角色|设定|关系|报告|文风` | `analysis_aggregates(book_id, kind, content)` | kind ∈ {plot, rhythm, emotion, settings, characters, relations, report, style} |
| 拆解进度 | `拆文库/{书名}/_progress.md` | `analysis_progress(book_id, stage, status)` | 断点恢复 |
| 作者记忆 | `.story/作者记忆/` | `author_memory(id, kind, content, scope, active, created_at)` | append-only |
| 对标 | `对标/{书名}/` | `benchmarks(project_id, book_title, content, is_primary)` | |
| 参考资料 | `参考资料/` | `reference_materials(project_id, title, content, kind)` | Reference Gate 检查该表 |
| 扫榜数据 | `扫榜/` | `scan_results(platform, snapshot_at, raw_jsonb, cleaned_jsonb, report)` | append-only |
| 封面 | `covers/{书名}/` | `covers(project_id, path)` | 二进制留磁盘，DB 存路径 |

**索引/能力**：`chapters(project_id, chapter_no)` 唯一索引；`characters(project_id, name)`；`timeline_events(project_id, chapter_no)`。预留 **pgvector**（情绪模块/伏笔语义召回）、**pg_trgm / zhparser**（拆文库中文检索）。迁移用 Alembic。

### 2.2 长期记忆（PostgreSQL + Redis）

记忆分三层，PG 是唯一权威，Redis 只做热读取：

| 层 | 载体 | 内容 | 失效/重建 |
|----|------|------|----------|
| 持久层（真值） | PostgreSQL | 全部业务数据（§2.1），含 `author_memory`、`tracking_state`、`chapters`、`analysis_*` | 任何写入必须落 PG 事务 |
| 长期记忆热层 | Redis | 写作 agent 高频读取的**派生**知识（见下） | 全部可从 PG 重建，可随时回填 |
| 工作记忆 | LangGraph checkpointer（Postgres） | 进行中的图执行状态 | 会话结束即弃 |

Redis 热层条目：

- `mem:author:{project_id}:{kind}` — 作者记忆 hot set（会话开始装载，query 直取，≤2KB/条）
- `ctx:view:{project_id}:{revision}` — 上下文视图（固定 7 列 ≤12KB）；`TrackingService.commit` 时写透，key 带 `state_revision` 防串版本
- `ctx:recall:{project_id}:{revision}` — write_prep 召回包（情绪模块 + 节奏参考 + 题材卡 + 文风），随 commit 失效
- `emb:*` — 语义检索结果缓存（pgvector 命中缓存）
- `scan:{platform}:{snapshot_at}` — 扫榜快照缓存（TTL）
- `lock:chapter:{project_id}:{chapter_no}` — 章节提交分布式锁（多写作 agent 并发时 `SET NX` 串行化提交）
- `sess:{session_id}` — 会话级工作记忆（本批次临时 segment、评审中间产物）

一致性规则（硬约束）：

1. **Redis 永远是派生层**：每条目都能从 PG 确定性重建，可 `FLUSHDB` 后由服务回填。
2. **写路径唯一入口是服务层**：只有 `TrackingService.commit` / `ChapterService.commit` 等能写 PG；Redis 条目由这些服务同步写透或失效（write-through / invalidate）。
3. **版本守卫**：上下文/召回缓存 key 带 `state_revision`，读取时校验，不匹配即回源 PG 重建。
4. **不引入双真值**：伏笔/角色/时间线等可写实体的权威只在 PG；Redis 只缓存"装配好的读取结果"，不缓存可写领域实体。
5. **向量只留一处**：语义检索以 pgvector 为权威，Redis 不另开向量索引，避免双套检索。

---

## 3. LangGraph 节点拆解

### 3.0 共享状态

```python
class StoryState(TypedDict):
    # 会话
    user_input: str
    messages: Annotated[list, add_messages]
    intent: str                     # router 输出
    # 项目
    project_id: int                 # DB 项目 ID（替代 project_root/book_dir）
    # 写作
    scenario: str                   # open_book / write_chapter / daily / revision
    chapter_no: int
    # 拆解
    source_book_id: int
    chapter_boundaries: list[dict]
    stage_progress: dict
    # 审查
    review_mode: str                # full / lean / solo
    findings: list[dict]
    # 通用产物
    report: str
    errors: list[str]
```

### 3.1 RouterGraph（story skill）

| 节点 | 类型 | 逻辑 |
|------|------|------|
| `intent_router` | LLM + tool | 从用户输入提取意图（写长篇/短篇、拆文、扫榜、审查、去味、导入、封面、查状态…） |
| `project_lookup` | 服务节点 | 查 `projects` 表：存在/活跃书/完成度，供路由决策（替代原 `.story-deployed` 探测） |
| `author_memory` | 服务节点 | 读/写作者记忆（MemoryService.query/record） |
| `dashboard` | 服务节点 | 启动/停止本地 Dashboard（读 DB 展示进度） |

**边**：`intent_router` 条件路由 → 子图（scan/analyze/write/review/deslop/import/cover/browser）。

### 3.2 ScanGraph（story-long-scan / story-short-scan）

| 节点 | 类型 | 逻辑 |
|------|------|------|
| `confirm_platform` | LLM 交互 | 确认平台 + 方向 |
| `collect_rankings` | 服务节点 | 调榜单采集器（按平台选 qidian/fanqie/qimao/jjwxc/ciweimao/dz/heiyan），结果写 `scan_results` |
| `clean_data` | LLM + 规则 | 数据清洗（模板文本剔除、解析串行、字段补采、简介截断），写回 `cleaned_jsonb` |
| `validate_quality` | 服务节点 | 完整性检查（≥15 条、必填字段、质量状态） |
| `analyze_trends` | LLM | 题材分布/新题材/书名模式/标签热词 |
| `generate_report` | LLM | 扫榜报告 |
| `topic_decision` | LLM | 选题四步 → 选题决策（硬规则：样本不足禁给"高"可行性） |

### 3.3 AnalyzeGraph（story-long-analyze）— 拆解管道

**最标准的"管道"，Stage 0-6 一一对应节点；输出全部进 `analysis_*` 表。**

| 节点 | 类型 | 逻辑 |
|------|------|------|
| `stage0_overview` | LLM | 概要 + **章节边界表**（唯一切片真值，写 `analysis_progress`） |
| `stage1_golden3` | LLM | 前 3 章深度拆解（`analysis_aggregates` kind=golden） |
| `stage1_checkpoint` | 条件路由 | 产出快速预览后询问是否继续全量（或按预设跳过） |
| `stage2_extract` | **map** | 逐章 spawn `chapter-extractor` 节点（批量 5-8 并行，`Send` API）→ `analysis_chapters` 按章 upsert |
| `stage2_validate` | 服务节点 | 机械校验：情节点数、白描字段、标签枚举（对 `analysis_chapters` 行）；失败 sonnet 重试一次 |
| `stage2_merge` | 服务节点 | 聚合 `analysis_chapters` → 章节摘要汇总（无损检查） |
| `stage3_aggregate` | LLM | 剧情聚合 → `analysis_aggregates`(plot/rhythm/emotion) + 角色合并/分级 |
| `stage4a_settings` | LLM | 世界观/金手指/势力（与 Stage 3 并行） |
| `stage4b_characters` | LLM | 角色完整档案（依赖 Stage 3 角色合并） |
| `stage4c_relations` | LLM | 角色关系提取（依赖 4b） |
| `stage5_report` | LLM | 拆文报告 + 全书概要（500-1000 字） |
| `stage6_style` | LLM | 文风（句长/标点/潜台词 + 原文锚点） |
| `progress_tracker` | 服务节点 | 每阶段写 `analysis_progress`（断点恢复） |

**并行结构**：`stage2_extract` map 完成后 → `stage3_aggregate` 与 `stage4a_settings` 并行 → `stage4b` → `stage4c` → `stage5` → `stage6`。

### 3.4 WriteGraph（story-long-write）— 最复杂

**场景路由 → 3 阶段开书 / 单章写作 / 日更循环 / 大修。**

| 节点 | 类型 | 逻辑 |
|------|------|------|
| `route_scenario` | LLM | 按匹配优先级：大修 > 写指定章 > 补纲 > 日更 > 开书；裸调用只诊断不停靠 |
| `phase1_topic` | LLM | 选题确认 + 对标发现 → `settings` + `benchmarks` 行 |
| `phase2_settings` | LLM | 核心设定：关系/题材定位/题材正文提示卡 → `settings` 行 |
| `phase3_outline` | LLM | 全书卷纲 + 逐章细纲（含大纲安全七检）→ `volumes` + `outline_chapters` |
| `validate_outline` | 服务节点 | `check_outline_contract` 对 `outline_chapters` 结构验收 |
| `write_prep` | LLM + service | 经 ContextService 装配召回包（追踪上下文 + 情绪模块 + 节奏 + 题材卡 + 文风，Redis 热层直取 + 版本守卫）；**Reference Gate**：查 `reference_materials` 主契约记录缺失即 fail-fast |
| `write_prose` | LLM agent | 调 `narrative-writer` 节点写正文（分两段临时 segment，只消费批准情节点），结果暂存 chapters(draft) |
| `wordcount_checkpoint` | 服务节点 | `wordcount_checkpoint`（对 DB 章节内容）非对称收口 |
| `quality_scan` | 服务节点 | `check_ai_patterns` / `check_degeneration` / `normalize_punctuation` / 禁用词（读 DB 正文） |
| `quality_review` | LLM | 章尾钩子、爽点、情绪核对（可证伪双查） |
| `tracking_commit` | 服务节点 | `chapter_commit` + `tracking_commit`（**DB 原子事务**：章节提交 + 角色/伏笔/时间线/派生视图重建 + revision 递增） |
| `snapshot_checkpoint` | 服务节点 | 每 3 章一致性检查 + 数据快照 |

**日更循环**：`route_scenario=daily` 时在 `write_prep→...→tracking_commit` 间循环 2-3 章（带 chapter_no 的条件边实现）。

### 3.5 ReviewGraph（story-review）

| 节点 | 类型 | 逻辑 |
|------|------|------|
| `preflight` | LLM + service | 解析 full/lean/solo；子代理递归守卫；决定 Effective Mode + Fallback |
| `deterministic_precheck` | 服务节点 | `normalize_punctuation --check` + `check_ai_patterns --fail-on=blocking` + `check_degeneration --check` |
| `load_rubric` | 服务节点 | 按平台（fanqie/qidian/zhihu）加载 rubric，不可读用内置 fallback |
| `fan_out_reviewers` | **map** | 并行 spawn 4 个 reviewer 节点（story-architect/character-designer/narrative-writer/consistency-checker），各返回 VERDICT+FINDINGS（经 repository 读正文/追踪） |
| `aggregate_findings` | LLM | 合并去重、按 S1-S4 排序、呈现 Agent 分歧（不自动妥协） |
| `fact_check` | LLM agent | 可选 spawn `story-researcher` 核查外部事实 |
| `output_report` | LLM | 按 full/lean/solo 模板输出（英文 key 元数据 + Findings Schema） |
| `tracking_maintenance` | 服务节点 | full/lean 模式用 `tracking_commit` 更新追踪（solo 不改） |

**并行结构**：`fan_out_reviewers` 用 `Send` 并行 → 汇合到 `aggregate_findings`。

### 3.6 DeslopGraph（story-deslop）

| 节点 | 类型 | 逻辑 |
|------|------|------|
| `ai_scan` | 服务 + LLM | `check_ai_patterns` 预检 + AI 味检测报告（问题标记表 + Gate 列） |
| `classify_severity` | LLM | 六指标量化定档：轻度/中度/重度 → 决定过哪些 Gate |
| `gate_processing` | LLM agent | 逐项执行 Gate A-G（禁用词/句式/心理外化/节奏/对话/结尾/解释腔）；优先判"能否删除"，超删除比例上限标 `[需复核]`；改写写回 chapters |
| `deterministic_finish` | 服务节点 | `check_ai_patterns` 复扫 + `check_degeneration` + `normalize_punctuation` 机械兜底 |
| `output_report` | LLM | 润色报告（字数协议 + 修改统计 + 对比） |

### 3.7 ImportGraph（story-import）

| 节点 | 类型 | 逻辑 |
|------|------|------|
| `confirm_source` | LLM 交互 | 确认书名/题材/平台/完本状态/篇幅类型/最后章完整性 |
| `length_routing` | 服务 + LLM | `wordcount_measure`（对导入内容）+ 规则判断长短篇 |
| `run_analyze` | **子图调用** | 复用 AnalyzeGraph（长篇 Stage 0-6 / 短篇管道），跳过停靠询问 |
| `migrate_structure` | LLM + service | 拆文库（`analysis_*` 表）→ 项目结构映射（3-L 长篇 / 3-S 短篇）：填充 settings/volumes/outline_chapters |
| `migrate_chapters` | 服务节点 | 正文标准化（章节切分、补零、命名）→ `chapters` 表 |
| `reverse_outline` | LLM | 从拆解反推 卷纲/细纲（用户确认卷界） |
| `init_tracking` | 服务节点 | `tracking_init` + `tracking_check`（一次性生成，**禁止手写**） |
| `bind_benchmark` | 服务节点 | 外部对标资产同步 → `benchmarks` |
| `activate_project` | 服务节点 | `projects.status='active'` + 质量检查 + 导入报告 |

### 3.8 叶子节点

| 节点 | 类型 | 逻辑 |
|------|------|------|
| `story_cover` | LLM + service | 收集书名/作者/平台 → 题材风格分析 → 调 image 生成 → 落盘 `covers/{书名}/` + `covers` 表记录 + 平台尺寸导出 |
| `browser_session` | 服务节点 | CDP 启动/导航/求值/抓取（供采集） |

### 3.9 原 7 个 Agent → LangGraph agent 节点

用 `create_agent` 定义，带各自 system prompt + 工具白名单 + 模型档：

```python
story_architect = create_agent(
    "claude-opus-5", system=AGENT_PROMPTS["story_architect"],
    tools=[memory_query, repo_read_settings, repo_write_settings, ...])
chapter_extractor = create_agent(
    "claude-haiku-4-5", system=AGENT_PROMPTS["chapter_extractor"],  # 只读
    tools=[repo_read_chapter], max_turns=12)
```

在图中被调用（`Command(goto=...)` / `Send(...)` 并行）。原 `story-explorer` 的语义查询（伏笔/角色当前状态/进度）用 repository 只读服务提供；保留 agent 形式用于更自然的语义追问。

---

## 4. 服务层 + 可选 MCP

> 设计原则：**服务层优先**。所有确定性能力是 Python service 函数，LangGraph 节点直接 import 调用；如需给外部工具复用，用薄的 MCP server（`story-mcp`）包一层。服务层按聚合拆分，DB 操作走 repository，追踪/章节提交是唯一的多表事务入口。

### 4.1 服务层结构

```
services/
  tracking.py      TrackingService: init / commit / check       ← 追踪唯一写入口
  wordcount.py     WordcountService: measure / checkpoint / evaluate
  chapter.py       ChapterService: check / commit / accept_length / draft
  quality.py       QualityService: ai_patterns / degeneration / punctuation / banned_words / outline_contract
  memory.py        MemoryService: record / query
  scan.py          ScanService: 各平台采集 + 清洗 + 校验
  cover.py         CoverService: 封面生成 + 尺寸导出
  dashboard.py     DashboardService: 启动/停止/状态
  context.py       ContextService: 装配召回包/上下文视图（写透 Redis，PG 回源）
  redis_store.py   RedisStore: 热层读写 + state_revision 版本守卫
repositories/      repository/dao 层（只做 CRUD，无业务规则）
schemas/           SQLAlchemy 模型 + Alembic 迁移
```

### 4.2 追踪与字数（内核）

| 服务函数 | 原脚本 | 输入 → 输出 | 调用点 |
|---------|--------|------------|--------|
| `TrackingService.init` | `tracking_commit.py init` | `{project_id, input_json}` → 生成追踪结构与权威状态 | ImportGraph / 开书 |
| `TrackingService.commit` | `tracking_commit.py commit` | `{project_id, transaction_json}` → 逐章事务（append/revision）**单事务** | WriteGraph / ReviewGraph |
| `TrackingService.check` | `tracking_commit.py check` | `{project_id}` → `{last_committed_chapter, state_revision, 视图一致性}` | 所有写前节点 |
| `WordcountService.measure` | `storyctl.py wordcount measure` | `{chapter_id}` → `{metric, actual}` | ImportGraph / 字数审计 |
| `WordcountService.checkpoint` | `storyctl.py wordcount checkpoint` | `{chapter_id, target}` → `actual/remaining_user_range` | WriteGraph 非对称收口 |
| `WordcountService.evaluate` | `storyctl.py wordcount evaluate` | `{chapter_id, target}` → in-range 判定 | WriteGraph |
| `ChapterService.check` | `storyctl.py chapter check` | `{project_id, chapter_no}` → `{status: in_range/under/over}` | WriteGraph |
| `ChapterService.commit` | `storyctl.py chapter commit` | `{project_id, chapter_no, transaction}` → 原子提交 | WriteGraph |
| `ChapterService.accept_length` | `storyctl.py chapter accept-current-length` | `{project_id, chapter_no}` → 接受自然长度 | WriteGraph |

**关键设计约束（原系统铁律，DB 版）**：追踪表 + 派生视图（`context_views` / `chapter_records` / 角色/伏笔/时间线联动）只能经 `TrackingService.commit` / `ChapterService.commit` 写入，**禁止 LLM 节点直接改库**。commit 在单一 PG 事务内完成（章节状态 + 追踪状态 + 派生重建 + revision 递增），比原 JSON 文件原子写更稳。

### 4.3 质量门禁

| 服务函数 | 原脚本 | 输入 → 输出 | 调用点 |
|---------|--------|------------|--------|
| `QualityService.ai_patterns` | `check-ai-patterns.js` | `{chapter_id / text, fail_on}` → blocking/advisory findings | Deslop / Review / Write 质量节点 |
| `QualityService.degeneration` | `check-degeneration.js` | `{chapter_id}` → 退化 findings | Deslop / Review |
| `QualityService.punctuation` | `normalize-punctuation.js` | `{chapter_id, check?, quote_mode}` → 归一或报告 | Deslop / Review |
| `QualityService.outline_contract` | `check-outline-contract.js` | `{project_id}` → 结构验收（对 `outline_chapters`） | WriteGraph phase3 |
| `QualityService.delivery_contract` | `check-delivery-contract.js` | `{project_id}` → 短篇契约校验 | WriteGraph 短篇 |
| `QualityService.banned_words` | banned-words.md + 扫描器 | `{chapter_id}` → 命中列表（含 `.deslop-whitelist` 豁免） | Deslop / Review / Write |

### 4.4 作者记忆

| 服务函数 | 原脚本 | 输入 → 输出 | 调用点 |
|---------|--------|------------|--------|
| `MemoryService.record` | `author_memory_commit.py record` | `{kind, content, scope}` → 回执（写 PG + Redis 写透） | Router / 各写作节点收尾 |
| `MemoryService.query` | `author_memory_commit.py query` | `{kinds}` → active 条目（≤2KB，Redis 直取、miss 回源 PG） | WriteGraph 写前 / Deslop / Review |

### 4.5 市场采集

| 服务函数 | 原脚本 | 输入 → 输出 | 调用点 |
|---------|--------|------------|--------|
| `ScanService.qidian` | `qidian-rank-scraper.js` | `{type(榜单)}` → `scan_results` | ScanGraph |
| `ScanService.fanqie` | `fanqie-rank-scraper.js` | `{channel, type, top}` → `scan_results` | ScanGraph |
| `ScanService.qimao` | `qimao-rank-scraper.js` | `{period}` → `scan_results` | ScanGraph |
| `ScanService.jjwxc` | `jjwxc-rank-scraper.js` | `{type, top, detail_limit}` → `scan_results` | ScanGraph |
| `ScanService.ciweimao` | `ciweimao-rank-scraper.js` | 榜单采集 | ScanGraph |
| `ScanService.dz_heiyan` | `dz-browse-scraper.js` / `heiyan-booklist-scraper.js` | 短篇榜单采集 | ScanGraph(短篇) |

> 依赖 CDP 的平台（番茄等）内部调用 browser 服务。采集器保留 Node 实现时用子进程调用，或逐步重写为 Python。

### 4.6 浏览器

`BrowserService.launch / navigate / evaluate / screenshot / close` — CDP 控制 Chrome，供采集与登录态场景（对应原 browser-cdp skill）。

### 4.7 其他

| 服务函数 | 原脚本 | 说明 |
|---------|--------|------|
| `DashboardService.start / stop` | `dashboard-server.mjs` | 本地写作工作台 HTTP 服务（读 DB） |
| `CoverService.generate` | GPT-Image-2 API | 封面生成（书名/作者/题材 → 图 + 平台尺寸） |

### 4.8 可选 MCP 封装

> 仅当需要外部工具复用同一能力时启用。用 `story-mcp`（tracking/wordcount/quality/memory）、`story-scan-mcp`、`browser-mcp` 三个薄 server 包住上述 service，内部仍是同一个 repository/DB。**本系统内的 LangGraph 节点不经过 MCP 协议。**

---

## 5. 对应关系总表

| 原系统 | LangGraph | 服务/MCP 工具 |
|--------|-----------|---------|
| story 路由 | RouterGraph.intent_router | — |
| story-setup | **不需要**（本系统自包含） | — |
| story-long-scan / short-scan | ScanGraph | ScanService 工具组 |
| story-long-analyze / short-analyze | AnalyzeGraph（Stage 0-6 节点）| 写 `analysis_*` 表 |
| story-long-write | WriteGraph（含日更循环）| TrackingService / WordcountService / ChapterService |
| story-short-write | WriteGraph 短篇分支 | 同上 |
| story-review | ReviewGraph（并行 reviewers）| QualityService 工具组 |
| story-deslop | DeslopGraph（7 Gate 节点）| QualityService |
| story-import | ImportGraph | TrackingService.init + WordcountService |
| story-cover | story_cover 叶子节点 | CoverService |
| browser-cdp | browser_session 节点 | BrowserService |
| chapter-extractor agent | AnalyzeGraph.stage2_extract 的 map 节点 | — |
| narrative-writer agent | WriteGraph.write_prose / DeslopGraph.gate_processing | — |
| story-architect agent | WriteGraph phase1-3 节点 / ReviewGraph reviewer | — |
| character-designer agent | ReviewGraph reviewer | — |
| consistency-checker agent | ReviewGraph reviewer | — |
| story-researcher agent | WriteGraph 资料研究节点 / ReviewGraph fact_check | — |
| story-explorer agent | 各图 context 加载节点 | TrackingService.check + repository 查询 |
| hooks（PreToolUse/PostToolUse…）| 图内守卫节点 | 写正文前置校验 / 写后质量扫描 |

---

## 6. 实现建议

1. **分层顺序**：先做存储层（SQLAlchemy 模型 + Alembic 迁移 + repository）→ 再 `TrackingService`/`WordcountService`/`QualityService`（确定性内核，可独立测试）→ 再搭 AnalyzeGraph 和 WriteGraph。
2. **追踪铁律保持**：追踪表 + 派生视图唯一写入口是 `TrackingService.commit`（PG 单事务），LLM 节点不得直写。
3. **并行策略**：`chapter-extractor` map 和 `reviewer` fan-out 用 `Send` API 实现真正的并行；批量受并发上限控制（原 5-8/批）。
4. **Reference Gate 保留**："写正文前必须完整读参考资料"做成 `write_prep` 的硬前置校验——查 `reference_materials` 表主契约记录（情绪模块/节奏/文风/题材卡），缺失即 fail-fast。
5. **停靠点（checkpoint）**：`stage1_checkpoint`、日更批次的用户确认，用图内条件边 + 中断（`interrupt_before`）实现人机协同。
6. **状态持久化**：PostgreSQL 为唯一真值源；LangGraph 用 Postgres checkpointer 恢复"进行中的图执行"（与业务库同源）。
7. **DB 选型理由（PostgreSQL vs MongoDB）**：追踪提交的多表原子性、卷↔章↔正文的强结构关系、派生视图确定性重建都需要真正的 ACID 事务与约束——PG 的单事务能力正是原系统最硬铁律的最省心落点；而原 `_tracking-state.json` 这类半结构化文档用 **JSONB 列** 即可零成本兼容。Mongo 的优势（schemaless 文档、无迁移）在本系统里被 JSONB 基本追平，而它缺失的正是我们需要的那两项能力。预留 pgvector（伏笔/情绪模块语义召回）与 pg_trgm/zhparser（拆文库中文检索）。Redis 承担长期记忆热层（§2.2），不承担权威存储。
8. **Python 实现**：原 Node 脚本（scrapers、质量检测器）用子进程调用或重写为 Python；追踪/字数逻辑已是 Python，直接落为 DB service。
9. **Redis 使用纪律**：只读热层、可重建、版本守卫、不经 Redis 提交业务写——防止 Redis 变成第二个真值源；`FLUSHDB` 永远安全。
