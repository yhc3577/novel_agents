<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { useAuthStore } from '@/stores/auth'
import { useSettingsStore } from '@/stores/settings'
import type { ProviderLite } from '@/types/settings'

const auth = useAuthStore()
const store = useSettingsStore()

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
  <div class="page-container">
    <div class="page-header">
      <h1 class="page-title">设置</h1>
    </div>

    <!-- 三档模型选择 -->
    <div class="section-card">
      <h3 class="section-title">三档模型选择（改完立即生效）</h3>
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
    </div>

    <!-- 供应商列表 -->
    <div class="section-card">
      <h3 class="section-title">模型供应商（{{ store.providers.length }}）</h3>
      <div v-if="store.providers.length === 0" class="empty">
        暂无供应商。请运行 seed_providers 脚本或等待后端首启种子。
      </div>
      <div v-for="p in store.providers" :key="p.id" class="provider-card" :class="{ 'is-active': p.enabled }">
        <div class="provider-head">
          <span class="provider-name">{{ p.name }}</span>
          <div class="provider-head-right">
            <el-tag :type="p.enabled ? 'success' : 'info'" size="small">{{ p.enabled ? '使用中' : '停用' }}</el-tag>
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
    </div>
  </div>
</template>

<style scoped>
.empty {
  color: var(--color-text-secondary);
  font-size: var(--font-size-sm);
  text-align: center;
  padding: var(--space-md) 0;
}
.tier-row {
  display: flex;
  align-items: center;
  gap: var(--space-md);
  margin-bottom: var(--space-sm);
}
.tier-label {
  width: 130px;
  font-size: var(--font-size-sm);
  color: var(--color-text-regular);
}
.tier-select {
  width: 320px;
}
.provider-card {
  border: 1px solid var(--color-border);
  border-radius: var(--radius-lg);
  padding: var(--space-lg);
  margin-bottom: var(--space-md);
  transition: border-color var(--transition-fast), background var(--transition-fast);
}
.provider-card.is-active {
  border-color: var(--color-primary);
  background: var(--color-primary-lighter);
}
.provider-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 10px;
  flex-wrap: wrap;
  gap: var(--space-sm);
}
.provider-name {
  font-weight: 600;
  font-size: var(--font-size-lg);
  color: var(--color-text-primary);
}
.provider-head-right {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
}
.test-result {
  font-size: var(--font-size-xs);
  border-radius: var(--radius-sm);
  padding: var(--space-xs) var(--space-sm);
  margin-bottom: var(--space-sm);
}
.test-result.ok {
  background: var(--color-success-light);
  color: var(--color-success);
}
.test-result.fail {
  background: var(--color-danger-light);
  color: var(--color-danger);
}
.provider-body {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 10px;
}
.field {
  display: flex;
  flex-direction: column;
  gap: var(--space-xs);
}
.field-label {
  font-size: var(--font-size-xs);
  color: var(--color-text-secondary);
}
.enable-switch {
  margin-top: var(--space-sm);
}
.provider-actions {
  margin-top: var(--space-md);
  display: flex;
  gap: var(--space-sm);
}
</style>
