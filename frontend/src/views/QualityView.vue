<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import AgentActivityPanel from '@/components/AgentActivityPanel.vue'
import { useAuthStore } from '@/stores/auth'
import { useProjectsStore } from '@/stores/projects'
import { useQualityStore } from '@/stores/quality'

const route = useRoute()
const auth = useAuthStore()
const projectsStore = useProjectsStore()
const quality = useQualityStore()

const pid = ref<number | null>(null)
const chapterNo = ref<number | null>(null)
const mode = ref('full')

// 供 ChapterView「审查 / 去味」跳转预选（?project=&chapter=）
const selectedPid = computed(() => Number(route.query.project) || null)
const selectedChapter = computed(() => Number(route.query.chapter) || null)

const currentChapter = computed(() =>
  quality.chapters.find((c) => c.chapter_no === chapterNo.value) ?? null,
)
const latestReview = computed(() => quality.reviews[0] ?? null)

const severityTag: Record<string, string> = { blocking: 'danger', warning: 'warning' }

async function onProjectChange() {
  chapterNo.value = null
  quality.reset()
  if (pid.value) await quality.loadChapters(pid.value)
}

async function onChapterChange() {
  if (!pid.value || !chapterNo.value) return
  quality.reset()
  await quality.loadAll(pid.value, chapterNo.value)
}

async function onRunReview() {
  if (!pid.value || !chapterNo.value) return
  try {
    await quality.runReview(pid.value, chapterNo.value, mode.value)
    ElMessage.info('审查任务已启动')
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || '启动审查失败')
  }
}

async function onRunDeslop() {
  if (!pid.value || !chapterNo.value) return
  try {
    await quality.runDeslop(pid.value, chapterNo.value)
    ElMessage.info('去味任务已启动')
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || '启动去味失败')
  }
}

async function onAcceptDeslop() {
  if (!pid.value || !chapterNo.value) return
  try {
    await quality.acceptDeslop(pid.value, chapterNo.value)
    ElMessage.success('已接受去味结果并提交章节')
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || '接受失败')
  }
}

onMounted(async () => {
  if (!auth.user) await auth.fetchMe()
  await projectsStore.fetchList()
  // 路由 query 预选：有 project 参数则联动预载项目与章节
  if (!selectedPid.value) return
  pid.value = selectedPid.value
  try {
    await quality.loadChapters(pid.value)
    if (selectedChapter.value) {
      chapterNo.value = selectedChapter.value
      await quality.loadAll(pid.value, chapterNo.value)
    }
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || '加载章节数据失败')
  }
})
</script>

