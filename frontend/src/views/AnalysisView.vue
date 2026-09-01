<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import AgentActivityPanel from '@/components/AgentActivityPanel.vue'
import { useAnalysisStore } from '@/stores/analysis'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const router = useRouter()
const store = useAnalysisStore()

const form = reactive({ title: '', genre: '', source_text: '' })
const selectedId = ref<number | null>(null)

const selectedBook = computed(() => store.books.find((b) => b.id === selectedId.value) ?? null)
const stageDone = computed(() =>
  store.snapshot ? Object.values(store.snapshot.progress).filter((s) => s === 'done').length : 0,
)
const stageTotal = computed(() => (store.snapshot ? Object.keys(store.snapshot.progress).length : 7))

async function onUpload() {
  if (!form.title.trim() || !form.source_text.trim()) {
    ElMessage.warning('请填写书名与正文')
    return
  }
  try {
    const book = await store.createAndRun({
      title: form.title,
      genre: form.genre || undefined,
      source_text: form.source_text,
    })
    selectedId.value = book.id
    ElMessage.info('已上传，拆解任务运行中…')
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || '上传失败')
  }
}

function onSelectBook(bid: number) {
  selectedId.value = bid
  void store.loadSnapshot(bid)
}

async function onAnalyze() {
  if (!selectedId.value || store.running) return
  await store.runAnalyze(selectedId.value)
}

async function onImport() {
  if (!selectedId.value) return
  try {
    const r = await store.importBook(selectedId.value)
    ElMessage.success(`已导入为可写项目 → ${r.slug}`)
    router.push(`/projects/${r.project_id}`)
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || '导入失败')
  }
}

onMounted(async () => {
  if (!auth.user) await auth.fetchMe()
  await store.fetchList()
})
</script>

<template>
  <div class="page-container">
    <el-row :gutter="16">
      <!-- 上传 -->
      <el-col :span="8">
        <el-card shadow="never" class="upload-card">
          <template #header>📤 上传整本书</template>
          <el-input v-model="form.title" placeholder="书名，如：仙路问道" maxlength="128" class="mb" />
          <el-input v-model="form.genre" placeholder="题材（可选），如：玄幻" maxlength="64" class="mb" />
          <el-input
            v-model="form.source_text"
            type="textarea"
            :rows="16"
            placeholder="粘贴整本书 txt 文本（按「第X章」自动切章）…"
          />
          <el-button type="primary" class="upload-btn" :loading="store.running" @click="onUpload">
            上传并拆解
          </el-button>
        </el-card>

        <!-- 书列表 -->
        <el-card shadow="never" class="list-card">
          <template #header>我的拆文书（{{ store.books.length }}）</template>
          <div v-if="store.books.length === 0" class="empty">还没有拆文书</div>
          <div
            v-for="b in store.books"
            :key="b.id"
            class="book-row"
            :class="{ active: b.id === selectedId }"
            @click="onSelectBook(b.id)"
          >
            <div class="book-row-head">
              <span class="book-title">{{ b.title }}</span>
              <el-tag :type="b.status === 'done' ? 'success' : b.status === 'imported' ? 'primary' : 'info'" size="small">
                {{ b.status }}
              </el-tag>
            </div>
            <div class="book-row-foot">
              <el-button size="small" :disabled="store.running" @click.stop="onAnalyze">拆解</el-button>
              <el-button size="small" type="success" :loading="store.importing" @click.stop="onImport">一键导入</el-button>
            </div>
          </div>
        </el-card>
      </el-col>

      <!-- 拆解结果 -->
      <el-col :span="16">
        <el-card shadow="never" class="detail-card" v-loading="!store.snapshot">
          <template #header>
            <div class="detail-head">
              <span>{{ selectedBook?.title ?? '请选择或上传一本书' }}</span>
              <div class="detail-head-right">
                <span v-if="store.snapshot" class="stage-pct">{{ stageDone }}/{{ stageTotal }} 阶段完成</span>
                <el-tag v-if="store.running" type="warning" size="small" effect="dark">
                  拆解中{{ store.task?.progress ? ` · ${store.task.progress}` : '' }}
                </el-tag>
              </div>
            </div>
          </template>

          <el-tabs v-if="store.snapshot">
            <el-tab-pane label="报告" name="report">
              <pre class="report">{{ store.snapshot.aggregates['report'] || '报告生成中…' }}</pre>
            </el-tab-pane>
            <el-tab-pane label="分维聚合" name="aggregates">
              <el-collapse v-for="k in Object.keys(store.snapshot.aggregates).filter((x) => x !== 'report')" :key="k">
                <el-collapse-item :title="`${k} · ${store.snapshot.aggregates[k]?.length ?? 0} 字`">
                  <pre class="agg">{{ store.snapshot.aggregates[k] }}</pre>
                </el-collapse-item>
              </el-collapse>
            </el-tab-pane>
            <el-tab-pane label="章节提取" name="chapters">
              <div v-for="c in store.snapshot.chapters" :key="c.chapter_no" class="chapter-card">
                <div class="chapter-head">第 {{ c.chapter_no }} 章</div>
                <div class="chapter-summary">{{ c.summary }}</div>
                <div class="beats">
                  <el-tag v-for="(bt, i) in c.beats" :key="i" size="small" class="beat">{{ bt }}</el-tag>
                </div>
              </div>
            </el-tab-pane>
            <el-tab-pane label="Agent 活动" name="agents">
              <AgentActivityPanel :events="store.events" />
            </el-tab-pane>
          </el-tabs>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<style scoped>
.mb {
  margin-bottom: 10px;
}
.upload-btn {
  margin-top: 12px;
  width: 100%;
}
.list-card {
  margin-top: 16px;
}
.empty {
  color: #9ca3af;
  font-size: 12px;
  text-align: center;
  padding: 16px 0;
}
.book-row {
  padding: 8px 10px;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  margin-bottom: 8px;
  cursor: pointer;
}
.book-row.active {
  border-color: var(--brand);
  background: #f0f7ff;
}
.book-row-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 6px;
}
.book-title {
  font-weight: 600;
  font-size: 14px;
  color: #1f2937;
}
.book-row-foot {
  display: flex;
  gap: 6px;
}
.detail-card {
  min-height: 70vh;
}
.detail-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.detail-head-right {
  display: flex;
  align-items: center;
  gap: 10px;
}
.stage-pct {
  font-size: 12px;
  color: #6b7280;
}
.report {
  white-space: pre-wrap;
  word-break: break-all;
  font-family: inherit;
  background: #f8fafc;
  border: 1px solid #eef2f7;
  border-radius: 8px;
  padding: 12px;
  font-size: 13px;
  line-height: 1.8;
  color: #334155;
}
.agg {
  white-space: pre-wrap;
  word-break: break-all;
  font-family: inherit;
  font-size: 13px;
  line-height: 1.7;
  color: #334155;
  margin: 0;
}
.chapter-card {
  border: 1px solid #eef2f7;
  border-radius: 8px;
  padding: 10px 12px;
  margin-bottom: 10px;
}
.chapter-head {
  font-weight: 600;
  font-size: 13px;
  color: #1f2937;
  margin-bottom: 4px;
}
.chapter-summary {
  font-size: 13px;
  color: #475569;
  margin-bottom: 6px;
}
.beats {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}
.beat {
  max-width: 100%;
}
</style>
