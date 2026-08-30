import { computed, ref } from 'vue'
import { defineStore } from 'pinia'
import { sseStream } from '@/api/sse'
import { scanApi } from '@/api/scan'
import { writingApi } from '@/api/writing'
import type { AgentEvent, Task } from '@/types/writing'
import type { ScanSnapshot } from '@/types/scan'

export const useScanStore = defineStore('scan', () => {
  const platforms = ref<ScanSnapshot[]>([])
  const history = ref<ScanSnapshot[]>([])
  const task = ref<Task | null>(null)
  const events = ref<AgentEvent[]>([])

  let abortCtrl: AbortController | null = null
  const running = computed(() => task.value?.status === 'running' || task.value?.status === 'pending')

  function stopStream() {
    abortCtrl?.abort()
    abortCtrl = null
  }

  async function loadLatest() {
    const data = await scanApi.latest()
    platforms.value = data.platforms
  }

  async function loadHistory(platform?: string) {
    history.value = await scanApi.listResults(platform)
  }

  async function runScan() {
    stopStream()
    events.value = []
    const t = await scanApi.runScan()
    task.value = { ...t, status: 'running' }
    void listen(t.id)
  }

  async function listen(tid: number) {
    abortCtrl = new AbortController()
    try {
      for await (const ev of sseStream(`/tasks/${tid}/events`, abortCtrl.signal)) {
        handleEvent(ev)
        if (ev.type === 'done') break
      }
      await afterDone()
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

  async function afterDone() {
    await loadLatest()
    await loadHistory()
  }

  function cancel() {
    if (task.value) void writingApi.cancelTask(task.value.id)
  }

  return {
    platforms,
    history,
    task,
    events,
    running,
    loadLatest,
    loadHistory,
    runScan,
    cancel,
  }
})
