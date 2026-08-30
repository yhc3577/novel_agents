export interface ProviderLite {
  id: number
  name: string
  base_url: string
  has_key: boolean
  models: Record<string, string>
  enabled: boolean
  priority: number
  /** 前端输入缓存：待保存的新 api_key（服务端永不回明文） */
  apiKey?: string
}

export interface SettingsData {
  providers: ProviderLite[]
  tiers: { high: string | null; mid: string | null; low: string | null }
}

export interface ProviderTestResult {
  ok: boolean
  provider: string
  model: string
  latency_ms: number
  error?: string | null
}
