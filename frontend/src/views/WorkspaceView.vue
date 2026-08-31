<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import AgentActivityPanel from '@/components/AgentActivityPanel.vue'
import DraftConfirmDialog from '@/components/DraftConfirmDialog.vue'
import PipelineBar from '@/components/PipelineBar.vue'
import { useAuthStore } from '@/stores/auth'
import { useOutlineStore } from '@/stores/outline'
import { useProjectsStore } from '@/stores/projects'
import { useWritingStore } from '@/stores/writing'
import type { PipelineStage } from '@/types/writing'
import { OPEN_BOOK_PIPELINE, WRITE_PIPELINE } from '@/types/writing'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const projectsStore = useProjectsStore()
const ws = useWritingStore()
const os = useOutlineStore()

const pid = computed(() => Number(route.params.id))

const project = computed(() => projectsStore.projects.find((p) => p.id === pid.value))
const displayName = computed(() => auth.user?.display_name || auth.user?.username || '')

// ---- 侧栏页签 / 开书 ----
const asideTab = ref('chapters')
const obScenario = ref('')

// ---- 写下一章 ----
const scenario = ref('')
const target = ref<number | null>(null)

async function onWriteNext(action: 'write_next' | 'daily' = 'write_next') {
  if (ws.running) return
  try {
    await ws.writeNext(pid.value, {
      action,
      scenario: scenario.value || undefined,
      target: target.value || undefined,
    })
    ElMessage.info(`已发起任务 #${ws.task?.id}`)
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || '任务发起失败')
  }
}

function onCancel() {
  ws.cancel()
  ElMessage.warning('已请求取消')
}

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
  if (os.running || ws.running) return
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

function onSelectChapter(chapterNo: number) {
  // 未在写作中才允许切换查看
  if (ws.running) return
  void loadChapter(chapterNo)
}

async function loadChapter(chapterNo: number) {
  const detail = await (await import('@/api/writing')).writingApi.getChapter(pid.value, chapterNo)
  ws.current = detail
}

function onBack() {
  router.push('/dashboard')
}

async function onLogout() {
  auth.logout()
  router.push('/login')
}

watch(
  pid,
  async (id) => {
    ws.reset()
    os.reset()
    await projectsStore.fetchList()
    await Promise.all([ws.load(id), os.load(id)])
  },
  { immediate: true },
)

onMounted(() => {
  if (!auth.user) void auth.fetchMe()
})

onUnmounted(() => {
  ws.reset()
  os.reset()
})
</script>

