<script setup lang="ts">
import { reactive } from 'vue'
import { ElMessage } from 'element-plus'
import { useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'

const auth = useAuthStore()
const router = useRouter()
const form = reactive({ name: auth.user?.name || '林晓满', email: auth.user?.email || 'demo@velapet.cn', goal: 10000, reminder: true })

function save() { ElMessage.success('演示资料已保存到当前页面状态') }
async function logout() { await auth.logout(); await router.push('/login') }
</script>

<template>
  <div class="page-stack">
    <div class="page-heading"><div><h2>个人资料</h2><p>管理展示信息与运动偏好。</p></div></div>
    <section class="profile-grid">
      <article class="surface surface-pad">
        <div class="profile-head"><span class="avatar large">晓</span><div><h3>{{ form.name }}</h3><p>VelaPet 演示用户 · 已绑定 1 台设备</p></div></div>
        <el-form label-position="top">
          <el-form-item label="昵称"><el-input v-model="form.name" /></el-form-item>
          <el-form-item label="邮箱"><el-input v-model="form.email" /></el-form-item>
          <el-form-item label="每日步数目标"><el-input-number v-model="form.goal" :step="500" :min="1000" :max="30000" /></el-form-item>
          <el-form-item label="活动提醒"><el-switch v-model="form.reminder" active-text="开启" inactive-text="关闭" /></el-form-item>
          <button type="button" class="primary-button" @click="save">保存演示资料</button>
        </el-form>
      </article>
      <aside class="page-stack">
        <article class="surface surface-pad"><div class="section-title"><div><h3>账户状态</h3><p>当前仅为前端演示会话</p></div></div><div class="setting-row"><span>认证模式</span><strong>Demo Token</strong></div><div class="setting-row"><span>数据模式</span><strong>Mock API</strong></div><div class="setting-row"><span>权限角色</span><strong>普通用户</strong></div></article>
        <article class="surface surface-pad danger-zone"><h3>退出当前账号</h3><p>退出会清除浏览器中的演示会话，不会影响任何真实设备数据。</p><button class="ghost-button" @click="logout">退出登录</button></article>
      </aside>
    </section>
  </div>
</template>

<style scoped>
.profile-grid{display:grid;grid-template-columns:minmax(0,1fr) minmax(300px,.65fr);gap:20px}.profile-head{display:flex;align-items:center;gap:16px;margin-bottom:28px;padding-bottom:22px;border-bottom:1px solid #eeecf3}.avatar.large{width:65px;height:65px;font-size:20px;background:linear-gradient(145deg,#8876ee,#5d49d2);color:white}.profile-head h3{margin:0;font-size:21px}.profile-head p{margin:5px 0 0;color:#8e8a9c;font-size:12px}.setting-row{display:flex;justify-content:space-between;padding:13px 0;border-bottom:1px solid #efedf4;font-size:12px}.setting-row span{color:#8e8a9d}.danger-zone p{color:#858193;font-size:12px;line-height:1.7}@media(max-width:780px){.profile-grid{grid-template-columns:1fr}}
</style>
