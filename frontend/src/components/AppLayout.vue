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
