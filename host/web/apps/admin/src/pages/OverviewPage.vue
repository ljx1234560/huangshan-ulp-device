<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import type { EChartsOption } from 'echarts'
import { adminApi, type AdminOverview } from '@velapet/api'
import { formatNumber, formatPercent } from '@velapet/shared'
import AdminChart from '../components/AdminChart.vue'
import KpiCard from '../components/KpiCard.vue'

const data = ref<AdminOverview>()
const loading = ref(true)
const error = ref('')
const dates = ref<[Date, Date]>()

async function load(){
  loading.value=true; error.value=''
  try{
    const query=dates.value?{startDate:toDate(dates.value[0]),endDate:toDate(dates.value[1])}:{}
    data.value=await adminApi.overview(query)
  }
  catch(reason){ error.value=reason instanceof Error?reason.message:'运营数据加载失败' }
  finally{ loading.value=false }
}
function toDate(value:Date){const month=String(value.getMonth()+1).padStart(2,'0');const day=String(value.getDate()).padStart(2,'0');return value.getFullYear()+'-'+month+'-'+day}
function width(value:number,total:number){return Math.round((total?value/total:0)*100)+'%'}

const activeOption = computed<EChartsOption>(()=>({
  tooltip:{trigger:'axis'},legend:{data:['Web DAU','Device DAU','Product DAU'],right:0,top:0,textStyle:{fontSize:10,color:'#73798c'}},
  grid:{left:18,right:15,top:48,bottom:18,containLabel:true},
  xAxis:{type:'category',boundaryGap:false,data:data.value?.trend.map(p=>new Date(p.date).toLocaleDateString('zh-CN',{month:'numeric',day:'numeric'}))||[],axisLine:{show:false},axisTick:{show:false},axisLabel:{color:'#999eac',fontSize:9}},
  yAxis:{type:'value',splitLine:{lineStyle:{color:'#edf0f4'}},axisLabel:{color:'#a2a6b3',fontSize:9}},
  series:[
    {name:'Web DAU',type:'line',smooth:true,symbol:'none',data:data.value?.trend.map(p=>p.webDau)||[],lineStyle:{width:2.5,color:'#5e6ff2'},areaStyle:{color:'rgba(94,111,242,.09)'}},
    {name:'Device DAU',type:'line',smooth:true,symbol:'none',data:data.value?.trend.map(p=>p.deviceDau)||[],lineStyle:{width:2,color:'#42b891'}},
    {name:'Product DAU',type:'line',smooth:true,symbol:'none',data:data.value?.trend.map(p=>p.productDau)||[],lineStyle:{width:2,color:'#f2a15a'}},
  ],
}))
const newUserOption=computed<EChartsOption>(()=>({
  tooltip:{trigger:'axis'},grid:{left:12,right:5,top:10,bottom:12,containLabel:true},
  xAxis:{type:'category',data:data.value?.trend.map(p=>new Date(p.date).getDate())||[],axisLine:{show:false},axisTick:{show:false},axisLabel:{color:'#a1a5b2',fontSize:8}},
  yAxis:{type:'value',splitLine:{lineStyle:{color:'#edf0f4'}},axisLabel:{color:'#a1a5b2',fontSize:8}},
  series:[{type:'bar',barMaxWidth:15,data:data.value?.trend.map(p=>p.newUsers)||[],itemStyle:{color:'#6878f3',borderRadius:[4,4,0,0]}}],
}))
const channelOption=computed<EChartsOption>(()=>({
  tooltip:{trigger:'item'},legend:{bottom:0,textStyle:{fontSize:9,color:'#7c8192'}},
  series:[{type:'pie',radius:['50%','72%'],center:['50%','43%'],label:{show:false},data:[{value:46,name:'自然访问',itemStyle:{color:'#5f70f2'}},{value:28,name:'设备引导',itemStyle:{color:'#45bb95'}},{value:17,name:'活动邀请',itemStyle:{color:'#f2a15a'}},{value:9,name:'其他',itemStyle:{color:'#c9ceda'}}]}],
}))
onMounted(load)
</script>

