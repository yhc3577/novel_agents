<script setup lang="ts">
import { computed, onUnmounted, watch } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import AgentActivityPanel from '@/components/AgentActivityPanel.vue'
import PipelineBar from '@/components/PipelineBar.vue'
import { useProjectsStore } from '@/stores/projects'
import { useWritingStore } from '@/stores/writing'
import { WRITE_PIPELINE } from '@/types/writing'

const route = useRoute()
const projectsStore = useProjectsStore()
const ws = useWritingStore()

const pid = computed(() => Number(route.params.id))

const project = computed(() => projectsStore.projects.find((p) => p.id === pid.value))

// ---- 写下一章 ----
async function onWriteNext(action: 'write_next' | 'daily' = 'write_next') {
  if (ws.running) return
  try {
    await ws.writeNext(pid.value, { action })
    ElMessage.info(`已发起任务 #${ws.task?.id}`)
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || '任务发起失败')
  }
}

function onCancel() {
  ws.cancel()
  ElMessage.warning('已请求取消')
}

function onSelectChapter(chapterNo: number) {
  // 未在写作中才允许切换查看
  if (ws.running) return
  void loadChapter(chapterNo)
}

async function loadChapter(chapterNo: number) {
  const detail = await (await import('@/api/writing')).writingApi.getChapter(pid.value, chapterNo)
  ws.current = detail
}

watch(
  pid,
  async (id) => {
    ws.reset()
    await projectsStore.fetchList()
    await ws.load(id)
  },
  { immediate: true },
)

onUnmounted(() => {
  ws.reset()
})
</script>

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

<style scoped>
.console-grid {
  display: grid;
  grid-template-columns: 1fr 320px;
  gap: var(--space-lg);
  align-items: start;
}

.header-actions {
  display: flex;
  align-items: center;
  gap: var(--space-md);
}

.editor-card {
  min-height: 72vh;
}

.editor-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: var(--space-sm);
}

.editor-title {
  font-size: var(--font-size-lg);
  font-weight: 600;
  color: var(--color-text-primary);
}

.editor-wc {
  color: var(--color-text-secondary);
  font-size: var(--font-size-sm);
}

.editor :deep(.el-textarea__inner) {
  font-family: 'Songti SC', 'SimSun', Georgia, serif;
  font-size: 16px;
  line-height: 2;
  color: var(--color-text-primary);
}

.chapter-list {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.chapter-item {
  display: flex;
  gap: 8px;
  align-items: center;
  padding: 8px;
  border-radius: var(--radius-md);
  cursor: pointer;
}

.chapter-item:hover {
  background: var(--color-primary-lighter);
}

.chapter-item:active {
  background: var(--color-primary-lighter);
}

.chapter-title {
  flex: 1;
  font-size: var(--font-size-sm);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.chapter-wc {
  font-size: var(--font-size-xs);
  color: var(--color-text-secondary);
}

.kv-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 6px 0;
  font-size: var(--font-size-sm);
  color: var(--color-text-regular);
  border-bottom: 1px dashed var(--color-border);
}

.ctx-view {
  max-height: 320px;
  overflow-y: auto;
  white-space: pre-wrap;
  word-break: break-all;
  background: var(--color-bg-page);
  border: 1px solid var(--color-border-light);
  border-radius: var(--radius-md);
  padding: var(--space-sm);
  font-size: 12px;
  color: var(--color-text-regular);
  font-family: var(--font-mono);
  margin: var(--space-md) 0 0;
}
</style>
