import type {
  ActivitySummary,
  AdminOverview,
  AiServiceMetric,
  AuthSession,
  BridgeStatus,
  CoachingAdvice,
  CoachingGeneration,
  DateRangeQuery,
  DataRange,
  DeviceRecord,
  PetGenerationInput,
  PetGenerationJob,
  PetAsset,
  PetSnapshot,
  RetentionPoint,
  SyncLog,
  UserProfile,
  WeeklySummary,
} from '@velapet/shared'
import { apiBaseUrl, apiMode, http } from './client'
import { mockApi } from './mock'

async function realGet<T>(path: string): Promise<T> {
  const response = await http.get<T>(path)
  return response.data
}

export { apiMode }

export function buildDateQuery(range: DataRange, dates: DateRangeQuery = {}): string {
  const params = new URLSearchParams({ range })
  if (dates.startDate) params.set('start_date', dates.startDate)
  if (dates.endDate) params.set('end_date', dates.endDate)
  return params.toString()
}

export const authApi = {
  login: (email: string, password: string, role: 'user' | 'admin' = 'user'): Promise<AuthSession> =>
    apiMode === 'mock'
      ? mockApi.login(email, role)
      : http.post<AuthSession>('/api/v1/auth/login', { email, password }).then((r) => r.data),
  register: (name: string, email: string, password: string): Promise<AuthSession> =>
    apiMode === 'mock'
      ? mockApi.register(name, email)
      : http.post<AuthSession>('/api/v1/auth/register', { name, email, password }).then((r) => r.data),
  me: (): Promise<AuthSession> =>
    apiMode === 'mock'
      ? mockApi.login('', 'user')
      : realGet('/api/v1/auth/me'),
  logout: (): Promise<void> =>
    apiMode === 'mock'
      ? Promise.resolve()
      : http.post('/api/v1/auth/logout').then(() => undefined),
}

export const activityApi = {
  daily: (range: DataRange, dates: DateRangeQuery = {}): Promise<ActivitySummary> =>
    apiMode === 'mock' ? mockApi.activity(range) : realGet('/api/v1/activity/daily?' + buildDateQuery(range, dates)),
  trends: (range: DataRange, dates: DateRangeQuery = {}): Promise<ActivitySummary> =>
    apiMode === 'mock' ? mockApi.activity(range) : realGet('/api/v1/activity/trends?' + buildDateQuery(range, dates)),
  weeklySummary: (dates: DateRangeQuery = {}): Promise<WeeklySummary> =>
    apiMode === 'mock'
      ? mockApi.weeklySummary()
      : realGet('/api/v1/activity/weekly-summary?' + buildDateQuery('week', dates)),
}

export const aiApi = {
  generate: (): Promise<CoachingGeneration> =>
    apiMode === 'mock'
      ? mockApi.generateCoaching()
      : http.post<CoachingGeneration>('/api/v1/ai/coaching').then((r) => r.data),
  latest: (): Promise<CoachingAdvice[]> =>
    apiMode === 'mock' ? mockApi.latestCoaching() : realGet('/api/v1/ai/coaching'),
  history: (): Promise<CoachingGeneration[]> =>
    apiMode === 'mock' ? mockApi.coachingHistory() : realGet('/api/v1/ai/coaching/history'),
}

function resolveProtectedImage<T extends { imageUrl?: string }>(item: T): T {
  if (apiMode === 'real' && item.imageUrl?.startsWith('/api/')) {
    return { ...item, imageUrl: new URL(item.imageUrl, apiBaseUrl).toString() }
  }
  return item
}

