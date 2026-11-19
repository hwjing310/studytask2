<script setup>
import { onMounted, ref } from 'vue'
import { get, post } from '../api'
import { toast } from '../store'

const items = ref([])
const loading = ref(false)
const error = ref('')

const LABEL = {
  PENDING: '待审核',
  APPROVED: '已通过',
  REJECTED: '已拒绝',
  CANCELLED: '已取消',
  WAITLISTED: '候补中',
}

async function load() {
  loading.value = true
  error.value = ''
  try {
    const res = await get('/registrations/mine')
    items.value = res.items
  } catch (err) {
    error.value = err.message
  } finally {
    loading.value = false
  }
}

async function cancel(item) {
  error.value = ''
  try {
    await post(`/registrations/${item.registration_id}/cancel`)
    toast('已取消报名')
    await load()
  } catch (err) {
    error.value = err.message
  }
}

onMounted(load)
</script>

<template>
  <div>
    <div class="row" style="margin-top: 18px">
      <h3 style="margin: 0">我的报名</h3>
      <span class="grow"></span>
      <button class="btn plain" @click="load" :disabled="loading">刷新</button>
    </div>

    <div v-if="error" class="alert error">{{ error }}</div>
    <div v-if="loading" class="empty">加载中…</div>
    <div v-else-if="items.length === 0" class="empty">还没有报名记录</div>

    <div v-for="r in items" :key="r.registration_id" class="card">
      <div class="row">
        <strong>{{ r.activity_title }}</strong>
        <span class="grow"></span>
        <span :class="['status', r.status]">{{ LABEL[r.status] || r.status }}</span>
      </div>
      <p class="muted" style="margin: 6px 0 0">
        活动时间：{{ (r.activity_start_at || '').replace('T', ' ') }} ·
        提交于 {{ r.created_at.replace('T', ' ') }}
        <span v-if="r.status === 'WAITLISTED' && r.waitlist_position">
          · 候补第 {{ r.waitlist_position }} 位
        </span>
      </p>
      <div class="row" style="margin-top: 10px">
        <button
          v-if="r.status === 'PENDING' || r.status === 'APPROVED' || r.status === 'WAITLISTED'"
          class="btn danger"
          @click="cancel(r)"
        >
          {{ r.status === 'WAITLISTED' ? '取消候补' : '取消报名' }}
        </button>
      </div>
    </div>
  </div>
</template>
