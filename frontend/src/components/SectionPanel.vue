<template>
  <section class="section-panel">
    <div class="section-header">
      <div>
        <h2>{{ title }}</h2>
        <p v-if="description">{{ description }}</p>
      </div>
      <slot name="actions" />
    </div>
    <slot />
  </section>
</template>

<script setup lang="ts">
defineProps<{
  title: string
  description?: string
}>()
</script>

