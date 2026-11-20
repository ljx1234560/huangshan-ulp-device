<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import type { EChartsOption } from 'echarts'
import { activityApi, aiApi, deviceApi, petApi, type ActivitySummary, type CoachingAdvice, type DeviceRecord, type PetSnapshot } from '@velapet/api'
import { formatDateTime, formatNumber } from '@velapet/shared'
import ChartPanel from '../components/ChartPanel.vue'
import StatCard from '../components/StatCard.vue'

const range = ref<'day' | 'week' | 'month'>('week')
const loading = ref(true)
const error = ref('')
const activity = ref<ActivitySummary>()
const pet = ref<PetSnapshot>()
const device = ref<DeviceRecord>()
const advice = ref<CoachingAdvice>()

async function load() {
  loading.value = true
  error.value = ''
  try {
    const [activityResult, petResult, adviceResult, devicesResult] = await Promise.all([
      activityApi.daily(range.value),
      petApi.current(),
      aiApi.coaching(),
      deviceApi.list(),
    ])
    activity.value = activityResult
    pet.value = petResult
    advice.value = adviceResult[0]
    device.value = devicesResult[0]
  } catch (reason) {
    error.value = reason instanceof Error ? reason.message : '数据加载失败'
  } finally {
    loading.value = false
  }
}

const trendOption = computed<EChartsOption>(() => ({
  tooltip: { trigger: 'axis', valueFormatter: (value) => formatNumber(Number(value)) + ' 步' },
  grid: { left: 18, right: 14, top: 22, bottom: 18, containLabel: true },
  xAxis: {
    type: 'category',
    boundaryGap: false,
    data: activity.value?.points.map((point) => new Date(point.date).toLocaleDateString('zh-CN', { month: 'numeric', day: 'numeric' })) || [],
    axisLine: { show: false }, axisTick: { show: false }, axisLabel: { color: '#9a97aa', fontSize: 11 },
  },
  yAxis: {
    type: 'value', splitLine: { lineStyle: { color: '#efedf5' } }, axisLabel: { color: '#aaa7b8', fontSize: 10 },
  },
  series: [{
    type: 'line',
    data: activity.value?.points.map((point) => point.steps) || [],
    smooth: 0.35,
    symbolSize: 7,
    lineStyle: { width: 3, color: '#6b59e8' },
    itemStyle: { color: '#6b59e8', borderColor: '#fff', borderWidth: 2 },
    areaStyle: {
      color: {
        type: 'linear', x: 0, y: 0, x2: 0, y2: 1,
        colorStops: [{ offset: 0, color: 'rgba(107,89,232,.28)' }, { offset: 1, color: 'rgba(107,89,232,.01)' }],
      },
    },
    markLine: { silent: true, symbol: 'none', lineStyle: { color: '#efac6b', type: 'dashed' }, data: [{ yAxis: 10000, name: '目标' }] },
  }],
}))

onMounted(load)
</script>

<template>
  <div class="page-stack">
    <div class="page-heading">
      <div><h2>早上好，晓满 👋</h2><p>今天也和露米一起，把日常走成闪闪发光的旅程。</p></div>
      <div class="pill-tabs">
        <button v-for="item in ['day', 'week', 'month'] as const" :key="item" :class="{ active: range === item }" @click="range = item; load()">
          {{ { day: '今日', week: '本周', month: '本月' }[item] }}
        </button>
      </div>
    </div>

    <el-alert v-if="error" :title="error" type="error" show-icon :closable="false">
      <template #default><el-button size="small" @click="load">重新加载</el-button></template>
    </el-alert>
    <div v-if="loading" class="surface surface-pad"><el-skeleton :rows="7" animated /></div>
    <template v-else-if="activity">
      <section class="stat-grid">
        <StatCard label="今日步数" :value="formatNumber(activity.todaySteps)" :hint="'目标 ' + formatNumber(activity.goal)" icon="↗" tone="violet" />
        <StatCard label="目标完成" :value="Math.round(activity.completionRate * 100) + '%'" :hint="activity.todaySteps >= activity.goal ? '今日目标已完成' : '再走 ' + formatNumber(activity.goal - activity.todaySteps) + ' 步'" icon="◎" tone="blue" />
        <StatCard label="活跃时长" :value="activity.activeMinutes + ' 分钟'" hint="今日累计活动" icon="◷" tone="coral" />
        <StatCard label="连续活跃" :value="activity.streakDays + ' 天'" hint="个人最好 12 天" icon="✦" tone="mint" />
      </section>

      <section class="two-col">
        <article class="surface surface-pad">
          <div class="section-title">
            <div><h3>运动步数趋势</h3><p>虚线为每日 10,000 步目标</p></div>
            <router-link to="/activity" class="ghost-button">查看详情</router-link>
          </div>
          <ChartPanel :option="trendOption" :height="290" />
        </article>

        <article class="pet-hero surface">
          <div class="pet-hero-copy">
            <span class="pet-level">LV.{{ pet?.level || 7 }} · {{ pet?.title }}</span>
            <h3>{{ pet?.name || '露米' }}</h3>
            <p>“再收集一点脚印，今晚的星光就会更亮啦！”</p>
            <div class="exp-row"><span>EXP</span><strong>{{ pet?.currentExp }} / {{ pet?.nextLevelExp }}</strong></div>
            <el-progress :percentage="Math.round(((pet?.currentExp || 0) / (pet?.nextLevelExp || 1)) * 100)" :show-text="false" :stroke-width="8" color="#ffffff" />
            <router-link to="/pet" class="pet-link">进入成长中心 →</router-link>
          </div>
          <img :src="pet?.imageUrl || '/pets/lumi.png'" alt="内置示例萌宠露米" />
          <span class="asset-label">内置 Mock 素材</span>
        </article>
      </section>

      <section class="two-col">
        <article class="surface surface-pad advice-card">
          <div class="section-title"><div><h3>AI 运动建议摘要</h3><p>依据步数、活动时长和近期趋势生成</p></div><span class="source-chip">MOCK</span></div>
          <div class="advice-content">
            <span class="advice-icon">✦</span>
            <div><strong>{{ advice?.title }}</strong><p>{{ advice?.content }}</p></div>
          </div>
          <div class="evidence-row"><span v-for="item in advice?.evidence" :key="item">{{ item }}</span></div>
          <router-link to="/coach" class="text-link">查看完整建议与本周计划 →</router-link>
        </article>
        <article class="surface surface-pad sync-card">
          <div class="section-title"><div><h3>设备同步</h3><p>同步链路当前使用 Mock API</p></div><span class="sync-ok">● 已同步</span></div>
          <div class="device-mini"><span class="watch-shape">V</span><div><strong>{{ device?.name || '尚未绑定设备' }}</strong><p>{{ device ? device.model + ' · ' + (device.battery === undefined ? '电量暂无' : '电量 ' + device.battery + '%') : '前往设备中心完成绑定' }}</p></div></div>
          <p class="sync-time">最近同步 {{ formatDateTime(activity.lastSyncAt) }}</p>
          <router-link to="/devices" class="text-link">查看同步记录 →</router-link>
        </article>
      </section>
    </template>
  </div>
