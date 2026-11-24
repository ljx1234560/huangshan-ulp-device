<script setup lang="ts">
defineProps<{
  label: string
  value: string
  hint: string
  icon: string
  tone?: 'violet' | 'blue' | 'coral' | 'mint'
}>()
</script>

<template>
  <article class="stat-card">
    <div class="stat-icon" :class="'is-' + (tone || 'violet')">{{ icon }}</div>
    <div>
      <p class="muted-label">{{ label }}</p>
      <strong class="stat-value">{{ value }}</strong>
      <p class="stat-hint">{{ hint }}</p>
    </div>
  </article>
</template>
