<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { useAuthStore } from '@/stores/auth'
import { useSettingsStore } from '@/stores/settings'
import type { ProviderLite } from '@/types/settings'

const auth = useAuthStore()
const router = useRouter()
const store = useSettingsStore()

const displayName = computed(() => auth.user?.display_name || auth.user?.username || '')
const saving = ref<Record<number, boolean>>({})

const TIER_LABEL: Record<string, string> = { high: '高（复杂推理）', mid: '中（常规写作）', low: '低（廉价提取）' }

// 三档选择：provider 下拉
const tierOptions = computed(() => {
  const map: Record<string, string[]> = {}
  for (const p of store.providers) {
    for (const tier of Object.keys(p.models || {})) {
      map[tier] = map[tier] ?? []
      map[tier].push(`${p.name}:${p.models[tier]}`)
    }
  }
  return map
})

function selectTier(tier: string, spec: string | null) {
  store.tiers[tier as 'high' | 'mid' | 'low'] = spec
}

async function onSaveTiers() {
  await store.saveTiers()
  ElMessage.success('三档模型选择已保存，立即生效')
}

async function onSaveProvider(p: ProviderLite) {
  saving.value[p.id] = true
  try {
    await store.saveProvider(p.id, {
      base_url: p.base_url,
      models: p.models,
      enabled: p.enabled,
      priority: p.priority,
    })
    ElMessage.success(`${p.name} 已保存`)
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || '保存失败')
  } finally {
    saving.value[p.id] = false
  }
}

async function onSaveKey(p: ProviderLite) {
  if (!p.apiKey) {
    ElMessage.warning('请输入 api_key')
    return
  }
  saving.value[p.id] = true
  try {
    await store.saveProvider(p.id, { api_key: p.apiKey })
    p.apiKey = ''
    ElMessage.success(`${p.name} api_key 已加密保存`)
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || '保存失败')
  } finally {
    saving.value[p.id] = false
  }
}

async function onTest(p: ProviderLite) {
  await store.testProvider(p.id)
}

function onLogout() {
  auth.logout()
  router.push('/login')
}

onMounted(async () => {
  if (!auth.user) await auth.fetchMe()
  try {
    await store.load()
  } catch {
    // 401 已由 http 拦截器处理
  }
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
        <el-menu-item index="/settings">设置</el-menu-item>
      </el-menu>
    </el-aside>

    <el-container>
      <el-header class="header">
        <div class="header-title">设置 · 模型供应商 + 三档模型选择</div>
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
        <!-- 三档模型选择 -->
        <el-card shadow="never" class="mb">
          <template #header>三档模型选择（改完立即生效）</template>
          <div class="tier-row" v-for="tier in ['high', 'mid', 'low']" :key="tier">
            <span class="tier-label">{{ TIER_LABEL[tier] }}</span>
            <el-select :model-value="store.tiers[tier as 'high' | 'mid' | 'low']" placeholder="跟随默认" clearable class="tier-select" @update:model-value="(v: string | null) => selectTier(tier, v)">
              <el-option
                v-for="opt in tierOptions[tier] ?? []"
                :key="opt"
                :label="opt"
                :value="opt"
              />
            </el-select>
          </div>
          <el-button type="primary" @click="onSaveTiers">保存三档选择</el-button>
        </el-card>

        <!-- 供应商列表 -->
        <el-card shadow="never">
          <template #header>模型供应商（{{ store.providers.length }}）</template>
          <div v-if="store.providers.length === 0" class="empty">
            暂无供应商。请运行 seed_providers 脚本或等待后端首启种子。
          </div>
          <div v-for="p in store.providers" :key="p.id" class="provider-card">
            <div class="provider-head">
              <span class="provider-name">{{ p.name }}</span>
              <div class="provider-head-right">
                <el-tag :type="p.enabled ? 'success' : 'info'" size="small">{{ p.enabled ? '启用' : '停用' }}</el-tag>
                <el-tag v-if="p.has_key" type="primary" size="small">key 已配置</el-tag>
                <el-tag v-else type="warning" size="small">未配置 key</el-tag>
                <el-button size="small" :loading="store.testing[p.id]" @click="onTest(p)">测试连通</el-button>
              </div>
            </div>

            <div v-if="store.testResults[p.id]" class="test-result" :class="store.testResults[p.id].ok ? 'ok' : 'fail'">
              {{ store.testResults[p.id].ok
                ? `✅ 连通正常 · ${store.testResults[p.id].latency_ms}ms`
                : `❌ ${store.testResults[p.id].error ?? '未知错误'}` }}
            </div>

            <div class="provider-body">
              <div class="field">
                <span class="field-label">base_url</span>
                <el-input v-model="p.base_url" size="small" />
              </div>
              <div class="field" v-for="tier in ['high', 'mid', 'low']" :key="tier">
                <span class="field-label">模型 {{ tier }}</span>
                <el-input v-model="p.models[tier]" size="small" placeholder="留空则该档不可用" />
              </div>
              <div class="field">
                <span class="field-label">api_key</span>
                <el-input
                  :model-value="p.has_key ? '(已加密保存，输入新值覆盖)' : ''"
                  :placeholder="p.has_key ? '输入新 key 覆盖' : '输入 api_key'"
                  size="small"
                  @update:model-value="(v: string) => (p.apiKey = v)"
                />
              </div>
              <div class="field">
                <span class="field-label">优先级（小者优先）</span>
                <el-input-number v-model="p.priority" :min="0" size="small" />
                <el-switch v-model="p.enabled" active-text="启用" class="enable-switch" />
              </div>
            </div>

            <div class="provider-actions">
              <el-button size="small" type="primary" :loading="saving[p.id]" @click="onSaveProvider(p)">保存配置</el-button>
              <el-button size="small" @click="onSaveKey(p)">保存 api_key</el-button>
            </div>
          </div>
        </el-card>
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
.mb {
  margin-bottom: 16px;
}
.empty {
  color: #9ca3af;
  font-size: 13px;
  text-align: center;
  padding: 16px 0;
}
.tier-row {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 12px;
}
.tier-label {
  width: 130px;
  font-size: 13px;
  color: #374151;
}
.tier-select {
  width: 320px;
}
.provider-card {
  border: 1px solid #e5e7eb;
  border-radius: 10px;
  padding: 14px;
  margin-bottom: 14px;
}
.provider-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 10px;
}
.provider-name {
  font-weight: 600;
  font-size: 15px;
  color: #1f2937;
}
.provider-head-right {
  display: flex;
  align-items: center;
  gap: 6px;
}
.test-result {
  font-size: 12px;
  border-radius: 6px;
  padding: 4px 8px;
  margin-bottom: 8px;
}
.test-result.ok {
  background: #f0fdf4;
  color: #15803d;
}
.test-result.fail {
  background: #fef2f2;
  color: #b91c1c;
}
.provider-body {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 10px;
}
.field {
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.field-label {
  font-size: 12px;
  color: #6b7280;
}
.enable-switch {
  margin-top: 8px;
}
.provider-actions {
  margin-top: 12px;
  display: flex;
  gap: 8px;
}
</style>
