import type { AgentEvent } from '@/types/writing'

/**
 * 基于 fetch + ReadableStream 的 SSE 客户端（axios 无法流式）。
 * 逐块解析 `data: {...}` 事件，`\n\n` 分隔；流结束或 abort 即返回。
 */
export async function* sseStream(path: string, signal?: AbortSignal): AsyncGenerator<AgentEvent> {
  const token = localStorage.getItem('access_token')
  const res = await fetch(`/api${path}`, {
    headers: { Authorization: `Bearer ${token ?? ''}` },
    signal,
  })
  if (!res.ok || !res.body) throw new Error(`SSE 连接失败：${res.status}`)

  const reader = res.body.getReader()
  const decoder = new TextDecoder()
  let buf = ''
  try {
    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      buf += decoder.decode(value, { stream: true })
      let idx: number
      while ((idx = buf.indexOf('\n\n')) >= 0) {
        const block = buf.slice(0, idx)
        buf = buf.slice(idx + 2)
        for (const line of block.split('\n')) {
          if (line.startsWith('data:')) {
            try {
              yield JSON.parse(line.slice(5).trim()) as AgentEvent
            } catch {
              // 忽略无法解析的帧
            }
          }
        }
      }
    }
  } finally {
    reader.releaseLock()
  }
}
