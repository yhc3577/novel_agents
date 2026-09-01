<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import AgentActivityPanel from '@/components/AgentActivityPanel.vue'
import { useAuthStore } from '@/stores/auth'
import { useScanStore } from '@/stores/scan'

const auth = useAuthStore()
const scan = useScanStore()

const activeTab = ref('dashboard')

const PLATFORM_NAMES: Record<string, string> = { qidian: '起点', fanqie: '番茄' }

async function onRunScan() {
  try {
    await scan.runScan()
    ElMessage.info('扫榜任务已启动（起点 + 番茄）')
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || '启动扫榜失败')
  }
}

function fmtTime(iso: string | null): string {
  if (!iso) return ''
  return new Date(iso).toLocaleString('zh-CN', { hour12: false })
}

onMounted(async () => {
  if (!auth.user) await auth.fetchMe()
  await scan.loadLatest()
})
</script>

<template>
  <div class="page-container">
    <div class="page-header">
      <h1 class="page-title">扫榜</h1>
      <div class="toolbar">
        <el-button type="primary" :loading="scan.running" @click="onRunScan">🚀 扫榜</el-button>
        <el-button :disabled="!scan.platforms.length" @click="scan.loadLatest()">刷新</el-button>
        <el-tag v-if="scan.running" type="warning" effect="dark" size="small">
          扫榜中{{ scan.task?.progress ? ` · ${scan.task.progress}` : '' }}
        </el-tag>
        <el-button v-if="scan.running" size="small" text @click="scan.cancel()">取消</el-button>
      </div>
    </div>

    <el-tabs v-model="activeTab" class="scan-tabs">
      <!-- 榜单视图 -->
      <el-tab-pane label="📊 榜单视图" name="dashboard">
        <el-empty v-if="!scan.platforms.length" description="尚无扫榜结果，点击「扫榜」抓取两平台榜单" />
        <div v-else class="platform-grid">
          <div v-for="p in scan.platforms" :key="p.platform" class="section-card">
            <div class="plat-head">
              <span class="plat-name">{{ PLATFORM_NAMES[p.platform] ?? p.platform }}</span>
              <span class="plat-time">{{ fmtTime(p.snapshot_at) }}</span>
            </div>
            <template v-if="p.cleaned">
              <!-- 选题决策 -->
              <div class="decision-card">
                <div class="decision-title">🎯 选题决策</div>
                <div class="decision-topic">{{ p.cleaned.topic_decision.topic }}</div>
                <div class="decision-meta">
                  <el-tag size="small" type="primary">{{ p.cleaned.topic_decision.genre }}</el-tag>
                  <el-tag size="small" type="warning">{{ p.cleaned.topic_decision.hot_tag }}</el-tag>
                  <span class="decision-count">{{ p.cleaned.stats.total }} 本有效</span>
                </div>
                <div class="decision-ratio">{{ p.cleaned.topic_decision.rationale }}</div>
                <ul class="hooks">
                  <li v-for="(h, i) in p.cleaned.topic_decision.hooks" :key="i">{{ h }}</li>
                </ul>
                <div v-if="p.cleaned.topic_decision.risk" class="decision-risk">风险：{{ p.cleaned.topic_decision.risk }}</div>
              </div>

              <!-- 题材分布 -->
              <div class="sub-section">
                <h3 class="section-title sub-title">题材分布</h3>
                <div class="chip-wrap">
                  <div v-for="g in p.cleaned.stats.genre_distribution" :key="g.genre" class="genre-chip">
                    <span class="genre-name">{{ g.genre }}</span>
                    <span class="genre-meta">{{ g.count }} 本 · 均增 {{ g.avg_growth }}</span>
                  </div>
                </div>
              </div>

              <!-- 热词 -->
              <div class="sub-section">
                <h3 class="section-title sub-title">热词</h3>
                <div class="chip-wrap">
                  <el-tag v-for="h in p.cleaned.stats.hot_tags.slice(0, 10)" :key="h.tag" size="small" effect="plain" class="tag-chip">
                    {{ h.tag }} ×{{ h.count }}
                  </el-tag>
                </div>
              </div>

              <!-- 头部增速 -->
              <div class="sub-section">
                <h3 class="section-title sub-title">头部增速 Top</h3>
                <div v-for="(t, i) in p.cleaned.stats.top_books" :key="i" class="top-line">
                  <span class="top-idx">{{ i + 1 }}</span>
                  <span>{{ t }}</span>
                </div>
              </div>

              <!-- 榜单表格 -->
              <div class="sub-section">
                <h3 class="section-title sub-title">榜单 Top {{ Math.min(10, p.cleaned.books.length) }}</h3>
                <el-table :data="p.cleaned.books.slice(0, 10)" size="small">
                  <el-table-column prop="rank" label="#" width="40" />
                  <el-table-column prop="title" label="书名" min-width="140" show-overflow-tooltip />
                  <el-table-column prop="genre" label="题材" width="56" />
                  <el-table-column prop="words" label="万字" width="52" />
                  <el-table-column prop="followers" label="收藏" width="72" />
                  <el-table-column label="7日增" width="64">
                    <template #default="{ row }">
                      <span class="growth">{{ row.growth_7d }}</span>
                    </template>
                  </el-table-column>
                  <el-table-column label="标签" min-width="120">
                    <template #default="{ row }">
                      <el-tag v-for="tg in row.tags.slice(0, 2)" :key="tg" size="small" effect="plain" class="table-tag">{{ tg }}</el-tag>
                    </template>
                  </el-table-column>
                </el-table>
              </div>

              <!-- 报告 -->
              <div class="sub-section">
                <h3 class="section-title sub-title">扫榜报告</h3>
                <pre class="report">{{ p.report }}</pre>
              </div>
            </template>
          </div>
        </div>
      </el-tab-pane>

      <!-- 历史 -->
      <el-tab-pane label="🗂 历史快照" name="history">
        <el-empty v-if="!scan.history.length" description="暂无历史扫榜记录" />
        <div v-else class="section-card">
          <el-table :data="scan.history" size="small">
            <el-table-column prop="id" label="ID" width="60" />
            <el-table-column label="平台" width="80">
              <template #default="{ row }">{{ PLATFORM_NAMES[row.platform] ?? row.platform }}</template>
            </el-table-column>
            <el-table-column label="时间" width="180">
              <template #default="{ row }">{{ fmtTime(row.snapshot_at) }}</template>
            </el-table-column>
            <el-table-column label="有效作品" width="90">
              <template #default="{ row }">{{ row.cleaned?.stats?.total ?? 0 }}</template>
            </el-table-column>
            <el-table-column label="选题决策" min-width="220">
              <template #default="{ row }">{{ row.cleaned?.topic_decision?.topic ?? '—' }}</template>
            </el-table-column>
          </el-table>
        </div>
      </el-tab-pane>

      <!-- Agent 活动 -->
      <el-tab-pane label="🤖 Agent 活动" name="agents">
        <AgentActivityPanel :events="scan.events" />
      </el-tab-pane>
    </el-tabs>
  </div>
