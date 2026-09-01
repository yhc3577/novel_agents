# 前端改造（对齐 auto_noval_agents 设计系统 + 布局 + 页面拆分）实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 novel_agents 前端按参考项目 auto_noval_agents 的设计语言重绘，引入 AppLayout 中央布局，并把合并式「写作工作台」拆分为 项目详情/大纲审核/创作控制台/章节阅读 四页。

**Architecture:** 全前端改造，零后端改动。引入参考项目 `frontend/src/styles/theme.css` 设计 token（Arco 蓝 `#165DFF` 主色）+ Element Plus 全局样式覆盖 + 工具类（`.page-container/.section-card/.section-title` 等）；新增 `AppLayout.vue` 作为全部已登录页的壳（固定可折叠侧栏 + sticky 顶栏面包屑）；按页逐步迁移，旧的 `WorkspaceView` 先保留在 `/projects/:id/workspace` 兜底，拆分完成后删除。

**Tech Stack:** Vue 3.5 · TypeScript（strict，`noUnusedLocals`/`noUnusedParameters`）· Element Plus 2.9 · Pinia 2.3 · Vue Router 4 · Vite 6 · `@element-plus/icons-vue`（新增显式依赖）。

**Spec:** [docs/superpowers/specs/2026-09-01-frontend-redesign-design.md](../../superpowers/specs/2026-09-01-frontend-redesign-design.md)

## Global Constraints

- **前端 only**：`backend/` 一行不改；`frontend/src/api/`、`frontend/src/types/`、`frontend/src/stores/` 的现有逻辑与 API 签名不改动（新增 UI 读取不改 store 接口）。
- **无暗色模式**：theme.css 不写 `html.dark` 块；AppLayout 顶栏不放日/月切换。
- **不新增功能页**：不加导出/Prompt 管理/大纲 AI 聊天；大纲页只读（后端无大纲更新 API）。
- 中文 UI 文案；沿用现有模块名：工作台 / 拆文库 / 审查去味 / 扫榜 / 用量 / 设置。
- 路由路径沿用 `/projects/:id/...`（不改成参考的 /novel）。
- 别名 `@` → `./src`；`@element-plus/icons-vue` 需显式加入 `package.json` dependencies（node_modules 里已有传递安装，但必须声明）。
- 每任务结束：`npm run typecheck` 零错误；阶段里程碑（Task 5 后每个 Task）`npm run build` 成功。
- 每任务完成即 `git add` + commit + push（用户工作习惯，直接提交 main）。
- 前端无测试框架（package.json 无 vitest）：验收 = `npm run typecheck` + `npm run build` + 本地 `npm run dev`（:5173，/api 代理 :8000）人工逐页核对。

---

## 文件结构总览

**新建：**
- `frontend/src/styles/theme.css` — 设计系统（token + EP 覆盖 + 工具类）
- `frontend/src/components/AppLayout.vue` — 中央布局壳
- `frontend/src/views/NovelDetailView.vue` — 项目详情 `/projects/:id`
- `frontend/src/views/OutlineReviewView.vue` — 大纲审核 `/projects/:id/review`
- `frontend/src/views/ConsoleView.vue` — 创作控制台 `/projects/:id/console`
- `frontend/src/views/ChapterView.vue` — 章节阅读 `/projects/:id/chapters/:chapterNo`

**修改：**
- `frontend/package.json` — 加 `@element-plus/icons-vue`
- `frontend/src/main.ts` — 全局注册图标 + 引 theme.css
- `frontend/src/router/index.ts` — AppLayout 子路由 + meta.title
- 所有 `frontend/src/views/*.vue` — 删重复布局骨架、套用设计系统（Login/Register/Dashboard/Analysis/Quality/Scan/Usage/Settings）
- `frontend/src/components/PipelineBar.vue` / `AgentActivityPanel.vue` / `DraftConfirmDialog.vue` — 重绘

**删除（Task 10）：**
- `frontend/src/views/WorkspaceView.vue`

---

### Task 1: 设计系统地基（theme.css + 图标 + main.ts）

**Files:**
- Modify: `frontend/package.json`
- Create: `frontend/src/styles/theme.css`
- Modify: `frontend/src/main.ts`

**Interfaces:**
- Consumes: 无（前置任务）
- Produces: `theme.css` 定义 `--color-*`、`--radius-*`、`--shadow-*`、`--space-*`、`--font-*`、`--sidebar-width`、`--topbar-height` 及 `.page-container/.page-header/.page-title/.section-card/.section-title/.stat-card/.card-grid` 等类，供后续所有视图使用。

- [ ] **Step 1: 声明图标依赖**

编辑 `frontend/package.json`，在 `dependencies` 中加入：

```json
"@element-plus/icons-vue": "^2.3.1",
```

- [ ] **Step 2: 安装依赖**

Run: `cd frontend && npm install`
Expected: 成功，`@element-plus/icons-vue` 出现在 dependencies。

- [ ] **Step 3: 编写 theme.css**

创建 `frontend/src/styles/theme.css`，内容为完整设计系统（Arco 蓝，亮色 only）：

```css
/* ================= 设计系统（对齐 auto_noval_agents） ================= */
:root {
  color-scheme: light;

  /* 主色 */
  --color-primary: #165dff;
  --color-primary-light: #4080ff;
  --color-primary-lighter: #e8f3ff;
  --color-primary-dark: #0e42d2;

  /* 语义色 */
  --color-success: #00b42a;
  --color-success-light: #e8ffea;
  --color-warning: #ff7d00;
  --color-warning-light: #fff7e8;
  --color-danger: #f53f3f;
  --color-danger-light: #ffece8;

  /* 中性色 */
  --color-text-primary: #1d2129;
  --color-text-regular: #4e5969;
  --color-text-secondary: #86909c;
  --color-text-placeholder: #c9cdd4;
  --color-border: #e5e6eb;
  --color-border-light: #f2f3f5;
  --color-bg-page: #f7f8fa;
  --color-bg-card: #ffffff;
  --color-bg-overlay: rgba(0, 0, 0, 0.45);

  /* 布局度量 */
  --sidebar-width: 220px;
  --sidebar-collapsed-width: 64px;
  --topbar-height: 56px;

  /* 圆角 */
  --radius-sm: 4px;
  --radius-md: 8px;
  --radius-lg: 12px;
  --radius-xl: 16px;

  /* 阴影 */
  --shadow-sm: 0 1px 2px rgba(0, 0, 0, 0.04);
  --shadow-md: 0 2px 8px rgba(0, 0, 0, 0.06);
  --shadow-lg: 0 4px 16px rgba(0, 0, 0, 0.08);
  --shadow-xl: 0 8px 24px rgba(0, 0, 0, 0.1);

  /* 间距 */
  --space-xs: 4px;
  --space-sm: 8px;
  --space-md: 16px;
  --space-lg: 24px;
  --space-xl: 32px;
  --space-2xl: 48px;

  /* 字体 */
  --font-family: -apple-system, BlinkMacSystemFont, 'PingFang SC', 'Hiragino Sans GB',
    'Microsoft YaHei', 'Helvetica Neue', Helvetica, Arial, sans-serif;
  --font-mono: 'SF Mono', 'Fira Code', 'Consolas', monospace;
  --font-size-xs: 12px;
  --font-size-sm: 13px;
  --font-size-md: 14px;
  --font-size-lg: 16px;
  --font-size-xl: 20px;
  --font-size-2xl: 24px;
  --font-size-3xl: 30px;

  /* 过渡 */
  --transition-fast: 0.15s ease;
  --transition-normal: 0.25s ease;
  --transition-slow: 0.35s ease;
}

html {
  font-size: 14px;
}

body {
  line-height: 1.5714;
  font-family: var(--font-family);
  background: var(--color-bg-page);
  color: var(--color-text-primary);
  -webkit-font-smoothing: antialiased;
}

* {
  box-sizing: border-box;
}

/* ================= Element Plus 覆盖 ================= */
.el-button--primary {
  --el-button-bg-color: var(--color-primary);
  --el-button-hover-bg-color: var(--color-primary-light);
  --el-button-active-bg-color: var(--color-primary-dark);
}
.el-button {
  border-radius: var(--radius-md) !important;
  font-weight: 500;
}
.el-card {
  border-radius: var(--radius-lg) !important;
  border: 1px solid var(--color-border-light) !important;
  box-shadow: var(--shadow-sm) !important;
}
.el-input__wrapper {
  border-radius: var(--radius-md) !important;
}
.el-tag {
  border-radius: var(--radius-sm) !important;
}
.el-progress-bar__outer,
.el-progress-bar__inner {
  border-radius: var(--radius-sm) !important;
}
.el-dialog {
  border-radius: var(--radius-lg) !important;
}

/* ================= 工具类 ================= */
.page-container {
  max-width: 1400px;
  margin: 0 auto;
  padding: var(--space-lg);
}

.page-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: var(--space-lg);
}

.page-title {
  font-size: var(--font-size-2xl);
  font-weight: 600;
  letter-spacing: -0.5px;
  color: var(--color-text-primary);
  margin: 0;
}

.card-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
  gap: var(--space-lg);
}

.stat-card {
  background: var(--color-bg-card);
  border: 1px solid var(--color-border-light);
  border-radius: var(--radius-lg);
  padding: var(--space-lg);
  box-shadow: var(--shadow-sm);
  transition: box-shadow var(--transition-normal);
}
.stat-card:hover {
  box-shadow: var(--shadow-md);
}

.section-card {
  background: var(--color-bg-card);
  border: 1px solid var(--color-border-light);
  border-radius: var(--radius-lg);
  padding: var(--space-lg);
  box-shadow: var(--shadow-sm);
  margin-bottom: var(--space-lg);
}

.section-title {
  display: flex;
  align-items: center;
  gap: var(--space-sm);
  font-size: var(--font-size-lg);
  font-weight: 600;
  color: var(--color-text-primary);
  margin: 0 0 var(--space-md);
}
.section-title::before {
  content: '';
  width: 3px;
  height: 16px;
  background: var(--color-primary);
  border-radius: 2px;
}

/* 自定义滚动条 */
::-webkit-scrollbar {
  width: 6px;
  height: 6px;
}
::-webkit-scrollbar-thumb {
  background: var(--color-text-placeholder);
  border-radius: 3px;
}
::-webkit-scrollbar-track {
  background: transparent;
}
```

