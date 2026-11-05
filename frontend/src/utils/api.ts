import axios from 'axios'
import type { AxiosInstance, AxiosRequestConfig } from 'axios'
import { ElMessage } from 'element-plus'
import { triggerLogout } from '@/store/authBus'
import type { ApiResponse, Paginated } from '@/types'

export type { ApiResponse, Paginated }

// 从 unknown 错误里提取可读信息（替代 catch (e: any) 内的 e?.response?.data?.detail 写法）
export function errMsg(e: unknown): string {
  if (e && typeof e === 'object') {
    const o = e as Record<string, unknown>
    const resp = o.response as Record<string, unknown> | undefined
    const data = resp?.data as Record<string, unknown> | undefined
    if (typeof data?.detail === 'string') return data.detail
    if (typeof data?.message === 'string') return data.message
    if (typeof o.message === 'string') return o.message
  }
  if (typeof e === 'string') return e
  return '操作失败'
}

// 扩展 axios 请求配置，支持本 api 层自定义的 silent 选项（静默错误、不弹全局提示）。
// 此前未在类型中声明，导致所有传 { silent: true } 的调用均报 TS2353；类型检查门禁恢复后才暴露。
declare module 'axios' {
  export interface AxiosRequestConfig {
    silent?: boolean
  }
}

// 生产模式（Electron 打包后 file:// 协议）需要绝对 URL
const isElectronProd = typeof window !== 'undefined' && window.location.protocol === 'file:'

const api = axios.create({
  baseURL: isElectronProd ? 'http://127.0.0.1:8765/api/v1' : '/api/v1',
  timeout: 120000,
  headers: {
    'Content-Type': 'application/json',
  },
})

// 会话凭证：内存令牌（authorize 时写入，供 axios 自动加 Bearer 头）+ 后端下发的 httpOnly 会话 Cookie（刷新后由浏览器自动携带）。
// 二者任一有效即可通过后端鉴权；前端不再从 localStorage 预设令牌。

// 请求拦截：FormData 时移除 Content-Type，让浏览器自动设置 multipart boundary
api.interceptors.request.use((config) => {
  if (config.data instanceof FormData) {
    delete config.headers['Content-Type']
  }
  return config
})

// 同一错误在全局拦截器与组件 catch 中重复弹出时做短窗口去重，避免一次失败弹两条提示
let lastErrorToast = { msg: '', at: 0 }
function showErrorToast(msg: string) {
  const now = Date.now()
  if (msg === lastErrorToast.msg && now - lastErrorToast.at < 800) return
  lastErrorToast = { msg, at: now }
  ElMessage.error(msg)
}

// 响应拦截
api.interceptors.response.use(
  (response) => response.data,
  (error) => {
    const cfg = error.config
    const status = error.response?.status
    const isPublicCall = cfg?.url?.includes('/auth/') || cfg?.url?.includes('/config/public')
    // 401 未登录/过期 → 清理登录态（localStorage + axios 头 + Pinia）并跳转登录页
    if (status === 401 && !isPublicCall) {
      localStorage.removeItem('tcm_user')
      delete api.defaults.headers.common['Authorization']
      // 同步清理 Pinia 内存登录态（通过总线，避免循环依赖）
      triggerLogout()
      if (typeof window !== 'undefined' && window.location.hash !== '#/login') {
        window.location.hash = '#/login'
      }
      return Promise.reject(error)
    }
    // 409 乐观锁冲突：并发编辑同一记录，对方已先提交。明确提示刷新，避免误以为失败。
    if (status === 409) {
      const msg = error.response?.data?.detail || '数据已被他人修改，请刷新页面后重试'
      if (!cfg?.silent) ElMessage.warning(msg)
      return Promise.reject(error)
    }
    // 组件自行处理（config.silent）的错误不再弹全局提示，避免重复报错
    if (!cfg?.silent) {
      const msg = error.response?.data?.detail || error.message || '请求失败'
      // 强制改密期间，被拦截的请求由全局改密弹窗接管，不再弹「请先修改初始密码」提示
      if (msg.includes('修改初始密码')) {
        return Promise.reject(error)
      }
      showErrorToast(msg)
    }
    return Promise.reject(error)
  }
)

// 响应拦截器已把 axios 的 response 解包为 response.data（即后端返回体本身），
// 因此运行时 api.get/post/... 的返回值就是后端数据，而非 AxiosResponse。
// 这里把导出类型校正为「返回 Promise<T>」，使类型与运行时一致；
// 此前类型停留在 AxiosResponse，导致大量调用处出现「属性在 AxiosResponse 上不存在」的误报。
type HttpMethod = <T = any>(url: string, config?: AxiosRequestConfig) => Promise<T>
interface HttpClient {
  get: HttpMethod
  delete: HttpMethod
  head: HttpMethod
  options: HttpMethod
  post: <T = any>(url: string, data?: unknown, config?: AxiosRequestConfig) => Promise<T>
  put: <T = any>(url: string, data?: unknown, config?: AxiosRequestConfig) => Promise<T>
  patch: <T = any>(url: string, data?: unknown, config?: AxiosRequestConfig) => Promise<T>
  request: <T = any>(config: AxiosRequestConfig) => Promise<T>
  defaults: AxiosInstance['defaults']
  interceptors: AxiosInstance['interceptors']
}
const http = api as unknown as HttpClient
export default http