</template>

<style scoped>
.pet-hero { min-height: 370px; position: relative; overflow: hidden; padding: 25px; color: white; background: radial-gradient(circle at 84% 20%, rgba(255,255,255,.26), transparent 27%), linear-gradient(145deg, #7260ec, #5442ce); }
.pet-hero::before { content:''; position:absolute; width:210px; height:210px; border:1px solid rgba(255,255,255,.15); border-radius:50%; right:-15px; top:24px; }
.pet-hero-copy { position: relative; z-index: 2; max-width: 58%; }
.pet-level { display:inline-block; padding:6px 9px; border-radius:99px; background:rgba(255,255,255,.16); font-size:10px; font-weight:700; letter-spacing:.6px; }
.pet-hero h3 { font-size:34px; margin:18px 0 5px; }.pet-hero-copy p { font-size:13px; color:rgba(255,255,255,.77); line-height:1.6; }
.pet-hero img { position:absolute; width:64%; max-width:290px; right:-20px; bottom:-4px; filter:drop-shadow(0 18px 20px rgba(31,20,95,.25)); z-index:1; }
.exp-row { display:flex; justify-content:space-between; font-size:10px; margin:25px 0 6px; }.pet-link { display:inline-block; margin-top:17px; font-size:12px; font-weight:700; }
.asset-label { position:absolute; right:12px; top:12px; z-index:3; padding:4px 7px; border-radius:99px; font-size:9px; color:rgba(255,255,255,.75); background:rgba(29,18,99,.22); }
.advice-content { display:flex; gap:13px; padding:17px; border-radius:16px; background:#f7f5ff; }.advice-icon { width:40px;height:40px;flex:0 0 auto;display:grid;place-items:center;border-radius:13px;color:#624ed7;background:white;box-shadow:0 6px 16px rgba(65,51,143,.1); }
.advice-content strong { font-size:15px; }.advice-content p { margin:7px 0 0; color:#706c86; font-size:13px; line-height:1.7; }
.evidence-row { display:flex; flex-wrap:wrap; gap:7px; margin:13px 0; }.evidence-row span,.source-chip { padding:5px 8px;border-radius:8px;background:#f0eef9;color:#767089;font-size:10px; }
.text-link { color:#5f4cda;font-size:12px;font-weight:700; }.sync-ok { color:#2fa985;font-size:11px; }.device-mini { display:flex;align-items:center;gap:13px;margin:20px 0; }.watch-shape { width:48px;height:58px;display:grid;place-items:center;border-radius:16px;color:white;font-weight:800;background:#2c2942;box-shadow:inset 0 0 0 4px #4a465e; }.device-mini p,.sync-time { color:#858295;font-size:12px;margin:4px 0 0; }.sync-time { padding:10px 0 16px;border-top:1px solid #efedf4; }
@media(max-width:600px){.pet-hero{min-height:350px}.pet-hero-copy{max-width:66%}.pet-hero img{width:58%;}.pet-hero h3{font-size:28px}}
</style>
