<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { aiApi, type CoachingGeneration } from '@velapet/api'
import { ElMessage } from 'element-plus'
import { formatDateTime, formatNumber } from '@velapet/shared'

const loading = ref(true)
const generating = ref(false)
const error = ref('')
const history = ref<CoachingGeneration[]>([])
const generation = ref<CoachingGeneration>()
const advice = computed(() => generation.value?.advice || [])

const categories = {
  today: { icon: '↗', label: '今日建议', tone: 'violet' },
  plan: { icon: '▦', label: '本周计划', tone: 'blue' },
  goal: { icon: '◎', label: '目标推荐', tone: 'coral' },
  trend: { icon: '⌁', label: '趋势分析', tone: 'mint' },
  sedentary: { icon: '◷', label: '久坐提醒', tone: 'coral' },
  encouragement: { icon: '✦', label: '萌宠鼓励', tone: 'violet' },
} as const

const completion = computed(() => {
  const insight = generation.value?.insight
  if (!insight?.current_goal) return 0
  return Math.min(100, Math.round(insight.today_steps / insight.current_goal * 100))
})

const sourceLabel = computed(() => ({
  mock: 'MOCK AI · 离线演示',
  deepseek: 'DEEPSEEK · 真实生成',
  existing_velapet: 'VELAPET AI · 真实生成',
  rules: 'SAFE RULES · 数据不足',
  local_fallback: 'LOCAL RULES',
}[generation.value?.source || 'rules']))

async function loadHistory() {
  loading.value = true
  error.value = ''
  try {
    history.value = await aiApi.history()
    generation.value = history.value[0]
  } catch (reason) { error.value = reason instanceof Error ? reason.message : '建议历史加载失败' }
  finally { loading.value = false }
}

async function generate() {
  generating.value = true
  error.value = ''
  try {
    const created = await aiApi.generate()
    generation.value = created
    history.value = [created, ...history.value.filter((item) => item.id !== created.id)]
    ElMessage.success(created.source === 'deepseek' ? 'DeepSeek 建议生成成功' : '运动建议已生成')
  } catch (reason) {
    error.value = reason instanceof Error ? reason.message : '建议生成失败'
    ElMessage.error(error.value)
  } finally { generating.value = false }
}

function showHistory(item: CoachingGeneration) {
  generation.value = item
  window.scrollTo({ top: 0, behavior: 'smooth' })
}

function enableReminder() {
  ElMessage.success('演示提醒已开启；正式版将由移动端或后端推送')
}

onMounted(loadHistory)
</script>

<template>
  <div class="page-stack">
    <div class="page-heading">
      <div><h2>AI 运动教练</h2><p>基于运动事实给出可解释建议，不替代医疗或专业训练意见。</p></div>
      <button class="primary-button" :disabled="loading || generating" @click="generate">{{ generating ? '生成中…' : generation ? '✦ 重新生成建议' : '✦ 生成运动建议' }}</button>
    </div>
    <div v-if="generation" class="coach-hero surface">
      <div class="coach-copy">
        <span class="source-label">{{ sourceLabel }}</span>
        <h3>今天的目标，不是更拼，<br />而是走得更有节奏。</h3>
        <p>当前依据：今日 {{ formatNumber(generation.insight.today_steps) }} 步、活跃 {{ generation.insight.today_active_minutes }} 分钟、已记录 {{ generation.insight.days_with_data }} 天、日均 {{ formatNumber(generation.insight.average_steps) }} 步。</p>
      </div>
      <div class="coach-orbit"><span>{{ completion }}%</span><small>今日目标</small></div>
    </div>
    <div v-else-if="!loading" class="surface surface-pad"><el-empty description="尚无运动建议，点击上方按钮生成" /></div>
    <el-alert v-if="error" :title="error" type="error" show-icon :closable="false" />
    <div v-if="loading || generating" class="surface surface-pad"><el-skeleton :rows="8" animated /></div>
    <template v-else-if="generation">
      <section class="advice-grid">
        <article v-for="item in advice" :key="item.id" class="surface advice-tile">
          <div class="tile-head">
            <span class="tile-icon" :class="'tone-' + categories[item.category].tone">{{ categories[item.category].icon }}</span>
            <span class="tile-label">{{ categories[item.category].label }}</span>
            <span class="source-label mini">{{ item.source }}</span>
          </div>
          <h3>{{ item.title }}</h3>
          <p>{{ item.content }}</p>
          <div class="basis"><strong>建议依据</strong><span v-for="evidence in item.evidence" :key="evidence">{{ evidence }}</span></div>
          <button v-if="item.category === 'sedentary'" class="ghost-button" @click="enableReminder">开启演示提醒</button>
        </article>
      </section>
      <section class="surface surface-pad">
        <div class="section-title"><div><h3>历史建议</h3><p>已保存的生成记录，仅展示当前登录用户的数据</p></div><el-tag effect="plain">最近 {{ history.length }} 次</el-tag></div>
        <div class="history-list">
          <button v-for="item in history" :key="item.id" class="history-item" :class="{ active: item.id === generation.id }" @click="showHistory(item)">
            <span>{{ formatDateTime(item.generatedAt) }}</span><strong>{{ item.source }}</strong><small>{{ item.model }}</small>
          </button>
        </div>
      </section>
      <div class="info-note">安全说明：页面没有采集或推断心率、血氧、GPS、疾病或身体状况；建议仅依据已同步的步数、活动时长、历史趋势与目标。真实 Provider 调用失败时会明确报错，不会用 Mock 冒充成功。</div>
    </template>
  </div>
