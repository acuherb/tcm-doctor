<template>
  <div class="login-page">
    <div class="login-card">
      <div class="card-head">
        <div class="logo-badge">
          <img v-if="clinicLogo" :src="clinicLogo" class="logo-img" alt="诊所Logo" />
          <span v-else class="logo-icon">🌿</span>
        </div>
        <h1 class="title">{{ clinicName || '中医诊所管理平台' }}</h1>
        <p class="subtitle">传承岐黄智慧 · 以数字化服务每一位患者</p>
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

      <p class="form-foot">未注册账号？请联系管理员开通</p>
    </div>

    <!-- 装饰圆环 -->
    <div class="deco deco-1"></div>
    <div class="deco deco-2"></div>
    <div class="deco deco-3">❋</div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, type FormInstance, type FormRules } from 'element-plus'
import { User, Lock } from '@element-plus/icons-vue'
import { useAuthStore } from '@/store/auth'
import api from '@/utils/api'

const router = useRouter()
const auth = useAuthStore()

const clinicName = ref('')
const clinicLogo = ref('')

onMounted(async () => {
  try {
    const res = await api.get('/config') as any
    clinicName.value = res.clinic_name?.trim() || ''
    clinicLogo.value = res.clinic_logo || ''
    document.title = clinicName.value || '中医诊所管理平台'
    if (clinicLogo.value) {
      let link = document.querySelector<HTMLLinkElement>('link[rel="icon"]')
      if (!link) {
        link = document.createElement('link')
        link.rel = 'icon'
        document.head.appendChild(link)
      }
      link.href = clinicLogo.value
    }
  } catch {}
})

const formRef = ref<FormInstance>()
const loading = ref(false)
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

</script>

<style scoped lang="scss">
.login-page {
  position: relative;
  width: 100%;
  min-height: 100vh;
  box-sizing: border-box;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 32px 20px;
  overflow: hidden;
  background: linear-gradient(140deg, #241209 0%, #4a2c1a 55%, #6b4423 100%);
}

.login-card {
  position: relative;
  z-index: 2;
  width: 400px;
  max-width: 100%;
  padding: 44px 38px 30px;
  background: #fff;
  border-radius: 20px;
  box-shadow: 0 24px 60px rgba(0, 0, 0, 0.35);

  .card-head {
    text-align: center;
    margin-bottom: 30px;

    .logo-badge {
      width: 64px;
      height: 64px;
      margin: 0 auto 16px;
      display: flex;
      align-items: center;
      justify-content: center;
      border-radius: 18px;
      background: linear-gradient(135deg, #8B4513, #6b3410);
      box-shadow: 0 8px 20px rgba(107, 52, 16, 0.35);

      .logo-icon {
        font-size: 32px;
      }

      .logo-img {
        width: 42px;
        height: 42px;
        object-fit: contain;
        filter: drop-shadow(0 2px 4px rgba(0,0,0,0.2));
      }
    }

    .title {
      margin: 0 0 8px;
      font-size: 21px;
      color: #2C1810;
      font-weight: 700;
      letter-spacing: 1px;
    }

    .subtitle {
      margin: 0;
      font-size: 13px;
      color: #9a8574;
    }
  }

  .submit-btn {
    width: 100%;
    margin-top: 4px;
    height: 46px;
    font-size: 16px;
    letter-spacing: 6px;
    border-radius: 8px;
  }

  .form-foot {
    margin-top: 20px;
    text-align: center;
    font-size: 13px;
    color: #b8a99c;
  }
}

/* 背景装饰圆环 */
.deco {
  position: absolute;
  border-radius: 50%;
  background: radial-gradient(circle at 30% 30%, rgba(212, 165, 116, 0.28), rgba(212, 165, 116, 0.04));
  pointer-events: none;
}
.deco-1 { width: 420px; height: 420px; top: -140px; right: -140px; }
.deco-2 { width: 340px; height: 340px; bottom: -130px; left: -110px; }
.deco-3 {
  width: 200px; height: 200px;
  left: 50%;
  bottom: -70px;
  transform: translateX(-50%);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 90px;
  color: rgba(212, 165, 116, 0.12);
  background: none;
}
</style>