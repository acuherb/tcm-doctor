import { createApp } from 'vue'
import { createPinia } from 'pinia'
import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'
import zhCn from 'element-plus/es/locale/lang/zh-cn'
import * as ElementPlusIconsVue from '@element-plus/icons-vue'

import App from './App.vue'
import router from './router'
import { useAuthStore } from './store/auth'

import './styles/tcm-theme.scss'
import { initTheme } from './utils/theme'
import { ElMessage } from 'element-plus'

// 主题必须在挂载前应用，避免首屏闪回默认配色
initTheme()

const app = createApp(App)

// 全局错误兜底：打到控制台；并延迟+去重地弹一次提示。
// 注意：绝不能在 errorHandler 内「同步」弹窗，否则渲染错误→弹窗→再渲染错误会形成
// 无限反馈回路，导致浏览器卡死、控制台刷屏。故用 setTimeout 脱离当前渲染周期 + 去重。
const errReported = new Set<string>()
app.config.errorHandler = (err, _instance, info) => {
  const msg = err instanceof Error ? err.message : String(err)
  console.error('[app error]', info, err)
  const key = (info || '') + '|' + msg
  if (!errReported.has(key) && errReported.size < 5) {
    errReported.add(key)
    setTimeout(() => {
      try { ElMessage.error('页面出错：' + msg) } catch { /* 忽略弹窗自身异常 */ }
    }, 0)
  }
}

// 注册所有 Element Plus 图标
for (const [key, component] of Object.entries(ElementPlusIconsVue)) {
  app.component(key, component)
}

const pinia = createPinia()
app.use(pinia)
app.use(router)
app.use(ElementPlus, { locale: zhCn })

// 刷新后用 /auth/me 校验 token 有效性，过期则清理登录态再进入；校验完成后再挂载
useAuthStore().restore().finally(() => {
  app.mount('#app')
})