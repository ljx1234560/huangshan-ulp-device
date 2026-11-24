import type {
  ActivityPoint,
  ActivitySummary,
  AdminOverview,
  AiServiceMetric,
  AuthSession,
  CoachingAdvice,
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

const wait = (ms = 420) => new Promise((resolve) => setTimeout(resolve, ms))

const memoryStorage = new Map<string, string>()
const storage = {
  get(key: string) {
    if (typeof localStorage !== 'undefined') return localStorage.getItem(key)
    return memoryStorage.get(key) ?? null
  },
  set(key: string, value: string) {
    if (typeof localStorage !== 'undefined') localStorage.setItem(key, value)
    else memoryStorage.set(key, value)
  },
}

function readStored<T>(key: string, fallback: T): T {
  try {
    const raw = storage.get(key)
    return raw ? (JSON.parse(raw) as T) : fallback
  } catch {
    return fallback
  }
}

function writeStored(key: string, value: unknown) {
  storage.set(key, JSON.stringify(value))
}

const syncStorageKey = 'velapet_mock_sync_logs'
const jobStorageKey = 'velapet_mock_pet_jobs'
const assetStorageKey = 'velapet_mock_pet_assets'
const currentAssetStorageKey = 'velapet_mock_current_asset'

function daysAgo(days: number): string {
  const date = new Date()
  date.setHours(8, 0, 0, 0)
  date.setDate(date.getDate() - days)
  return date.toISOString()
}

const stepPattern = [6210, 9840, 7420, 10680, 8930, 12460, 8362, 9500, 7120, 11800, 10240, 6800, 12840, 8362]

export function makeActivityPoints(days: number): ActivityPoint[] {
  return Array.from({ length: days }, (_, index) => {
    const remaining = days - index - 1
    const steps = stepPattern[index % stepPattern.length] ?? 8000
    return {
      date: daysAgo(remaining),
      steps,
      activeMinutes: Math.round(steps / 185),
      goal: 10_000,
      source: 'demo',
    }
  })
}

export const mockUsers: UserProfile[] = [
  {
    id: 'u_001',
    name: '林晓满',
    email: 'demo@velapet.cn',
    role: 'user',
    status: 'active',
    registeredAt: daysAgo(96),
    lastActiveAt: daysAgo(0),
    deviceBound: true,
  },
  {
    id: 'u_002',
    name: '陈星河',
    email: 'star@example.com',
    role: 'user',
    status: 'active',
    registeredAt: daysAgo(58),
    lastActiveAt: daysAgo(1),
    deviceBound: true,
  },
  {
    id: 'u_003',
    name: '周可可',
    email: 'coco@example.com',
    role: 'user',
    status: 'disabled',
    registeredAt: daysAgo(31),
    lastActiveAt: daysAgo(9),
    deviceBound: false,
  },
  {
    id: 'u_004',
    name: '许北辰',
    email: 'north@example.com',
    role: 'user',
    status: 'active',
    registeredAt: daysAgo(12),
    lastActiveAt: daysAgo(0),
    deviceBound: true,
  },
]

export const mockDevices: DeviceRecord[] = [
  {
    id: 'VP-52U-2400168',
    name: '我的 VelaPet',
    model: 'SF32LB52-ULP',
    firmwareVersion: '0.3.2-demo',
    battery: 78,
    bound: true,
    lastSyncAt: new Date(Date.now() - 18 * 60_000).toISOString(),
    syncState: 'synced',
    protocolVersion: 1,
    bridge: { state: 'not_running', connected: false, running: false, message: 'Mock 模式不连接本机桥接程序' },
  },
  {
    id: 'VP-52U-2400141',
    name: 'VelaPet 0141',
    model: 'SF32LB52-ULP',
    firmwareVersion: '0.3.1',
    battery: 34,
    bound: true,
    lastSyncAt: daysAgo(2),
    syncState: 'stale',
    anomaly: '超过 24 小时未同步',
  },
  {
    id: 'VP-52U-2400097',
    name: 'VelaPet 0097',
    model: 'SF32LB52-ULP',
    firmwareVersion: '0.2.8',
    bound: false,
    syncState: 'unbound',
  },
  {
    id: 'VP-52U-2400052',
    name: 'VelaPet 0052',
    model: 'SF32LB52-ULP',
    firmwareVersion: '0.3.0',
    battery: 51,
    bound: true,
    lastSyncAt: daysAgo(0),
    syncState: 'error',
    anomaly: '最近一次同步校验失败',
  },
]

export const syncLogs: SyncLog[] = [
  {
    id: 's_003',
    deviceId: 'VP-52U-2400168',
    createdAt: new Date(Date.now() - 18 * 60_000).toISOString(),
    status: 'success',
    source: 'device_upload',
    recordCount: 24,
    message: '运动快照与宠物状态已同步',
  },
  {
    id: 's_002',
    deviceId: 'VP-52U-2400168',
    createdAt: daysAgo(1),
    status: 'success',
    source: 'device_upload',
    recordCount: 18,
    message: '每日活动记录同步完成',
  },
  {
    id: 's_001',
    deviceId: 'VP-52U-2400168',
    createdAt: daysAgo(3),
    status: 'failed',
    source: 'web_request',
    recordCount: 0,
    message: '同步桥接服务未连接',
  },
]

export const petSnapshot: PetSnapshot = {
  id: 'pet_lumi',
  name: '露米',
  level: 7,
  currentExp: 680,
  nextLevelExp: 1000,
  title: '星光散步家',
  imageUrl: '/pets/lumi.png',
  skins: ['星云围巾', '晨光铃铛', '薄荷脚印'],
  tasks: [
    { id: 't1', title: '今天走到 10,000 步', progress: 8362, target: 10000, rewardLabel: '设备规则奖励', status: 'active' },
    { id: 't2', title: '保持活跃 45 分钟', progress: 45, target: 45, rewardLabel: '等待设备确认', status: 'completed' },
    { id: 't3', title: '连续活跃 7 天', progress: 6, target: 7, rewardLabel: '稀有装扮线索', status: 'active' },
  ],
  totalSteps: 486_320,
  streakDays: 6,
  lastSyncedAt: new Date(Date.now() - 18 * 60_000).toISOString(),
  source: 'mock',
  currentAssetId: 'asset_lumi_builtin',
}

const jobs = new Map<string, PetGenerationJob>(
  readStored<PetGenerationJob[]>(jobStorageKey, []).map((job) => [job.id, job]),
)

function persistJobs() {
  writeStored(jobStorageKey, [...jobs.values()])
}

function readAssets(): PetAsset[] {
  return readStored<PetAsset[]>(assetStorageKey, [])
}

export const mockApi = {
  async login(email: string, role: 'user' | 'admin' = 'user'): Promise<AuthSession> {
    await wait()
    const isAdmin = role === 'admin'
    return {
      token: 'demo-token-' + role,
      demo: true,
      user: {
        id: isAdmin ? 'admin_001' : 'u_001',
        name: isAdmin ? '运营管理员' : '林晓满',
        email: email || (isAdmin ? 'admin@velapet.cn' : 'demo@velapet.cn'),
        role,
        status: 'active',
        registeredAt: daysAgo(120),
        lastActiveAt: new Date().toISOString(),
        deviceBound: !isAdmin,
      },
    }
  },

  async register(name: string, email: string): Promise<AuthSession> {
    await wait(650)
    return this.login(email || name, 'user')
  },

  async activity(range: 'day' | 'week' | 'month' = 'week'): Promise<ActivitySummary> {
    await wait()
    const days = range === 'day' ? 1 : range === 'week' ? 7 : 30
    return {
      todaySteps: 8362,
      goal: 10_000,
      activeMinutes: 45,
      streakDays: 6,
      completionRate: 0.8362,
      lastSyncAt: new Date(Date.now() - 18 * 60_000).toISOString(),
      syncState: 'synced',
      dataSource: 'demo',
      points: makeActivityPoints(days),
    }
  },

  async weeklySummary(): Promise<WeeklySummary> {
    await wait(260)
    return { averageSteps: 9128, totalActiveMinutes: 327, completedDays: 4, previousPeriodDelta: 0.12 }
  },

  async coaching(): Promise<CoachingAdvice[]> {
    await wait(560)
    return [
      {
        id: 'a1',
        title: '把最后 1,638 步变成轻松散步',
        content: '晚饭后安排约 18 分钟舒缓步行，接近目标时放慢节奏即可。',
        evidence: ['今日 8,362 步', '目标 10,000 步', '近 7 天平均 9,128 步'],
        category: 'today',
        source: 'mock',
      },
      {
        id: 'a2',
        title: '本周节奏：两高、三稳、两轻',
        content: '周二与周五尝试超过 10,500 步，其余工作日维持 8,000 步，周末以恢复为主。',
        evidence: ['近 7 天有 4 天完成目标', '连续活跃 6 天'],
        category: 'plan',
        source: 'mock',
      },
      {
        id: 'a3',
        title: '久坐提醒',
        content: '如果已经连续坐了 60 分钟，起身走动 3–5 分钟。此建议不构成医疗判断。',
        evidence: ['当前仅依据活动时长和步数趋势', '未使用心率、血氧或 GPS'],
        category: 'sedentary',
        source: 'mock',
      },
      {
        id: 'a4',
        title: '露米的鼓励',
        content: '再一起去收集一点晚霞脚印吧，今天的星光徽章就快点亮啦！',
        evidence: ['今日目标完成 84%', '萌宠性格：活泼'],
        category: 'encouragement',
        source: 'mock',
      },
    ]
  },

  async createPetJob(input: PetGenerationInput): Promise<PetGenerationJob> {
    await wait(480)
    const id = 'job_' + Date.now()
    const job: PetGenerationJob = {
      id,
      status: 'queued',
      progress: 8,
      createdAt: new Date().toISOString(),
      input,
      source: 'mock_asset',
    }
    jobs.set(id, job)
    persistJobs()
    return job
  },

  async petJob(id: string): Promise<PetGenerationJob> {
    await wait(360)
    const job = jobs.get(id)
    if (!job) throw new Error('生成任务不存在')
    const elapsed = Date.now() - new Date(job.createdAt).getTime()
    if (elapsed > 2300) {
      job.status = 'succeeded'
      job.progress = 100
      job.imageUrl = '/pets/lumi.png'
      job.assetId = job.assetId || 'asset_' + id.slice(4)
      job.petId = 'pet_lumi'
      const assets = readAssets()
      if (!assets.some((asset) => asset.id === job.assetId)) {
        assets.unshift({
          id: job.assetId,
          ownerId: 'u_001',
          generationJobId: job.id,
          imageUrl: job.imageUrl,
          name: job.input.name,
          favorite: false,
          createdAt: new Date().toISOString(),
          source: 'mock_asset',
        })
        writeStored(assetStorageKey, assets)
      }
    } else {
      job.status = 'processing'
      job.progress = Math.min(88, 20 + Math.round(elapsed / 30))
    }
    persistJobs()
    return { ...job }
  },

  async petJobs(): Promise<PetGenerationJob[]> {
    await wait(180)
    return [...jobs.values()].sort((a, b) => b.createdAt.localeCompare(a.createdAt))
  },

  async favoriteAsset(assetId: string, favorite: boolean): Promise<PetAsset> {
    await wait(180)
    const assets = readAssets()
    const asset = assets.find((item) => item.id === assetId)
    if (!asset) throw new Error('萌宠资源不存在')
    asset.favorite = favorite
    writeStored(assetStorageKey, assets)
    return { ...asset }
  },

  async setCurrentAsset(assetId: string): Promise<{ ok: true }> {
    await wait(180)
    const asset = readAssets().find((item) => item.id === assetId)
    if (!asset) throw new Error('萌宠资源不存在')
    writeStored(currentAssetStorageKey, assetId)
    return { ok: true }
  },

  async pet(): Promise<PetSnapshot> {
    await wait()
    const currentAssetId = readStored(currentAssetStorageKey, petSnapshot.currentAssetId)
    const asset = readAssets().find((item) => item.id === currentAssetId)
    return { ...petSnapshot, currentAssetId, imageUrl: asset?.imageUrl || petSnapshot.imageUrl, name: asset?.name || petSnapshot.name }
  },

  async devices(): Promise<DeviceRecord[]> {
    await wait()
    return mockDevices.map((device) => ({ ...device }))
  },

  async syncDevice(deviceId: string): Promise<SyncLog> {
    await wait(1100)
    const log: SyncLog = {
      id: 's_' + Date.now(),
      deviceId,
      createdAt: new Date().toISOString(),
      status: 'pending',
      recordCount: 0,
      message: 'Mock 同步请求已记录；等待模拟桥接上传',
      source: 'web_request',
    }
    const stored = readStored<SyncLog[]>(syncStorageKey, syncLogs)
    stored.unshift(log)
    writeStored(syncStorageKey, stored)
    return log
  },

  async syncHistory(): Promise<SyncLog[]> {
    await wait(280)
    return readStored<SyncLog[]>(syncStorageKey, syncLogs).map((log) => ({ ...log }))
  },

  async bridgeStatus(deviceId: string) {
    await wait(120)
    return mockDevices.find((device) => device.id === deviceId)?.bridge || {
      state: 'not_running' as const,
      connected: false,
      running: false,
      message: 'Mock 模式不连接本机桥接程序',
    }
  },

  async adminOverview(): Promise<AdminOverview> {
    await wait()
    return {
      dau: 1284,
      deviceDau: 2148,
      activeDevices: 2,
      productDau: 2670,
      wau: 6490,
      mau: 18320,
      totalUsers: 24680,
      newUsers: 326,
      boundDevices: 16842,
      syncSuccessRate: 0.976,
      syncFailures: 126,
      bleBridgeSyncs: 0,
      firmwareVersions: { '0.3.2-demo': 1, '0.3.1': 1, '0.3.0': 1, '0.2.8': 1 },
      petGenerations: 2841,
      retentionRate: 0.428,
      syncedUsers: 15906,
      petOwners: 11284,
      petCreationRate: 0.71,
      goalCompletionRate: 0.563,
      dataSource: 'demo',
      trend: Array.from({ length: 14 }, (_, index) => ({
        date: daysAgo(13 - index),
        webDau: 920 + ((index * 83) % 410),
        deviceDau: 1710 + ((index * 127) % 520),
        productDau: 2050 + ((index * 101) % 650),
        newUsers: 180 + ((index * 29) % 170),
      })),
    }
  },

  async users(): Promise<UserProfile[]> {
    await wait()
    return mockUsers.map((user) => ({ ...user }))
  },

  async aiMetrics(): Promise<AiServiceMetric[]> {
    await wait()
    return Array.from({ length: 14 }, (_, index) => ({
      date: daysAgo(13 - index),
      textCalls: 1280 + ((index * 137) % 720),
      imageCalls: 220 + ((index * 47) % 260),
      successRate: 0.945 + ((index % 5) * 0.009),
      failedJobs: 8 + ((index * 3) % 16),
      cost: 186 + ((index * 29) % 130),
    }))
  },

  async retention(): Promise<RetentionPoint[]> {
    await wait(280)
    return [
      { cohort: '10/21–10/27', day1: 0.68, day7: 0.45, day30: 0.28 },
      { cohort: '10/28–11/03', day1: 0.71, day7: 0.48, day30: 0.31 },
      { cohort: '11/04–11/10', day1: 0.74, day7: 0.51, day30: 0 },
      { cohort: '11/11–11/17', day1: 0.76, day7: 0, day30: 0 },
    ]
  },
}
