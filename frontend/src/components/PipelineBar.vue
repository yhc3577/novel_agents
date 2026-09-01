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
          class="stage"
          :class="[status[s.key] ?? 'pending', { clickable: clickable && (status[s.key] === 'done' || status[s.key] === 'error') }]"
          :title="clickable && (status[s.key] === 'done' || status[s.key] === 'error') ? '点击从该阶段重跑（其后清空）' : undefined"
          @click="onClick(s.key, status[s.key])"
        >
          <div class="stage-head">
            <div class="step">
              <el-icon v-if="status[s.key] === 'done'"><i class="el-icon-check" /></el-icon>
              <span v-else-if="status[s.key] === 'running'" class="spin"><i class="el-icon-loading" /></span>
              <span v-else-if="status[s.key] === 'waiting'">✋</span>
              <span v-else-if="status[s.key] === 'error'">!</span>
              <span v-else>{{ i + 1 }}</span>
            </div>
            <div v-if="i < stages.length - 1" class="step-line" :class="{ active: status[s.key] === 'done' }" />
          </div>
          <span class="step-label">{{ s.label }}</span>
          <span v-if="status[s.key] === 'waiting'" class="step-tag">待确认</span>
          <span v-else-if="status[s.key] === 'error'" class="step-tag">失败</span>
        </div>
      </template>
    </div>
  </div>
</template>

<style scoped>
.pipeline {
  display: flex;
  align-items: center;
  gap: var(--space-md);
  min-width: 0;
}
.pipeline-title {
  font-size: var(--font-size-sm);
  font-weight: 600;
  color: var(--color-text-regular);
  white-space: nowrap;
}
.pipeline-track {
  display: flex;
  align-items: flex-start;
  gap: 0;
  flex: 1;
  min-width: 0;
}
.stage {
  display: flex;
  flex-direction: column;
  align-items: center;
}
.stage.clickable {
  cursor: pointer;
}
.stage-head {
  display: flex;
  align-items: center;
}
.step {
  width: 44px;
  height: 44px;
  border-radius: 50%;
  border: 2px solid var(--color-border);
  background: var(--color-bg-card);
  color: var(--color-text-secondary);
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-size: 15px;
  flex-shrink: 0;
  transition:
    border-color var(--transition-fast),
    box-shadow var(--transition-fast),
    background var(--transition-fast);
}
.stage.running .step {
  background: var(--color-primary-lighter);
  border-color: var(--color-primary);
  color: var(--color-primary);
  box-shadow: 0 0 0 4px rgba(22, 93, 255, 0.1);
}
.stage.done .step {
  background: var(--color-primary);
  border-color: var(--color-primary);
  color: #fff;
}
.stage.waiting .step {
  background: var(--color-warning-light);
  border-color: var(--color-warning);
  color: var(--color-warning);
}
.stage.error .step {
  background: var(--color-danger-light);
  border-color: var(--color-danger);
  color: var(--color-danger);
}
.stage.clickable:hover .step {
  border-color: var(--color-primary);
  box-shadow: 0 0 0 4px rgba(22, 93, 255, 0.1);
}
.step-line {
  width: 28px;
  height: 2px;
  background: var(--color-border-light);
  flex-shrink: 0;
}
.step-line.active {
  background: var(--color-success);
}
.step-label {
  margin-top: var(--space-xs);
  font-size: var(--font-size-xs);
  color: var(--color-text-regular);
  line-height: 1.4;
  text-align: center;
  white-space: nowrap;
}
.step-tag {
  margin-top: 4px;
  font-size: 10px;
  font-weight: 600;
  line-height: 1.4;
  padding: 1px 8px;
  border-radius: 999px;
}
.stage.waiting .step-tag {
  color: var(--color-warning);
  background: var(--color-warning-light);
}
.stage.error .step-tag {
  color: var(--color-danger);
  background: var(--color-danger-light);
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
</style>
