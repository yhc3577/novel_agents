<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, type FormInstance, type FormRules } from 'element-plus'
import { useAuthStore } from '@/stores/auth'
import { useProjectsStore } from '@/stores/projects'

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
  await projectsStore.activate(id)
  ElMessage.success('已设为活跃书')
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
  <div class="page-container">
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
