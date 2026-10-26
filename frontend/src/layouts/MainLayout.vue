<template>
  <el-container class="main-layout">
    <!-- 侧边栏 -->
    <el-aside :width="isCollapsed ? '64px' : '210px'" class="sidebar">
      <div class="sidebar-logo" @click="$router.push('/dashboard')">
        <span class="logo-icon">🌿</span>
        <span v-show="!isCollapsed" class="logo-text">中医诊所管理</span>
      </div>

      <el-menu
        :default-active="currentRoute"
        :collapse="isCollapsed"
        :collapse-transition="false"
        background-color="#2C1810"
        text-color="#E8D5C4"
        active-text-color="#D4A574"
        router
      >
        <el-menu-item index="/dashboard">
          <el-icon><HomeFilled /></el-icon>
          <template #title>工作台</template>
        </el-menu-item>
        <el-menu-item index="/statistics">
          <el-icon><DataAnalysis /></el-icon>
          <template #title>统计报表</template>
        </el-menu-item>

        <el-sub-menu index="patient-group">
          <template #title>
            <el-icon><User /></el-icon>
            <span>病号管理</span>
          </template>
          <el-menu-item index="/patients">患者列表</el-menu-item>
        </el-sub-menu>

        <el-sub-menu index="herb-group">
          <template #title>
            <el-icon><FirstAidKit /></el-icon>
            <span>药品管理</span>
          </template>
          <el-menu-item index="/herbs">药材字典</el-menu-item>
          <el-menu-item index="/herbs/inventory">库存管理</el-menu-item>
          <el-menu-item index="/acupoints">针灸穴位</el-menu-item>
        </el-sub-menu>

        <el-sub-menu index="prescription-group">
          <template #title>
            <el-icon><Document /></el-icon>
            <span>处方管理</span>
          </template>
          <el-menu-item index="/prescriptions">处方列表</el-menu-item>
          <el-menu-item index="/classic-formulas">经典方库</el-menu-item>
          <el-menu-item index="/acupoint-formulas">针灸方库</el-menu-item>
        </el-sub-menu>

        <el-menu-item index="/knowledge">
          <el-icon><Search /></el-icon>
          <template #title>知识检索</template>
        </el-menu-item>

        <el-menu-item index="/book-library">
          <el-icon><Reading /></el-icon>
          <template #title>医籍文库</template>
        </el-menu-item>

        <el-menu-item index="/diagnosis">
          <el-icon><ChatDotRound /></el-icon>
          <template #title>智能问诊</template>
        </el-menu-item>

        <el-menu-item index="/dictionaries">
          <el-icon><Coin /></el-icon>
          <template #title>主数据字典</template>
        </el-menu-item>

        <el-menu-item index="/settings">
          <el-icon><Setting /></el-icon>
          <template #title>系统设置</template>
        </el-menu-item>
      </el-menu>

      <div class="sidebar-toggle" @click="isCollapsed = !isCollapsed">
        <el-icon :size="16">
          <Fold v-if="!isCollapsed" />
          <Expand v-else />
        </el-icon>
      </div>
    </el-aside>

    <!-- 主内容区 -->
    <el-container class="main-container">
      <el-header class="main-header">
        <div class="header-left">
          <el-breadcrumb separator="/">
            <el-breadcrumb-item :to="{ path: '/dashboard' }">首页</el-breadcrumb-item>
            <el-breadcrumb-item v-if="currentPageTitle">{{ currentPageTitle }}</el-breadcrumb-item>
          </el-breadcrumb>
        </div>
        <div class="header-right">
          <el-tag type="info" size="small">v0.1.0</el-tag>
          <el-dropdown @command="onUserCommand">
            <span class="user-box">
              <el-icon><UserFilled /></el-icon>
              <span class="user-name">{{ auth.user?.display_name || auth.user?.username || '未登录' }}</span>
              <el-icon><ArrowDown /></el-icon>
            </span>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item disabled>{{ auth.user?.display_name || auth.user?.username }}</el-dropdown-item>
                <el-dropdown-item command="profile">个人中心</el-dropdown-item>
                <el-dropdown-item command="logout" divided>退出登录</el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </div>
      </el-header>

      <el-main class="main-content">
        <router-view />
      </el-main>
    </el-container>

    <!-- 个人中心：账号信息 + 修改密码 -->
    <el-dialog v-model="profileVisible" title="个人中心" width="440px" append-to-body>
      <el-descriptions :column="1" border class="profile-desc">
        <el-descriptions-item label="用户名">{{ auth.user?.username }}</el-descriptions-item>
        <el-descriptions-item label="显示名称">{{ auth.user?.display_name || '—' }}</el-descriptions-item>
        <el-descriptions-item label="角色">{{ auth.user?.is_admin ? '管理员' : '普通用户' }}</el-descriptions-item>
      </el-descriptions>

      <el-divider content-position="left">修改密码</el-divider>
      <el-form ref="pwdFormRef" :model="pwdForm" :rules="pwdRules" label-width="90px">
        <el-form-item label="原密码" prop="oldPassword">
          <el-input v-model="pwdForm.oldPassword" type="password" show-password placeholder="请输入原密码" />
        </el-form-item>
        <el-form-item label="新密码" prop="newPassword">
          <el-input v-model="pwdForm.newPassword" type="password" show-password placeholder="至少 6 位" />
        </el-form-item>
        <el-form-item label="确认密码" prop="confirmPassword">
          <el-input v-model="pwdForm.confirmPassword" type="password" show-password placeholder="再次输入新密码" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="profileVisible = false">取 消</el-button>
        <el-button type="primary" :loading="pwdLoading" @click="onChangePassword">保存</el-button>
      </template>
    </el-dialog>
  </el-container>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  HomeFilled, User, FirstAidKit, Document, Search,
  ChatDotRound, Setting, Fold, Expand, TrendCharts, Box, Notebook, DataAnalysis, Reading, Coin,
  UserFilled, ArrowDown,
} from '@element-plus/icons-vue'
import { ElMessage, type FormInstance, type FormRules } from 'element-plus'
import { useAuthStore } from '@/store/auth'
import api from '@/utils/api'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const isCollapsed = ref(false)

