<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, type FormInstance, type FormRules } from 'element-plus'
import { useAuthStore } from '@/stores/auth'
import { useProjectsStore } from '@/stores/projects'

const auth = useAuthStore()
const projectsStore = useProjectsStore()
const router = useRouter()

const displayName = computed(() => auth.user?.display_name || auth.user?.username || '')
const activeProject = computed(() => projectsStore.activeProject)

// ---- 新建项目 ----
const showCreate = ref(false)
const createRef = ref<FormInstance>()
const creating = ref(false)
const form = reactive({ slug: '', title: '', genre: '', platform: '' })

const rules: FormRules = {
  slug: [
    { required: true, message: '请输入书名标识', trigger: 'blur' },
    { pattern: /^[a-z0-9-]+$/, message: '仅小写字母、数字、连字符', trigger: 'blur' },
  ],
  title: [{ required: true, message: '请输入书名', trigger: 'blur' }],
}

async function onCreate() {
  if (!createRef.value) return
  await createRef.value.validate(async (valid) => {
    if (!valid) return
    creating.value = true
    try {
      await projectsStore.create({
        slug: form.slug,
        title: form.title,
        genre: form.genre || undefined,
        platform: form.platform || undefined,
      })
      ElMessage.success('项目创建成功')
      showCreate.value = false
      form.slug = form.title = form.genre = form.platform = ''
    } catch (e: any) {
      ElMessage.error(e?.response?.data?.detail || '创建失败')
    } finally {
      creating.value = false
    }
  })
}

async function onActivate(id: number) {
  await projectsStore.activate(id)
  ElMessage.success('已设为活跃书')
}

async function onLogout() {
  auth.logout()
  ElMessage.success('已退出登录')
  router.push('/login')
}

onMounted(async () => {
  try {
    if (!auth.user) await auth.fetchMe()
    await projectsStore.fetchList()
  } catch {
    // 401 已由 http 拦截器处理
  }
})
</script>

<template>
  <el-container class="layout">
    <el-aside width="220px" class="aside">
      <div class="aside-brand">
        <span class="aside-logo">文</span>
        <span class="aside-title">Novel Agents</span>
      </div>
      <el-menu :default-active="$route.path" router class="aside-menu">
        <el-menu-item index="/dashboard">
          <span>工作台</span>
        </el-menu-item>
        <el-menu-item index="/analysis">
          <span>拆文库</span>
        </el-menu-item>
        <el-menu-item index="/quality">
          <span>审查 / 去味</span>
        </el-menu-item>
        <el-menu-item index="/scan">
          <span>扫榜</span>
        </el-menu-item>
        <el-menu-item index="/settings">
          <span>设置</span>
        </el-menu-item>
      </el-menu>
      <div class="aside-placeholder">写作 · 拆文 · 审查 · 扫榜 模块陆续开放</div>
    </el-aside>

    <el-container>
      <el-header class="header">
        <div class="header-title">工作台</div>
        <el-dropdown @command="onLogout">
          <span class="user-chip">
            <el-avatar :size="28">{{ displayName[0]?.toUpperCase() || 'U' }}</el-avatar>
            <span class="user-name">{{ displayName }}</span>
          </span>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item command="logout">退出登录</el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
      </el-header>

      <el-main class="main">
        <el-card shadow="never" class="welcome">
          <h2>欢迎回来，{{ displayName }} 👋</h2>
          <p>
            你的 AI 多智能体创作空间。{{ activeProject ? `当前活跃书：《${activeProject.title}》` : '创建一个项目开始创作。' }}
          </p>
        </el-card>

        <div class="section-head">
          <h3>我的项目</h3>
          <el-button type="primary" @click="showCreate = true">+ 新建项目</el-button>
        </div>

        <el-row :gutter="16" v-loading="projectsStore.loading">
          <el-col :span="8" v-for="p in projectsStore.projects" :key="p.id">
            <el-card shadow="hover" class="project-card" :class="{ active: p.status === 'active' }">
              <div class="card-head">
                <el-tag v-if="p.status === 'active'" type="success" size="small">活跃</el-tag>
                <el-tag v-else size="small" type="info">未激活</el-tag>
              </div>
              <h4 class="card-title">{{ p.title }}</h4>
              <p class="card-meta">
                {{ p.genre || '未设题材' }} · {{ p.platform || '未设平台' }} · slug: {{ p.slug }}
              </p>
              <div class="card-actions">
                <el-button size="small" type="primary" plain @click="router.push(`/projects/${p.id}`)">
                  进入写作台
                </el-button>
                <el-button
                  v-if="p.status !== 'active'"
                  size="small"
                  @click="onActivate(p.id)"
                >
                  设为活跃书
                </el-button>
              </div>
            </el-card>
          </el-col>
          <el-col :span="8" v-if="!projectsStore.loading && projectsStore.projects.length === 0">
            <el-card class="empty-card">
              <p>还没有项目，点击右上角「新建项目」开始你的第一本书。</p>
            </el-card>
          </el-col>
        </el-row>
      </el-main>
    </el-container>
  </el-container>

  <el-dialog v-model="showCreate" title="新建项目" width="460px">
    <el-form ref="createRef" :model="form" :rules="rules" label-position="top">
      <el-form-item label="书名" prop="title">
        <el-input v-model="form.title" placeholder="例如：仙路问道" maxlength="128" />
      </el-form-item>
      <el-form-item label="书名标识 slug" prop="slug">
        <el-input v-model="form.slug" placeholder="小写字母/数字/连字符，例如 xian-lu-wen-dao" maxlength="64" />
      </el-form-item>
      <el-form-item label="题材" prop="genre">
        <el-input v-model="form.genre" placeholder="例如：玄幻 / 都市 / 科幻" maxlength="64" />
      </el-form-item>
      <el-form-item label="平台" prop="platform">
        <el-input v-model="form.platform" placeholder="例如：起点 / 番茄" maxlength="32" />
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="showCreate = false">取消</el-button>
      <el-button type="primary" :loading="creating" @click="onCreate">创建</el-button>
    </template>
  </el-dialog>
