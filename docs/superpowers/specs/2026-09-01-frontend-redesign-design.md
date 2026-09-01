# 前端改造设计：novel_agents 对齐 auto_noval_agents

日期：2026-09-01
状态：已获用户批准（在聊天中确认）

## 目标

将 novel_agents 前端（Vue3 + TS + Element Plus + Pinia）改造为参考项目 `/data/code/auto_novel/auto_noval_agents/frontend` 的设计语言与页面结构：采用其 Arco 蓝设计系统（theme.css）、中央 AppLayout 布局（可折叠侧栏 + 顶部面包屑），并把合并式「写作工作台」拆分为参考式多页（项目详情 / 大纲审核 / 创作控制台 / 章节阅读）。

## 范围（用户决策）

- **包含**：设计系统（theme.css）· AppLayout 中央布局 · 页面结构重构（拆分 WorkspaceView）
- **不包含**：暗色模式（用户选择「暂不需要」）；新增功能页（导出、Prompt 管理、大纲审核 AI 聊天）；任何后端改动；任何新增功能
- 现有 7 个模块全部保留：写作 / 审查去味 / 拆文库 / 扫榜 / 用量 / 设置

## 设计决策

### 1. 设计系统 `frontend/src/styles/theme.css`

照搬参考项目 theme.css 的亮色 token（Arco 蓝主色）：

- **主色**：`--color-primary: #165DFF`；light `#4080FF`；lighter（选中态底色）`#E8F3FF`；dark `#0E42D2`
- **语义色**：success `#00B42A` / warning `#FF7D00` / danger `#F53F3F`（各带 light 底色调）
- **中性色**：text-primary `#1D2129` / regular `#4E5969` / secondary `#86909C` / placeholder `#C9CDD4`；border `#E5E6EB` / border-light `#F2F3F5`；bg-page `#F7F8FA` / bg-card `#FFFFFF`
- **布局**：`--sidebar-width: 220px`（折叠 64px）、`--topbar-height: 56px`
- **圆角**：sm 4 / md 8 / lg 12 / xl 16；**阴影**：sm/md/lg/xl（`0 1px 2px rgba(0,0,0,0.04)` ~ `0 8px 24px rgba(0,0,0,0.1)`）
- **间距**：xs 4 / sm 8 / md 16 / lg 24 / xl 32 / 2xl 48；**字号**：xs 12 ~ 3xl 30
- **字体**：系统中文栈 + `--font-mono: 'SF Mono','Fira Code','Consolas',monospace`
- **Element Plus 覆盖**：`.el-button` 圆角 md（`!important`）weight 500；`.el-card` 圆角 lg、1px border-light、shadow-sm；`.el-input__wrapper` 圆角 md；`.el-tag` 圆角 sm；progress 圆角 sm
- **工具类**：`.page-container`（max-width 1400 / 居中 / padding lg）、`.page-header`、`.page-title`（24px/600）、`.card-grid`（auto-fill minmax 320px）、`.stat-card`、`.section-card`（白底 lg 圆角 24px padding）、`.section-title`（16px/600 + **3px×16px 主色竖条** `::before`）、自定义滚动条
- **无 `html.dark` 块**（用户决策）
- `main.ts`：全局注册 `@element-plus/icons-vue`（新增依赖）；`import './styles/theme.css'`

### 2. AppLayout 中央布局 `frontend/src/components/AppLayout.vue`

- 结构：`display:flex; min-height:100vh`；固定左侧栏 + sticky 顶栏 + 可滚内容
- **侧栏**：固定 220px（折叠 64px，宽度过渡动画）；logo 区 56px 高（渐变方块 `linear-gradient(135deg, primary, primary-light)` + EditPen 图标 + 「Novel Agents」）；`el-menu` router 模式，菜单项 44px 高 `margin 2px 8px` 圆角 md；激活态 = `primary-lighter` 底 + 主色字 + weight 500（软药丸，无左竖条）
  - 主菜单：工作台 / 拆文库 / 审查去味 / 扫榜 / 用量 / 设置
  - 当 `route.params.id` 存在时追加「当前项目」分组（group-title 12px 大写字母间距）：项目详情 / 大纲审核 / 创作控制台
  - 底部折叠开关
- **顶栏**：sticky 56px；左侧 `el-breadcrumb`（首页 / 当前 `meta.title`）；右侧用户下拉（圆形主色头像首字母 + 用户名 + 箭头，hover 变 bg-page）
- **内容**：`flex:1; overflow-y:auto` 包 `<router-view>`，page-fade out-in 过渡（0.2s）
- **路由重构** `router/index.ts`：`/login` `/register` 独立（guest）；其余全部为 AppLayout 子路由（requiresAuth），每路由 `meta.title` 供面包屑与 document.title

### 3. 页面结构重构（核心）

拆分 653 行合并式 `WorkspaceView.vue` 为参考式 4 页：