- [ ] **Step 4: 更新 main.ts**

编辑 `frontend/src/main.ts` 为：

```ts
import { createApp } from 'vue'
import { createPinia } from 'pinia'
import ElementPlus from 'element-plus'
import zhCn from 'element-plus/es/locale/lang/zh-cn'
import * as ElementPlusIconsVue from '@element-plus/icons-vue'
import 'element-plus/dist/index.css'

import App from './App.vue'
import router from './router'
import './styles/theme.css'

const app = createApp(App)
app.use(createPinia())
app.use(router)
app.use(ElementPlus, { locale: zhCn })
for (const [key, component] of Object.entries(ElementPlusIconsVue)) {
  app.component(key, component)
}
app.mount('#app')
```

- [ ] **Step 5: 验证**

Run: `cd frontend && npm run typecheck`
Expected: 零错误。

- [ ] **Step 6: Commit**

```bash
git add frontend/package.json frontend/package-lock.json frontend/src/styles/theme.css frontend/src/main.ts
git commit -m "feat: 引入参考项目设计系统 theme.css（Arco 蓝）+ 全局注册图标"
git push
```

---

### Task 2: AppLayout 中央布局 + 路由重构 + 视图骨架迁移

**Files:**
- Create: `frontend/src/components/AppLayout.vue`
- Modify: `frontend/src/router/index.ts`
- Modify: `frontend/src/views/DashboardView.vue`, `AnalysisView.vue`, `QualityView.vue`, `ScanView.vue`, `UsageView.vue`, `SettingsView.vue`, `WorkspaceView.vue`（删除各自 `el-container/el-aside/el-header` 布局骨架，只留内容区）
- 不改：`LoginView.vue` / `RegisterView.vue`（独立于布局）

**Interfaces:**
- Consumes: `useAuthStore`（`user/displayName`、`fetchMe`、`logout`）、`useProjectsStore`（`projects`、`fetchList`）
- Produces: 全局壳 `AppLayout`；路由下所有子路由在 `route.meta.title` 上设页面名（供面包屑与 document.title）；`route.params.id` 存在时侧栏出现「当前项目」分组。

**布局结构（参考 AppLayout.vue）：** `display:flex; min-height:100vh`。侧栏 `position:fixed; width:220px`（折叠 64px，`transition: width var(--transition-normal)`），`background: var(--color-bg-card)`，`border-right:1px solid var(--color-border-light)`。顶栏 `position:sticky; top:0; height:56px; background:var(--color-bg-card); border-bottom:1px solid var(--color-border-light); z-index:90; padding:0 var(--space-lg)`。内容 `flex:1; overflow-y:auto` 包 `<router-view>`（page-fade out-in 过渡）。

**AppLayout.vue 完整代码：**

```vue
<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { useProjectsStore } from '@/stores/projects'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const projectsStore = useProjectsStore()

const collapsed = ref(false)
const displayName = computed(() => auth.user?.display_name || auth.user?.username || '')

const pid = computed(() => (route.params.id ? Number(route.params.id) : null))
const currentProject = computed(() =>
  pid.value != null ? projectsStore.projects.find((p) => p.id === pid.value) : null,
)

const mainNav = [
  { path: '/dashboard', label: '工作台', icon: 'HomeFilled' },
  { path: '/analysis', label: '拆文库', icon: 'Reading' },
  { path: '/quality', label: '审查 / 去味', icon: 'DocumentChecked' },
  { path: '/scan', label: '扫榜', icon: 'TrendCharts' },
  { path: '/usage', label: '用量', icon: 'PieChart' },
  { path: '/settings', label: '设置', icon: 'Setting' },
]

const projectNav = [
  { suffix: '', label: '项目详情' },
  { suffix: '/review', label: '大纲审核' },
  { suffix: '/console', label: '创作控制台' },
]

const projectBase = computed(() => (pid.value != null ? `/projects/${pid.value}` : ''))
const currentNav = computed(() =>
  pid.value != null
    ? projectNav.map((n) => ({ ...n, path: `${projectBase.value}${n.suffix}` }))
    : [],
)

function onLogout() {
  auth.logout()
  router.push('/login')
}

onMounted(async () => {
  if (!auth.user) await auth.fetchMe()
  if (projectsStore.projects.length === 0 && !projectsStore.loading) await projectsStore.fetchList()
})
</script>

<template>
  <div class="app-layout">
    <aside class="app-sidebar" :class="{ collapsed }">
      <div class="sidebar-logo">
        <div class="logo-icon">
          <el-icon :size="18"><EditPen /></el-icon>
        </div>
        <span v-if="!collapsed" class="logo-text">Novel Agents</span>
      </div>

      <el-menu :default-active="$route.path" router class="sidebar-menu" :collapse="collapsed">
        <el-menu-item v-for="n in mainNav" :key="n.path" :index="n.path">
          <el-icon><component :is="n.icon" /></el-icon>
          <template #title>{{ n.label }}</template>
        </el-menu-item>

        <el-menu-item-group v-if="currentNav.length" class="project-group">
          <template #title>
            <span class="group-title">当前项目 · {{ currentProject?.title ?? '' }}</span>
          </template>
          <el-menu-item v-for="n in currentNav" :key="n.path" :index="n.path">
            <template #title>{{ n.label }}</template>
          </el-menu-item>
        </el-menu-item-group>
      </el-menu>

      <div class="sidebar-footer">
        <el-button text @click="collapsed = !collapsed">
          <el-icon><component :is="collapsed ? 'Expand' : 'Fold'" /></el-icon>
        </el-button>
      </div>
    </aside>

    <div class="app-main">
      <header class="app-topbar">
        <el-breadcrumb separator="/">
          <el-breadcrumb-item :to="{ path: '/dashboard' }">首页</el-breadcrumb-item>
          <el-breadcrumb-item>{{ route.meta.title ?? '' }}</el-breadcrumb-item>
        </el-breadcrumb>
        <el-dropdown trigger="click" @command="(cmd: string) => cmd === 'logout' && onLogout()">
          <span class="user-chip">
            <el-avatar :size="32" class="user-avatar">{{ displayName[0]?.toUpperCase() || 'U' }}</el-avatar>
            <span class="user-name">{{ displayName }}</span>
            <el-icon class="user-caret"><ArrowDown /></el-icon>
          </span>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item command="logout">退出登录</el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
      </header>

      <div class="app-content">
        <router-view v-slot="{ Component }">
          <transition name="page-fade" mode="out-in">
            <component :is="Component" />
          </transition>
        </router-view>
      </div>
    </div>
  </div>
</template>

<style scoped>
.app-layout {
  display: flex;
  min-height: 100vh;
  background: var(--color-bg-page);
}
.app-sidebar {
  position: fixed;
  top: 0;
  left: 0;
  bottom: 0;
  width: var(--sidebar-width);
  display: flex;
  flex-direction: column;
  background: var(--color-bg-card);
  border-right: 1px solid var(--color-border-light);
  z-index: 100;
  transition: width var(--transition-normal);
}
.app-sidebar.collapsed {
  width: var(--sidebar-collapsed-width);
}
.sidebar-logo {
  height: 56px;
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 0 var(--space-md);
  border-bottom: 1px solid var(--color-border-light);
  flex-shrink: 0;
  overflow: hidden;
}
.logo-icon {
  width: 36px;
  height: 36px;
  border-radius: var(--radius-md);
  background: linear-gradient(135deg, var(--color-primary), var(--color-primary-light));
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
.logo-text {
  font-size: var(--font-size-lg);
  font-weight: 600;
  color: var(--color-text-primary);
  white-space: nowrap;
}
.sidebar-menu {
  flex: 1;
  border-right: none;
  padding: var(--space-xs) 0;
  overflow-y: auto;
}
.sidebar-menu :deep(.el-menu-item) {
  height: 44px;
  margin: 2px 8px;
  border-radius: var(--radius-md);
}
.sidebar-menu :deep(.el-menu-item.is-active) {
  background: var(--color-primary-lighter) !important;
  color: var(--color-primary) !important;
  font-weight: 500;
}
.group-title {
  font-size: var(--font-size-xs);
  text-transform: uppercase;
  letter-spacing: 1px;
  color: var(--color-text-placeholder);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.sidebar-footer {
  display: flex;
  justify-content: center;
  padding: var(--space-sm);
  border-top: 1px solid var(--color-border-light);
  flex-shrink: 0;
}
.app-main {
  flex: 1;
  margin-left: var(--sidebar-width);
  min-width: 0;
  transition: margin-left var(--transition-normal);
}
.app-sidebar.collapsed + .app-main {
  margin-left: var(--sidebar-collapsed-width);
}
.app-topbar {
  position: sticky;
  top: 0;
  height: var(--topbar-height);
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 var(--space-lg);
  background: var(--color-bg-card);
  border-bottom: 1px solid var(--color-border-light);
  z-index: 90;
}
.user-chip {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  cursor: pointer;
  padding: 4px 8px;
  border-radius: var(--radius-md);
}
.user-chip:hover {
  background: var(--color-bg-page);
}
.user-avatar {
  background: var(--color-primary);
  color: #fff;
}
.user-name {
  font-size: var(--font-size-md);
  color: var(--color-text-regular);
}
.user-caret {
  color: var(--color-text-secondary);
}
.app-content {
  padding: var(--space-md);
}
.page-fade-enter-active,
.page-fade-leave-active {
  transition: opacity 0.2s ease;
}
.page-fade-enter-from,
.page-fade-leave-to {
  opacity: 0;
}
</style>
```

