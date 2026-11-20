<script setup lang="ts">
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'
import DemoBadge from '../components/DemoBadge.vue'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()

const items = [
  { to: '/', label: '今日概览', icon: '✦' },
  { to: '/activity', label: '运动数据', icon: '↗' },
  { to: '/coach', label: 'AI 教练', icon: '◈' },
  { to: '/pet-studio', label: '萌宠工坊', icon: '✧' },
  { to: '/pet', label: '成长中心', icon: '♡' },
  { to: '/devices', label: '设备中心', icon: '⌁' },
]

const title = computed(() => items.find((item) => item.to === route.path)?.label || 'VelaPet')

async function logout() {
  await auth.logout()
  await router.push('/login')
}
</script>

<template>
  <div class="app-shell">
    <aside class="user-sidebar">
      <router-link to="/" class="brand">
        <span class="brand-mark">V</span>
        <span><strong>VelaPet</strong><small>和萌宠一起动起来</small></span>
      </router-link>
      <nav class="side-nav" aria-label="主要导航">
        <router-link v-for="item in items" :key="item.to" :to="item.to">
          <span class="nav-icon">{{ item.icon }}</span>
          {{ item.label }}
        </router-link>
      </nav>
      <div class="sidebar-promo">
        <span class="promo-kicker">连续活跃</span>
        <strong>6 天 ✨</strong>
        <p>明天就能点亮本周星轨</p>
      </div>
      <router-link to="/profile" class="sidebar-user">
        <span class="avatar">晓</span>
        <span><strong>{{ auth.user?.name || '体验用户' }}</strong><small>查看个人资料</small></span>
        <span>›</span>
      </router-link>
    </aside>

    <div class="main-shell">
      <header class="topbar">
        <div>
          <p class="eyebrow">VELAPET SPACE</p>
          <h1>{{ title }}</h1>
        </div>
        <div class="top-actions">
          <DemoBadge />
          <el-tooltip content="通知中心（演示）"><button class="icon-button" aria-label="通知">♡</button></el-tooltip>
          <el-dropdown>
            <button class="profile-button">
              <span class="avatar small">晓</span>
              <span>{{ auth.user?.name || '体验用户' }}</span>
              <span>⌄</span>
            </button>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item @click="router.push('/profile')">个人资料</el-dropdown-item>
                <el-dropdown-item divided @click="logout">退出登录</el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </div>
      </header>

      <nav class="mobile-nav" aria-label="移动端导航">
        <router-link v-for="item in items" :key="item.to" :to="item.to">{{ item.icon }} {{ item.label }}</router-link>
      </nav>

      <main class="page-container">
        <router-view />
      </main>
    </div>
  </div>
</template>
