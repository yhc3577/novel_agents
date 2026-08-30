export interface UsageTotals {
  calls: number
  prompt_tokens: number
  completion_tokens: number
  cached_tokens: number
  cost: number
  tokens: number
  cache_hit_rate: number
}

export interface UsageDaily {
  date: string
  calls: number
  prompt_tokens: number
  completion_tokens: number
  tokens: number
  cached_tokens: number
  cost: number
}

export interface UsageBreakdown {
  calls: number
  tokens: number
  cost: number
}

export interface UsageRow extends UsageBreakdown {
  task_type: string
}

export interface ProviderRow extends UsageBreakdown {
  provider: string
}

export interface UsageSummary {
  days: number
  totals: UsageTotals
  daily: UsageDaily[]
  by_task_type: UsageRow[]
  by_provider: ProviderRow[]
}