> 注意：`.app-content` 内层视图再用 `.page-container` 约束宽度。折叠时菜单图标居中即可，标题用 `#title` 插槽隐藏。

- [ ] **Step 1: 创建 AppLayout.vue**

创建 `frontend/src/components/AppLayout.vue`（内容见上）。若 typecheck 报 `EditPen/ArrowDown` 等图标未注册，确认 Task 1 已全局注册（未注册的改由 `component :is` 字符串引用也可）。

- [ ] **Step 2: 重构路由**

改写 `frontend/src/router/index.ts`：

```ts
import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import AppLayout from '@/components/AppLayout.vue'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', redirect: '/dashboard' },
    {
      path: '/login',
      name: 'login',
      component: () => import('@/views/LoginView.vue'),
      meta: { guest: true, title: '登录' },
    },
    {
      path: '/register',
      name: 'register',
      component: () => import('@/views/RegisterView.vue'),
      meta: { guest: true, title: '注册' },
    },
    {
      path: '/',
      component: AppLayout,
      children: [
        {
          path: 'dashboard',
          name: 'dashboard',
          component: () => import('@/views/DashboardView.vue'),
          meta: { requiresAuth: true, title: '工作台' },
        },
        // NOTE 本任务四个新页面文件尚未创建，路由项「注释」保持 typecheck 通过；
        // 对应 Task 6/7/8/9 落地时依次取消注释并把 projects/:id 切到 NovelDetailView。
        // {
        //   path: 'projects/:id',
        //   name: 'novel-detail',
        //   component: () => import('@/views/NovelDetailView.vue'),
        //   meta: { requiresAuth: true, title: '项目详情' },
        // },
        // {
        //   path: 'projects/:id/review',
        //   name: 'outline-review',
        //   component: () => import('@/views/OutlineReviewView.vue'),
        //   meta: { requiresAuth: true, title: '大纲审核' },
        // },
        // {
        //   path: 'projects/:id/console',
        //   name: 'console',
        //   component: () => import('@/views/ConsoleView.vue'),
        //   meta: { requiresAuth: true, title: '创作控制台' },
        // },
        // {
        //   path: 'projects/:id/chapters/:chapterNo',
        //   name: 'chapter-view',
        //   component: () => import('@/views/ChapterView.vue'),
        //   meta: { requiresAuth: true, title: '章节阅读' },
        // },
        {
          // 本任务 projects/:id 仍指向旧工作台；Task 6 起切到 NovelDetailView 并把旧页移入本兜底路由
          path: 'projects/:id',
          name: 'workspace',
          component: () => import('@/views/WorkspaceView.vue'),
          meta: { requiresAuth: true, title: '写作工作台' },
        },
        {
          path: 'analysis',
          name: 'analysis',
          component: () => import('@/views/AnalysisView.vue'),
          meta: { requiresAuth: true, title: '拆文库' },
        },
        {
          path: 'quality',
          name: 'quality',
          component: () => import('@/views/QualityView.vue'),
          meta: { requiresAuth: true, title: '审查去味' },
        },
        {
          path: 'scan',
          name: 'scan',
          component: () => import('@/views/ScanView.vue'),
          meta: { requiresAuth: true, title: '扫榜' },
        },
        {
          path: 'usage',
          name: 'usage',
          component: () => import('@/views/UsageView.vue'),
          meta: { requiresAuth: true, title: '用量' },
        },
        {
          path: 'settings',
          name: 'settings',
          component: () => import('@/views/SettingsView.vue'),
          meta: { requiresAuth: true, title: '设置' },
        },
      ],
    },
  ],
})

router.beforeEach((to) => {
  const auth = useAuthStore()
  if (to.meta.requiresAuth && !auth.isAuthenticated) {
    return { name: 'login', query: { redirect: to.fullPath } }
  }
  if (to.meta.guest && auth.isAuthenticated) {
    return { name: 'dashboard' }
  }
})

router.afterEach((to) => {
  document.title = to.meta.title ? `${to.meta.title} · Novel Agents` : 'Novel Agents'
})

export default router
```

> `projects/:id` 本任务仍指向旧 WorkspaceView（上面的注释块是给 Task 6-9 的占位）。Task 6 起：把 `projects/:id` 切到 NovelDetailView、新增 `projects/:id/workspace`（name `workspace-legacy`）兜底旧页，并逐步打开四个注释路由。本任务只需保证 `projects/:id` → WorkspaceView 可用、typecheck 通过。

- [ ] **Step 3: 视图骨架迁移（关键折中）**

`AppLayout` 与旧视图自带侧栏叠加会双栏错乱。因此本任务**同时**把 7 个现有业务视图（Dashboard/Analysis/Quality/Scan/Usage/Settings/Workspace）从「自带 `el-container>el-aside+el-container>el-header+el-main`」改为「纯内容区」：

对每个视图，删掉整个外层布局骨架（`<el-container class="layout">…<el-aside>…</el-aside><el-container><el-header>…</el-header>` 及其对应样式 `.layout/.aside/.aside-brand/.aside-menu/.aside-placeholder/.header/.header-title/.user-chip/.user-name/.main`），保留原 `el-main` 内部的内容，改用 `page-container` 包裹。同时删掉各视图 script 里不再使用的 `onLogout`、`displayName`（顶栏已由 AppLayout 提供）。

具体到每个视图的最小改动：

- **DashboardView.vue**：删除整个侧栏与顶栏模板 + 相关样式与 `onLogout/displayName`；保留欢迎卡、项目网格、新建项目对话框。`<template>` 顶层改为 `<div class="page-container">…</div>`。
- **AnalysisView.vue / ScanView.vue / UsageView.vue / SettingsView.vue / QualityView.vue**：同法——删布局骨架与 `onLogout/displayName`，`el-main` 内容改包 `.page-container`。
- **WorkspaceView.vue**：删布局骨架；其内部 `el-header` 的操作区（开书/写下一章按钮、用户下拉）中「用户下拉」删除（AppLayout 顶栏已有），**操作按钮保留在页面顶部**；`aside` 的「章节/大纲」页签区改为页面内容。本任务只做「骨架外移 + 内容可读」，深度重绘交给 Task 6-9。