| 新页面 | 路由 | 内容来源与组成 |
|---|---|---|
| 项目详情 NovelDetail | `/projects/:id` | 项目信息 `el-descriptions`(3列) + 创作进度环 `el-progress type=dashboard`(按完成比例蓝→橙→绿渐变) + 分卷大纲概览（卷→章→细纲，只读）+ 操作按钮（进入创作台 / 进入大纲页） |
| 大纲审核 OutlineReview | `/projects/:id/review` | **开书三阶段流水线**（PipelineBar：世界观/设定→大纲→细纲，阶段草稿实时流式预览 + DraftConfirmDialog confirm/regenerate/cancel + auto/confirm 模式切换 + 点击阶段重跑，全部从原工作台迁来）+ 三层大纲全量展示（卷→章→细纲，只读） |
| 创作控制台 Console | `/projects/:id/console` | **写下一章**（4 阶段流水线 PipelineBar + 深色终端流式正文 + Agent 活动面板）+ 章节列表（可点选查看）+ 追踪上下文（侧栏页签） |
| 章节阅读 ChapterView | `/projects/:id/chapters/:no` | 章节阅读/编辑（字号 16 / line-height 2）+ 章节信息卡（章号/字数/状态）+ 细纲/摘要 + 「审查/去味」跳转按钮（到 /quality 预选该项目） |

**关键约束（数据现状）**：
- `GET /projects/{pid}/outline` 仅返回 `{has_outline, volumes}`，不含世界观设定 → NovelDetail 只展示大纲概览；世界观草稿仅在大纲页开书流水线中流式可见
- 后端无大纲更新 API → 大纲页**只读**展示，不做内联编辑 / AI 聊天（用户决策）
- 章节审查/去味功能保留在独立「审查去味」页；ChapterView 只做查看与跳转，不重复审查逻辑

### 4. 组件改造

- `PipelineBar.vue` → 参考「Agent 流水线」节点风：44px 圆形图标 + 2px 边框 + 状态点；active = `primary-lighter` 底 + 主色边框 + `0 0 0 4px rgba(22,93,255,0.1)` 光晕；done = 绿；节点间 2px 连线随完成变绿。保留现有 `retry`（点击已点亮阶段重跑）语义
- `AgentActivityPanel.vue` → 深色终端面板 `#1a1a2e` + `--font-mono` + 浅色文字；时间戳 + 消息行；实时流式 + 闪烁光标 `|`（0.8s step-end）；保留现有事件类型渲染（stage/tool/token/status/stage_draft/done/error）
- `DraftConfirmDialog.vue` → 按参考弹窗样式重绘（640px，pre 文本 + 确认/重新生成/取消）
- `LoginView` / `RegisterView` → 参考左右分栏：左 50% 品牌渐变（`linear-gradient(135deg,#0E42D2,#165DFF,#4080FF)` + 毛玻璃 logo + 特性列表毛玻璃药丸 + 装饰圆）；右 480px 白面板表单

### 5. 其余页面重绘

- `DashboardView` → 参考 Home：4 列统计卡（总项目/创作中/已完成/总章节）+ 项目卡片网格（白卡、hover 上浮 translateY(-2px) + shadow-lg、状态 el-tag、进度条、底部创建日期 + 进入控制台）；「新建项目」保持对话框（重绘样式）
- `AnalysisView` / `QualityView` / `ScanView` / `UsageView` / `SettingsView` → 套用 `.page-container` + `.section-card` + `.section-title`，删除重复布局骨架，保留各自功能与 store 逻辑
- `App.vue` → 仍为 `<router-view />`（布局交给 AppLayout）

### 6. 不动的东西

- 后端零改动；stores 逻辑保留（writing/outline/projects/quality/scan/analysis/usage/settings/auth）；`api/` 层不变；`types/` 不变
- 路由路径沿用 `/projects/:id/...` slug（不改成参考的 /novel）

## 实施阶段（每阶段 commit + push）

1. **Stage 1 设计系统**：`package.json` 加 `@element-plus/icons-vue`；新建 `styles/theme.css`；`main.ts` 注册图标 + 引 theme.css
2. **Stage 2 布局**：新建 `AppLayout.vue`；重构 `router/index.ts`；从各视图删除重复的 `el-container/el-aside/el-header` 骨架（先保证能渲染，样式后补）
3. **Stage 3 页面重绘**：Login/Register → 分栏品牌页；Dashboard → Home 风；Analysis/Quality/Scan/Usage/Settings → section-card 重绘
4. **Stage 4 工作台拆分**：WorkspaceView → NovelDetail / OutlineReview / Console / ChapterView；组件 PipelineBar / AgentActivityPanel / DraftConfirmDialog 重绘
5. **Stage 5 验证收尾**：`npm run typecheck` + `vite build` 通过；本地起 dev 逐页截图核对；修复视觉细节

## 验证

- `cd frontend && npm run typecheck` 零错误；`npm run build` 成功
- 本地 `npm run dev`（:5173，/api 代理 :8000）逐页人工核对：登录、工作台、项目详情、大纲、创作台、章节、拆文库、审查去味、扫榜、用量、设置
- 后端行为不变：写作/开书 SSE 流式、confirm 弹窗、PipelineBar 重跑等交互在新页面上仍可用
