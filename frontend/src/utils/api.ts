import axios from 'axios'
import { ElMessage } from 'element-plus'

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
    // 401 未登录/过期 → 跳转登录页
    if (error.response?.status === 401 && !error.config?.url?.includes('/auth/')) {
      localStorage.removeItem('tcm_token')
      localStorage.removeItem('tcm_user')
      if (typeof window !== 'undefined' && window.location.hash !== '#/login') {
        window.location.hash = '#/login'
      }
      return Promise.reject(error)
    }
    const msg = error.response?.data?.detail || error.message || '请求失败'
    ElMessage.error(msg)
    return Promise.reject(error)
  }
)

export default api