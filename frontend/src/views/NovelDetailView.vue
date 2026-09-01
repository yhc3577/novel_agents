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

onMounted(async () => {
  await projectsStore.fetchList()
  await Promise.all([ws.load(pid.value), os.load(pid.value)])
})
</script>

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

<style scoped>
.detail-grid {
  display: grid;
  grid-template-columns: 1fr 300px;
  gap: var(--space-lg);
  align-items: start;
}
.volume-block {
  border: 1px solid var(--color-border-light);
  border-radius: var(--radius-md);
  padding: var(--space-md);
  margin-bottom: var(--space-md);
}
.volume-title {
  color: var(--color-primary);
  font-size: var(--font-size-md);
  margin: 0 0 8px;
}
.outline-chapter-row {
  display: flex;
  gap: 8px;
  padding: 4px 0;
  font-size: var(--font-size-sm);
  color: var(--color-text-regular);
}
.progress-stats .kv {
  display: flex;
  justify-content: space-between;
  padding: 8px 0;
  border-bottom: 1px solid var(--color-border-light);
  font-size: var(--font-size-sm);
}
.header-actions {
  display: flex;
  align-items: center;
  gap: 12px;
}
</style>
