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
    <div class="toolbar">
      <el-button type="primary" :loading="scan.running" @click="onRunScan">🚀 扫榜</el-button>
      <el-button :disabled="!scan.platforms.length" @click="scan.loadLatest()">刷新</el-button>
      <el-tag v-if="scan.running" type="warning" effect="dark" size="small">
        扫榜中{{ scan.task?.progress ? ` · ${scan.task.progress}` : '' }}
      </el-tag>
      <el-button v-if="scan.running" size="small" text @click="scan.cancel()">取消</el-button>
    </div>

    <el-tabs v-model="activeTab" class="scan-tabs">
      <!-- 榜单视图 -->
      <el-tab-pane label="📊 榜单视图" name="dashboard">
        <el-empty v-if="!scan.platforms.length" description="尚无扫榜结果，点击「扫榜」抓取两平台榜单" />
        <el-row v-else :gutter="16">
          <el-col :span="12" v-for="p in scan.platforms" :key="p.platform">
            <el-card shadow="never" class="platform-card">
              <template #header>
                <div class="plat-head">
                  <span class="plat-name">{{ PLATFORM_NAMES[p.platform] ?? p.platform }}</span>
                  <span class="plat-time">{{ fmtTime(p.snapshot_at) }}</span>
                </div>
              </template>
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
                <div class="section">
                  <div class="section-title">题材分布</div>
                  <div class="chip-wrap">
                    <div v-for="g in p.cleaned.stats.genre_distribution" :key="g.genre" class="genre-chip">
                      <span class="genre-name">{{ g.genre }}</span>
                      <span class="genre-meta">{{ g.count }} 本 · 均增 {{ g.avg_growth }}</span>
                    </div>
                  </div>
                </div>

                <!-- 热词 -->
                <div class="section">
                  <div class="section-title">热词</div>
                  <div class="chip-wrap">
                    <el-tag v-for="h in p.cleaned.stats.hot_tags.slice(0, 10)" :key="h.tag" size="small" effect="plain" class="tag-chip">
                      {{ h.tag }} ×{{ h.count }}
                    </el-tag>
                  </div>
                </div>

                <!-- 头部增速 -->
                <div class="section">
                  <div class="section-title">头部增速 Top</div>
                  <div v-for="(t, i) in p.cleaned.stats.top_books" :key="i" class="top-line">
                    <span class="top-idx">{{ i + 1 }}</span>
                    <span>{{ t }}</span>
                  </div>
                </div>

                <!-- 榜单表格 -->
                <div class="section">
                  <div class="section-title">榜单 Top {{ Math.min(10, p.cleaned.books.length) }}</div>
                  <el-table :data="p.cleaned.books.slice(0, 10)" size="small" class="book-table">
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
                <div class="section">
                  <div class="section-title">扫榜报告</div>
                  <pre class="report">{{ p.report }}</pre>
                </div>
              </template>
            </el-card>
          </el-col>
        </el-row>
      </el-tab-pane>

      <!-- 历史 -->
      <el-tab-pane label="🗂 历史快照" name="history">
        <el-empty v-if="!scan.history.length" description="暂无历史扫榜记录" />
        <el-table v-else :data="scan.history" size="small" class="history-table">
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
  gap: 12px;
  margin-bottom: 12px;
}
.scan-tabs {
  min-height: 72vh;
}
.platform-card {
  margin-bottom: 16px;
}
.plat-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.plat-name {
  font-weight: 600;
  font-size: 15px;
  color: #1f2937;
}
.plat-time {
  font-size: 12px;
  color: #9ca3af;
}
.decision-card {
  background: linear-gradient(135deg, #eff6ff, #f5f3ff);
  border: 1px solid #c7d2fe;
  border-radius: 10px;
  padding: 12px 14px;
  margin-bottom: 14px;
}
.decision-title {
  font-size: 12px;
  color: #4f46e5;
  font-weight: 600;
  margin-bottom: 6px;
}
.decision-topic {
  font-size: 18px;
  font-weight: 700;
  color: #1e1b4b;
  margin-bottom: 6px;
}
.decision-meta {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 6px;
}
.decision-count {
  font-size: 12px;
  color: #6b7280;
}
.decision-ratio {
  font-size: 13px;
  color: #334155;
  line-height: 1.6;
  margin-bottom: 6px;
}
.hooks {
  margin: 0;
  padding-left: 18px;
  font-size: 13px;
  color: #475569;
  line-height: 1.7;
}
.decision-risk {
  font-size: 12px;
  color: #b45309;
  margin-top: 8px;
}
.section {
  margin-bottom: 14px;
}
.section-title {
  font-size: 12px;
  font-weight: 600;
  color: #6b7280;
  margin-bottom: 8px;
}
.chip-wrap {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
.genre-chip {
  display: flex;
  flex-direction: column;
  gap: 2px;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  padding: 6px 10px;
  background: #f9fafb;
  min-width: 84px;
}
.genre-name {
  font-size: 13px;
  font-weight: 600;
  color: #1f2937;
}
.genre-meta {
  font-size: 11px;
  color: #9ca3af;
}
.tag-chip {
  margin-bottom: 0;
}
.top-line {
  display: flex;
  gap: 8px;
  align-items: center;
  font-size: 13px;
  color: #334155;
  padding: 3px 0;
}
.top-idx {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 18px;
  height: 18px;
  border-radius: 4px;
  background: #eef2f7;
  color: #64748b;
  font-size: 11px;
  font-weight: 600;
}
.growth {
  color: #059669;
  font-weight: 600;
}
.table-tag {
  margin-right: 4px;
}
.report {
  white-space: pre-wrap;
  word-break: break-all;
  font-family: inherit;
  font-size: 13px;
  line-height: 1.8;
  color: #334155;
  background: #f8fafc;
  border: 1px solid #eef2f7;
  border-radius: 8px;
  padding: 12px;
  margin: 0;
}
.history-table {
  background: #fff;
  border-radius: 10px;
}
</style>
