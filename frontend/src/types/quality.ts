export interface ReviewFinding {
  reviewer: string
  severity: 'blocking' | 'warning'
  type: string
  quote: string
  reason: string
  suggestion: string
}

export interface ReviewRow {
  mode: string
  score: number
  verdict: string
  findings: ReviewFinding[]
  summary: string | null
  created_at: string | null
}

export interface DeslopResult {
  ready: boolean
  reason?: string
  grade?: string
  score?: number
  findings?: ReviewFinding[]
  original_wordcount?: number
  new_wordcount?: number
  delta_wordcount?: number
  original?: string
  rewritten?: string
}

export interface AcceptResult {
  chapter_no: number
  status: string
  revision: number
  wordcount: number
}