<template>
  <el-container class="layout">
    <el-aside width="240px" class="aside">
      <div class="aside-brand">
        <el-button link class="back-btn" @click="onBack">‹ 工作台</el-button>
        <div class="book-title">{{ project?.title ?? '未知项目' }}</div>
        <div class="book-meta">{{ project?.genre || '未设题材' }} · {{ project?.slug }}</div>
      </div>
      <el-tabs v-model="asideTab" class="aside-tabs">
        <el-tab-pane label="章节" name="chapters">
          <div class="pane-scroll">
            <div v-for="c in ws.chapters" :key="c.chapter_no" class="chapter-item" @click="onSelectChapter(c.chapter_no)">
              <el-tag :type="c.status === 'committed' ? 'success' : 'info'" size="small">
                {{ c.chapter_no }}
              </el-tag>
              <span class="chapter-title">{{ c.title }}</span>
              <span class="chapter-wc">{{ c.wordcount }}</span>
            </div>
            <div v-if="ws.chapters.length === 0" class="tree-empty">还没有章节，点「写下一章」开始</div>
          </div>
        </el-tab-pane>
        <el-tab-pane label="大纲" name="outline">
          <div class="pane-scroll">
            <!-- 开书进行中：实时进度 -->
            <AgentActivityPanel v-if="os.running" :events="os.events" />
            <!-- 已开书：卷 → 章 → 细纲 树 -->
            <template v-else-if="os.hasOutline && os.outline">
              <el-collapse v-for="vol in os.outline.volumes" :key="vol.no" class="vol-collapse">
                <el-collapse-item :title="`第${vol.no}卷 · ${vol.title}`" :name="vol.no">
                  <div v-for="ch in vol.chapters" :key="ch.chapter_no" class="outline-chapter">
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
            <!-- 未开书：引导开书 -->
            <div v-else class="open-book-cta">
              <div class="cta-title">📖 开书</div>
              <div class="cta-desc">
                生成第一卷大纲（卷 → 章 → 细纲）。配置 LLM key 后走真实模型；否则为 demo 确定性大纲。
              </div>
              <el-input
                v-model="obScenario"
                type="textarea"
                :rows="3"
                resize="none"
                placeholder="开书意图（可选），如：都市修仙 · 废柴崛起"
              />
              <el-button type="primary" class="cta-btn" @click="onOpenBook(false)">开始开书</el-button>
            </div>
          </div>
        </el-tab-pane>
      </el-tabs>
    </el-aside>

    <el-container>
      <el-header class="header">
        <div class="header-left">
          <span class="header-title">{{ project?.title ?? '工作台' }}</span>
          <el-tag v-if="ws.running" type="warning" size="small" effect="dark" class="running-tag">
            写作中{{ ws.task?.progress ? ` · ${ws.task.progress}` : '' }}
          </el-tag>
        </div>
        <div class="header-actions">
          <!-- 开书 / 重新开书 -->
          <el-popconfirm
            v-if="os.hasOutline && !os.running"
            title="重新开书会删除现有大纲并重新生成，确定继续？"
            confirm-button-text="重新开书"
            cancel-button-text="取消"
            @confirm="onOpenBook(true)"
          >
            <template #reference>
              <el-button :disabled="ws.running" plain>🔄 重新开书</el-button>
            </template>
          </el-popconfirm>
          <el-button v-else-if="!os.running" :disabled="ws.running" plain @click="onOpenBook(false)">
            📖 开书
          </el-button>
          <el-button v-else type="danger" plain @click="os.cancel()">取消开书</el-button>
          <el-dropdown v-if="!ws.running" trigger="click">
            <el-button type="primary">
              ✍️ 写下一章 <el-icon class="el-icon--right"><i class="el-icon-arrow-down" /></el-icon>
            </el-button>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item @click="onWriteNext('write_next')">写下一章</el-dropdown-item>
                <el-dropdown-item @click="onWriteNext('daily')">日更循环（连写至大纲末）</el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
          <el-button v-else type="danger" plain @click="onCancel">取消</el-button>
          <el-dropdown @command="onLogout">
            <span class="user-chip">
              <el-avatar :size="26">{{ displayName[0]?.toUpperCase() || 'U' }}</el-avatar>
              <span class="user-name">{{ displayName }}</span>
            </span>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item command="logout">退出登录</el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </div>
      </el-header>

      <!-- 顶部横向 Pipeline：开书三阶段 + 写作四阶段 -->
      <div class="pipeline-zone">
        <PipelineBar
          :stages="OPEN_BOOK_PIPELINE"
          :status="os.stageStatus"
          title="开书"
          clickable
          @retry="onRetryStage"
        />
        <el-segmented
          v-model="os.mode"
          class="ob-mode"
          :disabled="os.running || ws.running"
          :options="[
            { label: '自动入库', value: 'auto' },
            { label: '确认入库', value: 'confirm' },
          ]"
          aria-label="开书模式"
        />
      </div>
      <div v-if="ws.events.length > 0 || ws.running" class="pipeline-zone write">
        <PipelineBar :stages="WRITE_PIPELINE" :status="ws.stageStatus" title="写作" />
      </div>

      <!-- 开书阶段草稿实时流式预览 -->
      <div v-if="os.running && os.currentStage" class="draft-preview">
        <div class="draft-preview-head">
          <span>「{{ currentStageLabel }}」草稿 · 流式预览</span>
          <span class="draft-preview-wc">{{ currentStageText.length }} 字</span>
        </div>
        <pre class="draft-preview-body">{{ currentStageText }}</pre>
      </div>

      <el-main class="main">
        <el-row :gutter="16" class="main-row">
          <!-- 编辑器 -->
          <el-col :span="16">
            <el-card shadow="never" class="editor-card">
              <div class="editor-head">
                <span class="editor-title">
                  第 {{ ws.current?.chapter_no ?? '—' }} 章 · {{ ws.current?.title ?? '等待写作' }}
                </span>
                <span class="editor-wc">{{ ws.currentWordcount }} 字</span>
              </div>
              <el-input
                type="textarea"
                :model-value="ws.currentText"
                :readonly="ws.running"
                :autosize="{ minRows: 22, maxRows: 32 }"
                placeholder="点击「写下一章」，AI 会在这里流式输出正文…"
                resize="none"
                class="editor"
              />
              <div class="editor-foot">
                <span>demo 模式（无 API key）下正文为确定性占位；配置 key 后走真实模型流式。</span>
              </div>
            </el-card>
          </el-col>

          <!-- 侧栏 -->
          <el-col :span="8">
            <el-tabs class="side-tabs">
              <el-tab-pane label="追踪" name="tracking">
                <el-card shadow="never" class="side-card">
                  <div class="kv" v-if="ws.tracking">
                    <div class="kv-row"><span>已提交章节</span><b>{{ ws.tracking.last_committed_chapter }}</b></div>
                    <div class="kv-row"><span>状态修订</span><b>rev {{ ws.tracking.state_revision }}</b></div>
                    <div class="kv-row">
                      <span>视图一致</span>
                      <el-tag :type="ws.tracking.views_consistent ? 'success' : 'danger'" size="small">
                        {{ ws.tracking.views_consistent ? '一致' : '需重建' }}
                      </el-tag>
                    </div>
                  </div>
                  <div class="ctx-label">上下文视图（7 列 ≤12KB）</div>
                  <pre class="ctx-view">{{ ws.contextView?.content || '暂无上下文' }}</pre>
                </el-card>
              </el-tab-pane>
              <el-tab-pane label="Agent 活动" name="agents">
                <AgentActivityPanel :events="ws.events" />
              </el-tab-pane>
            </el-tabs>
          </el-col>
        </el-row>
      </el-main>
    </el-container>

    <!-- confirm 模式：阶段草稿待确认弹窗 -->
    <DraftConfirmDialog
      :visible="os.waiting"
      :stage="os.waitingDraft?.stage ?? ''"
      :content="os.waitingDraft?.content ?? ''"
      @confirm="onConfirmDraft"
      @regenerate="onRegenerateDraft"
      @cancel="os.cancel()"
    />
  </el-container>
