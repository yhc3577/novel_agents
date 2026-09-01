<script setup lang="ts">
import { ref, watch } from 'vue'
import type { AgentEvent } from '@/types/writing'

const props = defineProps<{ events: AgentEvent[] }>()

const listRef = ref<HTMLElement>()
// 每条事件到达时记录本地时间戳（仅用于终端展示，不影响数据）
const timestamps = ref<string[]>([])

// 新事件到来时自动滚到底部
watch(
  () => props.events.length,
  (n) => {
    while (timestamps.value.length < n) {
      timestamps.value.push(
        new Date().toLocaleTimeString('zh-CN', { hour12: false }),
      )
    }
    const el = listRef.value
    if (el) el.scrollTop = el.scrollHeight
  },
  { immediate: true },
)

const stageLabel: Record<string, string> = {
  prepare: '准备',
  worldview: '世界观/设定',
  outline: '大纲',
  beats: '细纲',
  planning: '写前规划',
  writing: '正文写作',
  submitting: '提交',
  route: '意图路由',
}
</script>

<template>
  <div class="agent-panel">
    <div class="panel-title">Agent 活动</div>
    <div
      ref="listRef"
      class="event-list"
      v-loading="events.length === 0"
      element-loading-text="等待 Agent 开始…"
      element-loading-background="rgba(26, 26, 46, 0.75)"
      element-loading-text-color="#e5e6eb"
    >
      <div v-if="events.length === 0" class="empty">点击「写下一章」开始创作</div>
      <div v-for="(ev, i) in events" :key="i" class="event-row">
        <span class="event-ts">{{ timestamps[i] }}</span>
        <!-- 阶段 -->
        <span v-if="ev.type === 'stage'" class="badge stage">{{ stageLabel[ev.stage ?? ''] ?? ev.stage }}</span>
        <!-- 工具调用 -->
        <span v-else-if="ev.type === 'tool'" class="badge tool">
          <span class="tool-name">{{ ev.tool }}</span>
          <el-icon v-if="ev.status === 'running'" class="spin"><i class="el-icon-loading" /></el-icon>
          <span v-else class="tool-status" :class="ev.status">{{ ev.status }}</span>
          <span v-if="ev.duration_ms != null" class="tool-ms">{{ ev.duration_ms }}ms</span>
        </span>
        <!-- 开书草稿待确认 -->
        <span v-else-if="ev.type === 'stage_draft'" class="badge draft-waiting">
          ✋ {{ stageLabel[ev.stage ?? ''] ?? ev.stage }} 草稿待确认
        </span>
        <!-- 状态进度 -->
        <span v-else-if="ev.type === 'status'" class="badge status">{{ ev.progress }}</span>
        <!-- 校验点 -->
        <span v-else-if="ev.type === 'checkpoint'" class="badge checkpoint">
          ✅ revision={{ ev.state_revision }} · 已提交至第 {{ ev.last_committed_chapter }} 章
        </span>
        <!-- 结束 -->
        <span v-else-if="ev.type === 'done'" class="badge done">
          {{ ev.status === 'cancelled' ? '已取消' : ev.status === 'failed' ? '失败' : '完成' }}
        </span>
        <span v-else-if="ev.type === 'error'" class="badge error">⚠ {{ ev.error }}</span>
        <!-- 流式正文 -->
        <span v-else class="token-line">
          <span v-if="ev.content" class="event-token">{{ ev.content }}</span>
          <span class="cursor-blink">|</span>
        </span>
      </div>
    </div>
  </div>
</template>

<style scoped>
.agent-panel {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: #1a1a2e;
  border-radius: var(--radius-md);
  color: #e5e6eb;
  font-family: var(--font-mono);
  font-size: var(--font-size-xs);
  overflow: hidden;
}
.panel-title {
  flex-shrink: 0;
  padding: 10px 14px;
  font-size: var(--font-size-xs);
  font-weight: 600;
  color: #e5e6eb;
  letter-spacing: 0.5px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.1);
}
.event-list {
  flex: 1;
  overflow-y: auto;
  max-height: 300px;
  padding: 8px 0;
  background: transparent;
}
.empty {
  color: #6b7280;
  text-align: center;
  padding: 16px 0;
}
.event-row {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  padding: 3px 14px;
  line-height: 1.6;
}
.event-row:hover {
  background: rgba(255, 255, 255, 0.04);
}
.event-ts {
  color: #6b7280;
  flex-shrink: 0;
  user-select: none;
}
.badge {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 11px;
  border-radius: var(--radius-sm);
  padding: 2px 8px;
  line-height: 1.5;
  max-width: 100%;
}
.stage {
  background: rgba(64, 128, 255, 0.18);
  color: #7ba7ff;
  font-weight: 600;
}
.tool {
  background: rgba(124, 58, 237, 0.22);
  color: #c4b5fd;
}
.tool-name {
  font-weight: 600;
}
.tool-status {
  font-size: 10px;
}
.tool-status.running {
  color: #c4b5fd;
}
.tool-status.done {
  color: #4ade80;
}
.tool-status.error {
  color: #f87171;
}
.tool-ms {
  color: #a78bfa;
  font-size: 10px;
}
.status {
  background: rgba(255, 184, 0, 0.16);
  color: #fbbf24;
}
.draft-waiting {
  background: rgba(255, 125, 0, 0.2);
  color: #ffb356;
  font-weight: 600;
}
.checkpoint {
  background: rgba(0, 180, 42, 0.16);
  color: #4ade80;
}
.done {
  background: rgba(64, 128, 255, 0.18);
  color: #7ba7ff;
  font-weight: 600;
}
.error {
  background: rgba(245, 63, 63, 0.18);
  color: #f87171;
}
.token-line {
  display: inline-flex;
  align-items: baseline;
  gap: 2px;
  color: #cbd5e1;
  word-break: break-all;
}
.event-token {
  color: #e5e6eb;
}
.cursor-blink {
  display: inline-block;
  color: #e5e6eb;
  animation: blink 0.8s step-end infinite;
}
@keyframes blink {
  50% {
    opacity: 0;
  }
}
.spin {
  animation: spin 1s linear infinite;
  display: inline-flex;
}
@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}
</style>
