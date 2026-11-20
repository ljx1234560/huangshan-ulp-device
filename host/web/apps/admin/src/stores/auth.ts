import { computed, ref } from 'vue'
import { defineStore } from 'pinia'
import { apiMode, authApi, type AuthSession } from '@velapet/api'

const key = 'velapet_admin_session'

export const useAdminAuth = defineStore('admin-auth', () => {
  const loading = ref(false)
  const initialized = ref(false)
  const session = ref<AuthSession | null>(null)
  const isAuthenticated = computed(() => session.value?.user.role === 'admin')

  async function initialize() {
    if (initialized.value) return
    try {
      if (apiMode === 'mock') {
        const raw = localStorage.getItem(key)
        session.value = raw ? (JSON.parse(raw) as AuthSession) : null
      } else {
        const restored = await authApi.me()
        session.value = restored.user.role === 'admin' ? restored : null
      }
    } catch { session.value = null }
    finally { initialized.value = true }
  }
  async function login(email: string, password: string) {
    loading.value = true
    try {
      const next = await authApi.login(email, password, 'admin')
      if (next.user.role !== 'admin') throw new Error('该账号没有管理员权限')
      session.value = next
      if (apiMode === 'mock') {
        localStorage.setItem(key, JSON.stringify(next))
        if (next.token) localStorage.setItem('velapet_token', next.token)
      }
    } finally { loading.value = false }
  }
  async function logout() {
    try { await authApi.logout() } catch { /* Clear local state even if the server is unavailable. */ }
    session.value = null
    localStorage.removeItem(key)
    localStorage.removeItem('velapet_token')
  }
  return { loading, session, initialized, isAuthenticated, initialize, login, logout }
})
