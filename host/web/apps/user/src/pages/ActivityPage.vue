<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import type { EChartsOption } from 'echarts'
import { activityApi, apiMode, type ActivitySummary, type WeeklySummary } from '@velapet/api'
import { formatDateTime, formatNumber } from '@velapet/shared'
import ChartPanel from '../components/ChartPanel.vue'
import StatCard from '../components/StatCard.vue'

const range = ref<'week' | 'month'>('week')
const dateRange = ref<[Date, Date]>()
const activity = ref<ActivitySummary>()
const weekly = ref<WeeklySummary>()
const loading = ref(true)
const error = ref('')

async function load() {
  loading.value = true
  error.value = ''
  try {
    const dates = dateRange.value
      ? { startDate: toDate(dateRange.value[0]), endDate: toDate(dateRange.value[1]) }
      : {}
    ;[activity.value, weekly.value] = await Promise.all([
      activityApi.trends(range.value, dates),
      activityApi.weeklySummary(dates),
    ])
  } catch (reason) {
    error.value = reason instanceof Error ? reason.message : '运动数据加载失败'
  } finally {
    loading.value = false
  }
}

function toDate(value: Date): string {
  const month = String(value.getMonth() + 1).padStart(2, '0')
  const day = String(value.getDate()).padStart(2, '0')
  return value.getFullYear() + '-' + month + '-' + day
}

const stepsOption = computed<EChartsOption>(() => ({
  tooltip: { trigger: 'axis' },
  grid: { left: 20, right: 12, top: 25, bottom: 18, containLabel: true },
  xAxis: { type: 'category', data: activity.value?.points.map((p) => new Date(p.date).toLocaleDateString('zh-CN', { month: 'numeric', day: 'numeric' })) || [], axisTick: { show: false }, axisLine: { show: false }, axisLabel: { color: '#9895a9' } },
  yAxis: { type: 'value', splitLine: { lineStyle: { color: '#efedf5' } }, axisLabel: { color: '#aaa7b8' } },
  series: [
    { name: '步数', type: 'bar', barMaxWidth: 24, data: activity.value?.points.map((p) => p.steps) || [], itemStyle: { color: '#7563ee', borderRadius: [7, 7, 2, 2] } },
    { name: '目标', type: 'line', symbol: 'none', data: activity.value?.points.map((p) => p.goal) || [], lineStyle: { color: '#ff9c79', type: 'dashed', width: 2 } },
  ],
}))

const durationOption = computed<EChartsOption>(() => ({
  tooltip: { trigger: 'axis', valueFormatter: (value) => value + ' 分钟' },
  grid: { left: 18, right: 12, top: 25, bottom: 18, containLabel: true },
  xAxis: { type: 'category', data: activity.value?.points.map((p) => new Date(p.date).toLocaleDateString('zh-CN', { month: 'numeric', day: 'numeric' })) || [], axisTick: { show: false }, axisLine: { show: false }, axisLabel: { color: '#9895a9' } },
  yAxis: { type: 'value', splitLine: { lineStyle: { color: '#efedf5' } }, axisLabel: { color: '#aaa7b8' } },
  series: [{ type: 'line', smooth: true, symbolSize: 6, data: activity.value?.points.map((p) => p.activeMinutes) || [], lineStyle: { width: 3, color: '#43bfa0' }, itemStyle: { color: '#43bfa0' }, areaStyle: { color: 'rgba(67,191,160,.13)' } }],
}))

onMounted(load)
</script>

