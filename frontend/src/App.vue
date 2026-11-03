<template>
  <el-container class="app-container">
    <router-view />
    <ForceChangePassword />
  </el-container>
</template>

<script setup lang="ts">
import { onMounted } from 'vue'
import api from '@/utils/api'
import { applyBranding } from '@/utils/branding'
import type { AppConfig } from '@/types'
import ForceChangePassword from '@/views/auth/ForceChangePassword.vue'

// 启动时按系统配置刷新浏览器标签标题与图标（诊所名称 / 诊所 Logo）
// 主题在 auth store 的 login/restore 中按需同步（该接口需登录，此处尚可能未鉴权）
onMounted(async () => {
  try {
    const res = await api.get<AppConfig>('/config', { silent: true })
    applyBranding(res.clinic_name, res.clinic_logo)
  } catch {
    /* 后端不可用或未登录时保持默认标题 */
  }
})
</script>

<style scoped>
.app-container {
  height: 100vh;
}
</style>