</template>

<style scoped>
.toolbar {
  display: flex;
  align-items: center;
  gap: var(--space-sm);
}
.scan-tabs {
  min-height: 72vh;
}
.platform-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(480px, 1fr));
  gap: var(--space-lg);
  align-items: start;
}
.plat-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding-bottom: var(--space-sm);
  border-bottom: 1px solid var(--color-border-light);
  margin-bottom: var(--space-md);
}
.plat-name {
  font-weight: 600;
  font-size: var(--font-size-lg);
  color: var(--color-text-primary);
}
.plat-time {
  font-size: var(--font-size-xs);
  color: var(--color-text-secondary);
}
.decision-card {
  background: linear-gradient(135deg, var(--color-primary-lighter), var(--color-bg-card));
  border: 1px solid var(--color-primary-light);
  border-radius: var(--radius-md);
  padding: var(--space-md) var(--space-lg);
  margin-bottom: var(--space-md);
}
.decision-title {
  font-size: var(--font-size-xs);
  color: var(--color-primary);
  font-weight: 600;
  margin-bottom: 6px;
}
.decision-topic {
  font-size: 18px;
  font-weight: 700;
  color: var(--color-text-primary);
  margin-bottom: 6px;
}
.decision-meta {
  display: flex;
  align-items: center;
  gap: var(--space-sm);
  margin-bottom: 6px;
  flex-wrap: wrap;
}
.decision-count {
  font-size: var(--font-size-xs);
  color: var(--color-text-secondary);
}
.decision-ratio {
  font-size: var(--font-size-sm);
  color: var(--color-text-regular);
  line-height: 1.6;
  margin-bottom: 6px;
}
.hooks {
  margin: 0;
  padding-left: 18px;
  font-size: var(--font-size-sm);
  color: var(--color-text-regular);
  line-height: 1.7;
}
.decision-risk {
  font-size: var(--font-size-xs);
  color: var(--color-warning);
  margin-top: var(--space-sm);
}
.sub-section {
  margin-bottom: var(--space-md);
}
.sub-title {
  font-size: var(--font-size-md);
  margin-bottom: var(--space-sm);
}
.chip-wrap {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-sm);
}
.genre-chip {
  display: flex;
  flex-direction: column;
  gap: 2px;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  padding: 6px 10px;
  background: var(--color-bg-page);
  min-width: 84px;
}
.genre-name {
  font-size: var(--font-size-sm);
  font-weight: 600;
  color: var(--color-text-primary);
}
.genre-meta {
  font-size: 11px;
  color: var(--color-text-secondary);
}
.tag-chip {
  margin-bottom: 0;
}
.top-line {
  display: flex;
  gap: var(--space-sm);
  align-items: center;
  font-size: var(--font-size-sm);
  color: var(--color-text-regular);
  padding: 3px 0;
}
.top-idx {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 18px;
  height: 18px;
  border-radius: var(--radius-sm);
  background: var(--color-bg-page);
  color: var(--color-text-secondary);
  font-size: 11px;
  font-weight: 600;
}
.growth {
  color: var(--color-success);
  font-weight: 600;
}
.table-tag {
  margin-right: var(--space-xs);
}
.report {
  white-space: pre-wrap;
  word-break: break-all;
  font-family: inherit;
  font-size: var(--font-size-sm);
  line-height: 1.8;
  color: var(--color-text-regular);
  background: var(--color-bg-page);
  border: 1px solid var(--color-border-light);
  border-radius: var(--radius-md);
  padding: var(--space-md);
  margin: 0;
}
:deep(.el-table__body tr:hover > td.el-table__cell) {
  background: var(--color-bg-page);
}
</style>
