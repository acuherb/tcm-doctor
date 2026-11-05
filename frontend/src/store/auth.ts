import { ref, computed } from 'vue'
import { defineStore } from 'pinia'
import api from '@/utils/api'
import { setLogoutHandler } from './authBus'
import type { AuthLoginResult, AppConfig, TcmUser } from '@/types'
import { applyTheme, isThemeKey } from '@/utils/theme'

// 登录态就绪后同步服务端界面风格（多终端统一）；失败静默，沿用本地已应用主题
async function syncTheme() {
  try {
    // 用户主动切过的主题优先，避免每次登录/刷新被服务端默认风格覆盖；
    // 未登录时该端点同样可读（仅品牌字段），普通账号不会再拿到 403。
    if (localStorage.getItem('tcm-theme')) return
    const res = await api.get<AppConfig>('/config/public', { silent: true })
    if (res.ui_theme && isThemeKey(res.ui_theme)) applyTheme(res.ui_theme, false)
  } catch {
    /* 后端不可用时沿用本地主题 */
  }
}

// 业务域 → 权限点（与后端 permissions.DOMAIN_PERMS 对应，用于 UI 按钮级灰显）
const DOMAIN_READ: Record<string, string> = {
  patients: 'patient:read', visits: 'patient:read', prescriptions: 'prescription:read',
  diagnosis: 'prescription:read', stock: 'stock:read', herbs: 'dict:read',
  acupoints: 'dict:read', 'acupoint-formulas': 'dict:read', knowledge: 'dict:read',
  'book-library': 'dict:read', dictionaries: 'dict:read', stats: 'stats:read',
  backup: 'system:read', system: 'system:read', config: 'system:read',
  billing: 'billing:read',
}
const DOMAIN_WRITE: Record<string, string | null> = {
  patients: 'patient:write', visits: 'patient:write', prescriptions: 'prescription:write',
  diagnosis: 'prescription:write', stock: 'stock:write', herbs: 'dict:write',
  acupoints: 'dict:write', 'acupoint-formulas': 'dict:write', knowledge: 'dict:write',
  'book-library': 'dict:write', dictionaries: 'dict:write', stats: 'stats:read',
  backup: 'system:write', system: 'system:write', config: 'system:write',
  billing: 'billing:write',
}

const USER_KEY = 'tcm_user'

function readStoredUser(): TcmUser | null {
  try {
    const raw = localStorage.getItem(USER_KEY)
    return raw ? (JSON.parse(raw) as TcmUser) : null
  } catch {
    // localStorage 被手工篡改/截断时不能让整个应用白屏
    localStorage.removeItem(USER_KEY)
    return null
  }
}

export const useAuthStore = defineStore('auth', () => {
  // 会话凭证双轨：内存令牌（登录时 authorize 写入，供 axios 自动加 Bearer 头）+ 后端下发的 httpOnly + SameSite=Lax 会话 Cookie（刷新后由浏览器自动携带，XSS 无法读取）。
  // 二者任一有效即可通过后端鉴权。非凭证的用户快照仍缓存于 localStorage，仅为刷新后即时恢复 UI 状态，并非会话凭证本身。
  const token = ref<string>('')
  const user = ref<TcmUser | null>(readStoredUser())

  // 登录态以「已校验的用户快照」为准：localStorage 中的 user 在刷新后被重新加载，
  // 且 restore() 会用 Cookie/内存令牌调用 /auth/me 校验其有效性，无效则清空。
  const isLoggedIn = computed(() => !!user.value)

  // 登录成功后：授权 axios + 持久化
  function authorize(t: string) {
    token.value = t
    api.defaults.headers.common['Authorization'] = `Bearer ${t}`
  }

  async function login(username: string, password: string) {
    const res = await api.post<AuthLoginResult>('/auth/login', { username, password })
    authorize(res.token)
    user.value = res.user
    localStorage.setItem(USER_KEY, JSON.stringify(res.user))
    await syncTheme()
    return res.user
  }

  // 页面刷新后恢复登录态（校验 token 是否仍有效）
  async function restore() {
    // 内存仍有令牌：直接续期
    if (token.value) {
      try {
        const me = await api.get<TcmUser>('/auth/me')
        user.value = me
        localStorage.setItem(USER_KEY, JSON.stringify(me))
        await syncTheme()
        return true
      } catch {
        logout()
        return false
      }
    }
    // 内存无令牌：尝试用后端下发的 httpOnly Cookie（同域）静默恢复会话，前端无需持有令牌
    try {
      const me = await api.get<TcmUser>('/auth/me')
      user.value = me
      localStorage.setItem(USER_KEY, JSON.stringify(me))
      await syncTheme()
      return true
    } catch {
      // Cookie/内存均无有效会话：清理可能残留的本地用户快照，避免 UI 误判为已登录
      user.value = null
      localStorage.removeItem(USER_KEY)
      token.value = ''
      delete api.defaults.headers.common['Authorization']
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
    localStorage.removeItem(USER_KEY)
    delete api.defaults.headers.common['Authorization']
  }

  // 注册 401 时清理内存登录态的回调（供 api 拦截器调用）
  setLogoutHandler(() => {
    token.value = ''
    user.value = null
  })

  // ── 角色与权限（与后端 app/permissions.py 的权限点同源）──
  // is_admin 为超级用户，优先于 role 字段（避免 seed 未显式设 role 时落到默认 'viewer' 导致管理员变只读）
  const role = computed<string>(() => {
    if (user.value?.is_admin) return 'admin'
    const r = user.value?.role
    if (r === 'admin' || r === 'doctor' || r === 'pharmacist' || r === 'viewer' || r === 'custom') return r
    return 'viewer'
  })

  const isAdmin = computed(() => role.value === 'admin')

  // 是否拥有某权限点（管理员视为拥有全部权限点）
  function can(perm: string): boolean {
    if (isAdmin.value) return true
    const perms = user.value?.permissions
    return Array.isArray(perms) && perms.includes(perm)
  }

  function hasAnyPerm(perms: string[]): boolean {
    return perms.some((p) => can(p))
  }

  // 当前账号是否可写某业务域（传 'patients' / 'stock' 等前缀，不带 /api/v1）
  function canWrite(domain: string): boolean {
    const p = DOMAIN_WRITE[domain]
    return p ? can(p) : false
  }

  // 当前账号是否可读某业务域（与后端一致：未登记域默认可读）
  function canRead(domain: string): boolean {
    const p = DOMAIN_READ[domain]
    return p ? can(p) : true
  }

  // 医籍文库 / 穴位公式库等基础资料维护：需 dict:write
  function canManageLibrary(): boolean {
    return can('dict:write')
  }

  const roleLabel = computed(() => {
    const map: Record<string, string> = {
      admin: '管理员', doctor: '医生', pharmacist: '药房', viewer: '只读', custom: '自定义',
    }
    return map[role.value] || role.value
  })

  // 是否需要强制修改初始密码（后端改密接口已在白名单内，故可正常调用）
  const mustChange = computed(() => !!user.value?.must_change_password)

  // 改密成功后刷新用户（must_change_password 置否，权限不变）
  function setUser(u: unknown) {
    user.value = u as TcmUser
    localStorage.setItem(USER_KEY, JSON.stringify(u))
  }

  return {
    token, user, isLoggedIn, login, logout, restore, setUser,
    role, isAdmin, roleLabel, can, hasAnyPerm, canWrite, canRead, canManageLibrary, mustChange,
  }
})