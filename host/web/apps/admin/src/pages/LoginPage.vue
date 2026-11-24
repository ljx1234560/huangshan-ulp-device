<script setup lang="ts">
import { reactive } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { apiMode } from '@velapet/api'
import { useAdminAuth } from '../stores/auth'

const auth = useAdminAuth()
const router = useRouter()
const form = reactive({ email: 'admin@velapet.cn', password: apiMode === 'real' ? 'VelaPetAdmin123!' : 'velapet-admin-demo' })
async function submit(){
  if(!form.email || !form.password) return ElMessage.warning('请输入账号和密码')
  try{ await auth.login(form.email,form.password); ElMessage.success(apiMode === 'real' ? '管理员登录成功' : '已进入运营演示环境'); router.push('/') }
  catch(error){ ElMessage.error(error instanceof Error ? error.message : '登录失败') }
}
</script>
<template>
  <div class="admin-login">
    <section class="admin-login-visual">
      <div class="admin-brand"><span>V</span><div><strong>VelaPet</strong><small>OPERATIONS</small></div></div>
      <div class="admin-login-copy"><span>DATA WITH CLEAR BOUNDARIES</span><h1>让每一次活跃，<br />都有清晰的解释。</h1><p>统一观察 Web 活跃、设备同步与产品触达，保持统计口径透明，帮助运营团队理解真正的用户参与。</p></div>
    </section>
    <section class="admin-login-form">
      <div class="admin-login-card admin-surface">
        <h2>登录运营控制台</h2><p>仅限授权运营与分析人员使用</p>
        <el-form label-position="top" @submit.prevent>
          <el-form-item label="管理员邮箱"><el-input v-model="form.email" /></el-form-item>
          <el-form-item label="密码"><el-input v-model="form.password" type="password" show-password @keyup.enter="submit" /></el-form-item>
          <el-button type="primary" :loading="auth.loading" @click="submit">进入控制台</el-button>
        </el-form>
        <div class="login-demo" v-if="apiMode === 'mock'">演示模式 · 任意非空密码可登录，不代表正式权限机制</div>
        <div class="login-demo" v-else>真实模式 · 管理员角色由后端 RBAC 强制验证</div>
      </div>
    </section>
  </div>
</template>
