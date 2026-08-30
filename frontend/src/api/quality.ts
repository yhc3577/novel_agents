import { http } from './http'
import type { Task } from '@/types/writing'
import type { AcceptResult, DeslopResult, ReviewRow } from '@/types/quality'

export const qualityApi = {
  runReview: (pid: number, chapterNo: number, mode: string) =>
    http.post(`/projects/${pid}/chapters/${chapterNo}/review`, { mode }) as Promise<Task>,
  listReviews: (pid: number, chapterNo: number) =>
    http.get(`/projects/${pid}/chapters/${chapterNo}/reviews`) as Promise<ReviewRow[]>,
  runDeslop: (pid: number, chapterNo: number) =>
    http.post(`/projects/${pid}/chapters/${chapterNo}/deslop`) as Promise<Task>,
  getDeslop: (pid: number, chapterNo: number) =>
    http.get(`/projects/${pid}/chapters/${chapterNo}/deslop`) as Promise<DeslopResult>,
  acceptDeslop: (pid: number, chapterNo: number) =>
    http.post(`/projects/${pid}/chapters/${chapterNo}/deslop/accept`) as Promise<AcceptResult>,
}
