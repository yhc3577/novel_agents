import { ref } from 'vue'
import { defineStore } from 'pinia'
import { usageApi } from '@/api/usage'
import type { UsageSummary } from '@/types/usage'

export const useUsageStore = defineStore('usage', () => {
  const summary = ref<UsageSummary | null>(null)
  const days = ref(30)
  const loading = ref(false)

  async function load() {
    loading.value = true
    try {
      summary.value = await usageApi.getSummary(days.value)
    } finally {
      loading.value = false
    }
  }

  async function setDays(d: number) {
    days.value = d
    await load()
  }

  return { summary, days, loading, load, setDays }
})
