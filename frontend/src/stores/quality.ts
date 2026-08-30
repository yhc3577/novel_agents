import { computed, ref } from 'vue'
import { defineStore } from 'pinia'
import { sseStream } from '@/api/sse'
import { qualityApi } from '@/api/quality'
import { writingApi } from '@/api/writing'
import type { AgentEvent, ChapterLite, Task } from '@/types/writing'
import type { DeslopResult, ReviewRow } from '@/types/quality'

export const useQualityStore = defineStore('quality', () => {
  const chapters = ref<ChapterLite[]>([])
  const reviews = ref<ReviewRow[]>([])
  const deslop = ref<DeslopResult | null>(null)
  const task = ref<Task | null>(null)
  const events = ref<AgentEvent[]>([])

  let abortCtrl: AbortController | null = null
  const running = computed(() => task.value?.status === 'running' || task.value?.status === 'pending')

  function stopStream() {
    abortCtrl?.abort()
    abortCtrl = null
  }

  function reset() {
    stopStream()
    chapters.value = []
    reviews.value = []
    deslop.value = null
    task.value = null
    events.value = []
  }

  async function loadChapters(pid: number) {
    chapters.value = await writingApi.listChapters(pid)
  }

  async function loadReviews(pid: number, chapterNo: number) {
    reviews.value = await qualityApi.listReviews(pid, chapterNo)
  }

  async function loadDeslop(pid: number, chapterNo: number) {
    deslop.value = await qualityApi.getDeslop(pid, chapterNo)
  }

  async function loadAll(pid: number, chapterNo: number) {
    await Promise.all([loadChapters(pid), loadReviews(pid, chapterNo), loadDeslop(pid, chapterNo)])
  }

  async function runReview(pid: number, chapterNo: number, mode: string) {
    stopStream()
    events.value = []
    const t = await qualityApi.runReview(pid, chapterNo, mode)
    task.value = { ...t, status: 'running' }
    void listen(pid, chapterNo, t.id, 'review')
  }

  async function runDeslop(pid: number, chapterNo: number) {
    stopStream()
    events.value = []
    const t = await qualityApi.runDeslop(pid, chapterNo)
    task.value = { ...t, status: 'running' }
    void listen(pid, chapterNo, t.id, 'deslop')
  }

  async function listen(pid: number, chapterNo: number, tid: number, kind: 'review' | 'deslop') {
    abortCtrl = new AbortController()
    try {
      for await (const ev of sseStream(`/tasks/${tid}/events`, abortCtrl.signal)) {
        handleEvent(ev)
        if (ev.type === 'done') break
      }
      await afterDone(pid, chapterNo, kind)
    } catch (e: any) {
      if (e?.name !== 'AbortError') {
        if (task.value) task.value.status = 'failed'
        events.value.push({ type: 'error', error: `SSE 中断：${e?.message ?? e}` })
      }
    }
  }

  function handleEvent(ev: AgentEvent) {
    switch (ev.type) {
      case 'stage':
      case 'tool':
      case 'status':
        events.value.push(ev)
        if (ev.type === 'status' && task.value) {
          task.value.progress = ev.progress ?? task.value.progress
        }
        break
      case 'checkpoint':
        events.value.push(ev)
        break
      case 'done':
        if (task.value) task.value.status = ev.status === 'cancelled' || ev.status === 'failed' ? ev.status : 'success'
        events.value.push(ev)
        break
      case 'error':
        if (task.value) {
          task.value.status = 'failed'
          task.value.error = ev.error
        }
        events.value.push(ev)
        break
    }
  }

  async function afterDone(pid: number, chapterNo: number, kind: 'review' | 'deslop') {
    if (kind === 'review') await loadReviews(pid, chapterNo)
    else await loadDeslop(pid, chapterNo)
    await loadChapters(pid)
  }

  async function acceptDeslop(pid: number, chapterNo: number) {
    await qualityApi.acceptDeslop(pid, chapterNo)
    await loadChapters(pid)
    await loadDeslop(pid, chapterNo)
  }

  function cancel() {
    if (task.value) void writingApi.cancelTask(task.value.id)
  }

  return {
    chapters,
    reviews,
    deslop,
    task,
    events,
    running,
    reset,
    loadChapters,
    loadReviews,
    loadDeslop,
    loadAll,
    runReview,
    runDeslop,
    acceptDeslop,
    cancel,
  }
})
