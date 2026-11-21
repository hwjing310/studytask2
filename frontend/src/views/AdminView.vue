<script setup>
import { onMounted, ref } from 'vue'
import { get, post, del } from '../api'
import { toast } from '../store'

const activityList = ref([])
const pending = ref([])
const error = ref('')
const selected = ref('')
const stats = ref(null)

const form = ref({
  title: '',
  category: '体育',
  start_at: '2026-12-20T14:00',
  location: '',
  capacity: 30,
  waitlist_capacity: 0,
  policy_type: 'DIRECT',
})

async function loadAll() {
  error.value = ''
  try {
    const [acts, pend] = await Promise.all([get('/activities'), get('/registrations/pending')])
    activityList.value = acts.items
    pending.value = pend.items
    if (!selected.value && acts.items.length) selected.value = acts.items[0].activity_id
    await loadStats()
  } catch (err) {
    error.value = err.message
  }
}

async function loadStats() {
  if (!selected.value) {
    stats.value = null
    return
  }
  try {
    stats.value = await get(`/activities/${selected.value}/stats`)
  } catch (err) {
    error.value = err.message
  }
}

async function createActivity() {
  error.value = ''
  try {
    const payload = { ...form.value, capacity: Number(form.value.capacity), waitlist_capacity: Number(form.value.waitlist_capacity) }
    const created = await post('/activities', payload)
    toast(`已创建：${created.title}`)
    form.value.title = ''
    form.value.location = ''
    await loadAll()
  } catch (err) {
    error.value = err.message
  }
}

async function approve(item) {
  try {
    await post(`/registrations/${item.registration_id}/approve`)
    toast('已批准')
    await loadAll()
  } catch (err) {
    error.value = err.message
  }
}

async function reject(item) {
  try {
    await post(`/registrations/${item.registration_id}/reject`)
    toast('已拒绝')
    await loadAll()
  } catch (err) {
    error.value = err.message
  }
}

async function waitlist(item) {
  try {
    const res = await post(`/registrations/${item.registration_id}/waitlist`)
    toast(`已转为候补（第 ${res.waitlist_position} 位）`)
    await loadAll()
  } catch (err) {
    error.value = err.message
  }
}

async function removeActivity(a) {
  if (!window.confirm(`确定下架「${a.title}」？（软删除，历史报名保留）`)) return
  try {
    await del(`/activities/${a.activity_id}`)
    toast('已下架')
    await loadAll()
  } catch (err) {
    error.value = err.message
  }
}

onMounted(loadAll)
</script>

<template>
  <div>
    <div v-if="error" class="alert error">{{ error }}</div>

    <div class="card">
      <h3>创建活动</h3>
      <div class="row" style="margin-top: 10px">
        <div class="grow" style="min-width: 200px">
          <label>名称</label>
          <input v-model="form.title" placeholder="例如：人工智能讲座" style="width: 100%" />
        </div>
        <div style="width: 130px">
          <label>类型</label>
          <input v-model="form.category" style="width: 100%" />
        </div>
        <div style="width: 210px">
          <label>开始时间</label>
          <input v-model="form.start_at" type="datetime-local" style="width: 100%" />
        </div>
      </div>
      <div class="row" style="margin-top: 10px">
        <div class="grow" style="min-width: 180px">
          <label>地点</label>
          <input v-model="form.location" placeholder="例如：报告厅" style="width: 100%" />
        </div>
        <div style="width: 120px">
          <label>人数上限</label>
          <input v-model="form.capacity" type="number" min="1" style="width: 100%" />
        </div>
        <div style="width: 120px">
          <label>候补上限</label>
          <input v-model="form.waitlist_capacity" type="number" min="0" style="width: 100%" />
        </div>
        <div style="width: 160px">
          <label>报名方式</label>
          <select v-model="form.policy_type" style="width: 100%">
            <option value="DIRECT">直接报名</option>
            <option value="REVIEW">审核型</option>
          </select>
        </div>
        <div style="align-self: flex-end">
          <button class="btn" @click="createActivity">创建</button>
        </div>
      </div>
    </div>

    <div class="card">
      <h3>待审核申请（{{ pending.length }}）</h3>
      <div v-if="pending.length === 0" class="empty">没有待审核的申请</div>
      <div v-for="p in pending" :key="p.registration_id" class="row" style="border-top: 1px solid var(--line); padding: 10px 0">
        <span><strong>{{ p.student_name }}</strong> 申请「{{ p.activity_title }}」</span>
        <span class="grow"></span>
        <span class="muted">{{ p.created_at.replace('T', ' ') }}</span>
        <button class="btn" @click="approve(p)">批准</button>
        <button class="btn plain" @click="waitlist(p)">转候补</button>
        <button class="btn danger" @click="reject(p)">拒绝</button>
      </div>
    </div>

    <div class="card">
      <h3>活动统计</h3>
      <div class="row" style="margin-top: 8px">
        <select v-model="selected" @change="loadStats" style="min-width: 260px">
          <option v-for="a in activityList" :key="a.activity_id" :value="a.activity_id">
            {{ a.title }}
          </option>
        </select>
        <button class="btn plain" @click="loadStats">刷新</button>
      </div>
      <div v-if="stats" class="stat">
        <div><b>{{ stats.approved }}</b>已通过</div>
        <div><b>{{ stats.pending }}</b>待审核</div>
        <div><b>{{ stats.waitlisted }}</b>候补中</div>
        <div><b>{{ stats.remaining }}</b>剩余名额</div>
        <div><b>{{ stats.capacity }}</b>总容量</div>
      </div>
    </div>

    <div class="card">
      <h3>活动管理</h3>
      <div v-for="a in activityList" :key="a.activity_id" class="row" style="border-top: 1px solid var(--line); padding: 10px 0">
        <span>{{ a.title }}</span>
        <span class="tag">{{ a.category }}</span>
        <span class="tag" :class="a.policy_type === 'DIRECT' ? 'direct' : 'review'">
          {{ a.policy_type === 'DIRECT' ? '直接' : '审核' }}
        </span>
        <span class="grow"></span>
        <span class="muted">{{ a.remaining }}/{{ a.capacity }}<template v-if="a.waitlisted > 0"> · 候补 {{ a.waitlisted }}</template></span>
        <button class="btn danger" @click="removeActivity(a)">下架</button>
      </div>
    </div>
  </div>
</template>
