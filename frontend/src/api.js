import { clearSession, state } from './store'

/**
 * 统一请求封装：自动带 Bearer Token、统一解析错误体 { error: { code, message } }。
 */
export async function api(path, { method = 'GET', body } = {}) {
  const headers = { Accept: 'application/json' }
  if (body !== undefined) headers['Content-Type'] = 'application/json; charset=utf-8'
  if (state.token) headers.Authorization = `Bearer ${state.token}`

  const resp = await fetch(`/api${path}`, {
    method,
    headers,
    body: body === undefined ? undefined : JSON.stringify(body),
  })

  let payload = null
  const text = await resp.text()
  if (text) {
    try {
      payload = JSON.parse(text)
    } catch {
      payload = { error: { code: 'BAD_RESPONSE', message: text } }
    }
  }

  if (!resp.ok) {
    if (resp.status === 401 && state.token) {
      clearSession()
    }
    const err = new Error(payload?.error?.message || `请求失败（${resp.status}）`)
    err.code = payload?.error?.code || `HTTP_${resp.status}`
    err.status = resp.status
    throw err
  }
  return payload
}

export const get = (path) => api(path)
export const post = (path, body = {}) => api(path, { method: 'POST', body })
export const del = (path) => api(path, { method: 'DELETE' })