<template>
  <div class="page-container">
    <div class="page-header">
      <h1 class="page-title">审查 · 去味</h1>
    </div>

    <el-row :gutter="16" class="layout-row">
      <!-- 左列：选择项目 / 章节 / 审查模式 -->
      <el-col :span="7">
        <div class="section-card">
          <h3 class="section-title">📁 选择项目与章节</h3>
          <el-select
            v-model="pid"
            placeholder="选择项目"
            class="mb w-full"
            filterable
            @change="onProjectChange"
          >
            <el-option v-for="p in projectsStore.projects" :key="p.id" :label="p.title" :value="p.id">
              <span>{{ p.title }}</span>
              <span class="option-slug">{{ p.slug }}</span>
            </el-option>
          </el-select>
          <el-select
            v-model="chapterNo"
            placeholder="选择章节"
            class="w-full"
            :disabled="!pid"
            @change="onChapterChange"
          >
            <el-option
              v-for="c in quality.chapters"
              :key="c.chapter_no"
              :label="`第 ${c.chapter_no} 章 · ${c.wordcount} 字 · ${c.status}`"
              :value="c.chapter_no"
            />
          </el-select>

          <div class="mode-line">
            <span class="mode-label">审查模式</span>
            <el-radio-group v-model="mode">
              <el-radio-button value="full">全量</el-radio-button>
              <el-radio-button value="lean">精简</el-radio-button>
              <el-radio-button value="solo">单评审</el-radio-button>
            </el-radio-group>
          </div>

          <div v-if="quality.running" class="running-line">
            <el-tag type="warning" effect="dark" size="small">
              运行中{{ quality.task?.progress ? ` · ${quality.task.progress}` : '' }}
            </el-tag>
            <el-button size="small" text @click="quality.cancel()">取消</el-button>
          </div>
        </div>

        <div class="section-card">
          <h3 class="section-title">📄 当前章节</h3>
          <div v-if="!currentChapter" class="empty">先选择章节</div>
          <div v-else>
            <div class="ch-meta">第 {{ currentChapter.chapter_no }} 章</div>
            <div class="ch-sub">{{ currentChapter.wordcount }} 字 · {{ currentChapter.status }} · rev {{ currentChapter.revision }}</div>
          </div>
        </div>
      </el-col>

      <!-- 右列：审查 / 去味结果 -->
      <el-col :span="17">
        <div class="section-card detail-card">
          <div class="detail-head">
            <span class="detail-book-title">
              {{ currentChapter ? `第 ${currentChapter.chapter_no} 章` : '审查 · 去味' }}
            </span>
            <div class="detail-head-right">
              <el-tag v-if="quality.running" type="warning" size="small" effect="dark">
                运行中{{ quality.task?.progress ? ` · ${quality.task.progress}` : '' }}
              </el-tag>
            </div>
          </div>

          <!-- 运行中实时展示 Agent 活动 -->
          <div v-if="quality.running" class="running-panel">
            <h3 class="section-title">🤖 Agent 活动</h3>
            <AgentActivityPanel :events="quality.events" />
          </div>

          <el-tabs v-if="currentChapter" class="result-tabs">
            <!-- 审查 -->
            <el-tab-pane label="🔍 审查结果" name="review">
              <div class="toolbar">
                <el-button type="primary" :loading="quality.running" @click="onRunReview">跑审查</el-button>
              </div>

              <el-empty v-if="quality.reviews.length === 0" description="尚未审查该章节" />
              <div v-else class="review-wrap">
                <div class="verdict-row">
                  <el-tag :type="(latestReview?.score ?? 0) >= 80 ? 'success' : (latestReview?.score ?? 0) >= 60 ? 'warning' : 'danger'" effect="dark" size="large">
                    {{ latestReview?.score }} 分 · {{ latestReview?.verdict }}
                  </el-tag>
                  <span class="rev-meta">{{ latestReview?.mode }} · {{ latestReview?.created_at }}</span>
                </div>
                <pre v-if="latestReview?.summary" class="summary">{{ latestReview.summary }}</pre>

                <div v-if="latestReview?.findings?.length">
                  <div class="section-label">findings（{{ latestReview.findings.length }} 条）</div>
                  <div v-for="(f, i) in latestReview.findings" :key="i" class="finding">
                    <div class="finding-head">
                      <el-tag size="small" :type="severityTag[f.severity] ?? 'info'">{{ f.severity }}</el-tag>
                      <el-tag size="small" type="primary" effect="plain">{{ f.reviewer }}</el-tag>
                      <span class="finding-type">{{ f.type }}</span>
                    </div>
                    <div class="finding-quote">「{{ f.quote }}」</div>
                    <div class="finding-reason">{{ f.reason }}</div>
                    <div v-if="f.suggestion" class="finding-suggest">建议：{{ f.suggestion }}</div>
                  </div>
                </div>
                <el-empty v-else description="未发现问题，写得不错" :image-size="60" />
              </div>
            </el-tab-pane>

            <!-- 去味 -->
            <el-tab-pane label="🧹 去味对照" name="deslop">
              <div class="toolbar">
                <el-button type="primary" plain :loading="quality.running" @click="onRunDeslop">一键去味</el-button>
                <el-button
                  v-if="quality.deslop?.ready"
                  type="success"
                  :disabled="quality.running"
                  @click="onAcceptDeslop"
                >
                  接受并提交
                </el-button>
              </div>

              <el-empty v-if="!quality.deslop" description="先去味该章节" />
              <el-empty
                v-else-if="!quality.deslop.ready"
                :description="quality.deslop.reason || '尚无去味结果'"
              />
              <div v-else>
                <div class="grade-row">
                  <el-tag type="primary" effect="dark" size="large">Gate {{ quality.deslop.grade }}</el-tag>
                  <span class="rev-meta">{{ quality.deslop.score }} 分 · 共 {{ quality.deslop.findings?.length ?? 0 }} 处问题</span>
                </div>
                <div class="wc-row">
                  <span>原文 {{ quality.deslop.original_wordcount }} 字</span>
                  <span>→</span>
                  <span>改写 {{ quality.deslop.new_wordcount }} 字</span>
                  <el-tag size="small" :type="(quality.deslop.delta_wordcount ?? 0) < 0 ? 'success' : 'info'">
                    变化 {{ (quality.deslop.delta_wordcount ?? 0) > 0 ? '+' : '' }}{{ quality.deslop.delta_wordcount ?? 0 }}
                  </el-tag>
                </div>

                <el-row :gutter="12" class="diff-row">
                  <el-col :span="12">
                    <div class="diff-head">原文</div>
                    <pre class="diff-body original">{{ quality.deslop.original }}</pre>
                  </el-col>
                  <el-col :span="12">
                    <div class="diff-head">去味后</div>
                    <pre class="diff-body rewritten">{{ quality.deslop.rewritten }}</pre>
                  </el-col>
                </el-row>
              </div>
            </el-tab-pane>

            <!-- Agent 活动 -->
            <el-tab-pane label="🤖 Agent 活动" name="agents">
              <AgentActivityPanel :events="quality.events" />
            </el-tab-pane>
          </el-tabs>

          <el-empty v-else class="empty-big" description="选择项目与章节后在此审查 / 去味" />
        </div>
      </el-col>
    </el-row>
  </div>
</template>

