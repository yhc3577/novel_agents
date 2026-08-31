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
  resume_stage?: PipelineStage
}

export interface AgentEvent {
  type: 'stage' | 'tool' | 'token' | 'checkpoint' | 'status' | 'stage_draft' | 'done' | 'error'
  stage?: string
  tool?: string
  status?: string
  duration_ms?: number
  content?: string
  /** token 事件的开书阶段标记（worldview/outline/beats），用于把流式内容路由到对应草稿 */
  stream?: string
  progress?: string
  error?: string
  state_revision?: number
  last_committed_chapter?: number
  views_consistent?: boolean
}

// ---- 流水线（Pipeline） ----

export type PipelineStage = 'worldview' | 'outline' | 'beats'
export type StageStatus = 'pending' | 'running' | 'waiting' | 'done' | 'error'

export interface PipelineStep {
  key: string
  label: string
}

/** 开书三阶段流水线：世界观/设定 → 大纲 → 细纲 */
export const OPEN_BOOK_PIPELINE: PipelineStep[] = [
  { key: 'worldview', label: '世界观/设定' },
  { key: 'outline', label: '大纲' },
  { key: 'beats', label: '细纲' },
]

/** 写一章流水线：准备 → 规划 → 正文 → 提交 */
export const WRITE_PIPELINE: PipelineStep[] = [
  { key: 'prepare', label: '准备' },
  { key: 'planning', label: '规划' },
  { key: 'writing', label: '正文' },
  { key: 'submitting', label: '提交' },
]

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
  /** auto=生成即入库；confirm=每阶段草稿待确认 */
  mode?: 'auto' | 'confirm'
  /** 重试起跑点：all 或某阶段（该阶段及其后的产物被清空重生成） */
  stage?: 'all' | PipelineStage
}
