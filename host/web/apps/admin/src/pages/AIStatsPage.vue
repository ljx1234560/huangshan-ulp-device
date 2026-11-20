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
const totals=computed(()=>metrics.value.reduce((sum,item)=>({text:sum.text+item.textCalls,image:sum.image+item.imageCalls,failed:sum.failed+item.failedJobs,cost:sum.cost+item.cost}),{text:0,image:0,failed:0,cost:0}))
const avgSuccess=computed(()=>metrics.value.length?metrics.value.reduce((sum,item)=>sum+item.successRate,0)/metrics.value.length:0)
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
onMounted(async()=>{try{metrics.value=await adminApi.aiMetrics()}catch(reason){error.value=reason instanceof Error?reason.message:'AI 统计加载失败'}finally{loading.value=false}})
</script>
<template>
  <div class="admin-page">
    <div class="admin-page-head"><div><h2>AI 服务统计</h2><p>观察文本建议与图片任务的调用、质量和估算成本。</p></div><div class="admin-filter"><button>最近 14 天</button><button class="primary-btn">导出账单明细</button></div></div>
    <el-alert title="图片生成尚未接入当前产品后端；以下图片调用与成本均为运营 Mock 数据，不代表真实账单。" type="warning" :closable="false" show-icon/>
    <el-alert v-if="error" :title="error" type="error" :closable="false" show-icon/>
    <div v-if="loading" class="admin-surface admin-pad"><el-skeleton :rows="8" animated/></div>
    <template v-else>
      <section class="kpi-grid ai-kpis"><KpiCard label="文本建议次数" :value="formatNumber(totals.text)" delta="11.2%" icon="T" tone="blue"/><KpiCard label="图片生成次数" :value="formatNumber(totals.image)" delta="16.4%" icon="I" tone="violet"/><KpiCard label="综合成功率" :value="formatPercent(avgSuccess,1)" delta="0.6%" icon="✓" tone="mint"/><KpiCard label="失败任务数" :value="formatNumber(totals.failed)" icon="!" tone="orange"/><KpiCard label="估算调用成本" :value="'¥'+formatNumber(totals.cost)" icon="¥" tone="blue"/></section>
      <section class="admin-equal"><article class="admin-surface admin-pad"><div class="admin-section-head"><div><h3>AI 调用量趋势</h3><p>按服务类型拆分</p></div></div><AdminChart :option="volumeOption" :height="300"/></article><article class="admin-surface admin-pad"><div class="admin-section-head"><div><h3>成功率与失败任务</h3><p>成功率使用左轴，失败数使用右轴</p></div></div><AdminChart :option="qualityOption" :height="300"/></article></section>
      <section class="admin-two-col">
        <article class="admin-surface admin-pad"><div class="admin-section-head"><div><h3>服务明细</h3><p>模型名与单价均为演示配置</p></div></div><el-table :data="[{service:'运动建议',model:'deepseek-flash / fallback',calls:totals.text,success:'98.1%',cost:'¥1,842'},{service:'萌宠图片',model:'image-provider (待接入)',calls:totals.image,success:'94.8%',cost:'¥1,386'}]"><el-table-column prop="service" label="服务"/><el-table-column prop="model" label="模型 / 通道" min-width="190"/><el-table-column prop="calls" label="调用量"/><el-table-column prop="success" label="成功率"/><el-table-column prop="cost" label="估算成本"/></el-table></article>
        <article class="admin-surface admin-pad"><div class="admin-section-head"><div><h3>失败原因</h3><p>Mock 任务失败分类</p></div></div><div class="failure-list"><div><span>上游超时</span><strong>42%</strong><i><b style="width:42%"/></i></div><div><span>内容校验失败</span><strong>27%</strong><i><b style="width:27%"/></i></div><div><span>额度或限流</span><strong>19%</strong><i><b style="width:19%"/></i></div><div><span>其他</span><strong>12%</strong><i><b style="width:12%"/></i></div></div></article>
      </section>
    </template>
  </div>
</template>
<style scoped>
.ai-kpis{grid-template-columns:repeat(5,1fr)}.failure-list{display:grid;gap:15px}.failure-list>div{display:grid;grid-template-columns:1fr auto;gap:7px;color:#777d8e;font-size:10px}.failure-list i{grid-column:1/-1;height:6px;border-radius:99px;background:#eef0f4}.failure-list b{display:block;height:100%;border-radius:99px;background:#ed996c}@media(max-width:1100px){.ai-kpis{grid-template-columns:repeat(3,1fr)}}@media(max-width:600px){.ai-kpis{grid-template-columns:repeat(2,1fr)}}
</style>
