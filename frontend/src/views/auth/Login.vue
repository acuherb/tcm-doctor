<template>
  <div class="login-page">
    <div class="login-card">
      <div class="brand">
        <span class="logo-icon">🌿</span>
        <h1 class="title">中医诊所管理平台</h1>
        <p class="subtitle">中医诊所问诊管理平台</p>
      </div>

      <el-form
        ref="formRef"
        :model="form"
        :rules="rules"
        label-position="top"
        @keyup.enter="onSubmit"
      >
        <el-form-item prop="username">
          <el-input
            v-model="form.username"
            placeholder="用户名"
            size="large"
            :prefix-icon="User"
            clearable
          />
        </el-form-item>
        <el-form-item prop="password">
          <el-input
            v-model="form.password"
            type="password"
            placeholder="密码"
            size="large"
            :prefix-icon="Lock"
            show-password
          />
        </el-form-item>
        <el-button
          type="primary"
          size="large"
          class="submit-btn"
          :loading="loading"
          @click="onSubmit"
        >
          登 录
        </el-button>
      </el-form>

      <div class="guest-row">
        <el-button
          size="default"
          class="guest-btn"
          plain
          :loading="guestLoading"
          @click="onGuestLogin"
        >
          游客登录（仅可浏览）
        </el-button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, type FormInstance, type FormRules } from 'element-plus'
import { User, Lock } from '@element-plus/icons-vue'
import { useAuthStore } from '@/store/auth'

const router = useRouter()
const auth = useAuthStore()

const formRef = ref<FormInstance>()
const loading = ref(false)
const guestLoading = ref(false)
const form = reactive({ username: '', password: '' })

const rules: FormRules = {
  username: [{ required: true, message: '请输入用户名', trigger: 'blur' }],
  password: [{ required: true, message: '请输入密码', trigger: 'blur' }],
}

async function doLogin(username: string, password: string) {
  await auth.login(username, password)
  ElMessage.success('登录成功')
  router.replace('/dashboard')
}

async function onSubmit() {
  if (!formRef.value) return
  await formRef.value.validate(async (valid) => {
    if (!valid) return
    if (loading.value) return
    loading.value = true
    try {
      await doLogin(form.username, form.password)
    } catch {
      /* 错误提示由拦截器处理 */
    } finally {
      loading.value = false
    }
  })
}

async function onGuestLogin() {
  if (guestLoading.value) return
  guestLoading.value = true
  try {
    await auth.guestLogin()
    ElMessage.info('已进入游客模式，仅可浏览')
    router.replace('/dashboard')
  } catch {
    /* 错误提示由拦截器处理 */
  } finally {
    guestLoading.value = false
  }
}
</script>

<style scoped lang="scss">
.login-page {
  height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, #2C1810 0%, #4a2c1a 60%, #6b4423 100%);
}

.login-card {
  width: 380px;
  padding: 40px 36px 28px;
  background: #fff;
  border-radius: 12px;
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.35);

  .brand {
    text-align: center;
    margin-bottom: 28px;

    .logo-icon {
      font-size: 44px;
    }
    .title {
      margin: 12px 0 6px;
      font-size: 22px;
      color: #2C1810;
      font-weight: 700;
    }
    .subtitle {
      margin: 0;
      font-size: 13px;
      color: #9a8574;
    }
  }

  .submit-btn {
    width: 100%;
    margin-top: 6px;
    background: #2C1810;
    border-color: #2C1810;

    &:hover {
      background: #4a2c1a;
      border-color: #4a2c1a;
    }
  }

  .guest-row {
    margin-top: 14px;

    .guest-btn {
      width: 100%;
      color: #4a2c1a;
      border-color: #d4c3b3;

      &:hover {
        border-color: #2C1810;
        color: #2C1810;
        background: #f5f0eb;
      }
    }
  }
}
</style>