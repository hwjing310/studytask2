<script setup>
import { computed, onMounted, watch } from 'vue'
import { state, go, clearSession, isAdmin } from './store'
import { get } from './api'

import LoginView from './views/LoginView.vue'
import ActivityListView from './views/ActivityListView.vue'
import ActivityDetailView from './views/ActivityDetailView.vue'
import MyRegistrationsView from './views/MyRegistrationsView.vue'
import MessagesView from './views/MessagesView.vue'
import AdminView from './views/AdminView.vue'

const tabs = computed(() => {
  if (isAdmin()) {
    return [
      { key: 'activities', label: '活动' },
      { key: 'messages', label: '消息', badge: state.unread },
      { key: 'admin', label: '管理' },
    ]
  }
  return [
    { key: 'activities', label: '活动' },
    { key: 'mine', label: '我的报名' },
    { key: 'messages', label: '消息', badge: state.unread },
  ]
})

const current = computed(() => state.view.name)
const isLoggedIn = computed(() => Boolean(state.token && state.user))

async function refreshUnread() {
  if (!isLoggedIn.value) return
  try {
    const res = await get('/messages/unread-count')
    state.unread = res.count
  } catch {
    /* 忽略：横幅不阻塞主流程 */
  }
}

async function logout() {
  // 本项目未实现服务端注销，前端清理即可（token 到期自动失效）
  clearSession()
}

onMounted(refreshUnread)
watch(() => state.view.name, refreshUnread)
watch(() => state.token, refreshUnread)

defineExpose({ refreshUnread })
</script>

<template>
  <div v-if="!isLoggedIn">
    <LoginView />
  </div>

  <div v-else>
    <header class="topbar">
      <div class="topbar-inner">
        <span class="brand">CampusEvent</span>
        <span class="muted">{{ state.user?.name }}（{{ isAdmin() ? '管理员' : '学生' }}）</span>
        <nav class="nav">
          <button
            v-for="tab in tabs"
            :key="tab.key"
            :class="{ active: current === tab.key || (tab.key === 'activities' && current === 'detail') }"
            @click="go(tab.key)"
          >
            {{ tab.label }}
            <span v-if="tab.badge" class="badge">{{ tab.badge }}</span>
          </button>
          <button @click="logout">退出</button>
        </nav>
      </div>
    </header>

    <main class="layout">
      <ActivityListView v-if="current === 'activities'" />
      <ActivityDetailView v-else-if="current === 'detail'" :activity-id="state.view.params.id" />
      <MyRegistrationsView v-else-if="current === 'mine' && !isAdmin()" />
      <MessagesView v-else-if="current === 'messages'" @read="refreshUnread" />
      <AdminView v-else-if="current === 'admin'" />
    </main>

    <div
      v-if="state.toast"
      class="layout"
      style="position: fixed; left: 0; right: 0; bottom: 18px; z-index: 50"
    >
      <div :class="['alert', state.toast.type === 'error' ? 'error' : 'ok']" style="margin: 0 auto; max-width: 480px">
        {{ state.toast.message }}
      </div>
    </div>
  </div>
</template>
