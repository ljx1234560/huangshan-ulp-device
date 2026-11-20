import axios, { type InternalAxiosRequestConfig } from 'axios'
import type { ApiMode } from '@velapet/shared'

export const apiMode: ApiMode = import.meta.env.VITE_API_MODE === 'real' ? 'real' : 'mock'

export const http = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000',
  timeout: 12_000,
  headers: { 'Content-Type': 'application/json' },
  withCredentials: true,
})

const refreshHttp = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000',
  timeout: 12_000,
  withCredentials: true,
  headers: { 'Content-Type': 'application/json' },
})

function readCookie(name: string): string | undefined {
  if (typeof document === 'undefined') return undefined
  const prefix = encodeURIComponent(name) + '='
  const item = document.cookie.split('; ').find((part) => part.startsWith(prefix))
  return item ? decodeURIComponent(item.slice(prefix.length)) : undefined
}

http.interceptors.request.use((config) => {
  if (apiMode === 'mock' && typeof localStorage !== 'undefined') {
    const token = localStorage.getItem('velapet_token')
    if (token) config.headers.Authorization = 'Bearer ' + token
  }
  const method = config.method?.toUpperCase()
  if (method && !['GET', 'HEAD', 'OPTIONS'].includes(method)) {
    const csrf = readCookie('velapet_csrf')
    if (csrf) config.headers['X-CSRF-Token'] = csrf
  }
  return config
})

let refreshPromise: Promise<void> | null = null

http.interceptors.response.use(
  (response) => response,
  async (error: unknown) => {
    if (axios.isAxiosError(error)) {
      const original = error.config as (InternalAxiosRequestConfig & { _retry?: boolean }) | undefined
      const url = original?.url || ''
      if (
        apiMode === 'real' &&
        error.response?.status === 401 &&
        original &&
        !original._retry &&
        !url.includes('/auth/login') &&
        !url.includes('/auth/register') &&
        !url.includes('/auth/refresh')
      ) {
        original._retry = true
        refreshPromise ||= refreshHttp
          .post('/api/v1/auth/refresh', {}, { headers: { 'X-CSRF-Token': readCookie('velapet_csrf') || '' } })
          .then(() => undefined)
          .finally(() => { refreshPromise = null })
        try {
          await refreshPromise
          return http(original)
        } catch {
          // Fall through to the normalized unauthorized error below.
        }
      }
      const message =
        (error.response?.data as { message?: string; detail?: string } | undefined)?.message ||
        (error.response?.data as { detail?: string } | undefined)?.detail ||
        (error.response?.status === 401 ? '登录已过期，请重新登录' : undefined) ||
        (error.code === 'ECONNABORTED' ? '请求超时，请稍后重试' : '服务暂时不可用')
      return Promise.reject(new Error(message))
    }
    return Promise.reject(error)
  },
)
