<script setup lang="ts">
import { reactive } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { apiMode } from '@velapet/api'
import { useAuthStore } from '../stores/auth'

const auth = useAuthStore()
const router = useRouter()
const form = reactive({ name: '', email: '', password: '', agreement: true })

async function submit() {
  if (!form.name || !form.email || form.password.length < 8) return ElMessage.warning('请完整填写信息，密码至少 8 位')
  if (!form.agreement) return ElMessage.warning('请先同意使用说明')
  try {
    await auth.register(form.name, form.email, form.password)
    ElMessage.success(apiMode === 'real' ? '账号已创建' : '演示账号已创建')
    await router.push('/')
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : '注册失败')
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
        <p class="eyebrow">YOUR PET, YOUR RHYTHM</p>
        <h1>从今天开始，<br />养成自己的星轨。</h1>
        <p>创建账号后即可体验运动数据、AI 教练和萌宠工坊。{{ apiMode === 'mock' ? '当前为纯前端 Mock 流程，不会上传真实个人数据。' : '真实模式下数据会保存到配置的后端数据库。' }}</p>
      </div>
    </section>
    <section class="auth-form-wrap">
      <div class="auth-card surface">
        <h2>{{ apiMode === 'mock' ? '创建演示账号' : '创建账号' }}</h2>
        <p>三步之后，就能遇见你的 VelaPet</p>
        <el-form label-position="top" @submit.prevent>
          <el-form-item label="昵称"><el-input v-model="form.name" placeholder="怎么称呼你？" /></el-form-item>
          <el-form-item label="邮箱"><el-input v-model="form.email" type="email" placeholder="name@example.com" /></el-form-item>
          <el-form-item label="密码"><el-input v-model="form.password" type="password" show-password placeholder="至少 8 位" @keyup.enter="submit" /></el-form-item>
          <el-checkbox v-model="form.agreement">{{ apiMode === 'mock' ? '我了解当前账号与数据均为本机演示' : '我同意创建账号并保存必要业务数据' }}</el-checkbox>
          <el-button class="auth-submit" style="margin-top: 20px" type="primary" :loading="auth.loading" @click="submit">开始体验</el-button>
        </el-form>
        <div class="auth-switch">已有账号？ <router-link to="/login">返回登录</router-link></div>
      </div>
    </section>
  </div>
</template>
