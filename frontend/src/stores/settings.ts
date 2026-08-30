import { reactive, ref } from 'vue'
import { defineStore } from 'pinia'
import { settingsApi, type ProviderUpdatePayload } from '@/api/settings'
import type { ProviderLite, ProviderTestResult } from '@/types/settings'

export const useSettingsStore = defineStore('settings', () => {
  const providers = ref<ProviderLite[]>([])
  const tiers = reactive<{ high: string | null; mid: string | null; low: string | null }>({
    high: null,
    mid: null,
    low: null,
  })
  const testing = ref<Record<number, boolean>>({})
  const testResults = ref<Record<number, ProviderTestResult>>({})

  async function load() {
    const data = await settingsApi.get()
    providers.value = data.providers
    tiers.high = data.tiers.high
    tiers.mid = data.tiers.mid
    tiers.low = data.tiers.low
  }

  async function saveProvider(id: number, payload: ProviderUpdatePayload) {
    const updated = await settingsApi.updateProvider(id, payload)
    const idx = providers.value.findIndex((p) => p.id === id)
    if (idx >= 0) providers.value[idx] = updated
  }

  async function testProvider(id: number) {
    testing.value[id] = true
    try {
      testResults.value[id] = await settingsApi.testProvider(id)
    } finally {
      testing.value[id] = false
    }
  }

  async function saveTiers() {
    const saved = await settingsApi.updateTiers({ high: tiers.high, mid: tiers.mid, low: tiers.low })
    tiers.high = saved.high
    tiers.mid = saved.mid
    tiers.low = saved.low
  }

  return { providers, tiers, testing, testResults, load, saveProvider, testProvider, saveTiers }
})
