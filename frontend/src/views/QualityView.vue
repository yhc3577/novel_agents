<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import AgentActivityPanel from '@/components/AgentActivityPanel.vue'
import { useAuthStore } from '@/stores/auth'
import { useProjectsStore } from '@/stores/projects'
import { useQualityStore } from '@/stores/quality'

const auth = useAuthStore()
const projectsStore = useProjectsStore()
const quality = useQualityStore()
const router = useRouter()

const displayName = computed(() => auth.user?.display_name || auth.user?.username || '')

const pid = ref<number | null>(null)
const chapterNo = ref<number | null>(null)
const mode = ref('full')

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

function onLogout() {
  auth.logout()
  router.push('/login')
}

onMounted(async () => {
  if (!auth.user) await auth.fetchMe()
  await projectsStore.fetchList()
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
        <el-menu-item index="/dashboard">工作台</el-menu-item>
        <el-menu-item index="/analysis">拆文库</el-menu-item>
        <el-menu-item index="/quality">审查 / 去味</el-menu-item>
        <el-menu-item index="/scan">扫榜</el-menu-item>
        <el-menu-item index="/settings">设置</el-menu-item>
      </el-menu>
    </el-aside>

    <el-container>
      <el-header class="header">
        <div class="header-title">审查 · 去味 · 已提交章节质量体检</div>
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
        <el-row :gutter="16">
          <!-- 选择区 -->
          <el-col :span="7">
            <el-card shadow="never" class="sel-card">
              <template #header>① 选择项目与章节</template>
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
              <div v-if="quality.running" class="running-line">
                <el-tag type="warning" effect="dark" size="small">
                  运行中{{ quality.task?.progress ? ` · ${quality.task.progress}` : '' }}
                </el-tag>
                <el-button size="small" text @click="quality.cancel()">取消</el-button>
              </div>
            </el-card>

            <el-card shadow="never" class="sel-card">
              <template #header>当前章节</template>
              <div v-if="!currentChapter" class="empty">先选择章节</div>
              <div v-else>
                <div class="ch-meta">第 {{ currentChapter.chapter_no }} 章</div>
                <div class="ch-sub">{{ currentChapter.wordcount }} 字 · {{ currentChapter.status }} · rev {{ currentChapter.revision }}</div>
              </div>
            </el-card>
          </el-col>

          <!-- 结果区 -->
          <el-col :span="17">
            <el-tabs v-if="currentChapter" class="result-tabs">
              <!-- 审查 -->
              <el-tab-pane label="🔍 审查" name="review">
                <div class="toolbar">
                  <el-radio-group v-model="mode">
                    <el-radio-button value="full">全量（4 评审）</el-radio-button>
                    <el-radio-button value="lean">精简</el-radio-button>
                    <el-radio-button value="solo">单评审</el-radio-button>
                  </el-radio-group>
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
              <el-tab-pane label="🧹 去味" name="deslop">
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
          </el-col>
        </el-row>
      </el-main>
    </el-container>
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
.header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  background: #fff;
  border-bottom: 1px solid #e5e7eb;
}
.header-title {
  font-size: 15px;
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
.sel-card {
  margin-bottom: 16px;
}
.mb {
  margin-bottom: 12px;
}
.w-full {
  width: 100%;
}
.option-slug {
  float: right;
  color: #9ca3af;
  font-size: 12px;
}
.running-line {
  margin-top: 12px;
  display: flex;
  align-items: center;
  gap: 8px;
}
.empty {
  color: #9ca3af;
  font-size: 13px;
  text-align: center;
  padding: 12px 0;
}
.ch-meta {
  font-weight: 600;
  font-size: 14px;
  color: #1f2937;
  margin-bottom: 4px;
}
.ch-sub {
  font-size: 13px;
  color: #6b7280;
}
.result-tabs {
  min-height: 70vh;
}
.toolbar {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 14px;
}
.review-wrap {
  border: 1px solid #eef2f7;
  border-radius: 10px;
  padding: 14px;
  background: #fff;
}
.verdict-row {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 10px;
}
.rev-meta {
  font-size: 12px;
  color: #6b7280;
}
.summary {
  white-space: pre-wrap;
  font-family: inherit;
  font-size: 13px;
  line-height: 1.8;
  color: #334155;
  background: #f8fafc;
  border: 1px solid #eef2f7;
  border-radius: 8px;
  padding: 10px 12px;
  margin: 0 0 12px;
}
.section-label {
  font-size: 12px;
  color: #6b7280;
  margin-bottom: 8px;
}
.finding {
  border: 1px solid #eef2f7;
  border-radius: 8px;
  padding: 8px 10px;
  margin-bottom: 8px;
}
.finding-head {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 4px;
}
.finding-type {
  font-size: 12px;
  color: #475569;
}
.finding-quote {
  font-size: 13px;
  color: #b45309;
  background: #fff7ed;
  border-radius: 4px;
  padding: 2px 6px;
  margin-bottom: 4px;
}
.finding-reason {
  font-size: 13px;
  color: #334155;
  line-height: 1.6;
}
.finding-suggest {
  font-size: 12px;
  color: #059669;
  margin-top: 2px;
}
.grade-row {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 8px;
}
.wc-row {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  color: #475569;
  margin-bottom: 14px;
}
.diff-row {
  margin-top: 8px;
}
.diff-head {
  font-size: 12px;
  font-weight: 600;
  color: #6b7280;
  margin-bottom: 6px;
}
.diff-body {
  white-space: pre-wrap;
  word-break: break-all;
  font-family: inherit;
  font-size: 13px;
  line-height: 1.8;
  border-radius: 8px;
  padding: 12px;
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