<style scoped>
.layout-row {
  align-items: flex-start;
}
.mb {
  margin-bottom: var(--space-sm);
}
.w-full {
  width: 100%;
}
.option-slug {
  float: right;
  color: var(--color-text-secondary);
  font-size: var(--font-size-xs);
}
.mode-line {
  display: flex;
  align-items: center;
  gap: var(--space-sm);
  margin-top: var(--space-md);
}
.mode-label {
  font-size: var(--font-size-sm);
  color: var(--color-text-secondary);
  flex-shrink: 0;
}
.running-line {
  margin-top: var(--space-md);
  display: flex;
  align-items: center;
  gap: var(--space-sm);
}
.empty {
  color: var(--color-text-secondary);
  font-size: var(--font-size-xs);
  text-align: center;
  padding: var(--space-md) 0;
}
.ch-meta {
  font-weight: 600;
  font-size: var(--font-size-md);
  color: var(--color-text-primary);
  margin-bottom: var(--space-xs);
}
.ch-sub {
  font-size: var(--font-size-sm);
  color: var(--color-text-secondary);
}
.detail-card {
  min-height: 70vh;
}
.detail-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: var(--space-sm);
  flex-wrap: wrap;
  padding-bottom: var(--space-sm);
  border-bottom: 1px solid var(--color-border-light);
  margin-bottom: var(--space-md);
}
.detail-book-title {
  font-weight: 600;
  font-size: var(--font-size-lg);
  color: var(--color-text-primary);
}
.detail-head-right {
  display: flex;
  align-items: center;
  gap: var(--space-sm);
}
.running-panel {
  border: 1px solid var(--color-border-light);
  border-radius: var(--radius-md);
  background: var(--color-bg-page);
  padding: var(--space-md);
  margin-bottom: var(--space-md);
}
.result-tabs {
  min-height: 60vh;
}
.toolbar {
  display: flex;
  align-items: center;
  gap: var(--space-sm);
  margin-bottom: var(--space-md);
}
.review-wrap {
  border: 1px solid var(--color-border-light);
  border-radius: var(--radius-md);
  padding: var(--space-md);
  background: var(--color-bg-card);
}
.verdict-row {
  display: flex;
  align-items: center;
  gap: var(--space-sm);
  margin-bottom: 10px;
}
.rev-meta {
  font-size: var(--font-size-xs);
  color: var(--color-text-secondary);
}
.summary {
  white-space: pre-wrap;
  font-family: inherit;
  font-size: var(--font-size-sm);
  line-height: 1.8;
  color: var(--color-text-regular);
  background: var(--color-bg-page);
  border: 1px solid var(--color-border-light);
  border-radius: var(--radius-md);
  padding: 10px var(--space-md);
  margin: 0 0 var(--space-md);
}
.section-label {
  font-size: var(--font-size-xs);
  color: var(--color-text-secondary);
  margin-bottom: var(--space-sm);
}
.finding {
  border: 1px solid var(--color-border-light);
  border-radius: var(--radius-md);
  padding: var(--space-sm) 10px;
  margin-bottom: var(--space-sm);
}
.finding-head {
  display: flex;
  align-items: center;
  gap: var(--space-sm);
  margin-bottom: var(--space-xs);
}
.finding-type {
  font-size: var(--font-size-xs);
  color: var(--color-text-regular);
}
.finding-quote {
  font-size: var(--font-size-sm);
  color: #b45309;
  background: #fff7ed;
  border-radius: var(--radius-sm);
  padding: 2px 6px;
  margin-bottom: var(--space-xs);
}
.finding-reason {
  font-size: var(--font-size-sm);
  color: var(--color-text-regular);
  line-height: 1.6;
}
.finding-suggest {
  font-size: var(--font-size-xs);
  color: #059669;
  margin-top: 2px;
}
.grade-row {
  display: flex;
  align-items: center;
  gap: var(--space-sm);
  margin-bottom: var(--space-sm);
}
.wc-row {
  display: flex;
  align-items: center;
  gap: var(--space-sm);
  font-size: var(--font-size-sm);
  color: var(--color-text-regular);
  margin-bottom: var(--space-md);
}
.diff-row {
  margin-top: var(--space-sm);
}
.diff-head {
  font-size: var(--font-size-xs);
  font-weight: 600;
  color: var(--color-text-secondary);
  margin-bottom: 6px;
}
.diff-body {
  white-space: pre-wrap;
  word-break: break-all;
  font-family: inherit;
  font-size: var(--font-size-sm);
  line-height: 1.8;
  border-radius: var(--radius-md);
  padding: var(--space-md);
  margin: 0;
  height: 52vh;
  overflow-y: auto;
}
.diff-body.original {
  background: #fff7ed;
  border: 1px solid #fed7aa;
  color: #7c2d12;
}
.diff-body.rewritten {
  background: #f0fdf4;
  border: 1px solid #bbf7d0;
  color: #14532d;
}
.empty-big {
  margin-top: 15vh;
}
</style>