> 折中说明：本任务让 app 在 AppLayout 下仍能渲染全部现有页面（内容可能未完全套用新卡片样式，视觉粗糙属预期，Task 3-12 逐个精修）。`onLogout/displayName` 删除后若有 `noUnusedLocals` 报错，一并清理未使用 import。

- [ ] **Step 4: 验证**

Run: `cd frontend && npm run typecheck`
Expected: 零错误。若 `WorkspaceView` 或其它视图因删了变量还有未用 import，清理之。

Run: `npm run dev`，浏览器手动访问 `/login`（独立页）与 `/dashboard`（AppLayout 壳 + 内容渲染）确认无双栏错乱、导航可切换。
Expected: 登录页正常；登录后工作台显示左侧单侧栏 + 顶栏 + 内容。

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/AppLayout.vue frontend/src/router/index.ts frontend/src/views/
git commit -m "feat: AppLayout 中央布局 + 路由重构 + 视图骨架迁移"
git push
```

---

### Task 3: 登录/注册页 → 参考式左右分栏

**Files:**
- Modify: `frontend/src/views/LoginView.vue`, `frontend/src/views/RegisterView.vue`
- Modify: `frontend/src/style.css`（清理不再需要的 `.page-centered`）

**Interfaces:**
- Consumes: `useAuthStore`（不变）
- Produces: 品牌分栏登录/注册页（左渐变品牌面板 + 右表单卡片）。

- [ ] **Step 1: 重写 LoginView.vue**

`<script setup>` 逻辑与现有 `LoginView` 完全一致（表单 rules、`auth.login`、redirect），只改 `<template>` 与 `<style>`。新结构：

```vue
<template>
  <div class="auth-split">
    <!-- 左：品牌面板 -->
    <div class="auth-brand">
      <div class="brand-decor d1" />
      <div class="brand-decor d2" />
      <div class="brand-decor d3" />
      <div class="brand-logo">
        <el-icon :size="28"><EditPen /></el-icon>
      </div>
      <h1 class="brand-title">Novel Agents</h1>
      <p class="brand-slogan">AI 多智能体协同小说创作系统</p>
      <ul class="brand-features">
        <li>多智能体编排：写作 · 审查 · 去味 · 拆文 · 扫榜</li>
        <li>三阶段开书流水线，层层约束剧情连贯</li>
        <li>多模型三档，国产大模型一键接入</li>
      </ul>
    </div>
    <!-- 右：表单 -->
    <div class="auth-panel">
      <div class="auth-card">
        <h2 class="auth-card-title">登录</h2>
        <el-form ref="formRef" :model="form" :rules="rules" size="large" label-position="top" @submit.prevent="onSubmit">
          <el-form-item label="用户名" prop="username">
            <el-input v-model="form.username" placeholder="请输入用户名" autocomplete="username" clearable />
          </el-form-item>
          <el-form-item label="密码" prop="password">
            <el-input v-model="form.password" type="password" placeholder="请输入密码" autocomplete="current-password" show-password @keyup.enter="onSubmit" />
          </el-form-item>
          <el-button type="primary" size="large" class="submit-btn" :loading="loading" @click="onSubmit">登 录</el-button>
        </el-form>
        <div class="auth-footer">还没有账号？<router-link to="/register">立即注册</router-link></div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.auth-split { display: flex; min-height: 100vh; }
.auth-brand {
  flex: 1;
  position: relative;
  overflow: hidden;
  display: flex;
  flex-direction: column;
  justify-content: center;
  padding: 0 64px;
  color: #fff;
  background: linear-gradient(135deg, #0e42d2 0%, #165dff 50%, #4080ff 100%);
}
.brand-decor {
  position: absolute;
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.04);
}
.brand-decor.d1 { width: 360px; height: 360px; top: -80px; right: -60px; }
.brand-decor.d2 { width: 240px; height: 240px; bottom: -60px; left: 120px; }
.brand-decor.d3 { width: 160px; height: 160px; bottom: 40px; right: 80px; background: rgba(255,255,255,0.05); }
.brand-logo {
  width: 56px; height: 56px;
  border-radius: var(--radius-lg);
  background: rgba(255, 255, 255, 0.2);
  backdrop-filter: blur(10px);
  display: flex; align-items: center; justify-content: center;
  margin-bottom: 24px;
}
.brand-title { font-size: var(--font-size-3xl); margin: 0 0 8px; letter-spacing: 1px; }
.brand-slogan { font-size: var(--font-size-lg); opacity: 0.85; margin: 0 0 32px; }
.brand-features { list-style: none; padding: 0; margin: 0; display: flex; flex-direction: column; gap: 12px; }
.brand-features li {
  background: rgba(255, 255, 255, 0.1);
  border-radius: var(--radius-md);
  padding: 12px 16px;
  backdrop-filter: blur(5px);
  font-size: var(--font-size-sm);
  width: fit-content;
}
.auth-panel {
  width: 480px;
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--color-bg-card);
  padding: var(--space-lg);
}
.auth-card { width: 100%; max-width: 380px; }
.auth-card-title { font-size: var(--font-size-2xl); margin: 0 0 24px; color: var(--color-text-primary); }
.submit-btn { width: 100%; margin-top: 8px; }
.auth-footer { margin-top: 16px; font-size: var(--font-size-sm); color: var(--color-text-secondary); text-align: center; }
.auth-footer a { color: var(--color-primary); text-decoration: none; }
</style>
```

- [ ] **Step 2: 重写 RegisterView.vue**

同构。`<template>` 用同样的 `.auth-split` 结构，右侧表单保留现有全部字段（username/password/confirm/email/display_name）与 rules；按钮文案「注 册」；底部链接指向 `/login`。

- [ ] **Step 3: 清理 style.css**

`frontend/src/style.css` 删除 `.page-centered`（不再使用）与 body 背景色（由 theme.css 接管）。保留 `html,body,#app` 高度与字体声明不冲突部分。

- [ ] **Step 4: 验证**

Run: `cd frontend && npm run typecheck`
Expected: 零错误。`npm run dev` 手动访问 `/login`、`/register` 确认左右分栏、表单可提交。

- [ ] **Step 5: Commit**

```bash
git add frontend/src/views/LoginView.vue frontend/src/views/RegisterView.vue frontend/src/style.css
git commit -m "feat: 登录/注册页改参考式左右分栏品牌页"
git push
```

---

### Task 4: 工作台 → 参考 Home 风（统计卡 + 项目卡片网格）

**Files:**
- Modify: `frontend/src/views/DashboardView.vue`

**Interfaces:**
- Consumes: `useProjectsStore`（`projects/loading/activeProject/fetchList/create/activate`）、`useAuthStore`
- Produces: 参考 Home 风工作台。统计卡：总项目数、创作中（status 含 active/inactive 中活动书）、已完成、总章节（汇总 `ws.chapters` 不含——项目卡片各自显示章数则从 `useWritingStore` 懒取；为控制范围，统计卡只做：总项目 / 活跃书 / 未激活 / 新建入口）。

- [ ] **Step 1: 重绘 DashboardView.vue**

保留现有 script 逻辑（`onCreate`、`onActivate`、dialog、`fetchList`），删除 `displayName/onLogout`（AppLayout 提供）。模板改为：

```vue
<template>
  <div class="page-container">
    <div class="page-header">
      <h1 class="page-title">工作台</h1>
      <el-button type="primary" @click="showCreate = true">＋ 新建项目</el-button>
    </div>

    <div class="stats-row">
      <div class="stat-card"><div class="stat-value">{{ projectsStore.projects.length }}</div><div class="stat-label">总项目</div></div>
      <div class="stat-card"><div class="stat-value warn">{{ activeCount }}</div><div class="stat-label">活跃书</div></div>
      <div class="stat-card"><div class="stat-value">{{ inactiveCount }}</div><div class="stat-label">未激活</div></div>
      <div class="stat-card"><div class="stat-value success">{{ totalChapters }}</div><div class="stat-label">已提交章节</div></div>
    </div>

    <div class="card-grid" v-loading="projectsStore.loading">
      <div v-for="p in projectsStore.projects" :key="p.id" class="novel-card" @click="router.push(`/projects/${p.id}`)">
        <div class="novel-card-head">
          <h4 class="novel-card-title">{{ p.title }}</h4>
          <el-tag :type="p.status === 'active' ? 'success' : 'info'" size="small">{{ p.status === 'active' ? '活跃' : '未激活' }}</el-tag>
        </div>
        <div class="novel-card-meta">
          <span>{{ p.genre || '未设题材' }}</span>
          <span>·</span>
          <span>{{ p.platform || '未设平台' }}</span>
          <span>·</span>
          <span>slug: {{ p.slug }}</span>
        </div>
        <div class="novel-card-foot">
          <span class="novel-card-date">{{ fmtDate(p.created_at) }}</span>
          <span class="novel-card-enter">进入项目 →</span>
        </div>
      </div>
    </div>

    <el-empty v-if="!projectsStore.loading && projectsStore.projects.length === 0" description="还没有项目，点击右上角「新建项目」开始你的第一本书" />
  </div>
  <!-- 新建项目 el-dialog 保留 -->
</template>
```

