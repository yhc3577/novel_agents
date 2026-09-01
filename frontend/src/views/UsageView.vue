<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { useAuthStore } from '@/stores/auth'
import { useUsageStore } from '@/stores/usage'

const auth = useAuthStore()
const usage = useUsageStore()

const totals = computed(() => usage.summary?.totals)
const daily = computed(() => usage.summary?.daily ?? [])
const maxDailyTokens = computed(() => Math.max(1, ...daily.value.map((d) => d.tokens)))

const TASK_LABELS: Record<string, string> = {
  write_chapter: '写章',
  review: '审查',
  review_summary: '审查汇总',
  deslop: '去味',
  analyze: '拆文',
  chapter_extractor: '章节提取',
  analysis_aggregate: '聚合',
  analysis_report: '报告',
  scan_topic: '扫榜选题',
  scan_report: '扫榜报告',
  import: '导入',
  router: '意图路由',
  test_usage: '测试',
}

function taskLabel(t: string): string {
  return TASK_LABELS[t] ?? t
}

function fmt(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(2)}M`
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}k`
  return `${Math.round(n)}`
}

function fmtCost(n: number): string {
  return `¥${n.toFixed(4)}`
}

onMounted(async () => {
  if (!auth.user) await auth.fetchMe()
  await usage.load()
})
</script>

<template>
  <div class="page-container" v-loading="usage.loading">
    <div class="page-header">
      <h1 class="page-title">用量</h1>
      <div class="days-bar">
        <el-radio-group :model-value="usage.days" @update:model-value="(v: number | string | boolean | undefined) => usage.setDays(Number(v))">
          <el-radio-button :value="7">近 7 天</el-radio-button>
          <el-radio-button :value="30">近 30 天</el-radio-button>
          <el-radio-button :value="90">近 90 天</el-radio-button>
        </el-radio-group>
      </div>
    </div>

    <el-empty v-if="!totals || totals.calls === 0" description="暂无 LLM 调用记录" />

    <template v-else>
      <!-- 汇总统计卡 -->
      <div class="stats-row">
        <div class="stat-card"><div class="stat-value">{{ totals.calls }}</div><div class="stat-label">调用次数</div></div>
        <div class="stat-card"><div class="stat-value">{{ fmt(totals.tokens) }}</div><div class="stat-label">总 token</div></div>
        <div class="stat-card"><div class="stat-value">{{ fmtCost(totals.cost) }}</div><div class="stat-label">估算成本</div></div>
        <div class="stat-card"><div class="stat-value">{{ Math.round(totals.cache_hit_rate * 100) }}%</div><div class="stat-label">缓存命中率</div></div>
      </div>

      <div class="usage-grid">
        <!-- 每日曲线 -->
        <div class="section-card chart-card">
          <h3 class="section-title">每日 token</h3>
          <div class="bars">
            <el-tooltip v-for="d in daily" :key="d.date" :content="`${d.date} · ${fmt(d.tokens)} tokens · ${d.calls} 次`" placement="top">
              <div class="bar-col">
                <div class="bar" :style="{ height: `${Math.max(3, (d.tokens / maxDailyTokens) * 160)}px` }"></div>
                <div class="bar-date">{{ d.date.slice(5) }}</div>
              </div>
            </el-tooltip>
          </div>
        </div>

        <!-- 分布 -->
        <div class="side-col">
          <div class="section-card chart-card">
            <h3 class="section-title">按任务类型</h3>
            <el-table :data="usage.summary!.by_task_type" size="small" class="mini-table">
              <el-table-column label="任务" min-width="90">
                <template #default="{ row }">{{ taskLabel(row.task_type) }}</template>
              </el-table-column>
              <el-table-column label="调用" width="60" prop="calls" />
              <el-table-column label="token" min-width="70">
                <template #default="{ row }">{{ fmt(row.tokens) }}</template>
              </el-table-column>
              <el-table-column label="成本" width="76">
                <template #default="{ row }">{{ fmtCost(row.cost) }}</template>
              </el-table-column>
            </el-table>
          </div>

          <div class="section-card chart-card">
            <h3 class="section-title">按 Provider</h3>
            <el-table :data="usage.summary!.by_provider" size="small" class="mini-table">
              <el-table-column prop="provider" label="Provider" min-width="90" />
              <el-table-column label="调用" width="60" prop="calls" />
              <el-table-column label="token" min-width="70">
                <template #default="{ row }">{{ fmt(row.tokens) }}</template>
              </el-table-column>
              <el-table-column label="成本" width="76">
                <template #default="{ row }">{{ fmtCost(row.cost) }}</template>
              </el-table-column>
            </el-table>
          </div>
        </div>
      </div>
    </template>
  </div>
</template>

<style scoped>
.days-bar {
  display: flex;
  align-items: center;
}
.stats-row {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: var(--space-lg);
  margin-bottom: var(--space-lg);
}
.stat-value {
  font-size: var(--font-size-2xl);
  font-weight: 600;
  color: var(--color-text-primary);
}
.stat-label {
  font-size: var(--font-size-xs);
  color: var(--color-text-secondary);
  margin-top: 4px;
}
.usage-grid {
  display: grid;
  grid-template-columns: 7fr 5fr;
  gap: var(--space-lg);
  align-items: start;
}
.side-col {
  display: flex;
  flex-direction: column;
}
.chart-card {
  margin-bottom: 0;
}
.side-col .chart-card {
  margin-bottom: var(--space-lg);
}
.side-col .chart-card:last-child {
  margin-bottom: 0;
}
.bars {
  display: flex;
  align-items: flex-end;
  gap: 6px;
  height: 190px;
  overflow-x: auto;
  padding-top: 6px;
}
.bar-col {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
  min-width: 26px;
}
.bar {
  width: 18px;
  border-radius: var(--radius-sm) var(--radius-sm) 0 0;
  background: linear-gradient(180deg, var(--color-primary-light), var(--color-primary));
}
.bar-date {
  font-size: 10px;
  color: var(--color-text-secondary);
}
.mini-table {
  width: 100%;
}
:deep(.el-table__body tr:hover > td.el-table__cell) {
  background: var(--color-bg-page);
}
</style>