</template>

<style scoped>
.coach-hero{min-height:250px;padding:35px;display:flex;align-items:center;justify-content:space-between;overflow:hidden;color:white;background:radial-gradient(circle at 78% 45%,rgba(141,231,255,.25),transparent 26%),linear-gradient(130deg,#332873,#5d4bd1 60%,#7765ea)}.coach-copy{max-width:690px}.coach-copy h3{font-size:clamp(27px,4vw,43px);line-height:1.2;letter-spacing:-1.5px;margin:17px 0 12px}.coach-copy p{max-width:620px;color:rgba(255,255,255,.74);line-height:1.7;font-size:13px}.source-label{display:inline-block;padding:6px 9px;border-radius:99px;background:rgba(255,255,255,.13);font-size:9px;font-weight:700;letter-spacing:.8px;text-transform:uppercase}.source-label.mini{margin-left:auto;color:#827d94;background:#f1eff6}.coach-orbit{width:150px;height:150px;flex:0 0 auto;display:grid;place-content:center;text-align:center;border:1px solid rgba(255,255,255,.26);border-radius:50%;box-shadow:inset 0 0 0 18px rgba(255,255,255,.06),0 0 0 25px rgba(255,255,255,.025)}.coach-orbit span{font-size:35px;font-weight:700}.coach-orbit small{color:rgba(255,255,255,.67)}.advice-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:17px}.advice-tile{padding:22px}.tile-head{display:flex;align-items:center;gap:9px}.tile-icon{width:38px;height:38px;display:grid;place-items:center;border-radius:12px}.tone-violet{color:#6854df;background:#efecff}.tone-blue{color:#397edb;background:#e8f2ff}.tone-coral{color:#dc6c56;background:#ffede8}.tone-mint{color:#279e7e;background:#e4f8f2}.tile-label{font-size:11px;color:#8c899c;font-weight:700}.advice-tile h3{margin:17px 0 8px;font-size:17px}.advice-tile>p{margin:0;color:#6f6b80;font-size:13px;line-height:1.8}.basis{display:flex;flex-wrap:wrap;gap:6px;margin:18px 0 0;padding-top:14px;border-top:1px solid #efedf5}.basis strong{width:100%;color:#9a96a9;font-size:10px}.basis span{padding:5px 8px;border-radius:8px;background:#f7f6fa;color:#7f7b8e;font-size:10px}.advice-tile .ghost-button{margin-top:14px}.week-plan{display:grid;grid-template-columns:repeat(7,1fr);gap:9px}.day-cell{text-align:center;padding:15px 7px;border:1px solid #eceaf3;border-radius:14px;background:#fafafd}.day-cell span,.day-cell small{display:block;color:#8b879a;font-size:10px}.day-cell strong{display:block;margin:7px 0;font-size:19px}.day-cell.done{color:white;border-color:transparent;background:linear-gradient(145deg,#7764eb,#5a47cf)}.day-cell.done span,.day-cell.done small{color:rgba(255,255,255,.72)}@media(max-width:760px){.coach-orbit{display:none}.advice-grid{grid-template-columns:1fr}.week-plan{grid-template-columns:repeat(4,1fr)}}@media(max-width:460px){.week-plan{grid-template-columns:repeat(2,1fr)}}
.history-list{display:grid;gap:8px}.history-item{display:grid;grid-template-columns:1fr auto auto;gap:12px;align-items:center;width:100%;padding:12px 14px;border:1px solid #eceaf3;border-radius:12px;background:#fafafd;text-align:left;color:#777386}.history-item.active{border-color:#7563e8;background:#f2efff}.history-item strong{color:#6555c9;text-transform:uppercase}.history-item small{color:#9995a5}@media(max-width:620px){.history-item{grid-template-columns:1fr}.history-item strong,.history-item small{font-size:10px}}
</style>
