<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { aiApi, type CoachingAdvice } from '@velapet/api'
import { ElMessage } from 'element-plus'

const loading = ref(true)
const error = ref('')
const advice = ref<CoachingAdvice[]>([])

const categories = {
  today: { icon: '↗', label: '今日建议', tone: 'violet' },
  plan: { icon: '▦', label: '本周计划', tone: 'blue' },
  goal: { icon: '◎', label: '目标推荐', tone: 'coral' },
  trend: { icon: '⌁', label: '趋势分析', tone: 'mint' },
  sedentary: { icon: '◷', label: '久坐提醒', tone: 'coral' },
  encouragement: { icon: '✦', label: '萌宠鼓励', tone: 'violet' },
} as const

const planDays = computed(() => [
  { day: '周一', value: '8k', state: '完成', done: true },
  { day: '周二', value: '10.5k', state: '高能日', done: false },
  { day: '周三', value: '8k', state: '稳定日', done: false },
  { day: '周四', value: '8k', state: '稳定日', done: false },
  { day: '周五', value: '10.5k', state: '高能日', done: false },
  { day: '周六', value: '6k', state: '轻松日', done: false },
  { day: '周日', value: '6k', state: '恢复日', done: false },
])

async function load() {
  loading.value = true
  error.value = ''
  try { advice.value = await aiApi.coaching() }
  catch (reason) { error.value = reason instanceof Error ? reason.message : '建议生成失败' }
  finally { loading.value = false }
}

function enableReminder() {
  ElMessage.success('演示提醒已开启；正式版将由移动端或后端推送')
}

onMounted(load)
</script>

<template>
  <div class="page-stack">
    <div class="page-heading">
      <div><h2>AI 运动教练</h2><p>基于运动事实给出可解释建议，不替代医疗或专业训练意见。</p></div>
      <button class="primary-button" :disabled="loading" @click="load">✦ 重新生成建议</button>
    </div>
    <div class="coach-hero surface">
      <div class="coach-copy">
        <span class="source-label">MOCK AI COACH · 仅演示</span>
        <h3>今天的目标，不是更拼，<br />而是走得更有节奏。</h3>
        <p>当前依据：今日 8,362 步、活跃 45 分钟、近 7 天平均 9,128 步、每日目标 10,000 步。</p>
      </div>
      <div class="coach-orbit"><span>84%</span><small>今日目标</small></div>
    </div>
    <el-alert v-if="error" :title="error" type="error" show-icon :closable="false" />
    <div v-if="loading" class="surface surface-pad"><el-skeleton :rows="8" animated /></div>
    <template v-else>
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
        <div class="section-title"><div><h3>本周运动计划</h3><p>根据近期活动趋势给出的目标建议，可随时调整</p></div><el-tag effect="plain">推荐目标 9,000–10,500 步</el-tag></div>
        <div class="week-plan">
          <div v-for="day in planDays" :key="day.day" class="day-cell" :class="{ done: day.done }">
            <span>{{ day.day }}</span><strong>{{ day.value }}</strong><small>{{ day.state }}</small>
          </div>
        </div>
      </section>
      <div class="info-note">安全说明：页面没有采集或推断心率、血氧、GPS、疾病或身体状况；建议仅由步数、活动时长、历史趋势与用户目标生成。真实 AI 服务不可用时，后端应返回 local_fallback 或明确的 Mock 来源。</div>
    </template>
  </div>
</template>

<style scoped>
.coach-hero{min-height:250px;padding:35px;display:flex;align-items:center;justify-content:space-between;overflow:hidden;color:white;background:radial-gradient(circle at 78% 45%,rgba(141,231,255,.25),transparent 26%),linear-gradient(130deg,#332873,#5d4bd1 60%,#7765ea)}.coach-copy{max-width:690px}.coach-copy h3{font-size:clamp(27px,4vw,43px);line-height:1.2;letter-spacing:-1.5px;margin:17px 0 12px}.coach-copy p{max-width:620px;color:rgba(255,255,255,.74);line-height:1.7;font-size:13px}.source-label{display:inline-block;padding:6px 9px;border-radius:99px;background:rgba(255,255,255,.13);font-size:9px;font-weight:700;letter-spacing:.8px;text-transform:uppercase}.source-label.mini{margin-left:auto;color:#827d94;background:#f1eff6}.coach-orbit{width:150px;height:150px;flex:0 0 auto;display:grid;place-content:center;text-align:center;border:1px solid rgba(255,255,255,.26);border-radius:50%;box-shadow:inset 0 0 0 18px rgba(255,255,255,.06),0 0 0 25px rgba(255,255,255,.025)}.coach-orbit span{font-size:35px;font-weight:700}.coach-orbit small{color:rgba(255,255,255,.67)}.advice-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:17px}.advice-tile{padding:22px}.tile-head{display:flex;align-items:center;gap:9px}.tile-icon{width:38px;height:38px;display:grid;place-items:center;border-radius:12px}.tone-violet{color:#6854df;background:#efecff}.tone-blue{color:#397edb;background:#e8f2ff}.tone-coral{color:#dc6c56;background:#ffede8}.tone-mint{color:#279e7e;background:#e4f8f2}.tile-label{font-size:11px;color:#8c899c;font-weight:700}.advice-tile h3{margin:17px 0 8px;font-size:17px}.advice-tile>p{margin:0;color:#6f6b80;font-size:13px;line-height:1.8}.basis{display:flex;flex-wrap:wrap;gap:6px;margin:18px 0 0;padding-top:14px;border-top:1px solid #efedf5}.basis strong{width:100%;color:#9a96a9;font-size:10px}.basis span{padding:5px 8px;border-radius:8px;background:#f7f6fa;color:#7f7b8e;font-size:10px}.advice-tile .ghost-button{margin-top:14px}.week-plan{display:grid;grid-template-columns:repeat(7,1fr);gap:9px}.day-cell{text-align:center;padding:15px 7px;border:1px solid #eceaf3;border-radius:14px;background:#fafafd}.day-cell span,.day-cell small{display:block;color:#8b879a;font-size:10px}.day-cell strong{display:block;margin:7px 0;font-size:19px}.day-cell.done{color:white;border-color:transparent;background:linear-gradient(145deg,#7764eb,#5a47cf)}.day-cell.done span,.day-cell.done small{color:rgba(255,255,255,.72)}@media(max-width:760px){.coach-orbit{display:none}.advice-grid{grid-template-columns:1fr}.week-plan{grid-template-columns:repeat(4,1fr)}}@media(max-width:460px){.week-plan{grid-template-columns:repeat(2,1fr)}}
</style>
