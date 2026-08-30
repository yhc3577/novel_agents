import { computed, ref } from 'vue'
import { defineStore } from 'pinia'
import { sseStream } from '@/api/sse'
import { analysisApi } from '@/api/analysis'
import type { AnalysisBook, AnalysisSnapshot, AnalysisTask, ImportResult } from '@/types/analysis'
import type { AgentEvent } from '@/types/writing'

export const useAnalysisStore = defineStore('analysis', () => {
  const books = ref<AnalysisBook[]>([])
  const snapshot = ref<AnalysisSnapshot | null>(null)
  const task = ref<AnalysisTask | null>(null)
  const events = ref<AgentEvent[]>([])
  const importing = ref(false)

  let abortCtrl: AbortController | null = null
  const running = computed(() => task.value?.status === 'running' || task.value?.status === 'pending')

  function reset() {
    abortCtrl?.abort()
    abortCtrl = null
    task.value = null
    events.value = []
  }

  async function fetchList() {
    books.value = await analysisApi.list()
  }

  async function createAndRun(payload: { title: string; genre?: string; source_text: string }) {
    const book = await analysisApi.create(payload)
    await fetchList()
    void runAnalyze(book.id)
    return book
  }

  async function runAnalyze(bid: number) {
    reset()
    const t = await analysisApi.analyze(bid)
    task.value = { ...t, status: 'running' }
    void listen(bid, t.id)
  }

  async function listen(bid: number, tid: number) {
    abortCtrl = new AbortController()
    try {
      for await (const ev of sseStream(`/tasks/${tid}/events`, abortCtrl.signal)) {
        if (ev.type === 'status' && task.value) {
          task.value.progress = ev.progress ?? task.value.progress
        }
        if (ev.type === 'done') {
          if (task.value) {
            task.value.status = ev.status === 'failed' || ev.status === 'cancelled' ? ev.status : 'success'
          }
          events.value.push(ev)
          break
        }
        if (ev.type === 'error' && task.value) {
          task.value.status = 'failed'
          task.value.error = ev.error
        }
        events.value.push(ev)
      }
      snapshot.value = await analysisApi.snapshot(bid)
    } catch (e: any) {
      if (e?.name !== 'AbortError' && task.value) {
        task.value.status = 'failed'
        task.value.error = `SSE 中断：${e?.message ?? e}`
      }
    } finally {
      task.value = null
    }
  }

  async function loadSnapshot(bid: number) {
    snapshot.value = await analysisApi.snapshot(bid)
  }

  async function importBook(bid: number): Promise<ImportResult> {
    importing.value = true
    try {
      const r = await analysisApi.importBook(bid)
      await loadSnapshot(bid)
      return r
    } finally {
      importing.value = false
    }
  }

  return {
    books,
    snapshot,
    task,
    events,
    running,
    importing,
    reset,
    fetchList,
    createAndRun,
    runAnalyze,
    loadSnapshot,
    importBook,
  }
})
