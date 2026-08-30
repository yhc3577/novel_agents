<script setup lang="ts">
import { ref, watch } from 'vue'
import type { AgentEvent } from '@/types/writing'

const props = defineProps<{ events: AgentEvent[] }>()

const listRef = ref<HTMLElement>()
// 新事件到来时自动滚到底部
watch(
  () => props.events.length,
  () => {
    const el = listRef.value
    if (el) el.scrollTop = el.scrollHeight
  },
)

const stageLabel: Record<string, string> = {
  prepare: '准备',
  'open-book': '开书',
  planning: '写前规划',
  writing: '正文写作',
  submitting: '提交',
  route: '意图路由',
}
</script>

<template>
  <div class="agent-panel">
    <div class="panel-title">Agent 活动</div>
    <div ref="listRef" class="event-list" v-loading="events.length === 0" element-loading-text="等待 Agent 开始…">
      <div v-if="events.length === 0" class="empty">点击「写下一章」开始创作</div>
      <div v-for="(ev, i) in events" :key="i" class="event-row">
        <!-- 阶段 -->
        <span v-if="ev.type === 'stage'" class="badge stage">{{ stageLabel[ev.stage ?? ''] ?? ev.stage }}</span>
        <!-- 工具调用 -->
        <span v-else-if="ev.type === 'tool'" class="badge tool">
          <span class="tool-name">{{ ev.tool }}</span>
          <el-icon v-if="ev.status === 'running'" class="spin"><i class="el-icon-loading" /></el-icon>
          <span v-else class="tool-status" :class="ev.status">{{ ev.status }}</span>
          <span v-if="ev.duration_ms != null" class="tool-ms">{{ ev.duration_ms }}ms</span>
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
        <span v-else class="badge token">… {{ (ev.content ?? '').length }} 字已流式</span>
      </div>
    </div>
  </div>
</template>

<style scoped>
.agent-panel {
  display: flex;
  flex-direction: column;
  height: 100%;
}
.panel-title {
  font-size: 12px;
  font-weight: 600;
  color: #64748b;
  padding: 8px 0 6px;
}
.event-list {
  flex: 1;
  overflow-y: auto;
  max-height: 300px;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  padding: 8px;
  background: #fff;
}
.empty {
  color: #9ca3af;
  font-size: 12px;
  text-align: center;
  padding: 16px 0;
}
.event-row {
  margin-bottom: 6px;
}
.badge {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-size: 12px;
  border-radius: 6px;
  padding: 3px 8px;
  max-width: 100%;
}
.stage {
  background: #eff6ff;
  color: #2563eb;
  font-weight: 600;
}
.tool {
  background: #f5f3ff;
  color: #7c3aed;
}
.tool-name {
  font-weight: 600;
}
.tool-status {
  font-size: 11px;
}
.tool-status.running {
  color: #7c3aed;
}
.tool-status.done {
  color: #16a34a;
}
.tool-status.error {
  color: #dc2626;
}
.tool-ms {
  color: #a78bfa;
  font-size: 11px;
}
.status {
  background: #fefce8;
  color: #a16207;
}
.checkpoint {
  background: #f0fdf4;
  color: #15803d;
}
.done {
  background: #e0e7ff;
  color: #4338ca;
  font-weight: 600;
}
.error {
  background: #fef2f2;
  color: #b91c1c;
}
.token {
  background: #f8fafc;
  color: #64748b;
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