script 增补：

```ts
import { writingApi } from '@/api/writing'
const activeCount = computed(() => projectsStore.projects.filter((p) => p.status === 'active').length)
const inactiveCount = computed(() => projectsStore.projects.filter((p) => p.status !== 'active').length)
const totalChapters = ref(0)
async function refreshTotalChapters() {
  let sum = 0
  for (const p of projectsStore.projects) {
    const chapters = await writingApi.listChapters(p.id)
    sum += chapters.filter((c) => c.status === 'committed').length
  }
  totalChapters.value = sum
}
// onMounted 里 fetchList 后调用 refreshTotalChapters()
function fmtDate(s: string) {
  return new Date(s).toLocaleDateString('zh-CN')
}
```

（`writingApi` 从 `@/api/writing` import。）

样式：`.stats-row { display:grid; grid-template-columns:repeat(auto-fit,minmax(180px,1fr)); gap:var(--space-lg); margin-bottom:var(--space-lg); }`；`.stat-value { font-size:var(--font-size-2xl); font-weight:600; color:var(--color-text-primary); }` `.stat-value.warn{color:var(--color-warning)}` `.stat-value.success{color:var(--color-success)}`；`.stat-label { font-size:var(--font-size-xs); color:var(--color-text-secondary); margin-top:4px; }`；`.novel-card` 白卡 radius-lg padding-lg border-light shadow-sm，hover `transform:translateY(-2px); box-shadow:var(--shadow-lg); border-color:var(--color-primary-lighter); transition:all var(--transition-normal)`；`cursor:pointer`；`head/foot` 用 `border-top:1px solid var(--color-border-light)` 分隔。

- [ ] **Step 2: 验证**

Run: `cd frontend && npm run typecheck` → 零错误。`npm run dev` 访问 `/dashboard` 核对统计卡与项目卡片。

- [ ] **Step 3: Commit**

```bash
git add frontend/src/views/DashboardView.vue
git commit -m "feat: 工作台改参考 Home 风（统计卡 + 项目卡片网格）"
git push
```

---

### Task 5: 组件重绘（PipelineBar / AgentActivityPanel / DraftConfirmDialog）

**Files:**
- Modify: `frontend/src/components/PipelineBar.vue`, `AgentActivityPanel.vue`, `DraftConfirmDialog.vue`

**Interfaces:**
- Consumes: `@/types/writing`（`PipelineStep/StageStatus/AgentEvent`，不变）
- Produces: 参考风组件，供 Task 7/8 的新页面使用。**保持 props/emits 签名不变**。

- [ ] **Step 1: 重绘 PipelineBar.vue → Agent 流水线节点风**

保留现有 props（`stages/status/title/clickable`）与 emit（`retry`）、点击已点亮阶段重跑逻辑。样式改为参考「agent-pipeline」：每个阶段为「圆形图标 + 下方标签」，节点间 2px 连线随 done 变绿；active(`running`) = `background:var(--color-primary-lighter); border-color:var(--color-primary); color:var(--color-primary); box-shadow:0 0 0 4px rgba(22,93,255,0.1)`；done = 主色圆底白字或绿；waiting = 橙色 ✋；error = danger。`.step` 圆形 44px，`border:2px solid var(--color-border)`；`.step-line { width:28px; height:2px; background:var(--color-border-light); } .step-line.active{background:var(--color-success)}`。顶部一行 flex 排列，标题放左侧。保留 `.step-tag`（待确认/失败小标签）与 `.spin` 动画。

- [ ] **Step 2: 重绘 AgentActivityPanel.vue → 深色终端**

保留事件类型渲染（stage/tool/status/stage_draft/checkpoint/done/error 分支）。样式改为深色终端：`.agent-panel { background:#1a1a2e; border-radius:var(--radius-md); color:#e5e6eb; font-family:var(--font-mono); font-size:var(--font-size-xs); }`；`.panel-title` 顶栏（border-bottom 1px rgba(255,255,255,0.1)）；`.event-row` 行 padding、时间戳灰 `#6b7280`；`tool 调用` 用 `.badge` 彩色小胶囊；流式正文行 `.event-token` 浅色；`.cursor-blink` 闪烁光标 `|`（`@keyframes blink { 50% { opacity: 0 } }` 0.8s step-end）。滚动条样式沿用全局。

- [ ] **Step 3: 重绘 DraftConfirmDialog.vue**

保留 props（`visible/stage/content`）与 emits（`confirm/regenerate/cancel`）。样式：`el-dialog` 宽 640px；`pre.draft-body` 放 `content`，`background:var(--color-bg-page); border-radius:var(--radius-md); padding:var(--space-md); max-height:60vh; overflow:auto; white-space:pre-wrap`；标题显示阶段标签（世界观/设定/大纲/细纲）。按钮：确认入库(primary)/重新生成(plain)/取消。

- [ ] **Step 4: 验证**

Run: `cd frontend && npm run typecheck` → 零错误。`npm run dev` 访问旧 `/projects/:id/workspace` 触发开书写章，目视三组件新样式与交互。

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/
git commit -m "feat: 组件重绘（Agent 流水线 / 深色终端 / 草稿确认弹窗）"
git push
```

---

### Task 6: 项目详情页 NovelDetailView（`/projects/:id`）

**Files:**
- Create: `frontend/src/views/NovelDetailView.vue`
- Modify: `frontend/src/router/index.ts`（打开 `projects/:id` → NovelDetailView；把旧 WorkspaceView 路由改为 `/projects/:id/workspace` 兜底，保留 `workspace-legacy`）

**Interfaces:**
- Consumes: `useProjectsStore`（`projects/fetchList`）、`useWritingStore`（`load/tracking/chapters/current`）、`useOutlineStore`（`load/outline/hasOutline`）
- Produces: 项目详情页。路由参数 `route.params.id`。

- [ ] **Step 1: 编写 NovelDetailView.vue**

```vue
<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useProjectsStore } from '@/stores/projects'
import { useWritingStore } from '@/stores/writing'
import { useOutlineStore } from '@/stores/outline'

const route = useRoute()
const router = useRouter()
const projectsStore = useProjectsStore()
const ws = useWritingStore()
const os = useOutlineStore()

const pid = computed(() => Number(route.params.id))
const project = computed(() => projectsStore.projects.find((p) => p.id === pid.value))

const outline = computed(() => os.outline)
const totalChapters = computed(
  () => outline.value?.volumes.reduce((n, v) => n + v.chapters.length, 0) ?? 0,
)
const committed = computed(() => ws.tracking?.last_committed_chapter ?? 0)
const progressPct = computed(() => {
  if (!totalChapters.value) return 0
  return Math.min(100, Math.round((committed.value / totalChapters.value) * 100))
})

function fmtDate(s: string | null) {
  return s ? new Date(s).toLocaleString('zh-CN') : '—'
}

function formatPoint(p: unknown): string {
  if (typeof p === 'string') return p
  if (p && typeof p === 'object') return (p as Record<string, unknown>).content ? String((p as Record<string, unknown>).content) : JSON.stringify(p)
  return String(p)
}

