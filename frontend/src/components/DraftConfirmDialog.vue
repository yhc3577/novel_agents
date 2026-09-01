<script setup lang="ts">
import { computed } from 'vue'
import { OPEN_BOOK_PIPELINE } from '@/types/writing'

const props = defineProps<{
  visible: boolean
  stage: string
  content: string
}>()
const emit = defineEmits<{
  (e: 'confirm', content: string): void
  (e: 'regenerate'): void
  (e: 'cancel'): void
}>()

const stageLabel = computed(() => OPEN_BOOK_PIPELINE.find((s) => s.key === props.stage)?.label ?? props.stage)
</script>

<template>
  <el-dialog
    :model-value="visible"
    :title="`确认「${stageLabel}」草稿`"
    width="640px"
    :close-on-click-modal="false"
    :close-on-press-escape="false"
    :show-close="false"
    append-to-body
  >
    <div class="dlg-hint">
      本阶段草稿已生成，任务处于暂停状态。确认后按此草稿入库；重新生成则放弃当前草稿、重跑本阶段。
    </div>
    <pre class="draft-body">{{ content }}</pre>
    <template #footer>
      <el-button @click="emit('cancel')">取消</el-button>
      <el-button plain @click="emit('regenerate')">重新生成</el-button>
      <el-button type="primary" @click="emit('confirm', content)">确认入库</el-button>
    </template>
  </el-dialog>
</template>

<style scoped>
.dlg-hint {
  font-size: var(--font-size-xs);
  color: var(--color-text-secondary);
  line-height: 1.6;
  margin-bottom: var(--space-md);
}
.draft-body {
  margin: 0;
  background: var(--color-bg-page);
  border-radius: var(--radius-md);
  padding: var(--space-md);
  max-height: 60vh;
  overflow: auto;
  white-space: pre-wrap;
  word-break: break-word;
  font-family: 'Songti SC', 'SimSun', Georgia, serif;
  font-size: var(--font-size-sm);
  line-height: 1.8;
  color: var(--color-text-primary);
}
</style>