<template>
  <div class="page-stack">
    <div class="page-heading">
      <div><h2>运动数据</h2><p>只展示已有硬件依据的步数与活动时长，不包含心率、血氧或 GPS。</p></div>
      <div class="filter-row">
        <el-date-picker v-model="dateRange" type="daterange" range-separator="至" start-placeholder="开始日期" end-placeholder="结束日期" size="default" @change="load" />
        <div class="pill-tabs"><button :class="{ active: range === 'week' }" @click="range='week'; load()">周</button><button :class="{ active: range === 'month' }" @click="range='month'; load()">月</button></div>
      </div>
    </div>
    <el-alert :title="apiMode === 'mock' ? 'Mock 数据模式：筛选参数会被保留，但演示数据仅模拟同一返回结构。' : 'Real API：日期范围将发送到后端并按当前登录用户隔离查询。'" :type="apiMode === 'mock' ? 'warning' : 'success'" show-icon :closable="false" />
    <el-alert v-if="error" :title="error" type="error" show-icon :closable="false" />
    <div v-if="loading" class="surface surface-pad"><el-skeleton :rows="8" animated /></div>
    <template v-else-if="activity && weekly">
      <section class="stat-grid">
        <StatCard label="期间日均步数" :value="formatNumber(weekly.averageSteps)" :hint="'较上期 +' + Math.round(weekly.previousPeriodDelta * 100) + '%'" icon="↗" />
        <StatCard label="累计活跃时长" :value="weekly.totalActiveMinutes + ' 分钟'" hint="基于活动记录汇总" icon="◷" tone="blue" />
        <StatCard label="目标完成天数" :value="weekly.completedDays + ' 天'" :hint="'目标 ' + formatNumber(activity.goal) + ' 步 / 天'" icon="◎" tone="coral" />
        <StatCard label="同步状态" :value="activity.syncState === 'synced' ? '已同步' : activity.syncState === 'pending' ? '等待同步' : '同步失败'" :hint="formatDateTime(activity.lastSyncAt)" icon="✓" tone="mint" />
      </section>
      <section class="surface surface-pad">
        <div class="section-title"><div><h3>每日步数与目标</h3><p>柱形为实际步数，虚线为目标</p></div><span class="sync-chip">● 来源：{{ activity.dataSource || (apiMode === 'mock' ? 'demo' : 'unknown') }}</span></div>
        <ChartPanel :option="stepsOption" :height="330" />
      </section>
      <section class="two-col equal">
        <article class="surface surface-pad">
          <div class="section-title"><div><h3>活动时长趋势</h3><p>按日累计的活跃分钟数</p></div></div>
          <ChartPanel :option="durationOption" :height="270" />
        </article>
        <article class="surface surface-pad">
          <div class="section-title"><div><h3>每周运动总结</h3><p>从趋势中提炼，不作健康诊断</p></div></div>
          <div class="summary-score"><strong>B+</strong><span>稳定上升</span></div>
          <ul class="insight-list">
            <li><span>01</span><div><strong>目标节奏更稳定</strong><p>本周已有 {{ weekly.completedDays }} 天完成 {{ formatNumber(activity.goal) }} 步目标。</p></div></li>
            <li><span>02</span><div><strong>周中表现最好</strong><p>最高活动日达到 {{ formatNumber(Math.max(...activity.points.map((p) => p.steps))) }} 步。</p></div></li>
            <li><span>03</span><div><strong>注意温和恢复</strong><p>连续活跃后可以安排轻松散步日，不必每天追求新高。</p></div></li>
          </ul>
        </article>
      </section>
      <section class="surface surface-pad table-surface">
        <div class="section-title"><div><h3>历史运动记录</h3><p>最近记录；服务端对真实数据分页</p></div></div>
        <el-table :data="[...activity.points].reverse().slice(0, 10)" style="width:100%">
          <el-table-column label="日期" min-width="120"><template #default="{ row }">{{ new Date(row.date).toLocaleDateString('zh-CN') }}</template></el-table-column>
          <el-table-column prop="steps" label="步数" min-width="120"><template #default="{ row }">{{ formatNumber(row.steps) }}</template></el-table-column>
          <el-table-column prop="activeMinutes" label="活跃时长" min-width="120"><template #default="{ row }">{{ row.activeMinutes }} 分钟</template></el-table-column>
          <el-table-column label="数据来源" width="120"><template #default="{ row }"><el-tag :type="row.source === 'hardware' ? 'success' : 'info'" effect="plain">{{ row.source === 'hardware' ? '硬件采集' : row.source === 'test_injected' ? '测试注入' : row.source || '未知' }}</el-tag></template></el-table-column>
          <el-table-column label="目标完成" min-width="180"><template #default="{ row }"><el-progress :percentage="Math.min(100, Math.round(row.steps / row.goal * 100))" :stroke-width="7" /></template></el-table-column>
          <el-table-column label="同步" width="100"><template #default><el-tag type="success" effect="plain">已同步</el-tag></template></el-table-column>
        </el-table>
      </section>
    </template>
  </div>
</template>

<style scoped>
.filter-row{display:flex;align-items:center;gap:10px}.sync-chip{font-size:11px;color:#2fa985}.equal{grid-template-columns:1fr 1fr}.summary-score{display:flex;align-items:baseline;gap:10px;padding:12px 0 18px;border-bottom:1px solid #eeecf4}.summary-score strong{font-size:44px;color:#6754df}.summary-score span{color:#48b190;font-weight:700}.insight-list{list-style:none;padding:0;margin:13px 0 0;display:grid;gap:13px}.insight-list li{display:flex;gap:12px}.insight-list li>span{width:30px;height:30px;display:grid;place-items:center;border-radius:10px;background:#f0edff;color:#6653da;font-size:10px;font-weight:700}.insight-list strong{font-size:13px}.insight-list p{margin:3px 0 0;color:#858195;font-size:12px;line-height:1.5}@media(max-width:900px){.equal{grid-template-columns:1fr}.filter-row{align-items:flex-end;flex-direction:column}.filter-row :deep(.el-date-editor){max-width:100%}}
</style>
