<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { get, post } from '../api'
import { go, toast, state } from '../store'

const props = defineProps({ activityId: { type: String, required: true } })

const activity = ref(null)
const stats = ref(null)
const error = ref('')
const busy = ref(false)
const mine = ref(null)

const STATUS_LABEL = {
  PENDING: '待审核',
  APPROVED: '已通过',
  REJECTED: '已拒绝',
  CANCELLED: '已取消',
  WAITLISTED: '候补中',
}
const ACTIVE_STATUS = ['PENDING', 'APPROVED', 'WAITLISTED']

const hasWaitlist = computed(() => {
  const a = activity.value
  if (!a) return false
  return a.waitlist_capacity > 0 && (stats.value?.remaining ?? 1) === 0 && !a.deleted_at
})

const isStudent = computed(() => state.user?.role === 'STUDENT')
const hasActiveRegistration = computed(() => Boolean(mine.value && ACTIVE_STATUS.includes(mine.value.status)))

async function loadMine() {
  if (!isStudent.value) {
    mine.value = null
    return
  }
  try {
    const res = await get('/registrations/mine')
    mine.value = res.items.find((r) => r.activity_id === props.activityId) || null
  } catch {
    mine.value = null
  }
}

async function load() {
  error.value = ''
  try {
    activity.value = await get(`/activities/${props.activityId}`)
    stats.value = await get(`/activities/${props.activityId}/stats`)
    await loadMine()
  } catch (err) {
    error.value = err.message
  }
}

async function register() {
  busy.value = true
  error.value = ''
  try {
    const res = await post(`/activities/${props.activityId}/registrations`)
    if (res.status === 'APPROVED') toast('报名成功，已通过')
    else if (res.status === 'PENDING') toast('已提交，等待管理员审核')
    else if (res.status === 'WAITLISTED') toast(`名额已满，已进入候补（第 ${res.waitlist_position} 位）`)
    else toast('已提交')
    await load()
  } catch (err) {
    error.value = err.message
  } finally {
    busy.value = false
  }
}

async function cancelMine() {
  if (!mine.value) return
  busy.value = true
  error.value = ''
  try {
    await post(`/registrations/${mine.value.registration_id}/cancel`)
    toast(mine.value.status === 'WAITLISTED' ? '已取消候补' : '已取消报名')
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
        <div><b>{{ stats?.waitlisted ?? '-' }}</b>候补中</div>
        <div><b>{{ stats?.remaining ?? '-' }}</b>剩余名额</div>
      </div>

      <div v-if="isStudent" class="card" style="margin: 12px 0 0; background: #f8fafc">
        <div class="row">
          <span class="muted">我的报名状态：</span>
          <span v-if="!mine" class="muted">尚未报名</span>
          <template v-else>
            <span :class="['status', mine.status]">{{ STATUS_LABEL[mine.status] || mine.status }}</span>
            <span v-if="mine.status === 'WAITLISTED' && mine.waitlist_position" class="muted">
              候补第 {{ mine.waitlist_position }} 位
            </span>
            <span v-if="mine.status === 'REJECTED' || mine.status === 'CANCELLED'" class="muted">
              可重新报名
            </span>
          </template>
          <span class="grow"></span>
          <button
            v-if="hasActiveRegistration"
            class="btn danger"
            :disabled="busy"
            @click="cancelMine"
          >
            {{ mine.status === 'WAITLISTED' ? '取消候补' : '取消报名' }}
          </button>
        </div>
      </div>

      <div class="row" style="margin-top: 16px">
        <button
          v-if="!hasActiveRegistration"
          class="btn"
          :disabled="busy || (!activity.open && !hasWaitlist)"
          @click="register"
        >
          {{ busy ? '提交中…' : (activity.open ? '报名' : (hasWaitlist ? '加入候补' : '已截止')) }}
        </button>
        <button class="btn plain" @click="go('mine')">我的报名</button>
        <span v-if="isStudent" class="muted">同一活动只能有一条有效报名</span>
      </div>
    </div>
  </div>
</template>
