<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { useUsageStore } from '@/stores/usage'

const auth = useAuthStore()
const usage = useUsageStore()
const router = useRouter()

const displayName = computed(() => auth.user?.display_name || auth.user?.username || '')

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

function onLogout() {
  auth.logout()
  router.push('/login')
}

onMounted(async () => {
  if (!auth.user) await auth.fetchMe()
  await usage.load()
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
        <el-menu-item index="/usage">用量</el-menu-item>
        <el-menu-item index="/settings">设置</el-menu-item>
      </el-menu>
    </el-aside>

    <el-container>
      <el-header class="header">
        <div class="header-title">用量 · token / 成本 / 缓存命中率</div>
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

      <el-main class="main" v-loading="usage.loading">
        <div class="days-bar">
          <el-radio-group :model-value="usage.days" @update:model-value="(v: number | string | boolean | undefined) => usage.setDays(Number(v))">
            <el-radio-button :value="7">近 7 天</el-radio-button>
            <el-radio-button :value="30">近 30 天</el-radio-button>
            <el-radio-button :value="90">近 90 天</el-radio-button>
          </el-radio-group>
        </div>

        <el-empty v-if="!totals || totals.calls === 0" description="暂无 LLM 调用记录" />

        <template v-else>
          <!-- 汇总卡片 -->
          <el-row :gutter="16" class="cards">
            <el-col :span="6"><el-card shadow="never" class="stat"><div class="stat-val">{{ totals.calls }}</div><div class="stat-label">调用次数</div></el-card></el-col>
            <el-col :span="6"><el-card shadow="never" class="stat"><div class="stat-val">{{ fmt(totals.tokens) }}</div><div class="stat-label">总 token</div></el-card></el-col>
            <el-col :span="6"><el-card shadow="never" class="stat"><div class="stat-val">{{ fmtCost(totals.cost) }}</div><div class="stat-label">估算成本</div></el-card></el-col>
            <el-col :span="6"><el-card shadow="never" class="stat"><div class="stat-val">{{ Math.round(totals.cache_hit_rate * 100) }}%</div><div class="stat-label">缓存命中率</div></el-card></el-col>
          </el-row>

          <el-row :gutter="16">
            <!-- 每日曲线 -->
            <el-col :span="14">
              <el-card shadow="never" class="chart-card">
                <template #header>每日 token</template>
                <div class="bars">
                  <el-tooltip v-for="d in daily" :key="d.date" :content="`${d.date} · ${fmt(d.tokens)} tokens · ${d.calls} 次`" placement="top">
                    <div class="bar-col">
                      <div class="bar" :style="{ height: `${Math.max(3, (d.tokens / maxDailyTokens) * 160)}px` }"></div>
                      <div class="bar-date">{{ d.date.slice(5) }}</div>
                    </div>
                  </el-tooltip>
                </div>
              </el-card>
            </el-col>

            <!-- 分布 -->
            <el-col :span="10">
              <el-card shadow="never" class="chart-card">
                <template #header>按任务类型</template>
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
              </el-card>

              <el-card shadow="never" class="chart-card">
                <template #header>按 Provider</template>
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
              </el-card>
            </el-col>
          </el-row>
        </template>
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
.days-bar {
  margin-bottom: 14px;
}
.cards {
  margin-bottom: 16px;
}
.stat {
  text-align: center;
}
.stat-val {
  font-size: 26px;
  font-weight: 700;
  color: #1f2937;
}
.stat-label {
  font-size: 12px;
  color: #9ca3af;
  margin-top: 4px;
}
.chart-card {
  margin-bottom: 16px;
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
  border-radius: 4px 4px 0 0;
  background: linear-gradient(180deg, #6366f1, #818cf8);
}
.bar-date {
  font-size: 10px;
  color: #9ca3af;
}
.mini-table {
  width: 100%;
}
</style>
