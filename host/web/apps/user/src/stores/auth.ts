import { computed, ref } from 'vue'
import { defineStore } from 'pinia'
import { apiMode, authApi, type AuthSession } from '@velapet/api'

const storageKey = 'velapet_user_session'

function readSession(): AuthSession | null {
  if (apiMode !== 'mock') return null
  try {
    const raw = localStorage.getItem(storageKey)
    return raw ? (JSON.parse(raw) as AuthSession) : null
  } catch {
    return null
  }
}

export const useAuthStore = defineStore('auth', () => {
  const session = ref<AuthSession | null>(readSession())
  const loading = ref(false)
  const initialized = ref(false)
  const isAuthenticated = computed(() => Boolean(session.value))
  const user = computed(() => session.value?.user ?? null)

  function persist(next: AuthSession) {
    session.value = next
    if (apiMode === 'mock') {
      localStorage.setItem(storageKey, JSON.stringify(next))
      if (next.token) localStorage.setItem('velapet_token', next.token)
    }
  }

  async function initialize() {
    if (initialized.value) return
    try {
      if (apiMode === 'real') session.value = await authApi.me()
    } catch {
      session.value = null
    } finally {
      initialized.value = true
    }
  }

  async function login(email: string, password: string) {
    loading.value = true
    try {
      persist(await authApi.login(email, password, 'user'))
    } finally {
      loading.value = false
    }
  }

  async function register(name: string, email: string, password: string) {
    loading.value = true
    try {
      persist(await authApi.register(name, email, password))
    } finally {
      loading.value = false
    }
  }

  async function logout() {
    try { await authApi.logout() } catch { /* Local state must still be cleared. */ }
    session.value = null
    localStorage.removeItem(storageKey)
    localStorage.removeItem('velapet_token')
  }

  return { session, loading, initialized, isAuthenticated, user, initialize, login, register, logout }
})
