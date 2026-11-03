<template>
  <el-dialog
    :model-value="visible"
    title="请修改初始密码"
    :show-close="false"
    :close-on-click-modal="false"
    :close-on-press-escape="false"
    width="420px"
    align-center
    append-to-body
  >
    <el-alert
      type="warning"
      :closable="false"
      style="margin-bottom:14px"
      title="首次登录需设置新密码"
      description="为保证账号安全，请先修改初始密码后再使用系统。"
    />
    <el-form ref="formRef" :model="form" :rules="rules" label-width="90px">
      <el-form-item label="原密码" prop="oldPassword">
        <el-input v-model="form.oldPassword" type="password" show-password placeholder="请输入当前密码" />
      </el-form-item>
      <el-form-item label="新密码" prop="newPassword">
        <el-input v-model="form.newPassword" type="password" show-password placeholder="至少 6 位" />
      </el-form-item>
      <el-form-item label="确认密码" prop="confirmPassword">
        <el-input v-model="form.confirmPassword" type="password" show-password placeholder="再次输入新密码" />
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button type="primary" :loading="loading" @click="submit">确认修改</el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { ref, reactive, computed } from 'vue'
import { ElMessage, type FormInstance, type FormRules } from 'element-plus'
import api from '@/utils/api'
import { useAuthStore } from '@/store/auth'

const auth = useAuthStore()
// 后端强制改密白名单已放行 /auth/password，故此处可正常调用
const visible = computed(() => !!auth.user && auth.mustChange)

const formRef = ref<FormInstance>()
const loading = ref(false)
const form = reactive({ oldPassword: '', newPassword: '', confirmPassword: '' })

const rules: FormRules = {
  oldPassword: [{ required: true, message: '请输入原密码', trigger: 'blur' }],
  newPassword: [
    { required: true, message: '请输入新密码', trigger: 'blur' },
    { min: 6, message: '新密码至少 6 位', trigger: 'blur' },
  ],
  confirmPassword: [
    { required: true, message: '请再次输入新密码', trigger: 'blur' },
    {
      validator: (_r, v, cb) => {
        if (v !== form.newPassword) cb(new Error('两次输入不一致'))
        else cb()
      },
      trigger: 'blur',
    },
  ],
}

async function submit() {
  if (!formRef.value) return
  await formRef.value.validate(async (valid) => {
    if (!valid) return
    loading.value = true
    try {
      await api.put('/auth/password', {
        old_password: form.oldPassword,
        new_password: form.newPassword,
      })
      // 刷新用户信息（must_change_password 已置否），重载页面以重新拉取被拦截的业务数据
      // 响应拦截器已返回 response.data，直接取用户对象（勿再 .data）
      const me = await api.get('/auth/me')
      auth.setUser(me)
      ElMessage.success('密码已修改')
      window.location.reload()
    } catch {
      /* 错误提示由拦截器处理 */
    } finally {
      loading.value = false
    }
  })
}
</script>
