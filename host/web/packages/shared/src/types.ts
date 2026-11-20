export type ApiMode = 'mock' | 'real'
export type UserRole = 'user' | 'admin'
export type DataRange = 'day' | 'week' | 'month'

export interface UserProfile {
  id: string
  name: string
  email: string
  avatar?: string
  role: UserRole
  status: 'active' | 'disabled'
  registeredAt: string
  lastActiveAt: string
  deviceBound: boolean
}

export interface AuthSession {
  token?: string
  demo: boolean
  user: UserProfile
  expiresAt?: string
}

export interface DateRangeQuery {
  startDate?: string
  endDate?: string
}

export interface ActivityQuery extends DateRangeQuery {
  range: DataRange
}

export interface ActivityPoint {
  date: string
  steps: number
  activeMinutes: number
  goal: number
  source?: 'hardware' | 'test_injected' | 'demo' | 'mixed' | 'unknown'
}

export interface ActivitySummary {
  todaySteps: number
  goal: number
  activeMinutes: number
  streakDays: number
  completionRate: number
  lastSyncAt: string
  syncState: 'synced' | 'pending' | 'failed'
  dataSource?: 'hardware' | 'test_injected' | 'demo' | 'mixed' | 'unknown' | 'empty'
  points: ActivityPoint[]
}

export interface WeeklySummary {
  averageSteps: number
  totalActiveMinutes: number
  completedDays: number
  previousPeriodDelta: number
}

export interface CoachingAdvice {
  id: string
  title: string
  content: string
  evidence: string[]
  category: 'today' | 'plan' | 'goal' | 'trend' | 'sedentary' | 'encouragement'
  source: 'mock' | 'deepseek' | 'mimo' | 'local_fallback'
}

export type PetSpecies = 'fox' | 'cat' | 'rabbit'
export type PetStyle = 'celestial' | 'forest' | 'pixel'
export type PetPersonality = 'energetic' | 'gentle' | 'curious'

export interface PetGenerationInput {
  species: PetSpecies
  color: string
  style: PetStyle
  personality: PetPersonality
  name: string
  description: string
}

export interface PetGenerationJob {
  id: string
  status: 'queued' | 'processing' | 'succeeded' | 'failed'
  progress: number
  createdAt: string
  imageUrl?: string
  assetId?: string
  petId?: string
  error?: string
  input: PetGenerationInput
  source: 'mock_asset' | 'ai_generated'
}

export interface PetAsset {
  id: string
  ownerId: string
  generationJobId: string
  imageUrl: string
  name: string
  favorite: boolean
  createdAt: string
  source: 'mock_asset' | 'ai_generated'
}

export interface PetTask {
  id: string
  title: string
  progress: number
  target: number
  rewardLabel: string
  status: 'active' | 'completed' | 'claimed'
}

export interface PetSnapshot {
  id: string
  name: string
  level: number
  currentExp: number
  nextLevelExp: number
  title: string
  imageUrl: string
  skins: string[]
  tasks: PetTask[]
  totalSteps: number
  streakDays: number
  lastSyncedAt: string
  source: 'device_snapshot' | 'mock'
  currentAssetId?: string
}

export interface DeviceRecord {
  id: string
  name: string
  model: string
  firmwareVersion?: string
  protocolVersion?: number
  battery?: number
  bound: boolean
  lastSyncAt?: string
  syncState: 'synced' | 'stale' | 'error' | 'unbound'
  anomaly?: string
  syncFailureCount?: number
  bridge?: BridgeStatus
}

export interface BridgeStatus {
  state: 'not_running' | 'authorized' | 'connecting' | 'connected' | 'syncing' | 'success' | 'failed' | 'disconnected' | 'stale'
  connected: boolean
  running: boolean
  message: string
  lastSeenAt?: string
  clientId?: string
  lastSyncStatus?: 'success' | 'failed'
  lastSyncAt?: string
  lastSyncMessage?: string
}

export interface SyncLog {
  id: string
  deviceId: string
  createdAt: string
  status: 'pending' | 'success' | 'failed'
  recordCount: number
  message: string
  source?: 'web_request' | 'device_upload'
  transport?: 'direct_api' | 'ble_bridge'
}

export interface AdminOverview {
  dau: number
  deviceDau: number
  activeDevices?: number
  productDau: number
  wau: number
  mau: number
  totalUsers: number
  newUsers: number
  boundDevices: number
  syncSuccessRate: number
  syncFailures?: number
  bleBridgeSyncs?: number
  firmwareVersions?: Record<string, number>
  petGenerations: number
  retentionRate: number
  syncedUsers: number
  petOwners: number
  petCreationRate: number
  goalCompletionRate: number
  dataSource: 'empty' | 'demo' | 'production' | 'mixed'
  trend: Array<{
    date: string
    webDau: number
    deviceDau: number
    productDau: number
    newUsers: number
  }>
}

export interface AiServiceMetric {
  date: string
  textCalls: number
  imageCalls: number
  successRate: number
  failedJobs: number
  cost: number
}

export interface RetentionPoint {
  cohort: string
  day1: number
  day7: number
  day30: number
}
