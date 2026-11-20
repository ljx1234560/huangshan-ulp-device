<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref } from 'vue'
import { apiMode, deviceApi, type BridgeStatus, type DeviceRecord, type SyncLog } from '@velapet/api'
import { ElMessage, ElMessageBox } from 'element-plus'
import { formatDateTime } from '@velapet/shared'

const devices = ref<DeviceRecord[]>([])
const logs = ref<SyncLog[]>([])
const loading = ref(true)
const syncing = ref(false)
const error = ref('')
const bridge = ref<BridgeStatus>()
let pollTimer: ReturnType<typeof setInterval> | undefined

async function refreshBridge() {
  const device = devices.value[0]
  if (!device) return
  try {
    bridge.value = await deviceApi.bridgeStatus(device.id)
    device.bridge = bridge.value
  } catch { /* normal while the bridge is starting */ }
}

async function load() {
  loading.value = true
  error.value = ''
  try { ;[devices.value, logs.value] = await Promise.all([deviceApi.list(), deviceApi.history()]); await refreshBridge() }
  catch (reason) { error.value = reason instanceof Error ? reason.message : '设备数据加载失败' }
  finally { loading.value = false }
}

async function sync(device: DeviceRecord) {
  syncing.value = true
  try {
    const result = await deviceApi.sync(device.id)
    logs.value.unshift(result)
    device.lastSyncAt = result.createdAt
    ElMessage.success(result.message)
  } catch (reason) {
    ElMessage.error(reason instanceof Error ? reason.message : '同步失败')
  } finally { syncing.value = false }
}

async function unbind(device: DeviceRecord) {
  await ElMessageBox.confirm(apiMode === 'mock' ? '这是演示操作，不会改变真实设备。确定继续吗？' : '解绑后该用户不能继续上传设备数据。确定继续吗？', '解绑设备', { confirmButtonText: '确认解绑', cancelButtonText: '取消', type: 'warning' })
  await deviceApi.unbind(device.id)
  device.bound = false
  device.syncState = 'unbound'
  ElMessage.success('设备绑定已解除')
}

onMounted(async () => { await load(); if (apiMode === 'real') pollTimer = setInterval(refreshBridge, 8000) })
onBeforeUnmount(() => { if (pollTimer) clearInterval(pollTimer) })
</script>

<template>
  <div class="page-stack">
    <div class="page-heading"><div><h2>设备中心</h2><p>浏览器通过后端观察 Windows BLE 桥接；不会直接访问本机蓝牙。</p></div><button class="ghost-button" @click="load">↻ 手动刷新</button></div>
    <el-alert :title="apiMode === 'mock' ? 'Mock 模式：设备与桥接状态均为演示数据。' : 'Real 模式：桥接状态来自短期授权会话；离线不等同于设备在全球范围离线。'" :type="apiMode === 'mock' ? 'warning' : 'success'" show-icon :closable="false" />
    <el-alert v-if="error" :title="error" type="error" show-icon :closable="false" />
    <div v-if="loading" class="surface surface-pad"><el-skeleton :rows="8" animated /></div>
    <template v-else>
      <section v-if="devices[0]" class="device-hero surface">
        <div class="watch-render"><span>V</span><i>78%</i></div>
        <div class="device-copy">
          <span class="status-online">● 已绑定 · {{ apiMode === 'mock' ? 'Mock' : '数据库' }}</span><h2>{{ devices[0].name }}</h2><p>{{ devices[0].model }} · {{ devices[0].id }}</p>
          <div class="device-facts">
            <div><span>设备电量</span><strong>{{ devices[0].battery ?? '—' }}%</strong></div>
            <div><span>固件版本</span><strong>{{ devices[0].firmwareVersion || '暂无' }}</strong></div>
            <div><span>上次同步</span><strong>{{ formatDateTime(devices[0].lastSyncAt) }}</strong></div>
            <div><span>同步协议</span><strong>{{ devices[0].protocolVersion ? 'v' + devices[0].protocolVersion : '暂无' }}</strong></div>
            <div><span>桥接程序</span><strong>{{ bridge?.running ? '运行中' : '未运行' }}</strong></div>
            <div><span>BLE 连接</span><strong>{{ bridge?.connected ? '已连接' : '未连接' }}</strong></div>
            <div><span>桥接心跳</span><strong>{{ formatDateTime(bridge?.lastSeenAt) }}</strong></div>
          </div>
          <div class="device-actions"><button class="primary-button" :disabled="syncing" @click="sync(devices[0])">{{ syncing ? '同步中…' : '↻ 立即同步' }}</button><button class="ghost-button" @click="unbind(devices[0])">解绑设备</button></div>
        </div>
      </section>
      <section class="two-col">
        <article class="surface surface-pad">
          <div class="section-title"><div><h3>同步架构状态</h3><p>{{ bridge?.message || '等待 Windows 桥接程序上报' }}</p></div></div>
          <div class="architecture-list">
            <div class="ready"><span>✓</span><div><strong>后端幂等上传</strong><p>数据库成功提交后才允许设备 ACK</p></div><b>已实现</b></div>
            <div :class="{ ready: bridge?.running }"><span>2</span><div><strong>Windows BLE 桥接</strong><p>短期用户授权；最近同步 {{ bridge?.lastSyncStatus || '暂无' }}，当前 BLE {{ bridge?.connected ? '已连接' : '未连接' }}</p></div><b>{{ bridge?.running ? '运行中' : '未运行' }}</b></div>
            <div><span>3</span><div><strong>SF32LB52 正式 GATT</strong><p>协议与候选实现已提供，仍需在真机固件集成验证</p></div><b>待真机</b></div>
          </div>
        </article>
        <article class="surface surface-pad">
          <div class="section-title"><div><h3>数据范围</h3><p>第一版仅接收明确的设备快照</p></div></div>
          <div class="data-scope"><span>每日步数</span><span>活跃时长</span><span>宠物等级/EXP</span><span>任务状态</span><span>装扮状态</span><span>设备诊断信息</span></div>
          <div class="info-note">不包含无硬件依据的心率、血氧或 GPS 数据。宠物状态只读展示，不由 Web 回写成长真值。</div>
        </article>
      </section>
      <section class="surface surface-pad table-surface">
        <div class="section-title"><div><h3>同步记录</h3><p>最近的设备数据传输结果</p></div><button class="ghost-button" @click="load">刷新</button></div>
        <el-table :data="logs" style="width:100%">
          <el-table-column label="时间" min-width="150"><template #default="{ row }">{{ formatDateTime(row.createdAt) }}</template></el-table-column>
          <el-table-column prop="deviceId" label="设备编号" min-width="170" />
          <el-table-column label="状态" width="100"><template #default="{ row }"><el-tag :type="row.status === 'success' ? 'success' : row.status === 'pending' ? 'warning' : 'danger'" effect="plain">{{ row.status === 'success' ? '成功' : row.status === 'pending' ? '等待上传' : '失败' }}</el-tag></template></el-table-column>
          <el-table-column prop="recordCount" label="记录数" width="90" />
          <el-table-column label="传输" width="110"><template #default="{ row }">{{ row.transport === 'ble_bridge' ? 'BLE 桥接' : row.source === 'web_request' ? 'Web 请求' : '设备 API' }}</template></el-table-column>
          <el-table-column prop="message" label="说明" min-width="220" />
        </el-table>
      </section>
    </template>
  </div>
