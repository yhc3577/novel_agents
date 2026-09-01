<script setup lang="ts">
import { computed, onUnmounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import AgentActivityPanel from '@/components/AgentActivityPanel.vue'
import DraftConfirmDialog from '@/components/DraftConfirmDialog.vue'
import PipelineBar from '@/components/PipelineBar.vue'
import { useOutlineStore } from '@/stores/outline'
import { useProjectsStore } from '@/stores/projects'
import type { PipelineStage } from '@/types/writing'
import { OPEN_BOOK_PIPELINE } from '@/types/writing'

const route = useRoute()
const projectsStore = useProjectsStore()
const os = useOutlineStore()

const pid = computed(() => Number(route.params.id))

const project = computed(() => projectsStore.projects.find((p) => p.id === pid.value))

// ---- 开书 ----
const obScenario = ref('')

async function onOpenBook(force: boolean) {
  try {
    await os.openBook(pid.value, { scenario: obScenario.value || undefined, force })
    ElMessage.info(`已发起开书任务 #${os.task?.id}`)
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || '开书任务发起失败')
  }
}

const currentStageLabel = computed(
  () => OPEN_BOOK_PIPELINE.find((s) => s.key === os.currentStage)?.label ?? os.currentStage ?? '',
)
const currentStageText = computed(() => (os.currentStage ? (os.stageDrafts[os.currentStage] ?? '') : ''))

/** 流水线点击重跑：从该阶段重新生成（该阶段及其后清空，上游保留）。 */
async function onRetryStage(stage: string) {
  if (os.running) return
  try {
    await os.retryStage(pid.value, stage as PipelineStage)
    const label = OPEN_BOOK_PIPELINE.find((s) => s.key === stage)?.label ?? stage
    ElMessage.info(`已从「${label}」重新生成`)
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || '重跑阶段失败')
  }
}

async function onConfirmDraft(content: string) {
  try {
    await os.confirmDraft(content)
    ElMessage.success('已确认入库，继续下一阶段')
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || '确认失败')
  }
}

async function onRegenerateDraft() {
  try {
    await os.regenerateDraft()
    ElMessage.info('正在重新生成本阶段')
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || '重新生成失败')
  }
}

function formatPoint(p: unknown): string {
  if (typeof p === 'string') return p
  if (p && typeof p === 'object') {
    const rec = p as Record<string, unknown>
    return rec.content ? String(rec.content) : JSON.stringify(rec)
  }
  return String(p)
}

watch(
  pid,
  async (id) => {
    os.reset()
    await projectsStore.fetchList()
    await os.load(id)
  },
  { immediate: true },
)

onUnmounted(() => {
  os.reset()
})
</script>

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
          <div v-else class="review-cta">
            <el-input
              v-model="obScenario"
              type="textarea"
              :rows="3"
              resize="none"
              placeholder="开书意图（可选），如：都市修仙 · 废柴崛起"
            />
            <div class="review-cta-hint">开书意图可选；填写后点击右上角「开始开书」</div>
          </div>
        </div>
      </div>
    </div>

    <DraftConfirmDialog :visible="os.waiting" :stage="os.waitingDraft?.stage ?? ''"
      :content="os.waitingDraft?.content ?? ''"
      @confirm="onConfirmDraft" @regenerate="onRegenerateDraft" @cancel="os.cancel()" />
  </div>
</template>

<style scoped>
.header-actions {
  display: flex;
  align-items: center;
  gap: 12px;
}
.review-grid {
  display: flex;
  flex-direction: column;
}
.main-col {
  flex: 1;
  min-width: 0;
}
.vol-collapse {
  border: none;
}
.vol-collapse :deep(.el-collapse-item__header) {
  font-size: 13px;
  background: transparent;
  color: #1f2937;
  border-bottom: 1px solid #eef2f7;
}
.vol-collapse :deep(.el-collapse-item__wrap) {
  background: transparent;
  border-bottom: none;
}
.vol-collapse :deep(.el-collapse-item__content) {
  color: #4e5969;
  padding-bottom: 8px;
}
.oc-synopsis {
  font-size: 12px;
  color: #4e5969;
  line-height: 1.6;
  background: var(--color-bg-page);
  border-radius: var(--radius-md);
  padding: var(--space-sm) var(--space-md);
  margin-bottom: var(--space-sm);
}
.oc-block {
  padding: 6px 4px;
  border-bottom: 1px dashed #eef2f7;
}
.oc-head {
  font-size: 12px;
  font-weight: 600;
  color: #1f2937;
}
.oc-summary {
  font-size: 12px;
  color: #6b7280;
  margin-top: 3px;
  line-height: 1.5;
}
.oc-wc {
  font-size: 11px;
  color: #9ca3af;
  margin-top: 2px;
}
.oc-points {
  margin: 4px 0 0;
  padding-left: 14px;
}
.oc-points li {
  font-size: 11px;
  color: #6b7280;
  margin-bottom: 2px;
}
.draft-preview {
  background: var(--color-bg-card);
  border: 1px solid var(--color-border-light);
  border-radius: var(--radius-lg);
  padding: 6px 16px 12px;
  margin-top: var(--space-md);
}
.draft-preview-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-size: 12px;
  font-weight: 600;
  color: #475569;
  margin-bottom: 6px;
}
.draft-preview-wc {
  color: #94a3b8;
  font-weight: 400;
}
.draft-preview-body {
  max-height: 160px;
  overflow-y: auto;
  white-space: pre-wrap;
  word-break: break-all;
  background: var(--color-bg-page);
  border: 1px solid #eef2f7;
  border-radius: 8px;
  padding: 10px;
  font-size: 12px;
  line-height: 1.7;
  color: #334155;
  font-family: 'Songti SC', 'SimSun', Georgia, serif;
  margin: 0;
}
.review-cta {
  max-width: 480px;
  margin: 0 auto;
  padding: var(--space-lg) 0;
  text-align: center;
}
.review-cta-hint {
  margin-top: var(--space-sm);
  font-size: var(--font-size-xs);
  color: var(--color-text-secondary);
}
</style>
