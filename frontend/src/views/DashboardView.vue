<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, type FormInstance, type FormRules } from 'element-plus'
import { useAuthStore } from '@/stores/auth'
import { useProjectsStore } from '@/stores/projects'
import { writingApi } from '@/api/writing'

const auth = useAuthStore()
const projectsStore = useProjectsStore()
const router = useRouter()

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
  try {
    await projectsStore.activate(id)
    ElMessage.success('已设为活跃书')
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || '设置活跃书失败')
  }
}

// ---- 统计 ----
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

function fmtDate(s: string) {
  return new Date(s).toLocaleDateString('zh-CN')
}

onMounted(async () => {
  try {
    if (!auth.user) await auth.fetchMe()
    await projectsStore.fetchList()
    await refreshTotalChapters()
  } catch {
    // 401 已由 http 拦截器处理
  }
})
</script>

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
          <span class="novel-card-actions">
            <el-button
              v-if="p.status !== 'active'"
              size="small"
              plain
              class="novel-card-activate"
              @click.stop="onActivate(p.id)"
            >设为活跃书</el-button>
            <span class="novel-card-enter">进入项目 →</span>
          </span>
        </div>
      </div>
    </div>

    <el-empty v-if="!projectsStore.loading && projectsStore.projects.length === 0" description="还没有项目，点击右上角「新建项目」开始你的第一本书" />
  </div>

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
.stats-row {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: var(--space-lg);
  margin-bottom: var(--space-lg);
}

.stat-value {
  font-size: var(--font-size-2xl);
  font-weight: 600;
  color: var(--color-text-primary);
}

.stat-value.warn {
  color: var(--color-warning);
}

.stat-value.success {
  color: var(--color-success);
}

.stat-label {
  font-size: var(--font-size-xs);
  color: var(--color-text-secondary);
  margin-top: 4px;
}

.novel-card {
  background: var(--color-bg-card);
  border: 1px solid var(--color-border-light);
  border-radius: var(--radius-lg);
  padding: var(--space-lg);
  box-shadow: var(--shadow-sm);
  cursor: pointer;
  transition: all var(--transition-normal);
}

.novel-card:hover {
  transform: translateY(-2px);
  box-shadow: var(--shadow-lg);
  border-color: var(--color-primary-lighter);
}

.novel-card-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-sm);
}

.novel-card-title {
  margin: 0;
  font-size: var(--font-size-lg);
  font-weight: 600;
  color: var(--color-text-primary);
}

.novel-card-meta {
  display: flex;
  align-items: center;
  gap: 6px;
  margin: var(--space-sm) 0 var(--space-md);
  font-size: var(--font-size-xs);
  color: var(--color-text-secondary);
}

.novel-card-foot {
  display: flex;
  align-items: center;
  justify-content: space-between;
  border-top: 1px solid var(--color-border-light);
  padding-top: var(--space-sm);
  font-size: var(--font-size-xs);
}

.novel-card-date {
  color: var(--color-text-secondary);
}

.novel-card-actions {
  display: flex;
  align-items: center;
  gap: var(--space-sm);
}

.novel-card-activate {
  margin: 0;
}

.novel-card-enter {
  color: var(--color-primary);
  font-weight: 500;
}
</style>
