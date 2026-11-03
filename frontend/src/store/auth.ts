import { ref, computed } from 'vue'
import { defineStore } from 'pinia'
import api from '@/utils/api'
import { setLogoutHandler } from './authBus'

interface UserInfo {
  id: number
  username: string
  display_name: string | null
  is_admin: boolean
  role: string
  permissions: string[]
  is_active: boolean
  must_change_password: boolean
}

// 业务域 → 权限点（与后端 permissions.DOMAIN_PERMS 对应，用于 UI 按钮级灰显）
const DOMAIN_READ: Record<string, string> = {
  patients: 'patient:read', visits: 'patient:read', prescriptions: 'prescription:read',
  diagnosis: 'prescription:read', stock: 'stock:read', herbs: 'dict:read',
  acupoints: 'dict:read', 'acupoint-formulas': 'dict:read', knowledge: 'dict:read',
  'book-library': 'dict:read', dictionaries: 'dict:read', stats: 'stats:read',
  backup: 'system:read', system: 'system:read', config: 'system:read',
}
const DOMAIN_WRITE: Record<string, string | null> = {
  patients: 'patient:write', visits: 'patient:write', prescriptions: 'prescription:write',
  diagnosis: 'prescription:write', stock: 'stock:write', herbs: 'dict:write',
  acupoints: 'dict:write', 'acupoint-formulas': 'dict:write', knowledge: 'dict:write',
  'book-library': 'dict:write', dictionaries: 'dict:write', stats: 'stats:read',
  backup: 'system:write', system: 'system:write', config: 'system:write',
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

  // 注册 401 时清理内存登录态的回调（供 api 拦截器调用）
  setLogoutHandler(() => {
    token.value = ''
    user.value = null
  })

  // ── 角色与权限（与后端 app/permissions.py 的权限点同源）──
  // 兼容旧数据：role 缺失时按 is_admin 推导，避免升级后管理员瞬间变只读
  const role = computed<string>(() => {
    const r = user.value?.role
    if (r === 'admin' || r === 'doctor' || r === 'pharmacist' || r === 'viewer' || r === 'custom') return r
    return user.value?.is_admin ? 'admin' : 'viewer'
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
  function setUser(u: any) {
    user.value = u
    localStorage.setItem(USER_KEY, JSON.stringify(u))
  }

  return {
    token, user, isLoggedIn, login, logout, restore, setUser,
    role, isAdmin, roleLabel, can, hasAnyPerm, canWrite, canRead, canManageLibrary, mustChange,
  }
})