onMounted(async () => {
  await projectsStore.fetchList()
  await Promise.all([ws.load(pid.value), os.load(pid.value)])
})
</script>
```

模板结构：

```vue
<template>
  <div class="page-container">
    <div class="page-header">
      <h1 class="page-title">{{ project?.title ?? '项目详情' }}</h1>
      <div class="header-actions">
        <el-button plain @click="router.push(`/projects/${pid}/review`)">大纲审核</el-button>
        <el-button type="primary" @click="router.push(`/projects/${pid}/console`)">进入创作台</el-button>
      </div>
    </div>

    <div class="detail-grid">
      <!-- 主列 -->
      <div class="main-col">
        <div class="section-card">
          <h3 class="section-title">项目信息</h3>
          <el-descriptions :column="3" border>
            <el-descriptions-item label="书名">{{ project?.title }}</el-descriptions-item>
            <el-descriptions-item label="标识 slug">{{ project?.slug }}</el-descriptions-item>
            <el-descriptions-item label="状态">
              <el-tag :type="project?.status === 'active' ? 'success' : 'info'" size="small">{{ project?.status === 'active' ? '活跃' : '未激活' }}</el-tag>
            </el-descriptions-item>
            <el-descriptions-item label="题材">{{ project?.genre || '未设' }}</el-descriptions-item>
            <el-descriptions-item label="平台">{{ project?.platform || '未设' }}</el-descriptions-item>
            <el-descriptions-item label="创建时间">{{ fmtDate(project?.created_at ?? null) }}</el-descriptions-item>
          </el-descriptions>
        </div>

        <div class="section-card">
          <h3 class="section-title">分卷大纲</h3>
          <template v-if="os.hasOutline && outline">
            <div v-for="vol in outline.volumes" :key="vol.no" class="volume-block">
              <h4 class="volume-title">第 {{ vol.no }} 卷 · {{ vol.title }}</h4>
              <p v-if="vol.synopsis" class="volume-synopsis">{{ vol.synopsis }}</p>
              <div class="outline-chapter-row" v-for="ch in vol.chapters" :key="ch.chapter_no">
                <span class="oc-no">第 {{ ch.chapter_no }} 章</span>
                <span class="oc-title">{{ ch.title }}</span>
              </div>
            </div>
          </template>
          <el-empty v-else description="尚未开书，先去「大纲审核」页生成大纲" />
        </div>
      </div>

      <!-- 侧列 -->
      <aside class="side-col">
        <div class="section-card">
          <h3 class="section-title">创作进度</h3>
          <el-progress type="dashboard" :percentage="progressPct" :width="160" :color="[
            { color: '#165DFF', percentage: 50 },
            { color: '#FF7D00', percentage: 80 },
            { color: '#00B42A', percentage: 100 },
          ]" />
          <div class="progress-stats">
            <div class="kv"><span>已提交章节</span><b>{{ committed }}</b></div>
            <div class="kv"><span>大纲总章数</span><b>{{ totalChapters }}</b></div>
          </div>
        </div>
      </aside>
    </div>
  </div>
</template>
```

样式：`.detail-grid { display:grid; grid-template-columns:1fr 300px; gap:var(--space-lg); align-items:start; }`；`.volume-block { border:1px solid var(--color-border-light); border-radius:var(--radius-md); padding:var(--space-md); margin-bottom:var(--space-md); }`；`.volume-title { color:var(--color-primary); font-size:var(--font-size-md); margin:0 0 8px; }`；`.outline-chapter-row { display:flex; gap:8px; padding:4px 0; font-size:var(--font-size-sm); color:var(--color-text-regular); }`；`.progress-stats .kv { display:flex; justify-content:space-between; padding:8px 0; border-bottom:1px solid var(--color-border-light); font-size:var(--font-size-sm); }`。

- [ ] **Step 2: 更新路由**

`router/index.ts`：把 `projects/:id` 的 component 改为 `@/views/NovelDetailView.vue`（打开该路由）；新增 `projects/:id/workspace` → WorkspaceView（保留旧页兜底，name `workspace-legacy`）。

- [ ] **Step 3: 验证**

Run: `cd frontend && npm run typecheck` → 零错误。`npm run dev`：访问 `/projects/{id}` 核对信息/大纲/进度环；访问 `/projects/{id}/workspace` 确认旧工作台仍可用（写作功能未回归）。

- [ ] **Step 4: Commit**

```bash
git add frontend/src/views/NovelDetailView.vue frontend/src/router/index.ts
git commit -m "feat: 项目详情页（信息/分卷大纲/进度环），旧工作台移入 /workspace 兜底"
git push
```

---

### Task 7: 大纲审核页 OutlineReviewView（`/projects/:id/review`）

**Files:**
- Create: `frontend/src/views/OutlineReviewView.vue`
- Modify: `frontend/src/router/index.ts`（打开 `projects/:id/review` 路由）

**Interfaces:**
- Consumes: `useOutlineStore`（`openBook/retryStage/confirmDraft/regenerateDraft/cancel/running/hasOutline/outline/events/stageDrafts/currentStage/mode/stageStatus/waiting/waitingDraft/task`）、`useProjectsStore`；组件 `PipelineBar`（OPEN_BOOK_PIPELINE, clickable）、`AgentActivityPanel`、`DraftConfirmDialog`
- Produces: 大纲审核页，承载从旧工作台迁来的完整开书流水线。**全部逻辑从 WorkspaceView 复制**（`onOpenBook/onRetryStage/onConfirmDraft/onRegenerateDraft/currentStageLabel/currentStageText/obScenario`）。

- [ ] **Step 1: 编写 OutlineReviewView.vue**

script 直接复用 `WorkspaceView.vue` 中开书相关全部逻辑（`onOpenBook`、`onRetryStage`、`onConfirmDraft`、`onRegenerateDraft`、`currentStageLabel/Text`、`obScenario`、`os.mode` 切换、onMounted `os.load`）。模板：

```vue
<template>
  <div class="page-container">
    <div class="page-header">
      <h1 class="page-title">大纲审核 · {{ project?.title ?? '' }}</h1>
      <div class="header-actions">
        <el-segmented v-model="os.mode" :disabled="os.running" :options="[
          { label: '自动入库', value: 'auto' },
          { label: '确认入库', value: 'confirm' },
        ]" />
        <el-popconfirm v-if="os.hasOutline && !os.running" title="重新开书会删除现有大纲并重新生成，确定继续？"
          confirm-button-text="重新开书" cancel-button-text="取消" @confirm="onOpenBook(true)">
          <template #reference><el-button plain>🔄 重新开书</el-button></template>
        </el-popconfirm>
        <el-button v-else-if="!os.running" type="primary" @click="onOpenBook(false)">📖 开始开书</el-button>
        <el-button v-else type="danger" plain @click="os.cancel()">取消开书</el-button>
      </div>
    </div>

    <div class="review-grid">
      <div class="main-col">
        <div class="section-card">
          <h3 class="section-title">开书流水线</h3>
          <PipelineBar :stages="OPEN_BOOK_PIPELINE" :status="os.stageStatus" clickable @retry="onRetryStage" />
          <div v-if="os.running && os.currentStage" class="draft-preview">
            <div class="draft-preview-head">
              <span>「{{ currentStageLabel }}」草稿 · 流式预览</span>
              <span class="draft-preview-wc">{{ currentStageText.length }} 字</span>
            </div>
            <pre class="draft-preview-body">{{ currentStageText }}</pre>
          </div>
          <AgentActivityPanel v-if="os.running" :events="os.events" />
        </div>

        <div class="section-card">
          <h3 class="section-title">三层大纲</h3>
          <template v-if="os.hasOutline && os.outline">
            <el-collapse v-for="vol in os.outline.volumes" :key="vol.no" class="vol-collapse">
              <el-collapse-item :title="`第${vol.no}卷 · ${vol.title}`" :name="vol.no">
                <div v-if="vol.synopsis" class="oc-synopsis">{{ vol.synopsis }}</div>
                <div v-for="ch in vol.chapters" :key="ch.chapter_no" class="oc-block">
                  <div class="oc-head">第{{ ch.chapter_no }}章 · {{ ch.title }}</div>
                  <div v-if="ch.beats.summary" class="oc-summary">{{ ch.beats.summary }}</div>
                  <div v-if="ch.beats.target_wordcount" class="oc-wc">目标 {{ ch.beats.target_wordcount }} 字</div>
                  <ul v-if="ch.beats.points?.length" class="oc-points">
                    <li v-for="(p, i) in ch.beats.points" :key="i">{{ formatPoint(p) }}</li>
                  </ul>
                </div>
              </el-collapse-item>
            </el-collapse>
          </template>
          <el-empty v-else description="点击「开始开书」生成三层大纲" />
        </div>
      </div>
    </div>

    <DraftConfirmDialog :visible="os.waiting" :stage="os.waitingDraft?.stage ?? ''"
      :content="os.waitingDraft?.content ?? ''"
      @confirm="onConfirmDraft" @regenerate="onRegenerateDraft" @cancel="os.cancel()" />
  </div>
</template>
```

样式沿用旧工作台大纲部分的 `.draft-preview*`/`.vol-collapse/`.oc-*` 类，但适配浅色卡片背景（`--color-bg-page`）。`formatPoint` 从 WorkspaceView 复制。

- [ ] **Step 2: 更新路由**

`router/index.ts`：`projects/:id/review` → `OutlineReviewView.vue`（打开）。

- [ ] **Step 3: 验证**

Run: `cd frontend && npm run typecheck` → 零错误。`npm run dev` 访问 `/projects/{id}/review`：无大纲时点开书看三阶段流水线 + confirm 弹窗；有大纲时看三层大纲 + 点击阶段重跑。

- [ ] **Step 4: Commit**

```bash
git add frontend/src/views/OutlineReviewView.vue frontend/src/router/index.ts
git commit -m "feat: 大纲审核页（开书三阶段流水线 + 三层大纲）"
git push
```

