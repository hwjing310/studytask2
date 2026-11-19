<script setup>
import { onMounted, ref } from 'vue'
import { get, post } from '../api'

const emit = defineEmits(['read'])

const items = ref([])
const loading = ref(false)
const error = ref('')

async function load() {
  loading.value = true
  error.value = ''
  try {
    const res = await get('/messages')
    items.value = res.items
  } catch (err) {
    error.value = err.message
  } finally {
    loading.value = false
  }
}

async function markRead(item) {
  if (item.is_read) return
  try {
    await post(`/messages/${item.message_id}/read`)
    item.is_read = true
    emit('read')
  } catch (err) {
    error.value = err.message
  }
}

onMounted(load)
</script>

<template>
  <div>
    <div class="row" style="margin-top: 18px">
      <h3 style="margin: 0">站内消息</h3>
      <span class="grow"></span>
      <button class="btn plain" @click="load" :disabled="loading">刷新</button>
    </div>

    <div v-if="error" class="alert error">{{ error }}</div>
    <div v-if="loading" class="empty">加载中…</div>
    <div v-else-if="items.length === 0" class="empty">暂无消息</div>

    <div v-for="m in items" :key="m.message_id" class="card" :style="m.is_read ? '' : 'border-left: 4px solid #2563eb'">
      <div class="row">
        <span v-if="!m.is_read" class="tag">未读</span>
        <span class="grow">{{ m.content }}</span>
        <button v-if="!m.is_read" class="btn plain" @click="markRead(m)">标记已读</button>
      </div>
      <p class="muted" style="margin: 6px 0 0">{{ m.created_at.replace('T', ' ') }}</p>
    </div>
  </div>
</template>