export const petApi = {
  current: (): Promise<PetSnapshot> =>
    apiMode === 'mock' ? mockApi.pet() : realGet<PetSnapshot>('/api/v1/pets/current').then(resolveProtectedImage),
  createGenerationJob: (input: PetGenerationInput): Promise<PetGenerationJob> =>
    apiMode === 'mock'
      ? mockApi.createPetJob(input)
      : http.post<PetGenerationJob>('/api/v1/pets/generation-jobs', input).then((r) => r.data),
  generationJob: (id: string): Promise<PetGenerationJob> =>
    apiMode === 'mock' ? mockApi.petJob(id) : realGet<PetGenerationJob>('/api/v1/pets/generation-jobs/' + id).then(resolveProtectedImage),
  generationHistory: (): Promise<PetGenerationJob[]> =>
    apiMode === 'mock' ? mockApi.petJobs() : realGet<PetGenerationJob[]>('/api/v1/pets/generation-jobs').then((items) => items.map(resolveProtectedImage)),
  favoriteAsset: (assetId: string, favorite = true): Promise<PetAsset> =>
    apiMode === 'mock'
      ? mockApi.favoriteAsset(assetId, favorite)
      : http.post<PetAsset>('/api/v1/pets/assets/' + assetId + '/favorite', { favorite }).then((r) => resolveProtectedImage(r.data)),
  setCurrentAsset: (assetId: string): Promise<{ ok: true }> =>
    apiMode === 'mock'
      ? mockApi.setCurrentAsset(assetId)
      : http.post<{ ok: true }>('/api/v1/pets/assets/' + assetId + '/set-current').then((r) => r.data),
}

export const deviceApi = {
  list: (): Promise<DeviceRecord[]> =>
    apiMode === 'mock' ? mockApi.devices() : realGet('/api/v1/devices'),
  sync: (id: string): Promise<SyncLog> =>
    apiMode === 'mock'
      ? mockApi.syncDevice(id)
      : http.post<SyncLog>('/api/v1/devices/' + id + '/sync').then((r) => r.data),
  history: (): Promise<SyncLog[]> =>
    apiMode === 'mock' ? mockApi.syncHistory() : realGet('/api/v1/devices/sync-logs'),
  bridgeStatus: (id: string): Promise<BridgeStatus> =>
    apiMode === 'mock' ? mockApi.bridgeStatus(id) : realGet('/api/v1/devices/' + id + '/bridge-status'),
  bind: (serialNumber: string, claimCode: string): Promise<DeviceRecord> =>
    apiMode === 'mock'
      ? Promise.resolve({ ...mockDevicesForBinding(serialNumber), bound: true, syncState: 'synced' })
      : http.post<DeviceRecord>('/api/v1/devices/bind', { serialNumber, claimCode }).then((r) => r.data),
  unbind: (id: string): Promise<{ ok: true }> =>
    apiMode === 'mock'
      ? Promise.resolve({ ok: true })
      : http.delete<{ ok: true }>('/api/v1/devices/' + id + '/binding').then((r) => r.data),
}

function mockDevicesForBinding(serialNumber: string): DeviceRecord {
  return {
    id: serialNumber,
    name: '我的 VelaPet',
    model: 'SF32LB52-ULP',
    bound: false,
    syncState: 'unbound',
  }
}

export const adminApi = {
  overview: (dates: DateRangeQuery = {}): Promise<AdminOverview> =>
    apiMode === 'mock'
      ? mockApi.adminOverview()
      : realGet('/api/v1/admin/metrics/overview?' + buildDateQuery('month', dates)),
  users: (): Promise<UserProfile[]> =>
    apiMode === 'mock' ? mockApi.users() : realGet('/api/v1/admin/users'),
  devices: (): Promise<DeviceRecord[]> =>
    apiMode === 'mock' ? mockApi.devices() : realGet('/api/v1/admin/devices'),
  aiMetrics: (dates: DateRangeQuery = {}): Promise<AiServiceMetric[]> =>
    apiMode === 'mock'
      ? mockApi.aiMetrics()
      : realGet('/api/v1/admin/metrics/ai-services?' + buildDateQuery('month', dates)),
  retention: (): Promise<RetentionPoint[]> =>
    apiMode === 'mock' ? mockApi.retention() : realGet('/api/v1/admin/metrics/retention'),
}

export type {
  ActivitySummary,
  AdminOverview,
  AiServiceMetric,
  AuthSession,
  BridgeStatus,
  CoachingAdvice,
  CoachingGeneration,
  DeviceRecord,
  PetGenerationInput,
  PetGenerationJob,
  PetSnapshot,
  RetentionPoint,
  SyncLog,
  UserProfile,
  WeeklySummary,
}
