<script setup lang="ts">
defineProps<{ label: string; value: string; delta?: string; icon: string; tone?: string }>()
</script>
<template><article class="kpi-card"><div class="kpi-top"><span>{{ label }}</span><i :class="'tone-' + (tone || 'blue')">{{ icon }}</i></div><strong>{{ value }}</strong><p v-if="delta"><b>↗ {{ delta }}</b> 较上一周期</p></article></template>
