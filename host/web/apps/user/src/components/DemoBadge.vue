<script setup lang="ts">
import { apiMode } from '@velapet/api'
</script>

<template>
  <span v-if="apiMode === 'mock'" class="demo-badge">
    <span class="demo-dot" />
    演示数据
  </span>
</template>
