import { http } from './http'
import type { Project, ProjectCreate, ProjectUpdate } from '@/types/project'

export const projectsApi = {
  list: () => http.get('/projects') as Promise<Project[]>,
  create: (payload: ProjectCreate) => http.post('/projects', payload) as Promise<Project>,
  get: (id: number) => http.get(`/projects/${id}`) as Promise<Project>,
  update: (id: number, payload: ProjectUpdate) => http.patch(`/projects/${id}`, payload) as Promise<Project>,
  activate: (id: number) => http.post(`/projects/${id}/activate`) as Promise<Project>,
}
