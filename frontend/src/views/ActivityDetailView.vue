<script setup>
import { onMounted, ref, watch } from 'vue'
import { get, post } from '../api'
import { go, toast, state } from '../store'

const props = defineProps({ activityId: { type: String, required: true } })

const activity = ref(null)
const stats = ref(null)
const error = ref('')
const busy = ref(false)

async function load() {
  error.value = ''
  try {
    activity.value = await get(`/activities/${props.activityId}`)
    stats.value = await get(`/activities/${props.activityId}/stats`)
  } catch (err) {
    error.value = err.message
  }
}

async function register() {
  busy.value = true
  error.value = ''
  try {
    const res = await post(`/activities/${props.activityId}/registrations`)
    toast(res.status === 'APPROVED' ? '报名成功，已通过' : '已提交，等待管理员审核')
    await load()
  } catch (err) {
    error.value = err.message
  } finally {
    busy.value = false
  }
}

onMounted(load)
watch(() => props.activityId, load)
</script>

<template>
  <div>
    <button class="btn plain" style="margin-top: 16px" @click="go('activities')">← 返回活动列表</button>

    <div v-if="error" class="alert error">{{ error }}</div>
    <div v-if="!activity" class="empty">加载中…</div>

    <div v-else class="card">
      <div class="row">
        <span class="tag">{{ activity.category }}</span>
        <span :class="['tag', activity.policy_type === 'DIRECT' ? 'direct' : 'review']">
          {{ activity.policy_type === 'DIRECT' ? '直接报名（自动通过）' : '审核型（需管理员批准）' }}
        </span>
      </div>
      <h3 style="font-size: 20px; margin: 10px 0">{{ activity.title }}</h3>
      <p class="muted">
        时间：{{ activity.start_at.replace('T', ' ') }}<br />
        地点：{{ activity.location }}<br />
        人数上限：{{ activity.capacity }}
      </p>

      <div class="stat">
        <div><b>{{ stats?.approved ?? '-' }}</b>已通过</div>
        <div><b>{{ stats?.pending ?? '-' }}</b>待审核</div>
        <div><b>{{ stats?.remaining ?? '-' }}</b>剩余名额</div>
      </div>

      <div class="row" style="margin-top: 16px">
        <button class="btn" :disabled="busy || !activity.open" @click="register">
          {{ activity.open ? (busy ? '提交中…' : '报名') : '已截止' }}
        </button>
        <button class="btn plain" @click="go('mine')">我的报名</button>
        <span v-if="state.user?.role === 'STUDENT'" class="muted">同一活动只能有一条有效报名</span>
      </div>
    </div>
  </div>
</template>
