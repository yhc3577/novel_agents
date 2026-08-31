<script setup lang="ts">
import type { PipelineStep, StageStatus } from '@/types/writing'

defineProps<{
  stages: PipelineStep[]
  status: Record<string, StageStatus>
  title?: string
  /** 是否允许点击已完成的阶段从该阶段重跑 */
  clickable?: boolean
}>()
const emit = defineEmits<{ (e: 'retry', stage: string): void }>()

function onClick(stage: string, st: StageStatus | undefined) {
  if (st === 'done' || st === 'error') emit('retry', stage)
}
</script>

<template>
  <div class="pipeline">
    <span v-if="title" class="pipeline-title">{{ title }}</span>
    <div class="pipeline-track">
      <template v-for="(s, i) in stages" :key="s.key">
        <div
          class="step"
          :class="[status[s.key] ?? 'pending', { clickable: clickable && (status[s.key] === 'done' || status[s.key] === 'error') }]"
          :title="clickable && (status[s.key] === 'done' || status[s.key] === 'error') ? '点击从该阶段重跑（其后清空）' : undefined"
          @click="onClick(s.key, status[s.key])"
        >
          <span class="step-dot">
            <el-icon v-if="status[s.key] === 'done'"><i class="el-icon-check" /></el-icon>
            <span v-else-if="status[s.key] === 'running'" class="spin"><i class="el-icon-loading" /></span>
            <span v-else-if="status[s.key] === 'waiting'">✋</span>
            <span v-else-if="status[s.key] === 'error'">!</span>
            <span v-else>{{ i + 1 }}</span>
          </span>
          <span class="step-label">{{ s.label }}</span>
          <span v-if="status[s.key] === 'waiting'" class="step-tag">待确认</span>
          <span v-else-if="status[s.key] === 'error'" class="step-tag">失败</span>
        </div>
        <div v-if="i < stages.length - 1" class="step-line" :class="{ active: status[s.key] === 'done' }" />
      </template>
    </div>
  </div>
</template>

<style scoped>
.pipeline {
  display: flex;
  align-items: center;
  gap: 14px;
  min-width: 0;
}
.pipeline-title {
  font-size: 12px;
  font-weight: 600;
  color: #64748b;
  white-space: nowrap;
}
.pipeline-track {
  display: flex;
  align-items: center;
  gap: 0;
  flex: 1;
  min-width: 0;
}
.step {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  padding: 4px 10px;
  border-radius: 999px;
  font-size: 12px;
  white-space: nowrap;
  background: #f1f5f9;
  color: #94a3b8;
  border: 1px solid transparent;
}
.step-dot {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 18px;
  height: 18px;
  border-radius: 50%;
  font-size: 11px;
  background: #e2e8f0;
  color: #64748b;
  flex-shrink: 0;
}
.step.running {
  background: #eff6ff;
  color: #1d4ed8;
  border-color: #bfdbfe;
  font-weight: 600;
}
.step.running .step-dot {
  background: #bfdbfe;
  color: #1d4ed8;
}
.step.done {
  background: #f0fdf4;
  color: #15803d;
}
.step.done .step-dot {
  background: #bbf7d0;
  color: #15803d;
}
.step.waiting {
  background: #fefce8;
  color: #a16207;
  border-color: #fde68a;
  font-weight: 600;
  animation: pulse 1.6s ease-in-out infinite;
}
.step.waiting .step-dot {
  background: #fde68a;
  color: #a16207;
}
.step.error {
  background: #fef2f2;
  color: #b91c1c;
  border-color: #fecaca;
}
.step.error .step-dot {
  background: #fecaca;
  color: #b91c1c;
}
.step.clickable {
  cursor: pointer;
}
.step.clickable:hover {
  box-shadow: 0 0 0 2px rgba(37, 99, 235, 0.25);
}
.step-label {
  line-height: 1;
}
.step-tag {
  font-size: 10px;
  font-weight: 600;
}
.step-line {
  flex: 1;
  min-width: 18px;
  height: 2px;
  background: #e2e8f0;
  margin: 0 4px;
}
.step-line.active {
  background: #bbf7d0;
}
.spin {
  display: inline-flex;
  animation: spin 1s linear infinite;
}
@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}
@keyframes pulse {
  0%,
  100% {
    opacity: 1;
  }
  50% {
    opacity: 0.55;
  }
}
</style>