</template>

<style scoped>
.layout {
  height: 100vh;
}
.aside {
  background: #1e2530;
  display: flex;
  flex-direction: column;
  color: #cbd5e1;
}
.aside-brand {
  padding: 14px 16px;
  border-bottom: 1px solid #2b3442;
}
.back-btn {
  color: #64748b;
  padding: 0;
  margin-bottom: 6px;
}
.book-title {
  color: #fff;
  font-size: 16px;
  font-weight: 600;
}
.book-meta {
  font-size: 12px;
  color: #64748b;
}
.aside-tabs {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-height: 0;
  padding: 6px 10px 0;
}
.aside-tabs :deep(.el-tabs__header) {
  margin-bottom: 6px;
}
.aside-tabs :deep(.el-tabs__content) {
  flex: 1;
  min-height: 0;
}
.aside-tabs :deep(.el-tab-pane) {
  height: 100%;
}
.pane-scroll {
  height: 100%;
  overflow-y: auto;
}
.vol-collapse {
  border: none;
}
.vol-collapse :deep(.el-collapse-item__header) {
  font-size: 13px;
  background: transparent;
  color: #cbd5e1;
  border-bottom: 1px solid #2b3442;
}
.vol-collapse :deep(.el-collapse-item__wrap) {
  background: transparent;
  border-bottom: none;
}
.vol-collapse :deep(.el-collapse-item__content) {
  color: #cbd5e1;
  padding-bottom: 8px;
}
.outline-chapter {
  padding: 6px 4px;
  border-bottom: 1px dashed #2b3442;
}
.oc-head {
  font-size: 12px;
  font-weight: 600;
  color: #e2e8f0;
}
.oc-summary {
  font-size: 12px;
  color: #94a3b8;
  margin-top: 3px;
  line-height: 1.5;
}
.oc-wc {
  font-size: 11px;
  color: #64748b;
  margin-top: 2px;
}
.oc-points {
  margin: 4px 0 0;
  padding-left: 14px;
}
.oc-points li {
  font-size: 11px;
  color: #94a3b8;
  margin-bottom: 2px;
}
.open-book-cta {
  padding: 4px 2px;
}
.cta-title {
  font-size: 14px;
  font-weight: 600;
  color: #e2e8f0;
  margin-bottom: 8px;
}
.cta-desc {
  font-size: 12px;
  color: #94a3b8;
  line-height: 1.6;
  margin-bottom: 10px;
}
.cta-btn {
  width: 100%;
  margin-top: 10px;
}
.chapter-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 8px;
  border-radius: 6px;
  cursor: pointer;
}
.chapter-item:hover {
  background: #2b3442;
}
.chapter-title {
  flex: 1;
  font-size: 13px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.chapter-wc {
  font-size: 11px;
  color: #64748b;
}
.tree-empty {
  font-size: 12px;
  color: #64748b;
  text-align: center;
  padding: 24px 0;
}
.pipeline-zone {
  display: flex;
  align-items: center;
  gap: 16px;
  background: #fff;
  border-bottom: 1px solid #eef2f7;
  padding: 8px 20px;
}
.pipeline-zone.write {
  padding-top: 0;
  border-top: 1px dashed #eef2f7;
}
.ob-mode {
  flex-shrink: 0;
}
.draft-preview {
  background: #fff;
  border-bottom: 1px solid #eef2f7;
  padding: 6px 20px 12px;
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
  background: #f8fafc;
  border: 1px solid #eef2f7;
  border-radius: 8px;
  padding: 10px;
  font-size: 12px;
  line-height: 1.7;
  color: #334155;
  font-family: 'Songti SC', 'SimSun', Georgia, serif;
  margin: 0;
}
.header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  background: #fff;
  border-bottom: 1px solid #e5e7eb;
}
.header-left {
  display: flex;
  align-items: center;
  gap: 10px;
}
.header-title {
  font-size: 16px;
  font-weight: 600;
  color: #1f2937;
}
.running-tag {
  max-width: 380px;
}
.header-actions {
  display: flex;
  align-items: center;
  gap: 12px;
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
.main-row {
  height: 100%;
}
.editor-card {
  min-height: 72vh;
}
.editor-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 10px;
}
.editor-title {
  font-size: 15px;
  font-weight: 600;
  color: #1f2937;
}
.editor-wc {
  color: #6b7280;
  font-size: 13px;
}
.editor :deep(.el-textarea__inner) {
  font-family: 'Songti SC', 'SimSun', Georgia, serif;
  font-size: 15px;
  line-height: 1.9;
  color: #1f2937;
}
.editor-foot {
  margin-top: 8px;
  font-size: 12px;
  color: #9ca3af;
}
.side-card {
  margin-top: 4px;
}
.kv-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 6px 0;
  font-size: 13px;
  color: #374151;
  border-bottom: 1px dashed #eef2f7;
}
.ctx-label {
  margin: 12px 0 6px;
  font-size: 12px;
  color: #64748b;
  font-weight: 600;
}
.ctx-view {
  max-height: 320px;
  overflow-y: auto;
  white-space: pre-wrap;
  word-break: break-all;
  background: #f8fafc;
  border: 1px solid #eef2f7;
  border-radius: 8px;
  padding: 10px;
  font-size: 12px;
  color: #475569;
  font-family: inherit;
  margin: 0;
}
.side-tabs {
  height: 100%;
}
</style>
