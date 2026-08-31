import { computed, ref } from 'vue'
import { defineStore } from 'pinia'
import { sseStream } from '@/api/sse'
import { outlineApi } from '@/api/outline'
import { writingApi } from '@/api/writing'
import type { AgentEvent, OpenBookPayload, ProjectOutline, Task } from '@/types/writing'

export const useOutlineStore = defineStore('outline', () => {
  const outline = ref<ProjectOutline | null>(null)
  const task = ref<Task | null>(null)
  const events = ref<AgentEvent[]>([])

  let abortCtrl: AbortController | null = null
  const running = computed(() => task.value?.status === 'running' || task.value?.status === 'pending')
  const hasOutline = computed(() => outline.value?.has_outline ?? false)

  function reset() {
    stopStream()
    outline.value = null
    task.value = null
    events.value = []
  }

  function stopStream() {
    abortCtrl?.abort()
    abortCtrl = null
  }

  async function load(pid: number) {
    outline.value = await outlineApi.getOutline(pid)
  }

  async function openBook(pid: number, payload: OpenBookPayload) {
    stopStream()
    events.value = []
    const t = await outlineApi.openBook(pid, payload)
    task.value = { ...t, status: 'running' }
    // 后台订阅 SSE（不阻塞，done 后自动刷新大纲）
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
    await load(pid)
  }

  function cancel() {
    if (task.value) void writingApi.cancelTask(task.value.id)
  }

  return {
    outline,
    task,
    events,
    running,
    hasOutline,
    reset,
    load,
    openBook,
    cancel,
  }
})