---

### Task 8: 创作控制台 ConsoleView（`/projects/:id/console`）

**Files:**
- Create: `frontend/src/views/ConsoleView.vue`
- Modify: `frontend/src/router/index.ts`（打开 `projects/:id/console` 路由）

**Interfaces:**
- Consumes: `useWritingStore`（`chapters/current/currentText/currentWordcount/running/task/events/tracking/contextView/stageStatus/writeNext/cancel/load/reset/loadLastCommitted/afterDone/listen`）、`useProjectsStore`；组件 `PipelineBar`（WRITE_PIPELINE）、`AgentActivityPanel`
- Produces: 创作控制台，承载从旧工作台迁来的完整写作链路。**写作逻辑从 WorkspaceView 复制**（`onWriteNext/onCancel/onSelectChapter/loadChapter`）。

- [ ] **Step 1: 编写 ConsoleView.vue**

script 复制 WorkspaceView 写作部分逻辑（`ws.writeNext/load/writeNext/afterDone/listen` 经 store 内部调用，页面只调用 `ws.load(pid)` 后由 store 处理 SSE；`onWriteNext/onCancel/onSelectChapter/loadChapter`）。模板（grid `1fr 320px`）：

```vue
<template>
  <div class="page-container">
    <div class="page-header">
      <h1 class="page-title">创作控制台 · {{ project?.title ?? '' }}</h1>
      <div class="header-actions">
        <el-tag v-if="ws.running" type="warning" effect="dark">写作中{{ ws.task?.progress ? ` · ${ws.task.progress}` : '' }}</el-tag>
        <el-dropdown v-if="!ws.running" trigger="click">
          <el-button type="primary">✍️ 写下一章<el-icon class="el-icon--right"><ArrowDown /></el-icon></el-button>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item @click="onWriteNext('write_next')">写下一章</el-dropdown-item>
              <el-dropdown-item @click="onWriteNext('daily')">日更循环（连写至大纲末）</el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
        <el-button v-else type="danger" plain @click="onCancel">取消</el-button>
      </div>
    </div>

    <div class="console-grid">
      <div class="main-col">
        <div class="section-card">
          <h3 class="section-title">写作流水线</h3>
          <PipelineBar v-if="ws.running || ws.events.length > 0" :stages="WRITE_PIPELINE" :status="ws.stageStatus" title="写作" />
          <AgentActivityPanel v-if="ws.running || ws.events.length > 0" :events="ws.events" />
        </div>

        <div class="section-card editor-card">
          <div class="editor-head">
            <span class="editor-title">第 {{ ws.current?.chapter_no ?? '—' }} 章 · {{ ws.current?.title ?? '等待写作' }}</span>
            <span class="editor-wc">{{ ws.currentWordcount }} 字</span>
          </div>
          <el-input type="textarea" :model-value="ws.currentText" :readonly="ws.running"
            :autosize="{ minRows: 22, maxRows: 32 }" placeholder="点击「写下一章」，AI 会在这里流式输出正文…" resize="none" class="editor" />
        </div>
      </div>

      <aside class="side-col">
        <div class="section-card">
          <h3 class="section-title">章节列表</h3>
          <div class="chapter-list">
            <div v-for="c in ws.chapters" :key="c.chapter_no" class="chapter-item" @click="onSelectChapter(c.chapter_no)">
              <el-tag :type="c.status === 'committed' ? 'success' : 'info'" size="small">{{ c.chapter_no }}</el-tag>
              <span class="chapter-title">{{ c.title }}</span>
              <span class="chapter-wc">{{ c.wordcount }}</span>
            </div>
            <el-empty v-if="ws.chapters.length === 0" description="还没有章节，点「写下一章」开始" />
          </div>
        </div>

        <div class="section-card">
          <h3 class="section-title">追踪上下文</h3>
          <div class="kv" v-if="ws.tracking">
            <div class="kv-row"><span>已提交章节</span><b>{{ ws.tracking.last_committed_chapter }}</b></div>
            <div class="kv-row"><span>状态修订</span><b>rev {{ ws.tracking.state_revision }}</b></div>
            <div class="kv-row"><span>视图一致</span><el-tag :type="ws.tracking.views_consistent ? 'success' : 'danger'" size="small">{{ ws.tracking.views_consistent ? '一致' : '需重建' }}</el-tag></div>
          </div>
          <pre class="ctx-view">{{ ws.contextView?.content || '暂无上下文' }}</pre>
        </div>
      </aside>
    </div>
  </div>
</template>
```

样式：`.console-grid { display:grid; grid-template-columns:1fr 320px; gap:var(--space-lg); align-items:start; }`；`.editor` textarea 字号 16 / line-height 2；`.ctx-view` 用 `--font-mono` 12px、`background:var(--color-bg-page)` 圆角；`.chapter-item { display:flex; gap:8px; align-items:center; padding:8px; border-radius:var(--radius-md); cursor:pointer; }` hover/active 用 `--color-primary-lighter`。

- [ ] **Step 2: 更新路由**

`router/index.ts`：`projects/:id/console` → `ConsoleView.vue`（打开）。

- [ ] **Step 3: 验证**

Run: `cd frontend && npm run typecheck` → 零错误。`npm run dev` 访问 `/projects/{id}/console`：点「写下一章」看 4 阶段流水线 + SSE 流式正文 + 章节列表；点章节可查看。

- [ ] **Step 4: Commit**

```bash
git add frontend/src/views/ConsoleView.vue frontend/src/router/index.ts
git commit -m "feat: 创作控制台（写作流水线 + 流式正文 + 章节/追踪）"
git push
```

---

### Task 9: 章节阅读页 ChapterView（`/projects/:id/chapters/:chapterNo`）

**Files:**
- Create: `frontend/src/views/ChapterView.vue`
- Modify: `frontend/src/router/index.ts`（打开 `projects/:id/chapters/:chapterNo` 路由）

**Interfaces:**
- Consumes: `useWritingStore`（`current/load`）、`useOutlineStore`（`outline`，取该章细纲）、`useProjectsStore`；`writingApi.getChapter`
- Produces: 章节阅读/编辑页。

- [ ] **Step 1: 编写 ChapterView.vue**

script：

```ts
const pid = computed(() => Number(route.params.id))
const chapterNo = computed(() => Number(route.params.chapterNo))
const chapter = computed(() => ws.current)
const beats = computed(() => {
  const vol = os.outline?.volumes.find((v) => v.chapters.some((c) => c.chapter_no === chapterNo.value))
  return vol?.chapters.find((c) => c.chapter_no === chapterNo.value)?.beats ?? null
})
const editing = ref(false)
const draft = ref('')
function startEdit() { draft.value = chapter.value?.content ?? ''; editing.value = true }
async function save() {
  // 后端无章节内容更新 API → 仅本地提示，不做持久化
  editing.value = false
  ElMessage.warning('章节正文由写作流水线维护，暂不支持手动修改')
}
onMounted(async () => {
  await Promise.all([projectsStore.fetchList(), ws.load(pid.value), os.load(pid.value)])
  await loadChapter(chapterNo.value)
})
```

模板（grid `1fr 360px`）：

```vue
<template>
  <div class="page-container">
    <div class="page-header">
      <h1 class="page-title">第 {{ chapterNo }} 章 · {{ chapter?.title ?? '' }}</h1>
      <div class="header-actions">
        <el-button plain @click="router.push(`/quality?project=${pid}&chapter=${chapterNo}`)">审查 / 去味</el-button>
        <el-button v-if="!editing" plain @click="startEdit">编辑</el-button>
        <template v-else>
          <el-button @click="editing = false">取消</el-button>
          <el-button type="primary" @click="save">保存</el-button>
        </template>
      </div>
    </div>

    <div class="chapter-grid">
      <div class="main-col">
        <div class="section-card content-area">
          <pre v-if="!editing" class="chapter-text">{{ chapter?.content || '（无正文）' }}</pre>
          <el-input v-else v-model="draft" type="textarea" :autosize="{ minRows: 30, maxRows: 40 }" />
        </div>
      </div>
      <aside class="side-col">
        <div class="section-card">
          <h3 class="section-title">章节信息</h3>
          <div class="info-row"><span>章号</span><b>{{ chapter?.chapter_no }}</b></div>
          <div class="info-row"><span>字数</span><b>{{ chapter?.wordcount }}</b></div>
          <div class="info-row"><span>状态</span><el-tag :type="chapter?.status === 'committed' ? 'success' : 'info'" size="small">{{ chapter?.status }}</el-tag></div>
          <div class="info-row"><span>修订</span><b>rev {{ chapter?.revision }}</b></div>
        </div>
        <div class="section-card">
          <h3 class="section-title">本章细纲</h3>
          <p v-if="beats?.summary" class="beats-summary">{{ beats.summary }}</p>
          <ul v-if="beats?.points?.length" class="beats-points"><li v-for="(p, i) in beats.points" :key="i">{{ formatPoint(p) }}</li></ul>
          <el-empty v-else description="暂无细纲" :image-size="60" />
        </div>
      </aside>
    </div>
  </div>
</template>
```

