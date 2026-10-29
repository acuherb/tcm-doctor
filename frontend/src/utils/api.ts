import axios from 'axios'
import { ElMessage } from 'element-plus'
import { triggerLogout } from '@/store/authBus'

// 生产模式（Electron 打包后 file:// 协议）需要绝对 URL
const isElectronProd = typeof window !== 'undefined' && window.location.protocol === 'file:'

const api = axios.create({
  baseURL: isElectronProd ? 'http://127.0.0.1:8765/api/v1' : '/api/v1',
  timeout: 120000,
  headers: {
    'Content-Type': 'application/json',
  },
})

// 启动时若已有令牌，直接带入请求头
const savedToken = typeof window !== 'undefined' && localStorage.getItem('tcm_token')
if (savedToken) {
  api.defaults.headers.common['Authorization'] = `Bearer ${savedToken}`
}

// 请求拦截：FormData 时移除 Content-Type，让浏览器自动设置 multipart boundary
api.interceptors.request.use((config) => {
  if (config.data instanceof FormData) {
    delete config.headers['Content-Type']
  }
  return config
})

// 响应拦截
api.interceptors.response.use(
  (response) => response.data,
  (error) => {
    const cfg = error.config as any
    const status = error.response?.status
    const isAuthCall = cfg?.url?.includes('/auth/')
    // 401 未登录/过期 → 清理登录态（localStorage + axios 头 + Pinia）并跳转登录页
    if (status === 401 && !isAuthCall) {
      localStorage.removeItem('tcm_token')
      localStorage.removeItem('tcm_user')
      delete api.defaults.headers.common['Authorization']
      // 同步清理 Pinia 内存登录态（通过总线，避免循环依赖）
      triggerLogout()
      if (typeof window !== 'undefined' && window.location.hash !== '#/login') {
        window.location.hash = '#/login'
      }
      return Promise.reject(error)
    }
    // 组件自行处理（config.silent）的错误不再弹全局提示，避免重复报错
    if (!cfg?.silent) {
      const msg = error.response?.data?.detail || error.message || '请求失败'
      ElMessage.error(msg)
    }
    return Promise.reject(error)
  }
)

export default api