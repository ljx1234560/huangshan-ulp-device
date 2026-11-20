<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { adminApi, type UserProfile } from '@velapet/api'
import { formatDateTime } from '@velapet/shared'

const users=ref<UserProfile[]>([])
const loading=ref(true)
const search=ref('')
const status=ref('')
const binding=ref('')
const selected=ref<UserProfile>()
const drawer=ref(false)
const error=ref('')

const filtered=computed(()=>users.value.filter((user)=>{
  const keyword=search.value.toLowerCase()
  const match=!keyword||user.name.toLowerCase().includes(keyword)||user.email.toLowerCase().includes(keyword)
  const statusMatch=!status.value||user.status===status.value
  const bindingMatch=!binding.value||String(user.deviceBound)===binding.value
  return match&&statusMatch&&bindingMatch
}))
function openDetail(user:UserProfile){selected.value=user;drawer.value=true}
onMounted(async()=>{try{users.value=await adminApi.users()}catch(reason){error.value=reason instanceof Error?reason.message:'用户列表加载失败'}finally{loading.value=false}})
</script>

<template>
  <div class="admin-page">
    <div class="admin-page-head"><div><h2>用户管理</h2><p>查看账号状态与设备绑定概况，不暴露完整个人运动明细。</p></div><button class="primary-btn">导出脱敏列表</button></div>
    <el-alert v-if="error" :title="error" type="error" show-icon :closable="false"/>
    <section class="kpi-grid user-kpis">
      <article class="mini-stat"><span>总注册用户</span><strong>24,680</strong><small>演示口径</small></article>
      <article class="mini-stat"><span>正常账号</span><strong>24,102</strong><small>97.7%</small></article>
      <article class="mini-stat"><span>设备绑定率</span><strong>68.2%</strong><small>16,842 台</small></article>
      <article class="mini-stat"><span>本周新增</span><strong>1,482</strong><small>↗ 8.1%</small></article>
    </section>
    <section class="admin-surface admin-pad">
      <div class="table-toolbar">
        <el-input v-model="search" class="search" clearable placeholder="搜索昵称或邮箱"><template #prefix>⌕</template></el-input>
        <div class="admin-filter"><el-select v-model="status" clearable placeholder="账号状态" style="width:130px"><el-option label="正常" value="active"/><el-option label="停用" value="disabled"/></el-select><el-select v-model="binding" clearable placeholder="设备绑定" style="width:130px"><el-option label="已绑定" value="true"/><el-option label="未绑定" value="false"/></el-select></div>
      </div>
      <el-table v-loading="loading" :data="filtered" style="width:100%">
        <el-table-column label="用户" min-width="190"><template #default="{row}"><div class="user-cell"><span>{{ row.name.slice(0,1) }}</span><div><strong>{{ row.name }}</strong><small>{{ row.email.replace(/(.{2}).+(@.+)/,'$1***$2') }}</small></div></div></template></el-table-column>
        <el-table-column label="状态" width="100"><template #default="{row}"><span class="status-chip" :class="row.status==='active'?'ok':'error'">{{ row.status==='active'?'正常':'停用' }}</span></template></el-table-column>
        <el-table-column label="注册时间" min-width="130"><template #default="{row}">{{ formatDateTime(row.registeredAt) }}</template></el-table-column>
        <el-table-column label="最后活跃" min-width="130"><template #default="{row}">{{ formatDateTime(row.lastActiveAt) }}</template></el-table-column>
        <el-table-column label="设备" width="110"><template #default="{row}"><span :class="['status-chip',row.deviceBound?'ok':'warn']">{{ row.deviceBound?'已绑定':'未绑定' }}</span></template></el-table-column>
        <el-table-column label="操作" width="90" fixed="right"><template #default="{row}"><el-button link type="primary" @click="openDetail(row)">查看</el-button></template></el-table-column>
      </el-table>
      <el-empty v-if="!loading&&filtered.length===0" description="没有符合筛选条件的用户"/>
    </section>
    <el-drawer v-model="drawer" title="用户基本详情" size="420px">
      <template v-if="selected">
        <div class="drawer-profile"><span>{{ selected.name.slice(0,1) }}</span><div><h3>{{ selected.name }}</h3><p>{{ selected.email.replace(/(.{2}).+(@.+)/,'$1***$2') }}</p></div></div>
        <el-descriptions :column="1" border>
          <el-descriptions-item label="用户 ID">{{ selected.id }}</el-descriptions-item>
          <el-descriptions-item label="账号状态">{{ selected.status==='active'?'正常':'停用' }}</el-descriptions-item>
          <el-descriptions-item label="注册时间">{{ formatDateTime(selected.registeredAt) }}</el-descriptions-item>
          <el-descriptions-item label="最后活跃">{{ formatDateTime(selected.lastActiveAt) }}</el-descriptions-item>
          <el-descriptions-item label="设备绑定">{{ selected.deviceBound?'已绑定':'未绑定' }}</el-descriptions-item>
        </el-descriptions>
        <el-alert style="margin-top:18px" title="隐私边界" description="运营角色默认只查看账号与设备绑定概况。完整运动记录需要更高权限、业务理由与后端审计。" type="info" :closable="false" show-icon/>
      </template>
    </el-drawer>
  </div>
</template>

<style scoped>
.user-kpis{grid-template-columns:repeat(4,1fr)}.mini-stat{padding:15px 17px;border:1px solid var(--line);border-radius:13px;background:white}.mini-stat span,.mini-stat strong,.mini-stat small{display:block}.mini-stat span{color:#858a9c;font-size:9px}.mini-stat strong{margin:7px 0 3px;font-size:20px}.mini-stat small{color:#45a481;font-size:9px}.user-cell{display:flex;align-items:center;gap:10px}.user-cell>span,.drawer-profile>span{width:31px;height:31px;display:grid;place-items:center;border-radius:9px;color:#5968d9;background:#edf0ff;font-size:10px;font-weight:700}.user-cell strong,.user-cell small{display:block}.user-cell strong{font-size:11px}.user-cell small{margin-top:3px;color:#999daa;font-size:9px}.drawer-profile{display:flex;align-items:center;gap:12px;margin-bottom:22px;padding:15px;border-radius:12px;background:#f6f7fb}.drawer-profile>span{width:45px;height:45px;font-size:15px}.drawer-profile h3{margin:0}.drawer-profile p{margin:4px 0 0;color:#858a9a;font-size:11px}@media(max-width:740px){.user-kpis{grid-template-columns:repeat(2,1fr)}}@media(max-width:440px){.user-kpis{grid-template-columns:1fr}}
</style>
