import { http } from './http'
import type {
  ChapterDetail,
  ChapterLite,
  NextChapterPayload,
  Task,
  TrackingContext,
  TrackingInfo,
} from '@/types/writing'

export const writingApi = {
  chaptersNext: (pid: number, payload: NextChapterPayload) =>
    http.post(`/projects/${pid}/chapters/next`, payload) as Promise<Task>,
  getTask: (tid: number) => http.get(`/tasks/${tid}`) as Promise<Task>,
  cancelTask: (tid: number) => http.post(`/tasks/${tid}/cancel`) as Promise<Task>,
  listChapters: (pid: number) => http.get(`/projects/${pid}/chapters`) as Promise<ChapterLite[]>,
  getChapter: (pid: number, chapterNo: number) =>
    http.get(`/projects/${pid}/chapters/${chapterNo}`) as Promise<ChapterDetail>,
  tracking: (pid: number) => http.get(`/projects/${pid}/tracking`) as Promise<TrackingInfo>,
  trackingContext: (pid: number) =>
    http.get(`/projects/${pid}/tracking/context`) as Promise<TrackingContext>,
}