</template>

<style scoped>
.layout {
  height: 100vh;
}

.aside {
  background: #1e2530;
  display: flex;
  flex-direction: column;
}

.aside-brand {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 18px 20px;
  color: #fff;
}

.aside-logo {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 30px;
  height: 30px;
  border-radius: 8px;
  background: var(--brand);
  color: #fff;
  font-family: Georgia, serif;
  font-weight: bold;
}

.aside-title {
  font-size: 15px;
  font-weight: 600;
}

.aside-menu {
  border-right: none;
  background: transparent;
  --el-menu-text-color: #cbd5e1;
  --el-menu-hover-bg-color: #2b3442;
  --el-menu-active-color: #fff;
  --el-menu-bg-color: transparent;
}

.aside-menu .el-menu-item {
  background: transparent;
}

.aside-placeholder {
  margin-top: auto;
  padding: 16px 20px;
  font-size: 12px;
  color: #64748b;
}

.header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  background: #fff;
  border-bottom: 1px solid #e5e7eb;
}

.header-title {
  font-size: 16px;
  font-weight: 600;
  color: #1f2937;
}

.user-chip {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  cursor: pointer;
}

.user-name {
  font-size: 14px;
  color: #374151;
}

.main {
  background: #f5f6fa;
}

.welcome {
  margin-bottom: 16px;
}

.welcome h2 {
  margin: 0 0 8px;
  color: #1f2937;
}

.welcome p {
  margin: 0;
  color: #6b7280;
  font-size: 14px;
}

.section-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin: 8px 0 16px;
}

.section-head h3 {
  margin: 0;
  color: #1f2937;
}

.project-card {
  margin-bottom: 16px;
}

.project-card.active {
  border-color: var(--brand);
}

.card-head {
  display: flex;
  justify-content: flex-end;
  margin-bottom: 8px;
}

.card-title {
  margin: 0 0 6px;
  color: #1f2937;
  font-size: 16px;
}

.card-meta {
  margin: 0 0 12px;
  font-size: 13px;
  color: #6b7280;
}

.card-actions {
  display: flex;
  gap: 8px;
}

.empty-card p {
  margin: 0;
  color: #9ca3af;
  text-align: center;
  padding: 24px 0;
}
</style>