const currentRoute = computed(() => route.path)
const currentPageTitle = computed(() => (route.meta.title as string) || '')

// 个人中心 / 修改密码
const profileVisible = ref(false)
const pwdFormRef = ref<FormInstance>()
const pwdLoading = ref(false)
const pwdForm = ref({ oldPassword: '', newPassword: '', confirmPassword: '' })

const pwdRules: FormRules = {
  oldPassword: [{ required: true, message: '请输入原密码', trigger: 'blur' }],
  newPassword: [
    { required: true, message: '请输入新密码', trigger: 'blur' },
    { min: 6, message: '新密码至少 6 位', trigger: 'blur' },
  ],
  confirmPassword: [
    { required: true, message: '请再次输入新密码', trigger: 'blur' },
    {
      validator: (_rule, value, callback) => {
        if (value !== pwdForm.value.newPassword) {
          callback(new Error('两次输入的密码不一致'))
        } else {
          callback()
        }
      },
      trigger: 'blur',
    },
  ],
}

async function onChangePassword() {
  if (!pwdFormRef.value) return
  await pwdFormRef.value.validate(async (valid) => {
    if (!valid) return
    pwdLoading.value = true
    try {
      await api.put('/auth/password', {
        old_password: pwdForm.value.oldPassword,
        new_password: pwdForm.value.newPassword,
      })
      ElMessage.success('密码已修改，请重新登录')
      profileVisible.value = false
      await auth.logout()
      router.replace('/login')
    } catch {
      /* 错误提示由拦截器处理 */
    } finally {
      pwdLoading.value = false
    }
  })
}

async function onUserCommand(command: string) {
  if (command === 'logout') {
    await auth.logout()
    ElMessage.success('已退出登录')
    router.replace('/login')
  } else if (command === 'profile') {
    profileVisible.value = true
  }
}
</script>

<style scoped lang="scss">
.main-layout {
  height: 100vh;
  background-color: #F5F0EB;
}

.profile-desc {
  :deep(.el-descriptions__label) {
    width: 90px;
    color: #8a7563;
  }
}

.sidebar {
  background-color: #2C1810;
  overflow-y: auto;
  overflow-x: hidden;
  transition: width 0.2s;
  display: flex;
  flex-direction: column;

  .sidebar-logo {
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 16px 8px;
    cursor: pointer;
    border-bottom: 1px solid rgba(232, 213, 196, 0.1);

    .logo-icon {
      font-size: 28px;
    }

    .logo-text {
      color: #E8D5C4;
      font-size: 16px;
      font-weight: 600;
      margin-left: 8px;
      white-space: nowrap;
    }
  }

  .el-menu {
    border-right: none;
    flex: 1;
  }

  .sidebar-toggle {
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 12px;
    cursor: pointer;
    color: #E8D5C4;
    border-top: 1px solid rgba(232, 213, 196, 0.1);

    &:hover {
      color: #D4A574;
    }
  }
}

.main-container {
  background-color: #F5F0EB;
}

.main-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  background: #fff;
  border-bottom: 1px solid #e8e0d8;
  padding: 0 20px;
  height: 48px;

  .header-right {
    display: flex;
    align-items: center;
    gap: 16px;
  }

  .user-box {
    display: flex;
    align-items: center;
    gap: 4px;
    cursor: pointer;
    color: #5b4636;
    font-size: 14px;
    outline: none;

    .user-name {
      margin: 0 2px;
    }
    &:hover {
      color: #2C1810;
    }
  }
}

.main-content {
  padding: 20px;
  overflow-y: auto;
}
</style>