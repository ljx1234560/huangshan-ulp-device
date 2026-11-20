<script setup lang="ts">
import { onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { apiMode, petApi, type PetGenerationInput, type PetGenerationJob } from '@velapet/api'

const input = reactive<PetGenerationInput>({
  species: 'fox',
  color: 'lavender',
  style: 'celestial',
  personality: 'energetic',
  name: '露米',
  description: '喜欢追逐晚霞，尾巴上有淡淡的星光纹理',
})
const job = ref<PetGenerationJob>()
const history = ref<PetGenerationJob[]>([])
const generating = ref(false)
const saved = ref(false)
let pollTimer: ReturnType<typeof setTimeout> | undefined

const species = [
  { value: 'fox', label: '星狐', icon: '◇' },
  { value: 'cat', label: '云猫', icon: '◉' },
  { value: 'rabbit', label: '月兔', icon: '♢' },
] as const
const colors = [
  { value: 'lavender', label: '星雾紫', color: '#a99bfa' },
  { value: 'mint', label: '薄荷青', color: '#71d7c2' },
  { value: 'coral', label: '珊瑚粉', color: '#ff9d91' },
  { value: 'midnight', label: '夜幕蓝', color: '#48589c' },
]

async function poll(id: string) {
  try {
    const result = await petApi.generationJob(id)
    job.value = result
    if (result.status === 'succeeded') {
      if (!history.value.some((item) => item.id === result.id)) history.value.unshift(result)
      generating.value = false
      ElMessage.success('演示宠物形象已准备好')
      return
    }
    if (result.status === 'failed') {
      generating.value = false
      return
    }
    pollTimer = setTimeout(() => poll(id), 650)
  } catch (error) {
    generating.value = false
    if (job.value) {
      job.value.status = 'failed'
      job.value.error = error instanceof Error ? error.message : '生成任务查询失败'
    }
  }
}

async function generate() {
  if (!input.name.trim()) return ElMessage.warning('先给萌宠取个名字吧')
  generating.value = true
  saved.value = false
  try {
    job.value = await petApi.createGenerationJob({ ...input })
    await poll(job.value.id)
  } catch (error) {
    generating.value = false
    ElMessage.error(error instanceof Error ? error.message : '创建生成任务失败')
  }
}

async function savePet() {
  if (!job.value?.assetId) return ElMessage.warning('生成任务尚未产出可收藏的资源')
  try {
    await petApi.favoriteAsset(job.value.assetId, true)
    saved.value = true
    ElMessage.success(apiMode === 'mock' ? '已持久化到本机演示收藏' : '已保存到账号收藏')
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : '收藏失败')
  }
}

async function setCurrent() {
  if (!job.value?.assetId) return ElMessage.warning('生成任务尚未产出宠物资源')
  await petApi.setCurrentAsset(job.value.assetId)
  ElMessage.success(apiMode === 'mock' ? '已持久化为当前演示形象' : '已设置为当前萌宠形象')
}

onMounted(async () => {
  try { history.value = await petApi.generationHistory() }
  catch { history.value = [] }
})

onBeforeUnmount(() => clearTimeout(pollTimer))
</script>

