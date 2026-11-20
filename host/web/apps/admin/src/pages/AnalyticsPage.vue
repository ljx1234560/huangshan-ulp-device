<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import type { EChartsOption } from 'echarts'
import { adminApi, type AdminOverview, type RetentionPoint } from '@velapet/api'
import { formatPercent } from '@velapet/shared'
import AdminChart from '../components/AdminChart.vue'

const overview=ref<AdminOverview>()
const retention=ref<RetentionPoint[]>([])
const loading=ref(true)
const error=ref('')
const activityOption=computed<EChartsOption>(()=>({
  tooltip:{trigger:'axis'},legend:{data:['Web DAU','Device DAU','Product DAU'],right:0,textStyle:{fontSize:9}},
  grid:{left:18,right:10,top:45,bottom:18,containLabel:true},xAxis:{type:'category',data:overview.value?.trend.map(p=>new Date(p.date).toLocaleDateString('zh-CN',{month:'numeric',day:'numeric'}))||[],axisLine:{show:false},axisTick:{show:false},axisLabel:{fontSize:8,color:'#a1a5b2'}},
  yAxis:{type:'value',splitLine:{lineStyle:{color:'#edf0f4'}},axisLabel:{fontSize:8,color:'#a1a5b2'}},
  series:[{name:'Web DAU',type:'line',smooth:true,symbol:'none',data:overview.value?.trend.map(p=>p.webDau)||[],lineStyle:{color:'#5f70f2',width:2.5}},{name:'Device DAU',type:'line',smooth:true,symbol:'none',data:overview.value?.trend.map(p=>p.deviceDau)||[],lineStyle:{color:'#45bb95',width:2.5}},{name:'Product DAU',type:'line',smooth:true,symbol:'none',data:overview.value?.trend.map(p=>p.productDau)||[],lineStyle:{color:'#f2a15a',width:2.5}}],
}))
const conversionOption: EChartsOption={
  tooltip:{trigger:'axis'},grid:{left:18,right:10,top:20,bottom:18,containLabel:true},xAxis:{type:'category',data:['注册→绑定','绑定→同步','同步→创建宠物','7日活跃','完成运动目标'],axisLine:{show:false},axisTick:{show:false},axisLabel:{fontSize:9,color:'#8d92a2'}},yAxis:{type:'value',max:100,axisLabel:{formatter:'{value}%',fontSize:8,color:'#a1a5b2'},splitLine:{lineStyle:{color:'#edf0f4'}}},series:[{type:'bar',barMaxWidth:28,data:[68.2,94.4,71.0,42.8,56.3],itemStyle:{color:(params)=>['#6071f2','#4f82ef','#9a7ee9','#45b991','#f0a05e'][params.dataIndex]||'#6071f2',borderRadius:[5,5,0,0]},label:{show:true,position:'top',formatter:'{c}%',fontSize:9,color:'#5e6475'}}],
}
onMounted(async()=>{try{[overview.value,retention.value]=await Promise.all([adminApi.overview(),adminApi.retention()])}catch(reason){error.value=reason instanceof Error?reason.message:'运营分析加载失败'}finally{loading.value=false}})
</script>
<template>
  <div class="admin-page">
    <div class="admin-page-head"><div><h2>运营分析</h2><p>从活跃、留存、转化与运动目标多个视角理解产品使用。</p></div><div class="admin-filter"><button>近 30 天</button><button class="primary-btn">保存当前视图</button></div></div>
    <el-alert title="Product DAU 是 Web 与 Device 有效活跃用户的去重并集；自动上传不会被直接记为 Web DAU。" type="info" show-icon :closable="false"/>
    <el-alert v-if="error" :title="error" type="error" show-icon :closable="false"/>
    <div v-if="loading" class="admin-surface admin-pad"><el-skeleton :rows="9" animated/></div>
    <template v-else>
      <section class="admin-surface admin-pad"><div class="admin-section-head"><div><h3>活跃用户口径对比</h3><p>区分主动打开网页、设备有效活动与产品整体触达</p></div></div><AdminChart :option="activityOption" :height="325"/></section>
      <section class="admin-equal">
        <article class="admin-surface admin-pad"><div class="admin-section-head"><div><h3>关键转化与完成率</h3><p>当前周期 Mock 汇总</p></div></div><AdminChart :option="conversionOption" :height="285"/></article>
        <article class="admin-surface admin-pad"><div class="admin-section-head"><div><h3>用户留存 Cohort</h3><p>按注册周分组</p></div></div><table class="retention-table"><thead><tr><th>注册 Cohort</th><th>次日</th><th>7 日</th><th>30 日</th></tr></thead><tbody><tr v-for="row in retention" :key="row.cohort"><td>{{ row.cohort }}</td><td><span :style="{opacity:.35+row.day1}">{{ formatPercent(row.day1) }}</span></td><td><span v-if="row.day7" :style="{opacity:.35+row.day7}">{{ formatPercent(row.day7) }}</span><i v-else>—</i></td><td><span v-if="row.day30" :style="{opacity:.35+row.day30}">{{ formatPercent(row.day30) }}</span><i v-else>—</i></td></tr></tbody></table></article>
      </section>
      <section class="analysis-cards">
        <article class="admin-surface admin-pad"><span class="analysis-icon blue">↗</span><strong>萌宠创建转化率</strong><b>45.7%</b><p>在注册且完成首次同步的用户中，约一半进入并完成萌宠创建。</p></article>
        <article class="admin-surface admin-pad"><span class="analysis-icon mint">◎</span><strong>运动目标完成率</strong><b>56.3%</b><p>按用户日聚合；未同步的日期不计为失败，也不计入分母。</p></article>
        <article class="admin-surface admin-pad"><span class="analysis-icon orange">↺</span><strong>7 日留存</strong><b>48.2%</b><p>至少产生一次 Web 主动访问或设备有效活动，且进行用户去重。</p></article>
      </section>
    </template>
  </div>
</template>
<style scoped>
.retention-table{width:100%;border-collapse:separate;border-spacing:5px 9px;font-size:9px}.retention-table th{color:#8c91a1;font-weight:600}.retention-table td{text-align:center}.retention-table td:first-child{text-align:left;color:#686e80}.retention-table span{display:block;padding:9px 5px;border-radius:7px;color:#263b86;background:#92a2ff;font-weight:700}.retention-table i{display:block;padding:9px 5px;color:#aaaebb;background:#f3f4f7;border-radius:7px;font-style:normal}.analysis-cards{display:grid;grid-template-columns:repeat(3,1fr);gap:14px}.analysis-cards article{position:relative}.analysis-cards strong,.analysis-cards b{display:block}.analysis-cards strong{margin-top:14px;color:#73798b;font-size:10px}.analysis-cards b{margin:7px 0;font-size:24px}.analysis-cards p{margin:0;color:#989cab;font-size:9px;line-height:1.7}.analysis-icon{width:34px;height:34px;display:grid;place-items:center;border-radius:10px}.analysis-icon.blue{color:#5565df;background:#edf0ff}.analysis-icon.mint{color:#259679;background:#e7f7f2}.analysis-icon.orange{color:#d8764f;background:#ffefe8}@media(max-width:720px){.analysis-cards{grid-template-columns:1fr}}
</style>