</template>

<style scoped>
.device-hero{display:flex;align-items:center;gap:48px;padding:38px 8%;overflow:hidden;background:radial-gradient(circle at 5% 50%,rgba(119,98,236,.13),transparent 29%),white}.watch-render{width:180px;height:215px;flex:0 0 auto;position:relative;display:grid;place-items:center;border:12px solid #27253a;border-radius:55px;background:radial-gradient(circle at 50% 45%,#8979ee,#4d3bb9);box-shadow:0 22px 35px rgba(41,35,83,.23),inset 0 0 0 3px #57536c}.watch-render::before,.watch-render::after{content:'';position:absolute;left:52px;width:52px;height:55px;background:#373447;z-index:-1}.watch-render::before{top:-52px;border-radius:18px 18px 0 0}.watch-render::after{bottom:-52px;border-radius:0 0 18px 18px}.watch-render span{font-size:64px;color:white;font-weight:800}.watch-render i{position:absolute;bottom:18px;color:rgba(255,255,255,.72);font-style:normal;font-size:11px}.device-copy{flex:1}.status-online{color:#2e9f7f;font-size:11px;font-weight:700}.device-copy h2{margin:10px 0 3px;font-size:30px}.device-copy>p{margin:0;color:#858193;font-size:12px}.device-facts{display:grid;grid-template-columns:repeat(3,1fr);gap:12px;margin:26px 0}.device-facts div{padding:13px;border-radius:13px;background:#f7f6fb}.device-facts span,.device-facts strong{display:block}.device-facts span{color:#9995a5;font-size:9px}.device-facts strong{margin-top:6px;font-size:13px}.device-actions{display:flex;gap:9px}.architecture-list{display:grid;gap:12px}.architecture-list>div{display:grid;grid-template-columns:auto 1fr auto;gap:12px;align-items:center;padding:12px;border:1px solid #eeecf3;border-radius:14px}.architecture-list>div>span{width:32px;height:32px;display:grid;place-items:center;border-radius:10px;background:#f0eef9;color:#736e83;font-size:11px}.architecture-list .ready>span{color:#279879;background:#e4f7f1}.architecture-list strong{font-size:12px}.architecture-list p{margin:3px 0 0;color:#9995a5;font-size:9px}.architecture-list b{color:#898598;font-size:9px}.architecture-list .ready b{color:#279879}.data-scope{display:flex;flex-wrap:wrap;gap:8px;margin-bottom:20px}.data-scope span{padding:8px 10px;border-radius:10px;background:#f1effb;color:#6757bf;font-size:11px}@media(max-width:700px){.device-hero{align-items:flex-start;gap:25px;flex-direction:column}.watch-render{transform:scale(.82);transform-origin:left top;margin-bottom:-35px}.device-facts{grid-template-columns:1fr}.device-actions{flex-wrap:wrap}}
</style>