样式：`.chapter-grid { display:grid; grid-template-columns:1fr 360px; gap:var(--space-lg); align-items:start; }`；`.chapter-text { white-space:pre-wrap; line-height:2; font-size:var(--font-size-lg); font-family:var(--font-family); margin:0; }`；`.info-row { display:flex; justify-content:space-between; padding:8px 0; border-bottom:1px solid var(--color-border-light); font-size:var(--font-size-sm); }`。`formatPoint` 复制自 WorkspaceView。

> 「保存」后端无更新 API → 点击给出提示不持久化（符合「不动后端」约束）。若后端将来支持，再接通。

- [ ] **Step 2: 更新路由**

`router/index.ts`：`projects/:id/chapters/:chapterNo` → `ChapterView.vue`（打开）。

- [ ] **Step 3: 验证**

Run: `cd frontend && npm run typecheck` → 零错误。`npm run dev` 访问 `/projects/{id}/chapters/{no}` 核对正文/细纲/跳转链接。

- [ ] **Step 4: Commit**

```bash
git add frontend/src/views/ChapterView.vue frontend/src/router/index.ts
git commit -m "feat: 章节阅读页（正文/细纲/审查跳转）"
git push
```

---

### Task 10: 删除旧 WorkspaceView 兜底路由

**Files:**
- Delete: `frontend/src/views/WorkspaceView.vue`
- Modify: `frontend/src/router/index.ts`（删除 `projects/:id/workspace` 与 `workspace-legacy`）

- [ ] **Step 1: 删除路由与文件**

`router/index.ts` 删除 `projects/:id/workspace` 路由项；删除 `WorkspaceView.vue` 文件。

- [ ] **Step 2: 验证**

Run: `cd frontend && npm run typecheck` → 零错误。`npm run dev` 确认工作台→详情→创作台/大纲/章节全链路可达，无残留引用旧页面。

- [ ] **Step 3: Commit**

```bash
git add -A frontend/src
git commit -m "refactor: 删除旧合并式 WorkspaceView 兜底"
git push
```

---

### Task 11: 模块页重绘（拆文库 / 扫榜 / 用量 / 设置）

**Files:**
- Modify: `frontend/src/views/AnalysisView.vue`, `ScanView.vue`, `UsageView.vue`, `SettingsView.vue`

**Interfaces:**
- Consumes: 各自 store（不变）
- Produces: section-card 风模块页。

- [ ] **Step 1: 逐页套用 section-card**

对 4 个页面，在 Task 2 已删骨架基础上：
- 页面根用 `.page-container` + `.page-header`（`h1.page-title` 放模块名）+ 操作按钮
- 每个功能区块用 `.section-card` + `h3.section-title`
- 统计卡用 `.stat-card`（Usage 的 4 项：调用次数/token/成本/缓存命中率）
- 列表/表格样式统一：行 hover `--color-bg-page`、选中 `--color-primary-lighter`；状态用 `el-tag` 语义色（进行中 warning / 完成 success / 失败 danger）
- 保留各页全部 store 交互逻辑与数据绑定，只改 class/结构

具体：
- **AnalysisView**：上传卡片（`section-card` + 表单）+ 拆书列表卡片（`.book-row` hover 态）
- **ScanView**：工具栏（平台/刷新/选题）+ 平台卡片网格 + 决策卡；题材分布/热词用现有展示（若用 el-progress 则套用主题色）
- **UsageView**：日期条 + 4 `stat-card` + 图表卡（现有表格/柱状保留，若用 el-progress/条形改为主题色）
- **SettingsView**：三档选择卡（`.tier-row`）+ 供应商列表（`.provider-card` 2px 边框、`.is-active` 主色边 + `--color-primary-lighter` 底 + 「使用中」success 标签）+ 新增/编辑对话框 560px

- [ ] **Step 2: 验证**

Run: `cd frontend && npm run typecheck` → 零错误。`npm run dev` 逐页核对视觉与交互。

- [ ] **Step 3: Commit**

```bash
git add frontend/src/views/AnalysisView.vue frontend/src/views/ScanView.vue frontend/src/views/UsageView.vue frontend/src/views/SettingsView.vue
git commit -m "feat: 拆文库/扫榜/用量/设置 套用 section-card 重绘"
git push
```

---

### Task 12: 审查去味页重绘 + 章节跳转预选

**Files:**
- Modify: `frontend/src/views/QualityView.vue`

**Interfaces:**
- Consumes: `useQualityStore`、`useProjectsStore`、`useRouter`/`useRoute`
- Produces: section-card 风审查去味页，并支持 `?project=&chapter=` query 预选（供 ChapterView 跳转）。

- [ ] **Step 1: 支持路由 query 预选**

script 增补：

```ts
const route = useRoute()
const selectedPid = computed(() => Number(route.query.project) || null)
const selectedChapter = computed(() => Number(route.query.chapter) || null)
// onMounted 中 fetchList 后：
onMounted(async () => {
  if (!auth.user) await auth.fetchMe()
  await projectsStore.fetchList()
  if (selectedPid.value) {
    pid.value = selectedPid.value
    await quality.loadChapters(pid.value)
    if (selectedChapter.value) {
      chapterNo.value = selectedChapter.value
      await quality.loadAll(pid.value, chapterNo.value)
    }
  }
})
```

（`pid/chapterNo/mode` 为现有 ref，逻辑不变。）

- [ ] **Step 2: 重绘模板**

按 Task 11 的 section-card 模式重绘：`.page-container` + `.page-header`（标题「审查 · 去味」）+ 左侧选择卡（项目下拉 + 章节下拉 + 审查模式）+ 右侧结果卡（审查结果 / 去味对照 / 接受按钮）。保留全部现有功能与事件处理。运行中显示 `AgentActivityPanel`。

- [ ] **Step 3: 验证**

Run: `cd frontend && npm run typecheck` → 零错误。`npm run dev` 从章节页点「审查 / 去味」确认跳转并预选项目/章节。

- [ ] **Step 4: Commit**

```bash
git add frontend/src/views/QualityView.vue
git commit -m "feat: 审查去味页 section-card 重绘 + 支持章节跳转预选"
git push
```

---

### Task 13: 全量验证与收尾

**Files:** 视发现的问题而定（样式微调、未用 import 清理）

- [ ] **Step 1: 类型与构建**

Run: `cd frontend && npm run typecheck` → 零错误；`npm run build` → 成功。

- [ ] **Step 2: 全链路人工核对**

`npm run dev`，逐页核对：登录/注册、工作台、项目详情、大纲审核（开书+confirm+重跑）、创作控制台（写下一章 SSE 流式+取消）、章节阅读、拆文库、审查去味（含跳转预选）、扫榜、用量、设置。重点确认：
- 侧栏「当前项目」分组在项目页正确高亮；折叠切换正常
- 深色终端、Agent 流水线、草稿弹窗视觉到位
- 无控制台报错、无重复侧栏

- [ ] **Step 3: 修复发现的视觉/交互问题**

对发现的问题逐项修复（改回相应 `.vue`）。

- [ ] **Step 4: 最终提交**

```bash
git add -A frontend
git commit -m "polish: 前端改造全量验收与视觉收尾"
git push
```

---

## Self-Review

- **Spec 覆盖**：spec 第 1 节设计系统 → Task 1；第 2 节 AppLayout/路由 → Task 2；第 3 节四页拆分 → Task 6-10；第 4 节组件重绘 → Task 5，登录页 → Task 3；第 5 节其余页面 → Task 4/11/12；验证 → Task 13。无遗漏。
- **占位符扫描**：所有代码步骤均给出实际内容；大视图采用「复制现有逻辑 + 给出结构与样式」的方式，避免重复打印已有 store/逻辑。`NovelDetailView` 总章节数来自大纲卷章数、已提交来自 `ws.tracking`——已在 Task 6 script 给出。
- **类型一致性**：复用 store 现有字段名（`ws.current/currentText/currentWordcount/tracking/contextView/stageStatus/chapters`，`os.outline/hasOutline/stageStatus/events/running/waiting/waitingDraft/currentStage/stageDrafts`，`projectsStore.projects/loading/fetchList`）；组件 props/emits 签名不变；路由参数 `chapterNo`（Task 9）与后端 `ChapterDetail.chapter_no` 一致。
