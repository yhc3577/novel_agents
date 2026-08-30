import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

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
      path: '/dashboard',
      name: 'dashboard',
      component: () => import('@/views/DashboardView.vue'),
      meta: { requiresAuth: true, title: '工作台' },
    },
    {
      path: '/projects/:id',
      name: 'workspace',
      component: () => import('@/views/WorkspaceView.vue'),
      meta: { requiresAuth: true, title: '写作工作台' },
    },
    {
      path: '/analysis',
      name: 'analysis',
      component: () => import('@/views/AnalysisView.vue'),
      meta: { requiresAuth: true, title: '拆文库' },
    },
    {
      path: '/quality',
      name: 'quality',
      component: () => import('@/views/QualityView.vue'),
      meta: { requiresAuth: true, title: '审查 / 去味' },
    },
    {
      path: '/settings',
      name: 'settings',
      component: () => import('@/views/SettingsView.vue'),
      meta: { requiresAuth: true, title: '设置' },
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
