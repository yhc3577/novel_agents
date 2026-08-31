<script setup lang="ts">
import { computed, ref, watch } from 'vue'
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

const edit = ref(props.content)
watch(
  () => props.content,
  (v) => (edit.value = v),
)
watch(
  () => props.visible,
  (v) => {
    if (v) edit.value = props.content
  },
)

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
      本阶段草稿已生成，任务处于暂停状态。内容可直接修改，确认后按修改后的内容入库；重新生成则放弃当前草稿、重跑本阶段。
    </div>
    <el-input v-model="edit" type="textarea" :rows="14" resize="none" class="dlg-editor" />
    <template #footer>
      <el-button type="danger" plain @click="emit('cancel')">取消任务</el-button>
      <el-button @click="emit('regenerate')">重新生成</el-button>
      <el-button type="primary" @click="emit('confirm', edit)">确认入库</el-button>
    </template>
  </el-dialog>
</template>

<style scoped>
.dlg-hint {
  font-size: 12px;
  color: #6b7280;
  line-height: 1.6;
  margin-bottom: 10px;
}
.dlg-editor :deep(.el-textarea__inner) {
  font-family: 'Songti SC', 'SimSun', Georgia, serif;
  font-size: 13px;
  line-height: 1.8;
}
</style>
