<script setup>
import { ref } from 'vue'
import { post } from '../api'
import { setSession, toast } from '../store'

const username = ref('')
const password = ref('')
const loading = ref(false)
const error = ref('')

async function submit() {
  error.value = ''
  loading.value = true
  try {
    const res = await post('/login', { username: username.value.trim(), password: password.value })
    setSession(res.token, res.user)
    toast(`欢迎，${res.user.name}`)
  } catch (err) {
    error.value = err.message
  } finally {
    loading.value = false
  }
}

function fill(name, pwd) {
  username.value = name
  password.value = pwd
}
</script>

<template>
  <div class="layout" style="max-width: 420px; padding-top: 12vh">
    <div class="card">
      <h3>登录 CampusEvent</h3>
      <p class="muted">校园活动报名与管理系统 · 实验二</p>

      <div v-if="error" class="alert error">{{ error }}</div>

      <form @submit.prevent="submit">
        <div style="margin: 12px 0">
          <label>账号</label>
          <input v-model="username" placeholder="admin 或 s001" style="width: 100%" autocomplete="username" />
        </div>
        <div style="margin: 12px 0">
          <label>口令</label>
          <input v-model="password" type="password" placeholder="admin123 或 student123" style="width: 100%" autocomplete="current-password" />
        </div>
        <button class="btn" type="submit" :disabled="loading" style="width: 100%">
          {{ loading ? '登录中…' : '登录' }}
        </button>
      </form>

      <p class="muted" style="margin-top: 14px">演示账号：</p>
      <div class="row">
        <button class="plain btn" @click="fill('admin', 'admin123')">管理员 admin</button>
        <button class="plain btn" @click="fill('s001', 'student123')">学生 s001</button>
      </div>
    </div>
  </div>
</template>
