# 开发计划 — US 拆分 · 工作量 · 每日可运行 MVP

> 假设：**单人开发 + AI 辅助编码**（Claude Code）。总工作量 ≈ 34.5 人日；12 天×每天交付一个**可运行 MVP 增量**。工作量单位为"人日"，含编码+测试+当天自测。

## 1. 里程碑总览

| 阶段 | 天数 | 内容 | 结束时可运行 |
|------|------|------|-------------|
| **P0 核心写作闭环** | D1-D5 | 骨架/鉴权 → 模型+提示词 → 服务层 → 写作后端 → 写作前端 | 登录后网页里写并提交一章 |
| **P1 内容工厂** | D6-D9 | 拆文 → 导入 → 审查/去味 → 扫榜 | 导入/拆解/审查/扫榜全流程 |
| **P2 增强与上线** | D10-D12 | 多模型增强+用量 → Redis+部署 → 缓冲 | docker-compose 全栈上线 |

## 2. User Stories 拆分（编号 / 工作量 / 优先级 / 依赖）

优先级：**P0**=核心闭环必须；**P1**=内容增值；**P2**=增强/收尾。

| US | 描述 | 工作量 | 优先级 | 依赖 |
|----|------|-------|-------|------|
| US-01 | monorepo 骨架：backend(FastAPI)/frontend(Vite+EP)/docker-compose(pg)/配置 | 0.5 | P0 | — |
| US-02 | 用户鉴权：register/login/refresh/me，JWT+argon2 | 1 | P0 | US-01 |
| US-03 | 当前用户依赖 + repository 层 owner 作用域强制隔离 | 0.5 | P0 | US-02 |
| US-04 | 业务数据模型（§1 全部表）+ Alembic 迁移 + seed providers | 1.5 | P0 | US-03 |
| US-05 | 项目 CRUD + 活跃书切换 API | 0.5 | P0 | US-04 |
| US-06 | LLM 抽象：providers 表 + ModelFactory + 三档映射 + **输出契约后校验 + 反馈式重试** + 用量记录 | 2 | P0 | US-04 |
| US-07 | 提示词文件化：prompts/ 目录 + PromptRegistry + Jinja2 渲染 + 热重载 + **KV cache 复用装配**（稳定前缀/断点/摘要不动前缀） | 1.5 | P0 | US-06 |
| US-08 | TrackingService：init/commit/check，PG 单事务 + 派生视图重建 + 版本守卫 | 2 | P0 | US-04 |
| US-09 | WordcountService + ChapterService：草稿/非对称收口/原子提交/接受长度 | 1 | P0 | US-04 |
| US-10 | QualityService：AI 句式/退化/标点/禁用词/大纲契约 | 1 | P0 | US-04 |
| US-11 | ContextService：上下文视图(7列≤12KB) + 写前召回包 + Reference Gate | 0.5 | P0 | US-08 |
| US-12 | RouterGraph + 意图路由节点 | 0.5 | P0 | US-07 |
| US-13 | WriteGraph：route_scenario / 开书三阶段 / 写章 / 日更循环 / 大修 | 2.5 | P0 | US-08,09,10,11 |
| US-14 | 任务管理：tasks 表 + asyncio 后台执行 + 取消 + 恢复 | 1.5 | P0 | US-01 |
| US-15 | SSE 事件流（stage/token/**tool**/checkpoint）+ 执行器事件总线（astream_events 捕获工具调用） | 1 | P0 | US-14 |
| US-16 | 前端：登录/注册 + Dashboard + 工作台（章节树/流式编辑器/追踪侧栏/**Agent 活动面板**） | 2 | P0 | US-13,15 |
| US-17 | 前端设置页：三档模型选择 + provider 测试 | 1 | P0 | US-06 |
| US-18 | AnalyzeGraph：stage0-6 + map 并行 + 断点恢复（analysis_progress） | 2 | P1 | US-13 模式 |
| US-19 | 拆文 API + 前端（上传/进度/报告查看） | 1.5 | P1 | US-18 |
| US-20 | ImportGraph：拆解→结构迁移→正文入库→追踪初始化→激活 | 1.5 | P1 | US-18 |
| US-21 | ReviewGraph：full/lean/solo + 4 reviewer 并行 + 汇总 | 1.5 | P1 | US-08,10 |
| US-22 | DeslopGraph：AI 扫描→定级→Gate A-G→确定性兜底 | 1.5 | P1 | US-10 |
| US-23 | 审查/去味前端页面 | 1 | P1 | US-21,22 |
| US-24 | ScanGraph：2 平台采集 + 清洗 + 趋势 + 选题决策 | 1.5 | P1 | US-06 |
| US-25 | 扫榜前端页面 | 0.5 | P1 | US-24 |
| US-26 | 多模型增强：API 级重试/超时/跨 provider 降级（不改 prompt）+ 失败提示 | 1 | P1 | US-06 |
| US-27 | 用量统计页（token/成本/天） | 0.5 | P1 | US-06 |
| US-28 | Redis 预留接口 + PG 回源实现 + 版本守卫（**可禁用**） | 0.5 | P2 | US-08 |
| US-29 | 章节提交并发锁（PG advisory lock）+ Redis 锁可选 | 0.5 | P2 | US-09 |
| US-30 | 生产部署：docker-compose 全栈 + nginx + 部署文档 | 0.5 | P2 | US-01 |
| US-31 | 日志/request-id/错误捕获 + README | 0.5 | P2 | US-01 |
| US-32 | 缓冲日：修复/打磨/演示脚本 | 0.5 | P2 | — |

**工作量合计 ≈ 34.5 人日。**

## 3. 每日可运行 MVP 计划

> 每天结束必须能"跑起来 + 看到东西"。验收标准 = 当天是否可运行的最小可演示场景。

### D1 — 骨架 + 鉴权（US-01, 02）
- **交付**：monorepo；`docker-compose up postgres`；FastAPI `/health`+CORS+配置；Alembic 首迁移（users）；Vue3+Vite+TS+ElementPlus 脚手架；登录/注册 API + 前端页。
- **验收**：浏览器注册→登录→进入空 Dashboard；`GET /api/auth/me` 返回当前用户；pytest 鉴权用例通过。

### D2 — 数据模型 + LLM 抽象 + 提示词框架（US-03, 04, 05, 06, 07）
- **交付**：全部业务表迁移 + owner 作用域 repository；项目 CRUD API；providers 配置驱动（DeepSeek/Qwen/GLM/Kimi/豆包/MiniMax 种子）+ ModelFactory 三档；**输出契约(后校验) + 反馈式重试引擎**；`prompts/` 目录 + PromptRegistry + **KV cache 复用装配**（稳定前缀顺序 + 断点）。
- **验收**：pytest 覆盖租户隔离（A 看不到 B 的项目）；CLI 脚本用 DeepSeek 生成一句话并写 usage_logs；**坏 JSON→契约校验失败→错误封装回喂→模型修正成功**单测通过；**连续两次调用前缀缓存命中（usage_logs.cached_tokens 递增）**；提示词从文件加载渲染。

### D3 — 服务层核心（US-08, 09, 10, 11）
- **交付**：TrackingService / WordcountService / ChapterService / QualityService / ContextService，全 async + 单事务。
- **验收**：pytest 覆盖"章节提交事务"——一次 commit 同时更新 chapters、角色/伏笔/时间线、重建 chapter_records/context_views、revision+1；**追踪事务 JSON 先过契约后校验再入库**；字数非对称收口；质量门禁返回 findings。

### D4 — 写作闭环后端（US-12, 13, 14, 15）
- **交付**：RouterGraph + WriteGraph（开书三阶段 + 写一章 + 日更循环最小版）；任务管理（tasks 表 + asyncio 后台）+ SSE 事件流。
- **验收**：种子项目+细纲，`POST /chapters/next` 返回 task_id；SSE 看到 `stage→tool→token→checkpoint→done`（含 narrative-writer 调用的工具记录）；提交后 `tracking_state` 正确更新、chapters 出现 committed 行。

### D5 — 写作闭环前端（US-16）
- **交付**：Dashboard + 工作台（章节树 / 流式编辑器 / 追踪侧栏 / 任务进度条），SSE 客户端。
- **验收**：网页里点"写下一章"→正文流式滚动→底部 Agent 活动面板实时显示工具调用（running→done）→提交→侧栏追踪上下文刷新。**P0 达成：登录后网页可完整写一章。**

### D6 — 拆文后端（US-18）
- **交付**：AnalyzeGraph stage0-6 + map 并行（chapter-extractor）+ 断点恢复；拆文 API。
- **验收**：上传一本书文本→跑完拆解→analysis_aggregates 各 kind 落库；中断后重跑从 analysis_progress 续。

### D7 — 拆文前端 + 导入 + 设置页（US-17, 19, 20）
- **交付**：拆文页（上传/进度/报告）；ImportGraph（导入→结构迁移→正文入库→追踪初始化→激活）；前端设置页（三档模型切换 + provider 测试）。
- **验收**：网页上传 txt→拆解→看报告；一键导入生成可写项目；设置页切换模型立即生效。

### D8 — 审查 + 去味（US-21, 22, 23）
- **交付**：ReviewGraph（full/lean/solo + 4 reviewer `Send` 并行）+ DeslopGraph（扫描/定级/Gate/兜底）+ 前端页面。
- **验收**：对已提交章节跑 full 审查→网页看到 findings 列表；一键去味→对比前后文本与字数变化。

### D9 — 扫榜（US-24, 25）
- **交付**：ScanGraph（2 平台采集 + 清洗 + 趋势 + 选题）+ 扫榜页。
- **验收**：抓取真实榜单→网页展示分布/热词→生成选题决策。

### D10 — 多模型增强 + 用量（US-26, 27）
- **交付**：重试/超时/跨 provider 降级/失败提示；usage_logs 汇总页。
- **验收**：主 provider 故意配错→自动降级到同档备用；用量页显示 token/成本曲线。

### D11 — Redis 预留 + 并发 + 部署（US-28, 29, 30, 31）
- **交付**：RedisStore 接口 + PG 回源（可禁用）；章节提交 PG advisory lock；docker-compose 全栈 + nginx；日志/README。
- **验收**：`docker compose up` 全栈可注册→登录→写章节；并发提交两章不产生脏状态；Redis 关闭时功能等价。

### D12 — 缓冲日（US-32）
- **交付**：修复遗留、打磨交互、演示脚本、设计文档同步。
- **验收**：全链路演示跑通一遍，无已知阻塞性 bug。

## 4. 工作量与节奏说明

- 总量 34.5 人日 ÷ 12 天 ≈ **2.9× AI 辅助加速**（Claude Code 承担脚手架/样板/测试生成，人负责架构决策与验收）。若纯手写，周期约 3-4 周。
- **并行空间**：D3 服务层与前端登录页可并行；D7 的导入/设置页与 D6 拆文可部分并行。但为保持"每天可运行"，计划按串行为主，预留 D12 缓冲。
- **每日节奏**：上午 → 按 US 编码；下午 → 当天 MVP 验收 + 修复；收尾 → 提交（`docs/` 随代码同步更新）。

## 5. 风险与依赖

| 风险 | 影响 | 缓解 |
|------|------|------|
| 国内模型输出格式不稳定（JSON 解析失败） | 拆文/审查/追踪解析失败 | 输出契约后校验 + 统一错误反馈重试（可升档），见详细设计 §5.1 |
| 长文生成 token 超限/成本 | 单章成本高、超时 | 三档分级（正文用 mid）、分段临时 segment、非对称收口 |
| 并发章节提交竞态 | 追踪状态错乱 | PG advisory lock 串行化 + revision 版本守卫 + 冲突重试 |
| 拆文耗时（几百章） | 任务悬挂 | map 分 5-8 章/批 + 断点恢复 + 60min 超时 |
| 模型提供商故障/限流 | 写作中断 | 跨 provider 降级 + 重试退避 + 任务可重试 |
| 追踪铁律被 LLM 绕过 | 派生视图不一致 | repository 层不暴露写追踪工具给 agent + 提交校验 |

## 6. 验收工具链

- **测试**：pytest（services/graph 单测）+ pytest-asyncio；前端 vitest（store/组件）+ Playwright 冒烟。
- **演示数据**：scripts/seed_demo.py 生成一个含细纲的演示项目，D4 起每日可用。
- **每日验收清单**：`docker compose up` → 前端可登录 → 当天新增功能可操作 → `pytest` 绿 → git commit。
