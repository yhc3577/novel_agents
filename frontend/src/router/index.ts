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
