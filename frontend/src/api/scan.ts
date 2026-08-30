import { http } from './http'
import type { Task } from '@/types/writing'
import type { ScanLatest, ScanSnapshot } from '@/types/scan'

export const scanApi = {
  runScan: (platforms?: string[]) =>
    http.post('/scan/runs', { platforms }) as Promise<Task>,
  listResults: (platform?: string, limit = 50) =>
    http.get('/scan/results', { params: { platform, limit } }) as Promise<ScanSnapshot[]>,
  latest: () => http.get('/scan/latest') as Promise<ScanLatest>,
}
