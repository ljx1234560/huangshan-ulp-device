<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { petApi, type PetSnapshot } from '@velapet/api'
import { formatDateTime, formatNumber } from '@velapet/shared'

const pet = ref<PetSnapshot>()
const loading = ref(true)
const error = ref('')
const expPercent = computed(() => Math.round(((pet.value?.currentExp || 0) / (pet.value?.nextLevelExp || 1)) * 100))

onMounted(async () => {
  try { pet.value = await petApi.current() }
  catch (reason) { error.value = reason instanceof Error ? reason.message : '宠物状态加载失败' }
  finally { loading.value = false }
})
</script>

<template>
  <div class="page-stack">
    <div class="page-heading"><div><h2>宠物成长中心</h2><p>等级、经验与任务均来自设备端权威快照，Web 不重复计算成长规则。</p></div><router-link to="/pet-studio" class="primary-button">✦ 创造新形象</router-link></div>
    <el-alert v-if="error" :title="error" type="error" show-icon :closable="false" />
    <div v-if="loading" class="surface surface-pad"><el-skeleton :rows="9" animated /></div>
    <template v-else-if="pet">
      <section class="growth-hero surface">
        <div class="growth-visual"><span class="asset-note">内置 Mock 素材</span><div class="halo" /><img :src="pet.imageUrl" :alt="pet.name" /></div>
        <div class="growth-copy">
          <span class="level-pill">LEVEL {{ pet.level }}</span><h2>{{ pet.name }}</h2><p class="pet-title">{{ pet.title }}</p>
          <div class="exp-title"><span>成长进度</span><strong>{{ pet.currentExp }} / {{ pet.nextLevelExp }} EXP</strong></div>
          <el-progress :percentage="expPercent" :stroke-width="11" :show-text="false" color="#725ee9" />
          <p class="authority-note">下一等级所需 EXP 由设备同步快照提供，页面仅负责展示。</p>
          <div class="growth-stats"><div><strong>{{ formatNumber(pet.totalSteps) }}</strong><span>累计步数</span></div><div><strong>{{ pet.streakDays }} 天</strong><span>连续活跃</span></div><div><strong>{{ pet.skins.length }}</strong><span>已解锁装扮</span></div></div>
        </div>
      </section>
      <section class="two-col">
        <article class="surface surface-pad">
          <div class="section-title"><div><h3>今日宠物任务</h3><p>完成状态需由设备端确认后同步</p></div><span class="device-source">DEVICE SNAPSHOT · MOCK</span></div>
          <div class="task-list">
            <div v-for="task in pet.tasks" :key="task.id" class="task-row">
              <span class="task-state" :class="{ complete: task.status === 'completed' }">{{ task.status === 'completed' ? '✓' : '✦' }}</span>
              <div><strong>{{ task.title }}</strong><p>{{ task.rewardLabel }}</p><el-progress :percentage="Math.min(100, Math.round(task.progress / task.target * 100))" :stroke-width="7" :show-text="false" /></div>
              <span>{{ task.progress.toLocaleString() }} / {{ task.target.toLocaleString() }}</span>
            </div>
          </div>
        </article>
        <article class="surface surface-pad">
          <div class="section-title"><div><h3>装扮收藏</h3><p>随成长与活动逐步解锁</p></div></div>
          <div class="skin-grid"><div v-for="(skin,index) in pet.skins" :key="skin"><span>{{ ['✦','◇','⌁'][index] }}</span><strong>{{ skin }}</strong><small>已解锁</small></div><div class="locked"><span>?</span><strong>未知装扮</strong><small>继续探索</small></div></div>
        </article>
      </section>
      <section class="surface surface-pad">
        <div class="section-title"><div><h3>成长历史</h3><p>演示记录；真实环境由同步事件提供</p></div><span>最近同步 {{ formatDateTime(pet.lastSyncedAt) }}</span></div>
        <el-timeline>
          <el-timeline-item timestamp="今天 08:20" type="primary"><strong>保持活跃 45 分钟</strong><p>任务完成，等待设备端奖励事件确认。</p></el-timeline-item>
          <el-timeline-item timestamp="昨天 21:06" color="#48c6a4"><strong>解锁「薄荷脚印」</strong><p>连续完成运动目标获得的新装扮。</p></el-timeline-item>
          <el-timeline-item timestamp="11 月 14 日" color="#ff9b78"><strong>升至 LV.7</strong><p>设备端宠物状态同步成功。</p></el-timeline-item>
        </el-timeline>
      </section>
    </template>
  </div>
