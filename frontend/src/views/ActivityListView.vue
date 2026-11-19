<script setup>
import { onMounted, ref } from 'vue'
import { get } from '../api'
import { go } from '../store'

const items = ref([])
const q = ref('')
const loading = ref(false)
const error = ref('')

async function load() {
  loading.value = true
  error.value = ''
  try {
    const res = await get(`/activities?q=${encodeURIComponent(q.value.trim())}`)
    items.value = res.items
  } catch (err) {
    error.value = err.message
  } finally {
    loading.value = false
  }
}

onMounted(load)
</script>

<template>
  <div>
    <div class="row" style="margin-top: 18px">
      <input
        v-model="q"
        class="grow"
        placeholder="按活动名称筛选…"
        @keyup.enter="load"
        style="min-width: 200px"
      />
      <button class="btn plain" @click="load" :disabled="loading">查询</button>
    </div>

    <div v-if="error" class="alert error">{{ error }}</div>

    <div v-if="loading" class="empty">加载中…</div>
    <div v-else-if="items.length === 0" class="empty">暂无活动</div>

    <div class="grid">
      <div v-for="a in items" :key="a.activity_id" class="card" style="margin: 0">
        <div class="row">
          <span class="tag">{{ a.category }}</span>
          <span :class="['tag', a.policy_type === 'DIRECT' ? 'direct' : 'review']">
            {{ a.policy_type === 'DIRECT' ? '直接报名' : '需审核' }}
          </span>
          <span class="grow"></span>
          <span class="muted">{{ a.remaining }} / {{ a.capacity }} 名额</span>
        </div>
        <h3 style="margin-top: 8px">{{ a.title }}</h3>
        <p class="muted" style="margin: 4px 0">
          {{ a.start_at.replace('T', ' ') }} · {{ a.location }}
        </p>
        <p v-if="a.waitlisted > 0" class="muted" style="margin: 0">
          候补中 {{ a.waitlisted }} 人<template v-if="a.waitlist_capacity > 0">（上限 {{ a.waitlist_capacity }}）</template>
        </p>
        <div class="row" style="margin-top: 10px">
          <button class="btn plain" @click="go('detail', { id: a.activity_id })">查看详情</button>
          <span v-if="!a.open" class="muted">已截止或已满</span>
        </div>
      </div>
    </div>
  </div>
</template>
