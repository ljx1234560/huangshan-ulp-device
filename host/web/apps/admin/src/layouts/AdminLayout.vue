<script setup lang="ts">
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAdminAuth } from '../stores/auth'
import { apiMode } from '@velapet/api'

const route = useRoute()
const router = useRouter()
const auth = useAdminAuth()
const items = [
  { to: '/', label: '运营总览', icon: '⌂' },
  { to: '/users', label: '用户管理', icon: '♙' },
  { to: '/devices', label: '设备管理', icon: '▣' },
  { to: '/ai-services', label: 'AI 服务统计', icon: '✦' },
  { to: '/analytics', label: '运营分析', icon: '↗' },
]
const title = computed(() => items.find((item) => item.to === route.path)?.label || '运营控制台')
async function logout(){ await auth.logout(); await router.push('/login') }
</script>

<template>
  <div class="admin-shell">
    <aside class="admin-sidebar">
      <router-link to="/" class="admin-brand"><span>V</span><div><strong>VelaPet</strong><small>OPERATIONS</small></div></router-link>
      <p class="nav-section">WORKSPACE</p>
      <nav><router-link v-for="item in items" :key="item.to" :to="item.to"><span>{{ item.icon }}</span>{{ item.label }}</router-link></nav>
      <div class="system-card"><div><span class="pulse" />系统状态</div><strong>所有演示服务正常</strong><small>Mock API · 本地环境</small></div>
      <button class="admin-user" @click="logout"><span>运</span><div><strong>运营管理员</strong><small>退出演示账号</small></div><b>›</b></button>
    </aside>
    <div class="admin-main">
      <header class="admin-topbar">
        <div><p>VelaPet Console / {{ title }}</p><h1>{{ title }}</h1></div>
          <div class="admin-actions"><span class="mock-state"><i /> {{ apiMode === 'mock' ? 'MOCK DATA' : 'REAL API' }}</span><button aria-label="通知">◌</button><span class="admin-avatar">运</span></div>
      </header>
      <nav class="admin-mobile-nav"><router-link v-for="item in items" :key="item.to" :to="item.to">{{ item.icon }} {{ item.label }}</router-link></nav>
      <main class="admin-content"><router-view /></main>
    </div>
  </div>
</template>
