<template>
  <el-container class="app-container">
    <router-view />
    <ForceChangePassword />
  </el-container>
</template>

<script setup lang="ts">
import { onMounted } from 'vue'
import api from '@/utils/api'
import type { AppConfig } from '@/types'
import ForceChangePassword from '@/views/auth/ForceChangePassword.vue'

// 启动时按系统配置刷新浏览器标签标题与图标（诊所名称 / 诊所 Logo）
// 主题在 auth store 的 login/restore 中按需同步（该接口需登录，此处尚可能未鉴权）
onMounted(async () => {
  try {
    const res = await api.get<AppConfig>('/config', { silent: true })
    document.title = res.clinic_name?.trim() || '中医诊所管理平台'
    if (res.clinic_logo) setFavicon(res.clinic_logo)
  } catch {
    /* 后端不可用或未登录时保持默认标题 */
  }
})

function setFavicon(href: string) {
  let link = document.querySelector<HTMLLinkElement>('link[rel="icon"]')
  if (!link) {
    link = document.createElement('link')
    link.rel = 'icon'
    document.head.appendChild(link)
  }
  link.href = href
}
</script>

<style scoped>
.app-container {
  height: 100vh;
}
</style>