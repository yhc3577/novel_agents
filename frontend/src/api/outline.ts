import { http } from './http'
import type { OpenBookPayload, ProjectOutline, Task } from '@/types/writing'

export const outlineApi = {
  getOutline: (pid: number) => http.get(`/projects/${pid}/outline`) as Promise<ProjectOutline>,
  openBook: (pid: number, payload: OpenBookPayload) =>
    http.post(`/projects/${pid}/open-book`, payload) as Promise<Task>,
}
