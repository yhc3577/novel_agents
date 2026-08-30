export interface Project {
  id: number
  slug: string
  title: string
  genre: string | null
  platform: string | null
  status: string
  created_at: string
  updated_at: string
}

export interface ProjectCreate {
  slug: string
  title: string
  genre?: string
  platform?: string
}

export interface ProjectUpdate {
  title?: string
  genre?: string
  platform?: string
}
