import { http } from './http'
import type { OpenBookPayload, ProjectOutline, Task } from '@/types/writing'

export interface DraftConfirmPayload {
  action: 'confirm' | 'regenerate' | 'cancel'
  content?: string
}

export const outlineApi = {
  getOutline: (pid: number) => http.get(`/projects/${pid}/outline`) as Promise<ProjectOutline>,
  openBook: (pid: number, payload: OpenBookPayload) =>
    http.post(`/projects/${pid}/open-book`, payload) as Promise<Task>,
  /** confirm 模式：确认/重生成/取消暂停的开书阶段 */
  draftConfirm: (tid: number, payload: DraftConfirmPayload) =>
    http.post(`/tasks/${tid}/draft-confirm`, payload) as Promise<Task>,
}
