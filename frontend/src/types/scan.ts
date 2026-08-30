export interface ScanBook {
  rank: number
  title: string
  author: string
  genre: string
  words: number
  followers: number
  growth_7d: number
  rating: number
  tags: string[]
}

export interface GenreStat {
  genre: string
  count: number
  avg_followers: number
  avg_growth: number
}

export interface HotTag {
  tag: string
  count: number
}

export interface TrendStats {
  total: number
  insights: string
  genre_distribution: GenreStat[]
  hot_tags: HotTag[]
  top_books: string[]
}

export interface TopicDecision {
  topic: string
  genre: string
  hot_tag: string
  rationale: string
  hooks: string[]
  risk: string
}

export interface ScanSnapshot {
  id: number
  platform: string
  snapshot_at: string | null
  raw: { platform: string; books: ScanBook[] } | null
  cleaned: {
    platform: string
    books: ScanBook[]
    invalid: ScanBook[]
    dropped: number
    stats: TrendStats
    topic_decision: TopicDecision
  } | null
  report: string | null
}

export interface ScanLatest {
  platforms: ScanSnapshot[]
}
