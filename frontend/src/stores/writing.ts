import { computed, ref } from 'vue'
import { defineStore } from 'pinia'
import { sseStream } from '@/api/sse'
import { writingApi } from '@/api/writing'
import type {
  AgentEvent,
  ChapterDetail,
  ChapterLite,
  NextChapterPayload,
  StageStatus,
  Task,
  TrackingContext,
  TrackingInfo,
} from '@/types/writing'
import { WRITE_PIPELINE } from '@/types/writing'

export const useWritingStore = defineStore('writing', () => {
  const chapters = ref<ChapterLite[]>([])
  const current = ref<ChapterDetail | null>(null)
  const streaming = ref('')
  const task = ref<Task | null>(null)
  const events = ref<AgentEvent[]>([])
  const tracking = ref<TrackingInfo | null>(null)
  const contextView = ref<TrackingContext | null>(null)

  let abortCtrl: AbortController | null = null
  const running = computed(() => task.value?.status === 'running' || task.value?.status === 'pending')

  const currentText = computed(() => {
    if (running.value && streaming.value) return streaming.value
    return current.value?.content ?? ''
  })
  const currentWordcount = computed(() => {
    const text = currentText.value
    const cjk = (text.match(/[一-鿿]/g) || []).length
    const words = (text.match(/[A-Za-z0-9_]+/g) || []).length
    return cjk + words
  })

  /** 写作流水线阶段状态（prepare → planning → writing → submitting）。 */
  const stageStatus = computed<Record<string, StageStatus>>(() => {
    const order = WRITE_PIPELINE.map((s) => s.key)
    const st: Record<string, StageStatus> = {}
    for (const k of order) st[k] = 'pending'
    let last = -1
    for (const ev of events.value) {
      if (ev.type === 'stage' && order.includes(ev.stage ?? '')) {
        last = order.indexOf(ev.stage!)
        st[ev.stage!] = 'running'
      }
    }
    if (task.value?.status === 'success') {
      for (const k of order) st[k] = 'done'
    } else if (task.value?.status === 'failed' && last >= 0) {
      st[order[last]] = 'error'
    }
    for (let i = 0; i < last; i++) st[order[i]] = 'done'
    return st
  })

  function reset() {
    stopStream()
    chapters.value = []
    current.value = null
    streaming.value = ''
    task.value = null
    events.value = []
    tracking.value = null
    contextView.value = null
  }

  function stopStream() {
    abortCtrl?.abort()
    abortCtrl = null
  }

  async function load(pid: number) {
    await refresh(pid)
    await loadLastCommitted(pid)
  }

  async function refresh(pid: number) {
    const [chs, tk, ctx] = await Promise.all([
      writingApi.listChapters(pid),
      writingApi.tracking(pid),
      writingApi.trackingContext(pid),
    ])
    chapters.value = chs
    tracking.value = tk
    contextView.value = ctx
  }

  async function loadLastCommitted(pid: number) {
    const committed = chapters.value.filter((c) => c.status === 'committed')
    const last = committed[committed.length - 1]
    if (last) current.value = await writingApi.getChapter(pid, last.chapter_no)
  }

  async function writeNext(pid: number, payload: NextChapterPayload) {
    stopStream()
    streaming.value = ''
    events.value = []
    const t = await writingApi.chaptersNext(pid, payload)
    task.value = { ...t, status: 'running' }
    // 后台订阅 SSE（不阻塞，done 后自动刷新）
    void listen(pid, t.id)
  }

  async function listen(pid: number, tid: number) {
    abortCtrl = new AbortController()
    try {
      for await (const ev of sseStream(`/tasks/${tid}/events`, abortCtrl.signal)) {
        handleEvent(ev)
        if (ev.type === 'done') break
      }
      await afterDone(pid)
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
      case 'token':
        streaming.value += ev.content ?? ''
        break
      case 'checkpoint':
        tracking.value = {
          state_revision: ev.state_revision ?? 0,
          last_committed_chapter: ev.last_committed_chapter ?? 0,
          views_consistent: ev.views_consistent ?? false,
        }
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

  async function afterDone(pid: number) {
    await refresh(pid)
    await loadLastCommitted(pid)
    streaming.value = ''
  }

  function cancel() {
    if (task.value) void writingApi.cancelTask(task.value.id)
  }

  return {
    chapters,
    current,
    streaming,
    task,
    events,
    tracking,
    contextView,
    running,
    currentText,
    currentWordcount,
    stageStatus,
    reset,
    load,
    refresh,
    writeNext,
    cancel,
  }
})
