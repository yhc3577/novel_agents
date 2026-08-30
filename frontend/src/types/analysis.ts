export interface AnalysisBook {
  id: number
  title: string
  genre?: string | null
  status: string
}

export interface AnalysisChapter {
  chapter_no: number
  summary?: string | null
  beats?: string[] | null
}

export interface AnalysisSnapshot {
  id: number
  title: string
  genre?: string | null
  status: string
  chapters: AnalysisChapter[]
  aggregates: Record<string, string>
  progress: Record<string, string>
}

export interface ImportResult {
  project_id: number
  slug: string
  title: string
  imported: boolean
}

export interface AnalysisTask {
  id: number
  type: string
  status: string
  progress?: string | null
  error?: string | null
}
