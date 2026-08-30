import { http } from './http'
import type { UsageSummary } from '@/types/usage'

export const usageApi = {
  getSummary: (days = 30) => http.get('/usage', { params: { days } }) as Promise<UsageSummary>,
}