<template>
  <div class="admin-page">
    <div class="admin-page-head"><div><h2>业务运行概览</h2><p>观察用户、设备与 AI 服务的核心演示指标。</p></div><div class="admin-filter"><el-date-picker v-model="dates" type="daterange" range-separator="至" start-placeholder="开始" end-placeholder="结束" size="small" @change="load"/><button @click="load">↻ 刷新</button><button class="primary-btn">导出演示数据</button></div></div>
    <el-alert v-if="error" :title="error" type="error" show-icon :closable="false"/>
    <div v-if="loading" class="admin-surface admin-pad"><el-skeleton :rows="9" animated/></div>
    <template v-else-if="data">
      <el-alert v-if="data.dataSource !== 'production'" :title="data.dataSource === 'empty' ? '当前数据库没有运营数据，指标按零值返回。' : '当前指标包含明确标记的 Demo 种子数据，不代表真实运营结果。'" :type="data.dataSource === 'empty' ? 'info' : 'warning'" show-icon :closable="false"/>
      <section class="kpi-grid">
        <KpiCard label="Web DAU" :value="formatNumber(data.dau)" icon="W" tone="blue"/>
        <KpiCard label="WAU" :value="formatNumber(data.wau)" icon="7" tone="mint"/>
        <KpiCard label="MAU" :value="formatNumber(data.mau)" icon="30" tone="violet"/>
        <KpiCard label="总注册用户" :value="formatNumber(data.totalUsers)" icon="人" tone="orange"/>
        <KpiCard label="设备绑定数" :value="formatNumber(data.boundDevices)" icon="▣" tone="blue"/>
      </section>
      <section class="admin-two-col">
        <article class="admin-surface admin-pad"><div class="admin-section-head"><div><h3>活跃用户趋势</h3><p>三种口径独立统计，不将自动上传直接等同于 Web 活跃</p></div></div><AdminChart :option="activeOption" :height="315"/></article>
        <article class="admin-surface admin-pad"><div class="admin-section-head"><div><h3>关键转化</h3><p>所选周期汇总</p></div></div><div class="funnel">
          <div><span>注册用户</span><strong>{{ formatNumber(data.totalUsers) }}</strong><i style="width:100%"/></div>
          <div><span>绑定设备</span><strong>{{ formatNumber(data.boundDevices) }}</strong><i :style="{width:width(data.boundDevices,data.totalUsers)}"/></div>
          <div><span>完成首次同步</span><strong>{{ formatNumber(data.syncedUsers) }}</strong><i :style="{width:width(data.syncedUsers,data.totalUsers)}"/></div>
          <div><span>创建萌宠</span><strong>{{ formatNumber(data.petOwners) }}</strong><i :style="{width:width(data.petOwners,data.totalUsers)}"/></div>
        </div></article>
      </section>
      <section class="admin-equal">
        <article class="admin-surface admin-pad"><div class="admin-section-head"><div><h3>新增用户趋势</h3><p>本周期新增 {{ formatNumber(data.newUsers) }} 人</p></div></div><AdminChart :option="newUserOption" :height="220"/></article>
        <article class="admin-surface admin-pad"><div class="admin-section-head"><div><h3>用户来源结构</h3><p>仅 Demo 数据提供演示渠道归因</p></div></div><AdminChart v-if="data.dataSource === 'demo'" :option="channelOption" :height="220"/><el-empty v-else description="暂无可靠渠道归因数据" :image-size="65"/></article>
      </section>
      <section class="kpi-grid secondary">
        <KpiCard label="同步成功率" :value="formatPercent(data.syncSuccessRate,1)" icon="✓" tone="mint"/>
        <KpiCard label="AI 萌宠生成" :value="formatNumber(data.petGenerations)" icon="✦" tone="violet"/>
        <KpiCard label="用户留存率" :value="formatPercent(data.retentionRate,1)" icon="↺" tone="orange"/>
        <KpiCard label="今日新增" :value="formatNumber(data.newUsers)" icon="+" tone="blue"/>
      </section>
      <div class="metric-definition"><strong>统计口径</strong><span><b>Web DAU</b>：主动打开 Web 的去重用户</span><span><b>Device DAU</b>：产生有效设备活动快照的去重设备用户</span><span><b>Product DAU</b>：Web 或设备任一有效活跃的去重用户，做集合去重而非相加</span></div>
    </template>
  </div>
</template>

<style scoped>
.funnel{display:grid;gap:17px;padding:10px 0}.funnel>div{display:grid;grid-template-columns:1fr auto;gap:6px;position:relative}.funnel span{color:#777d8e;font-size:10px}.funnel strong{font-size:11px}.funnel i{grid-column:1/-1;height:7px;border-radius:99px;background:linear-gradient(90deg,#6374f2,#9aa5ff)}.kpi-grid.secondary{grid-template-columns:repeat(4,1fr)}.metric-definition{display:flex;align-items:center;flex-wrap:wrap;gap:12px;padding:13px 16px;border:1px solid #dde1eb;border-radius:12px;color:#7b8193;background:#eef1f7;font-size:9px}.metric-definition>strong{color:#3f465d}.metric-definition span{padding-left:12px;border-left:1px solid #ccd1dd}.metric-definition b{color:#545d78}@media(max-width:900px){.kpi-grid.secondary{grid-template-columns:repeat(2,1fr)}}@media(max-width:520px){.kpi-grid.secondary{grid-template-columns:1fr}.metric-definition{align-items:flex-start;flex-direction:column}.metric-definition span{padding-left:0;border-left:0}}
</style>
