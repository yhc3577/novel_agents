export interface Task {
  id: number
  type: string
  status: string
  progress?: string | null
  error?: string | null
}

export interface ChapterLite {
  chapter_no: number
  title: string
  wordcount: number
  status: string
  revision: number
}

export interface ChapterDetail extends ChapterLite {
  content: string
}

export interface TrackingInfo {
  last_committed_chapter: number
  state_revision: number
  views_consistent: boolean
}

export interface TrackingContext {
  revision: number
  content: string
}

export interface NextChapterPayload {
  action: 'write_next' | 'write_chapter' | 'daily'
  scenario?: string
  chapter_no?: number
  target?: number
}

export interface AgentEvent {
  type: 'stage' | 'tool' | 'token' | 'checkpoint' | 'status' | 'done' | 'error'
  stage?: string
  tool?: string
  status?: string
  duration_ms?: number
  content?: string
  progress?: string
  error?: string
  state_revision?: number
  last_committed_chapter?: number
  views_consistent?: boolean
}

// ---- 开书（大纲） ----

/** 归一化后的细纲情节点（兼容开书写入 / 拆文导入两种形状）。 */
export interface OutlineBeatsView {
  summary: string
  target_wordcount?: number | null
  points?: unknown[]
}

export interface OutlineChapter {
  chapter_no: number
  title: string
  contract_status: string
  beats: OutlineBeatsView
}

export interface VolumeOutline {
  no: number
  title: string
  synopsis: string | null
  chapters: OutlineChapter[]
}

export interface ProjectOutline {
  has_outline: boolean
  volumes: VolumeOutline[]
}

export interface OpenBookPayload {
  scenario?: string
  force?: boolean
}
