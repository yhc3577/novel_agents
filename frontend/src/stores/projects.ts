import { computed, ref } from 'vue'
import { defineStore } from 'pinia'
import { projectsApi } from '@/api/projects'
import type { Project, ProjectCreate } from '@/types/project'

export const useProjectsStore = defineStore('projects', () => {
  const projects = ref<Project[]>([])
  const loading = ref(false)

  const activeProject = computed(() => projects.value.find((p) => p.status === 'active') ?? null)
  const hasProjects = computed(() => projects.value.length > 0)

  async function fetchList() {
    loading.value = true
    try {
      projects.value = await projectsApi.list()
    } finally {
      loading.value = false
    }
  }

  async function create(payload: ProjectCreate) {
    const project = await projectsApi.create(payload)
    projects.value.unshift(project)
    return project
  }

  async function activate(id: number) {
    const activated = await projectsApi.activate(id)
    projects.value = projects.value.map((p) =>
      p.id === id ? activated : { ...p, status: 'inactive' },
    )
    return activated
  }

  return { projects, loading, activeProject, hasProjects, fetchList, create, activate }
})
