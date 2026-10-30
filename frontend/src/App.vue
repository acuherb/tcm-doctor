<template>
  <el-container class="app-container">
    <router-view />
  </el-container>
</template>

<script setup lang="ts">
import { onMounted } from 'vue'
import api from '@/utils/api'

// 启动时按系统配置刷新浏览器标签标题与图标（诊所名称 / 诊所 Logo）
onMounted(async () => {
  try {
    const res = await api.get('/config') as any
    document.title = res.clinic_name?.trim() || '中医诊所管理平台'
    if (res.clinic_logo) setFavicon(res.clinic_logo)
  } catch {
    /* 后端不可用时保持默认标题 */
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