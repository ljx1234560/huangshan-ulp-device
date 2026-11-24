<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import type { EChartsOption } from 'echarts'
import { adminApi, type AiServiceMetric } from '@velapet/api'
import { formatNumber, formatPercent } from '@velapet/shared'
import AdminChart from '../components/AdminChart.vue'
import KpiCard from '../components/KpiCard.vue'

const metrics=ref<AiServiceMetric[]>([])
const loading=ref(true)
const error=ref('')
const rangeDays=ref(14)
const totals=computed(()=>metrics.value.reduce((sum,item)=>({text:sum.text+item.textCalls,image:sum.image+item.imageCalls,failed:sum.failed+item.failedJobs,succeeded:sum.succeeded+(item.imageSucceeded||0),tokens:sum.tokens+(item.imageTokens||0),duration:sum.duration+(item.imageAverageDurationMs||0),cost:sum.cost+(item.cost||0)}),{text:0,image:0,failed:0,succeeded:0,tokens:0,duration:0,cost:0}))
const hasCost=computed(()=>metrics.value.some(item=>item.cost!==null))
const models=computed(()=>{const result:Record<string,number>={};for(const item of metrics.value)for(const [model,count] of Object.entries(item.imageModels||{}))result[model]=(result[model]||0)+count;return result})
const avgSuccess=computed(()=>totals.value.text+totals.value.image?(totals.value.text+totals.value.succeeded)/(totals.value.text+totals.value.image):0)
const volumeOption=computed<EChartsOption>(()=>({
  tooltip:{trigger:'axis'},legend:{data:['文本建议','图片生成'],right:0,top:0,textStyle:{fontSize:9}},
  grid:{left:15,right:10,top:40,bottom:16,containLabel:true},xAxis:{type:'category',data:metrics.value.map(m=>new Date(m.date).toLocaleDateString('zh-CN',{month:'numeric',day:'numeric'})),axisLine:{show:false},axisTick:{show:false},axisLabel:{color:'#a0a4b1',fontSize:8}},
  yAxis:{type:'value',splitLine:{lineStyle:{color:'#edf0f4'}},axisLabel:{color:'#a0a4b1',fontSize:8}},
  series:[{name:'文本建议',type:'bar',stack:'calls',barMaxWidth:17,data:metrics.value.map(m=>m.textCalls),itemStyle:{color:'#6374f2',borderRadius:[0,0,0,0]}},{name:'图片生成',type:'bar',stack:'calls',data:metrics.value.map(m=>m.imageCalls),itemStyle:{color:'#a894f5',borderRadius:[4,4,0,0]}}],
}))
const qualityOption=computed<EChartsOption>(()=>({
  tooltip:{trigger:'axis'},grid:{left:15,right:10,top:18,bottom:16,containLabel:true},xAxis:{type:'category',data:metrics.value.map(m=>new Date(m.date).getDate()),axisLine:{show:false},axisTick:{show:false},axisLabel:{fontSize:8,color:'#a0a4b1'}},
  yAxis:[{type:'value',min:90,max:100,axisLabel:{formatter:'{value}%',fontSize:8,color:'#a0a4b1'},splitLine:{lineStyle:{color:'#edf0f4'}}},{type:'value',axisLabel:{fontSize:8,color:'#a0a4b1'},splitLine:{show:false}}],
  series:[{name:'成功率',type:'line',smooth:true,symbol:'none',data:metrics.value.map(m=>+(m.successRate*100).toFixed(1)),lineStyle:{width:2.5,color:'#42b891'},areaStyle:{color:'rgba(66,184,145,.1)'}},{name:'失败任务',type:'bar',yAxisIndex:1,barMaxWidth:12,data:metrics.value.map(m=>m.failedJobs),itemStyle:{color:'#f1a063',borderRadius:[3,3,0,0]}}],
}))
async function load(days=rangeDays.value){rangeDays.value=days;loading.value=true;error.value='';try{const end=new Date();const start=new Date();start.setDate(end.getDate()-days+1);metrics.value=await adminApi.aiMetrics({startDate:start.toISOString().slice(0,10),endDate:end.toISOString().slice(0,10)})}catch(reason){error.value=reason instanceof Error?reason.message:'AI 统计加载失败'}finally{loading.value=false}}
onMounted(()=>load())
</script>
<template>
  <div class="admin-page">
    <div class="admin-page-head"><div><h2>AI 服务统计</h2><p>观察文本建议与图片任务的调用、成功率、模型和供应商用量。</p></div><div class="admin-filter"><button :class="{active:rangeDays===14}" @click="load(14)">最近 14 天</button><button :class="{active:rangeDays===30}" @click="load(30)">最近 30 天</button></div></div>
    <el-alert title="成本仅在供应商返回可靠费用时展示；当前不会根据 Token 自行估算或伪造账单。" type="info" :closable="false" show-icon/>
    <el-alert v-if="error" :title="error" type="error" :closable="false" show-icon/>
    <div v-if="loading" class="admin-surface admin-pad"><el-skeleton :rows="8" animated/></div>
    <template v-else>
      <section class="kpi-grid ai-kpis"><KpiCard label="文本建议次数" :value="formatNumber(totals.text)" icon="T" tone="blue"/><KpiCard label="图片生成次数" :value="formatNumber(totals.image)" icon="I" tone="violet"/><KpiCard label="综合成功率" :value="formatPercent(avgSuccess,1)" icon="✓" tone="mint"/><KpiCard label="失败任务数" :value="formatNumber(totals.failed)" icon="!" tone="orange"/><KpiCard label="供应商成本" :value="hasCost?'$'+formatNumber(totals.cost):'暂无可靠数据'" icon="$" tone="blue"/></section>
      <section class="admin-equal"><article class="admin-surface admin-pad"><div class="admin-section-head"><div><h3>AI 调用量趋势</h3><p>按服务类型拆分</p></div></div><AdminChart :option="volumeOption" :height="300"/></article><article class="admin-surface admin-pad"><div class="admin-section-head"><div><h3>成功率与失败任务</h3><p>成功率使用左轴，失败数使用右轴</p></div></div><AdminChart :option="qualityOption" :height="300"/></article></section>
      <section class="admin-two-col">
        <article class="admin-surface admin-pad"><div class="admin-section-head"><div><h3>图片模型明细</h3><p>来自数据库任务记录</p></div></div><el-table :data="Object.entries(models).map(([model,calls])=>({model,calls}))"><el-table-column prop="model" label="模型 / 通道" min-width="190"/><el-table-column prop="calls" label="任务量"/></el-table></article>
        <article class="admin-surface admin-pad"><div class="admin-section-head"><div><h3>图片任务质量</h3><p>不包含尚在队列中的任务</p></div></div><div class="failure-list"><div><span>成功任务</span><strong>{{ formatNumber(totals.succeeded) }}</strong></div><div><span>失败任务</span><strong>{{ formatNumber(totals.failed) }}</strong></div><div><span>供应商 Token</span><strong>{{ formatNumber(totals.tokens) }}</strong></div><div><span>日均成功任务耗时</span><strong>{{ formatNumber(Math.round(totals.duration/Math.max(metrics.length,1))) }} ms</strong></div></div></article>
      </section>
    </template>
  </div>
</template>
<style scoped>
.ai-kpis{grid-template-columns:repeat(5,1fr)}.failure-list{display:grid;gap:15px}.failure-list>div{display:grid;grid-template-columns:1fr auto;gap:7px;color:#777d8e;font-size:10px}.failure-list i{grid-column:1/-1;height:6px;border-radius:99px;background:#eef0f4}.failure-list b{display:block;height:100%;border-radius:99px;background:#ed996c}@media(max-width:1100px){.ai-kpis{grid-template-columns:repeat(3,1fr)}}@media(max-width:600px){.ai-kpis{grid-template-columns:repeat(2,1fr)}}
</style>