</template>

<style scoped>
.growth-hero{display:grid;grid-template-columns:minmax(310px,.8fr) minmax(400px,1.15fr);overflow:hidden;min-height:430px}.growth-visual{position:relative;display:grid;place-items:center;background:radial-gradient(circle at 50% 48%,#fff 0 23%,transparent 24%),linear-gradient(145deg,#ebe7ff,#d9e9ff)}.growth-visual img{width:88%;max-width:400px;position:relative;z-index:2;filter:drop-shadow(0 24px 24px rgba(72,54,164,.2))}.halo{position:absolute;width:280px;height:280px;border:1px solid rgba(100,77,211,.17);border-radius:50%;box-shadow:0 0 0 27px rgba(255,255,255,.22),0 0 0 55px rgba(255,255,255,.11)}.asset-note{position:absolute;left:18px;top:18px;padding:5px 8px;border-radius:9px;background:rgba(255,255,255,.66);color:#746e8e;font-size:9px;z-index:3}.growth-copy{padding:48px}.level-pill,.device-source{display:inline-block;padding:6px 9px;border-radius:99px;color:#604dd5;background:#efecff;font-size:9px;font-weight:700;letter-spacing:.7px}.growth-copy h2{margin:15px 0 1px;font-size:44px;letter-spacing:-1.6px}.pet-title{margin:0 0 32px;color:#777287}.exp-title{display:flex;justify-content:space-between;margin-bottom:8px;font-size:12px}.authority-note{font-size:11px;color:#9290a0;line-height:1.6}.growth-stats{display:grid;grid-template-columns:repeat(3,1fr);gap:10px;margin-top:30px}.growth-stats div{padding:14px;border-radius:15px;background:#f7f6fb}.growth-stats strong,.growth-stats span{display:block}.growth-stats strong{font-size:17px}.growth-stats span{margin-top:3px;color:#9793a4;font-size:10px}.task-list{display:grid;gap:10px}.task-row{display:grid;grid-template-columns:auto 1fr auto;gap:11px;align-items:center;padding:12px;border:1px solid #eeecf4;border-radius:14px}.task-state{width:35px;height:35px;display:grid;place-items:center;border-radius:11px;color:#6653db;background:#efecff}.task-state.complete{color:#278f73;background:#e4f7f1}.task-row>div strong{font-size:12px}.task-row>div p{margin:3px 0 8px;color:#9995a5;font-size:9px}.task-row>span:last-child{font-size:10px;color:#8d899a}.skin-grid{display:grid;grid-template-columns:repeat(2,1fr);gap:10px}.skin-grid>div{padding:19px;border-radius:15px;background:linear-gradient(145deg,#faf9fe,#f0eef9)}.skin-grid>div>span{font-size:25px;color:#7360e5}.skin-grid strong,.skin-grid small{display:block}.skin-grid strong{margin-top:14px;font-size:12px}.skin-grid small{margin-top:3px;color:#45a689;font-size:9px}.skin-grid .locked{filter:grayscale(1);opacity:.52}.section-title>span{color:#9894a4;font-size:10px}.el-timeline p{margin:5px 0;color:#8a8797;font-size:12px}@media(max-width:900px){.growth-hero{grid-template-columns:1fr}.growth-visual{min-height:370px}.growth-copy{padding:28px}}@media(max-width:520px){.growth-visual{min-height:310px}.growth-copy h2{font-size:34px}.growth-stats{grid-template-columns:1fr}.skin-grid{grid-template-columns:1fr}}
</style>
