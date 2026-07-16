<template>
  <span class="badge" :class="`badge-${status}`">{{ label }}</span>
</template>

<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{ status: string }>()

const labelMap: Record<string, string> = {
  draft: '草稿',
  pending: '待运行',
  queued: '排队中',
  running: '运行中',
  completed: '已完成',
  failed: '失败',
  archived: '已归档'
}

const label = computed(() => labelMap[props.status] || props.status)
</script>
