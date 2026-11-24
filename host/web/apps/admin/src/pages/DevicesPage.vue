<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { adminApi, type AdminOverview, type DeviceRecord } from '@velapet/api'
import { formatDateTime } from '@velapet/shared'
import KpiCard from '../components/KpiCard.vue'

const devices=ref<DeviceRecord[]>([])
const loading=ref(true)
const search=ref('')
const state=ref('')
const error=ref('')
const overview=ref<AdminOverview>()
const filtered=computed(()=>devices.value.filter(device=>(!search.value||device.id.toLowerCase().includes(search.value.toLowerCase())||device.name.toLowerCase().includes(search.value.toLowerCase()))&&(!state.value||device.syncState===state.value)))
function syncStateLabel(value: DeviceRecord['syncState']) {
  return { synced: '最近同步成功', stale: '长时间未同步', error: '异常', unbound: '未绑定' }[value]
}
const boundCount=computed(()=>devices.value.filter(item=>item.bound).length)
const activeCount=computed(()=>devices.value.filter(item=>item.syncState==='synced').length)
const failureCount=computed(()=>overview.value?.syncFailures ?? devices.value.reduce((sum,item)=>sum+(item.syncFailureCount||0),0))
const firmwareRows=computed(()=>Object.entries(overview.value?.firmwareVersions || devices.value.reduce<Record<string,number>>((map,item)=>{const key=item.firmwareVersion||'unknown';map[key]=(map[key]||0)+1;return map},{})).sort((a,b)=>b[1]-a[1]))
const firmwareTotal=computed(()=>firmwareRows.value.reduce((sum,item)=>sum+item[1],0)||1)
onMounted(async()=>{try{[devices.value,overview.value]=await Promise.all([adminApi.devices(),adminApi.overview()])}catch(reason){error.value=reason instanceof Error?reason.message:'设备列表加载失败'}finally{loading.value=false}})
</script>
<template>
  <div class="admin-page">
    <div class="admin-page-head"><div><h2>设备管理</h2><p>监控绑定、固件、同步与异常状态。</p></div><button class="secondary-btn">导出设备清单</button></div>
    <el-alert v-if="error" :title="error" type="error" show-icon :closable="false"/>
    <section class="kpi-grid device-kpis"><KpiCard label="已绑定设备" :value="String(overview?.boundDevices ?? boundCount)" icon="▣" tone="blue"/><KpiCard label="24h 活跃设备" :value="String(overview?.activeDevices ?? activeCount)" icon="↗" tone="mint"/><KpiCard label="同步成功率" :value="Math.round((overview?.syncSuccessRate||0)*1000)/10+'%'" icon="✓" tone="violet"/><KpiCard label="同步失败次数" :value="String(failureCount)" icon="!" tone="orange"/></section>
    <section class="admin-surface admin-pad admin-table-surface">
      <div class="table-toolbar"><el-input v-model="search" class="search" clearable placeholder="搜索设备名称或编号"><template #prefix>⌕</template></el-input><div class="admin-filter"><el-select v-model="state" clearable placeholder="同步状态" style="width:140px"><el-option label="最近同步成功" value="synced"/><el-option label="长时间未同步" value="stale"/><el-option label="异常" value="error"/><el-option label="未绑定" value="unbound"/></el-select></div></div>
      <el-table v-loading="loading" :data="filtered" style="width:100%">
        <el-table-column prop="id" label="设备编号" min-width="170"/>
        <el-table-column prop="name" label="设备名称" min-width="150"/>
        <el-table-column prop="model" label="型号" min-width="150"/>
        <el-table-column label="固件版本" width="120"><template #default="{row}">{{ row.firmwareVersion||'—' }}</template></el-table-column>
        <el-table-column label="绑定" width="90"><template #default="{row}"><span :class="['status-chip',row.bound?'ok':'warn']">{{ row.bound?'已绑定':'未绑定' }}</span></template></el-table-column>
        <el-table-column label="电量" width="90"><template #default="{row}">{{ row.battery===undefined?'—':row.battery+'%' }}</template></el-table-column>
        <el-table-column label="最近同步" min-width="140"><template #default="{row}">{{ formatDateTime(row.lastSyncAt) }}</template></el-table-column>
        <el-table-column label="当前连接" min-width="150"><template #default="{row}">{{ row.bridge?.connected ? 'BLE 已连接' : row.bridge?.running ? '桥接运行，BLE 未连接' : '桥接未运行' }}</template></el-table-column>
        <el-table-column label="同步状态" min-width="145"><template #default="{row}"><span class="status-chip" :class="row.syncState==='synced'?'ok':row.syncState==='error'?'error':'warn'">{{ syncStateLabel(row.syncState) }}</span></template></el-table-column>
        <el-table-column label="异常说明" min-width="190"><template #default="{row}">{{ row.anomaly||'—' }}</template></el-table-column>
      </el-table>
    </section>
    <div class="admin-equal">
      <article class="admin-surface admin-pad"><div class="admin-section-head"><div><h3>固件版本分布</h3><p>来自数据库设备记录，不推测未知版本</p></div></div><div class="version-bars"><div v-for="([version,count]) in firmwareRows" :key="version"><span>{{ version }}</span><i><b :style="{width:Math.round(count/firmwareTotal*100)+'%'}"/></i><strong>{{ Math.round(count/firmwareTotal*100) }}%</strong></div><p v-if="!firmwareRows.length">暂无设备数据</p></div></article>
      <article class="admin-surface admin-pad"><div class="admin-section-head"><div><h3>异常处理边界</h3><p>运营可观察，不能越权修改设备权威状态</p></div></div><div class="boundary-list"><p><span>1</span>同步失败可创建排查记录</p><p><span>2</span>解绑与固件操作必须由后端鉴权并审计</p><p><span>3</span>浏览器不直接读取固件本地存储</p></div></article>
    </div>
  </div>
</template>
<style scoped>
.device-kpis{grid-template-columns:repeat(4,1fr)}.version-bars{display:grid;gap:14px}.version-bars>div{display:grid;grid-template-columns:55px 1fr 35px;align-items:center;gap:10px;font-size:10px}.version-bars i{height:7px;border-radius:99px;background:#eef0f5;overflow:hidden}.version-bars b{display:block;height:100%;border-radius:99px;background:#6979f3}.version-bars strong{text-align:right}.boundary-list p{display:flex;align-items:center;gap:10px;margin:0;padding:11px 0;border-bottom:1px solid #edf0f4;color:#747a8d;font-size:10px}.boundary-list span{width:23px;height:23px;display:grid;place-items:center;border-radius:7px;color:#5d6be0;background:#edf0ff;font-size:9px;font-weight:700}@media(max-width:740px){.device-kpis{grid-template-columns:repeat(2,1fr)}}
</style>
