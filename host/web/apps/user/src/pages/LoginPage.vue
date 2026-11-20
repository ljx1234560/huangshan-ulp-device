<script setup lang="ts">
import { reactive } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { apiMode } from '@velapet/api'
import { useAuthStore } from '../stores/auth'

const auth = useAuthStore()
const router = useRouter()
const route = useRoute()
const form = reactive({
  email: 'demo@velapet.cn',
  password: apiMode === 'real' ? 'VelaPetDemo123!' : 'velapet-demo',
})

async function submit() {
  if (!form.email || !form.password) return ElMessage.warning('请填写邮箱和密码')
  try {
    await auth.login(form.email, form.password)
    ElMessage.success(apiMode === 'real' ? '登录成功' : '已进入 VelaPet 演示空间')
    await router.push((route.query.redirect as string) || '/')
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : '登录失败')
  }
}
</script>

<template>
  <div class="auth-page">
    <section class="auth-visual">
      <div class="auth-logo"><span class="brand-mark">V</span> VelaPet</div>
      <div class="auth-orbit" />
      <span class="auth-star s1" /><span class="auth-star s2" /><span class="auth-star s3" />
      <div class="auth-copy">
        <p class="eyebrow">MOVE · GROW · BOND</p>
        <h1>每一步，<br />都有萌宠陪伴。</h1>
        <p>把日常运动变成一场温柔的成长冒险。查看同步数据、获得 AI 建议，和你的专属萌宠一起养成更好的节奏。</p>
      </div>
    </section>
    <section class="auth-form-wrap">
      <div class="auth-card surface">
        <h2>欢迎回来</h2>
        <p>登录后继续你和萌宠的今日旅程</p>
        <el-form label-position="top" @submit.prevent>
          <el-form-item label="邮箱">
            <el-input v-model="form.email" type="email" placeholder="name@example.com" />
          </el-form-item>
          <el-form-item label="密码">
            <el-input v-model="form.password" type="password" show-password placeholder="请输入密码" @keyup.enter="submit" />
          </el-form-item>
          <el-button class="auth-submit" type="primary" :loading="auth.loading" @click="submit">进入我的 VelaPet</el-button>
        </el-form>
        <div class="auth-demo" v-if="apiMode === 'mock'">演示模式 · 任意非空密码均可登录，不代表正式认证机制</div>
        <div class="auth-demo" v-else>真实模式 · 身份与权限由服务端验证，会话使用安全 Cookie 恢复</div>
        <div class="auth-switch">还没有账号？ <router-link to="/register">创建账号</router-link></div>
      </div>
    </section>
  </div>
</template>