<template>
  <div class="page-stack">
    <div class="page-heading">
      <div><h2>AI 萌宠工坊</h2><p>组合物种、配色与性格，创造属于你的运动伙伴。</p></div>
      <span class="studio-status">✦ {{ apiMode === 'mock' ? 'MOCK GENERATION LAB' : 'PERSISTED GENERATION JOBS' }}</span>
    </div>
    <el-alert :title="apiMode === 'mock' ? '当前未连接真实图像生成服务。任务、收藏和当前形象会持久化到浏览器，图片仍为内置示例。' : '生成任务、资源归属、收藏与当前形象将保存到数据库；当前 Provider 仍可配置为 Mock。'" :type="apiMode === 'mock' ? 'warning' : 'success'" show-icon :closable="false" />
    <section class="studio-grid">
      <article class="surface studio-form">
        <div class="step-heading"><span>01</span><div><h3>选择萌宠原型</h3><p>先决定陪伴你的基础形态</p></div></div>
        <div class="choice-grid three">
          <button v-for="item in species" :key="item.value" :class="{ selected: input.species === item.value }" @click="input.species = item.value">
            <b>{{ item.icon }}</b><span>{{ item.label }}</span>
          </button>
        </div>
        <div class="step-heading"><span>02</span><div><h3>挑选主题配色</h3><p>颜色会影响形象氛围</p></div></div>
        <div class="color-row">
          <button v-for="item in colors" :key="item.value" :class="{ selected: input.color === item.value }" @click="input.color = item.value">
            <i :style="{ background: item.color }" /><span>{{ item.label }}</span>
          </button>
        </div>
        <div class="form-two">
          <div><label>视觉风格</label><el-select v-model="input.style" style="width:100%"><el-option label="星际软萌" value="celestial" /><el-option label="森林童话" value="forest" /><el-option label="复古像素" value="pixel" /></el-select></div>
          <div><label>性格</label><el-select v-model="input.personality" style="width:100%"><el-option label="活泼热情" value="energetic" /><el-option label="温柔安静" value="gentle" /><el-option label="好奇探索" value="curious" /></el-select></div>
        </div>
        <div class="field"><label>萌宠名字</label><el-input v-model="input.name" maxlength="12" show-word-limit /></div>
        <div class="field"><label>补充形象描述</label><el-input v-model="input.description" type="textarea" :rows="3" maxlength="100" show-word-limit placeholder="例如：尾巴带星光纹理，喜欢收集云朵..." /></div>
        <button class="generate-button" :disabled="generating" @click="generate">
          <span v-if="generating">正在准备形象 {{ job?.progress || 0 }}%</span>
          <span v-else>✦ 生成专属萌宠</span>
        </button>
      </article>

      <aside class="surface preview-panel">
        <div class="preview-top"><span>LIVE PREVIEW</span><span class="mock-chip">内置示例</span></div>
        <div class="preview-stage" :class="{ generating }">
          <div class="stage-orbit one" /><div class="stage-orbit two" />
          <img v-if="job?.status === 'succeeded' || !job" :src="job?.imageUrl || '/pets/lumi.png'" :alt="input.name + ' 的内置示例形象'" />
          <div v-if="generating" class="generation-overlay">
            <el-progress type="circle" :percentage="job?.progress || 8" color="#7562eb" :width="90" />
            <strong>{{ job?.status === 'queued' ? '正在排队' : '正在组合特征' }}</strong>
            <p>{{ apiMode === 'mock' ? 'Mock 异步任务 · 不会调用外部模型' : '数据库异步任务 · Provider 由后端配置' }}</p>
          </div>
          <div v-if="job?.status === 'failed'" class="generation-overlay error">
            <strong>生成失败</strong><p>{{ job.error }}</p><button class="ghost-button" @click="generate">重新生成</button>
          </div>
        </div>
        <div class="pet-nameplate">
          <div><span>你的 VelaPet</span><h3>{{ input.name || '未命名' }}</h3></div>
          <span class="personality">{{ { energetic: '活泼热情', gentle: '温柔安静', curious: '好奇探索' }[input.personality] }}</span>
        </div>
        <div class="preview-actions">
          <button class="ghost-button" :disabled="job?.status !== 'succeeded'" @click="savePet">{{ saved ? '♥ 已收藏' : '♡ 保存形象' }}</button>
          <button class="primary-button" :disabled="job?.status !== 'succeeded'" @click="setCurrent">设为当前萌宠</button>
        </div>
      </aside>
    </section>
    <section class="surface surface-pad">
      <div class="section-title"><div><h3>历史生成记录</h3><p>{{ apiMode === 'mock' ? '浏览器持久化的 Mock 任务记录' : '账号数据库中的生成任务记录' }}</p></div></div>
      <el-empty v-if="history.length === 0" description="还没有生成记录，先创造你的第一只萌宠吧" :image-size="82" />
      <div v-else class="history-row">
        <article v-for="item in history" :key="item.id"><img :src="item.imageUrl" alt="历史示例萌宠" /><div><strong>{{ item.input.name }}</strong><span>{{ new Date(item.createdAt).toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' }) }} · Mock 素材</span></div></article>
      </div>
    </section>
  </div>
</template>

<style scoped>
.studio-status,.mock-chip{padding:7px 10px;border-radius:99px;background:#efecff;color:#6250d3;font-size:9px;font-weight:700;letter-spacing:.7px}.studio-grid{display:grid;grid-template-columns:minmax(0,1.05fr) minmax(340px,.78fr);gap:20px;align-items:start}.studio-form{padding:26px}.step-heading{display:flex;gap:11px;align-items:center;margin:4px 0 13px}.step-heading>span{width:30px;height:30px;display:grid;place-items:center;border-radius:10px;color:#6552d9;background:#efecff;font-size:10px;font-weight:700}.step-heading h3{margin:0;font-size:15px}.step-heading p{margin:2px 0 0;color:#9692a5;font-size:10px}.choice-grid{display:grid;gap:10px;margin-bottom:25px}.choice-grid.three{grid-template-columns:repeat(3,1fr)}.choice-grid button{padding:15px;border:1px solid #ebe9f2;border-radius:14px;background:#fafafd;cursor:pointer;color:#6e6a7c}.choice-grid button b{display:block;font-size:25px;margin-bottom:5px}.choice-grid button span{font-size:12px;font-weight:700}.choice-grid button.selected{border-color:#8979ec;color:#5f4dd0;background:#f2efff;box-shadow:0 0 0 2px rgba(112,94,225,.08)}.color-row{display:grid;grid-template-columns:repeat(4,1fr);gap:8px;margin-bottom:23px}.color-row button{padding:9px 5px;border:1px solid #eceaf3;border-radius:12px;background:white;cursor:pointer}.color-row i{display:block;width:23px;height:23px;border-radius:50%;margin:0 auto 5px;box-shadow:inset 0 0 0 3px rgba(255,255,255,.5)}.color-row span{font-size:10px;color:#7d798b}.color-row button.selected{border-color:#8271e9;background:#f7f5ff}.form-two{display:grid;grid-template-columns:1fr 1fr;gap:12px}.form-two label,.field label{display:block;margin:0 0 7px;color:#777385;font-size:11px;font-weight:700}.field{margin-top:16px}.studio-form :deep(.el-input__wrapper),.studio-form :deep(.el-textarea__inner),.studio-form :deep(.el-select__wrapper){border-radius:11px;box-shadow:0 0 0 1px #e6e4ef inset}.generate-button{width:100%;height:49px;margin-top:21px;border:0;border-radius:14px;color:white;background:linear-gradient(135deg,#7967ee,#5542cb);box-shadow:0 11px 23px rgba(89,70,210,.27);font-weight:700;cursor:pointer}.generate-button:disabled{opacity:.7;cursor:wait}.preview-panel{padding:18px;position:sticky;top:115px}.preview-top{display:flex;justify-content:space-between;align-items:center;padding:3px 4px 14px;color:#9692a6;font-size:9px;font-weight:700;letter-spacing:1px}.preview-stage{height:420px;position:relative;overflow:hidden;display:grid;place-items:center;border-radius:20px;background:radial-gradient(circle at 50% 54%,rgba(255,255,255,.85),transparent 29%),linear-gradient(145deg,#eeebff,#dcd7ff 55%,#c9e9ff)}.preview-stage::before{content:'✦';position:absolute;top:12%;left:13%;font-size:21px;color:white}.preview-stage img{width:92%;max-width:410px;position:relative;z-index:2;filter:drop-shadow(0 22px 22px rgba(63,47,148,.22));transition:.3s}.preview-stage.generating img{filter:blur(7px);opacity:.35}.stage-orbit{position:absolute;border:1px solid rgba(100,80,210,.13);border-radius:50%}.stage-orbit.one{width:310px;height:310px}.stage-orbit.two{width:250px;height:250px}.generation-overlay{position:absolute;inset:0;z-index:3;display:grid;place-content:center;justify-items:center;gap:10px;background:rgba(246,244,255,.77);backdrop-filter:blur(5px)}.generation-overlay strong{font-size:14px}.generation-overlay p{margin:0;color:#777288;font-size:10px}.generation-overlay.error{color:#b4564a}.pet-nameplate{display:flex;align-items:center;justify-content:space-between;padding:17px 5px 12px}.pet-nameplate span{color:#9793a4;font-size:10px}.pet-nameplate h3{margin:3px 0 0;font-size:22px}.personality{padding:6px 8px;border-radius:9px;background:#f1eff9}.preview-actions{display:grid;grid-template-columns:1fr 1fr;gap:9px}.preview-actions button:disabled{opacity:.45;cursor:not-allowed}.history-row{display:flex;gap:12px;overflow-x:auto}.history-row article{min-width:190px;display:flex;align-items:center;gap:9px;padding:10px;border:1px solid #eceaf2;border-radius:14px}.history-row img{width:58px;height:58px;object-fit:contain;border-radius:11px;background:#efecff}.history-row strong,.history-row span{display:block}.history-row span{margin-top:4px;color:#9793a4;font-size:9px}@media(max-width:1000px){.studio-grid{grid-template-columns:1fr}.preview-panel{position:static}.preview-stage{height:370px}}@media(max-width:520px){.color-row{grid-template-columns:repeat(2,1fr)}.preview-stage{height:330px}.form-two{grid-template-columns:1fr}}
</style>
