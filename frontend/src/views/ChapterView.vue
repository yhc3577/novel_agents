<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { useOutlineStore } from '@/stores/outline'
import { useProjectsStore } from '@/stores/projects'
import { useWritingStore } from '@/stores/writing'

const route = useRoute()
const router = useRouter()
const projectsStore = useProjectsStore()
const ws = useWritingStore()
const os = useOutlineStore()

const pid = computed(() => Number(route.params.id))
const chapterNo = computed(() => Number(route.params.chapterNo))
const chapter = computed(() => ws.current)
const beats = computed(() => {
  const vol = os.outline?.volumes.find((v) => v.chapters.some((c) => c.chapter_no === chapterNo.value))
  return vol?.chapters.find((c) => c.chapter_no === chapterNo.value)?.beats ?? null
})
const editing = ref(false)
const draft = ref('')
function startEdit() {
  draft.value = chapter.value?.content ?? ''
  editing.value = true
}
async function save() {
  // 后端无章节内容更新 API → 仅本地提示，不做持久化
  editing.value = false
  ElMessage.warning('章节正文由写作流水线维护，暂不支持手动修改')
}
onMounted(async () => {
  await Promise.all([projectsStore.fetchList(), ws.load(pid.value), os.load(pid.value)])
  await loadChapter(chapterNo.value)
})

async function loadChapter(chapterNo: number) {
  const detail = await (await import('@/api/writing')).writingApi.getChapter(pid.value, chapterNo)
  ws.current = detail
}

function formatPoint(p: unknown): string {
  if (typeof p === 'string') return p
  if (p && typeof p === 'object') {
    const rec = p as Record<string, unknown>
    return rec.content ? String(rec.content) : JSON.stringify(rec)
  }
  return String(p)
}
</script>

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

<style scoped>
.chapter-grid {
  display: grid;
  grid-template-columns: 1fr 360px;
  gap: var(--space-lg);
  align-items: start;
}

.header-actions {
  display: flex;
  align-items: center;
  gap: var(--space-md);
}

.main-col {
  min-width: 0;
}

.content-area {
  min-height: 72vh;
}

.chapter-text {
  white-space: pre-wrap;
  line-height: 2;
  font-size: var(--font-size-lg);
  font-family: var(--font-family);
  margin: 0;
}

.info-row {
  display: flex;
  justify-content: space-between;
  padding: 8px 0;
  border-bottom: 1px solid var(--color-border-light);
  font-size: var(--font-size-sm);
}

.beats-summary {
  margin: 0 0 var(--space-sm);
  font-size: var(--font-size-sm);
  line-height: 1.7;
  color: var(--color-text-regular);
}

.beats-points {
  margin: 0;
  padding-left: var(--space-lg);
}

.beats-points li {
  font-size: var(--font-size-sm);
  color: var(--color-text-regular);
  margin-bottom: 4px;
}
</style>
