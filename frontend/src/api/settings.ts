import { http } from './http'
import type { ProviderLite, ProviderTestResult, SettingsData } from '@/types/settings'

export interface ProviderUpdatePayload {
  base_url?: string
  api_key?: string
  models?: Record<string, string>
  enabled?: boolean
  priority?: number
}

export const settingsApi = {
  get: () => http.get('/settings') as Promise<SettingsData>,
  updateProvider: (id: number, payload: ProviderUpdatePayload) =>
    http.put(`/settings/providers/${id}`, payload) as Promise<ProviderLite>,
  testProvider: (id: number) => http.post(`/settings/providers/${id}/test`) as Promise<ProviderTestResult>,
  updateTiers: (tiers: { high?: string | null; mid?: string | null; low?: string | null }) =>
    http.put('/settings/tiers', tiers) as Promise<{ high: string | null; mid: string | null; low: string | null }>,
}
