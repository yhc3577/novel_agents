import { computed, ref } from 'vue'
import { defineStore } from 'pinia'
import { sseStream } from '@/api/sse'
import { outlineApi } from '@/api/outline'
import { writingApi } from '@/api/writing'
import type {
  AgentEvent,
  OpenBookPayload,
  PipelineStage,
  ProjectOutline,
  StageStatus,
  Task,
} from '@/types/writing'
import { OPEN_BOOK_PIPELINE } from '@/types/writing'

/**
 * 开书 store：三阶段流水线（世界观/设定 → 大纲 → 细纲）。
 *
 * - 阶段状态机：pending → running →（confirm 模式）waiting → done / error
 * - token 事件带 stream 标记，流式内容按阶段累积到 stageDrafts（世界观边生成边显示）
 * - confirm 模式：stage_draft 事件保存草稿并置 waitingDraft，用户确认/重生成后经
 *   draft-confirm 唤醒任务继续；auto 模式生成即入库（无 waiting）
 * - 重试：点击已完成的阶段 → 从该阶段重新开书（该阶段及其后产物清空，上游保留）
 */
export const useOutlineStore = defineStore('outline', () => {
  const outline = ref<ProjectOutline | null>(null)
  const task = ref<Task | null>(null)
  const events = ref<AgentEvent[]>([])
  const mode = ref<'auto' | 'confirm'>('auto')
  const currentStage = ref<PipelineStage | null>(null)
  const stageStatus = ref<Record<string, StageStatus>>({})
  const stageDrafts = ref<Record<string, string>>({})
  const waitingDraft = ref<{ stage: PipelineStage; content: string } | null>(null)

  let abortCtrl: AbortController | null = null

  const running = computed(() => task.value?.status === 'running' || task.value?.status === 'pending')
  const hasOutline = computed(() => outline.value?.has_outline ?? false)
  const waiting = computed(() => waitingDraft.value !== null)

  function _initStages() {
    stageStatus.value = {}
    stageDrafts.value = {}
    for (const s of OPEN_BOOK_PIPELINE) stageStatus.value[s.key] = 'pending'
    currentStage.value = null
    waitingDraft.value = null
  }

  function reset() {
    stopStream()
    outline.value = null
    task.value = null
    events.value = []
    mode.value = 'auto'
    _initStages()
  }

  function stopStream() {
    abortCtrl?.abort()
    abortCtrl = null
  }

  async function load(pid: number) {
    outline.value = await outlineApi.getOutline(pid)
    // 已有大纲 → 三个阶段视为完成（刷新页面后流水线仍显示已点亮）
    if (outline.value?.has_outline) {
      for (const s of OPEN_BOOK_PIPELINE) stageStatus.value[s.key] = 'done'
    }
  }

  async function openBook(pid: number, payload: OpenBookPayload) {
    stopStream()
    events.value = []
    _initStages()
    // 从某阶段重跑：该阶段之前的产物保留 → 流水线显示为已完成
    if (payload.stage && payload.stage !== 'all') {
      const idx = OPEN_BOOK_PIPELINE.findIndex((s) => s.key === payload.stage)
      for (let i = 0; i < idx; i++) stageStatus.value[OPEN_BOOK_PIPELINE[i].key] = 'done'
    }
    const t = await outlineApi.openBook(pid, {
      ...payload,
      mode: mode.value,
      stage: payload.stage ?? 'all',
    })
    task.value = { ...t, status: 'running' }
    // 后台订阅 SSE（不阻塞，done 后自动刷新大纲）
    void listen(pid, t.id)
  }

  /** 重试：从指定阶段重新生成（上游产物保留，该阶段及其后清空重跑）。 */
  async function retryStage(pid: number, stage: PipelineStage) {
    await openBook(pid, { stage, mode: mode.value })
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

  function _markDoneBefore(key: string) {
    const idx = OPEN_BOOK_PIPELINE.findIndex((s) => s.key === key)
    for (let i = 0; i < idx; i++) stageStatus.value[OPEN_BOOK_PIPELINE[i].key] = 'done'
  }

  function handleEvent(ev: AgentEvent) {
    switch (ev.type) {
      case 'stage': {
        events.value.push(ev)
        if (ev.stage && OPEN_BOOK_PIPELINE.some((s) => s.key === ev.stage)) {
          // 该阶段开始 → 之前的阶段已完成
          _markDoneBefore(ev.stage)
          stageStatus.value[ev.stage] = 'running'
          currentStage.value = ev.stage as PipelineStage
        }
        break
      }
      case 'token': {
        // 开书 token 带 stream 标记 → 流式内容累积到对应阶段草稿
        if (ev.stream && OPEN_BOOK_PIPELINE.some((s) => s.key === ev.stream)) {
          stageDrafts.value[ev.stream] = (stageDrafts.value[ev.stream] ?? '') + (ev.content ?? '')
        } else {
          events.value.push(ev)
        }
        break
      }
      case 'status': {
        events.value.push(ev)
        if (task.value) task.value.progress = ev.progress ?? task.value.progress
        break
      }
      case 'stage_draft': {
        const key = ev.stage as PipelineStage
        if (key && OPEN_BOOK_PIPELINE.some((s) => s.key === key)) {
          stageStatus.value[key] = 'waiting'
          stageDrafts.value[key] = ev.content ?? ''
          waitingDraft.value = { stage: key, content: ev.content ?? '' }
          events.value.push(ev)
        }
        break
      }
      case 'done': {
        if (task.value) task.value.status = ev.status === 'cancelled' || ev.status === 'failed' ? ev.status : 'success'
        if (ev.status === 'success') {
          for (const s of OPEN_BOOK_PIPELINE) {
            if (stageStatus.value[s.key] !== 'error') stageStatus.value[s.key] = 'done'
          }
        }
        waitingDraft.value = null
        events.value.push(ev)
        break
      }
      case 'error': {
        if (task.value) {
          task.value.status = 'failed'
          task.value.error = ev.error
        }
        if (currentStage.value) stageStatus.value[currentStage.value] = 'error'
        waitingDraft.value = null
        events.value.push(ev)
        break
      }
    }
  }

  async function afterDone(pid: number) {
    await load(pid)
  }

  async function confirmDraft(content: string) {
    const d = waitingDraft.value
    if (!d || !task.value) return
    const stage = d.stage
    const t = await outlineApi.draftConfirm(task.value.id, { action: 'confirm', content })
    task.value = { ...t, status: 'running' }
    waitingDraft.value = null
    // 提交成功，等待下一阶段 stage 事件补 done
    stageStatus.value[stage] = 'done'
  }

  async function regenerateDraft() {
    const d = waitingDraft.value
    if (!d || !task.value) return
    const stage = d.stage
    const t = await outlineApi.draftConfirm(task.value.id, { action: 'regenerate' })
    task.value = { ...t, status: 'running' }
    waitingDraft.value = null
    stageStatus.value[stage] = 'running'
    stageDrafts.value[stage] = ''
  }

  function cancel() {
    // confirm 模式暂停中：用 draft-confirm cancel 唤醒任务取消
    if (waitingDraft.value && task.value) {
      void outlineApi.draftConfirm(task.value.id, { action: 'cancel' })
      waitingDraft.value = null
      return
    }
    if (task.value) void writingApi.cancelTask(task.value.id)
  }

  return {
    outline,
    task,
    events,
    mode,
    currentStage,
    stageStatus,
    stageDrafts,
    waitingDraft,
    running,
    hasOutline,
    waiting,
    reset,
    load,
    openBook,
    retryStage,
    confirmDraft,
    regenerateDraft,
    cancel,
  }
})
