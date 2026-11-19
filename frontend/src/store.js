import { reactive } from 'vue'

const TOKEN_KEY = 'ce_token'
const USER_KEY = 'ce_user'

export const state = reactive({
  token: localStorage.getItem(TOKEN_KEY) || '',
  user: JSON.parse(localStorage.getItem(USER_KEY) || 'null'),
  view: { name: 'activities', params: {} },
  unread: 0,
  toast: null,
})

export function setSession(token, user) {
  state.token = token
  state.user = user
  localStorage.setItem(TOKEN_KEY, token)
  localStorage.setItem(USER_KEY, JSON.stringify(user))
}

export function clearSession() {
  state.token = ''
  state.user = null
  localStorage.removeItem(TOKEN_KEY)
  localStorage.removeItem(USER_KEY)
  state.unread = 0
  go('activities')
}

export function go(name, params = {}) {
  state.view = { name, params }
  window.scrollTo({ top: 0 })
}

export function toast(message, type = 'ok') {
  state.toast = { message, type }
  setTimeout(() => {
    if (state.toast && state.toast.message === message) state.toast = null
  }, 2600)
}

export function isAdmin() {
  return state.user?.role === 'ADMIN'
}
