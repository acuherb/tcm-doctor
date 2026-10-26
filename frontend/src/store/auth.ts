import { ref, computed } from 'vue'
import { defineStore } from 'pinia'
import api from '@/utils/api'

interface UserInfo {
  id: number
  username: string
  display_name: string | null
  is_admin: boolean
}

const TOKEN_KEY = 'tcm_token'
const USER_KEY = 'tcm_user'

export const useAuthStore = defineStore('auth', () => {
  const token = ref<string>(localStorage.getItem(TOKEN_KEY) || '')
  const user = ref<UserInfo | null>(
    JSON.parse(localStorage.getItem(USER_KEY) || 'null')
  )

  const isLoggedIn = computed(() => !!token.value)

  // 登录成功后：授权 axios + 持久化
  function authorize(t: string) {
    token.value = t
    localStorage.setItem(TOKEN_KEY, t)
    api.defaults.headers.common['Authorization'] = `Bearer ${t}`
  }

  async function login(username: string, password: string) {
    const res = (await api.post('/auth/login', { username, password })) as any
    authorize(res.token)
    user.value = res.user
    localStorage.setItem(USER_KEY, JSON.stringify(res.user))
    return res.user
  }

  // 游客一键登录：免密码进入只读浏览
  async function guestLogin() {
    const res = (await api.post('/auth/guest')) as any
    authorize(res.token)
    user.value = res.user
    localStorage.setItem(USER_KEY, JSON.stringify(res.user))
    return res.user
  }

  // 页面刷新后恢复登录态（校验 token 是否仍有效）
  async function restore() {
    if (!token.value) return false
    authorize(token.value)
    try {
      const me = (await api.get('/auth/me')) as any
      user.value = me
      localStorage.setItem(USER_KEY, JSON.stringify(me))
      return true
    } catch {
      logout()
      return false
    }
  }

  async function logout() {
    try {
      await api.post('/auth/logout')
    } catch {
      /* 忽略登出网络错误 */
    }
    token.value = ''
    user.value = null
    localStorage.removeItem(TOKEN_KEY)
    localStorage.removeItem(USER_KEY)
    delete api.defaults.headers.common['Authorization']
  }

  return { token, user, isLoggedIn, login, guestLogin, logout, restore }
})