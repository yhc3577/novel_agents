import { http } from './http'
import type { AnalysisBook, AnalysisSnapshot, AnalysisTask, ImportResult } from '@/types/analysis'

export const analysisApi = {
  list: () => http.get('/analysis/books') as Promise<AnalysisBook[]>,
  create: (payload: { title: string; genre?: string; source_text: string }) =>
    http.post('/analysis/books', payload) as Promise<AnalysisBook>,
  analyze: (bid: number) => http.post(`/analysis/books/${bid}/analyze`) as Promise<AnalysisTask>,
  snapshot: (bid: number) => http.get(`/analysis/books/${bid}`) as Promise<AnalysisSnapshot>,
  importBook: (bid: number) => http.post(`/analysis/books/${bid}/import`) as Promise<ImportResult>,
}
