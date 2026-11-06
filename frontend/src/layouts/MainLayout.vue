<template>
  <el-container class="main-layout">
    <!-- 手机端遮罩（点击关抽屉） -->
    <div v-show="isMobile && mobileOpen" class="mobile-mask" @click="mobileOpen = false"></div>

    <!-- 侧边栏 -->
    <el-aside :width="isMobile ? '176px' : (isCollapsed ? '64px' : '210px')" class="sidebar" :class="{ 'sidebar-mobile-open': mobileOpen }">
      <div class="sidebar-logo" @click="$router.push('/dashboard')">
        <img v-if="clinicLogo" :src="clinicLogo" class="logo-img" alt="诊所Logo" />
        <span v-else class="logo-icon">🌿</span>
        <span v-show="!isCollapsed || isMobile" class="logo-text">{{ clinicName || '中医诊所管理' }}</span>
      </div>

      <el-menu
        :default-active="currentRoute"
        :collapse="isCollapsed && !isMobile"
        :collapse-transition="false"
        @select="onMenuSelect"
      >
        <el-menu-item index="/dashboard">
          <el-icon><HomeFilled /></el-icon>
          <template #title>工作台</template>
        </el-menu-item>
        <el-menu-item index="/statistics">
          <el-icon><DataAnalysis /></el-icon>
          <template #title>统计报表</template>
        </el-menu-item>

        <el-sub-menu index="frontdesk-group">
          <template #title>
            <el-icon><Money /></el-icon>
            <span>挂号收费</span>
          </template>
          <el-menu-item v-if="auth.can('patient:write')" index="/registration">挂号台</el-menu-item>
          <el-menu-item v-if="auth.can('billing:read')" index="/billing">收费管理</el-menu-item>
        </el-sub-menu>

        <el-sub-menu index="patient-group">
          <template #title>
            <el-icon><User /></el-icon>
            <span>病号管理</span>
          </template>
          <el-menu-item index="/patients">患者列表</el-menu-item>
        </el-sub-menu>

        <el-sub-menu index="prescription-group">
          <template #title>
            <el-icon><Document /></el-icon>
            <span>处方管理</span>
          </template>
          <el-menu-item index="/prescriptions">处方列表</el-menu-item>
          <el-menu-item index="/classic-formulas">中药方库</el-menu-item>
          <el-menu-item index="/acupoint-formulas">针灸方库</el-menu-item>
        </el-sub-menu>

        <el-sub-menu index="treatment-group">
          <template #title>
            <el-icon><FirstAidKit /></el-icon>
            <span>诊疗管理</span>
          </template>
          <el-menu-item index="/herbs">药材字典</el-menu-item>
          <el-menu-item index="/acupoints">针灸穴位</el-menu-item>
          <el-menu-item index="/dictionaries">数据字典</el-menu-item>
        </el-sub-menu>

        <el-sub-menu index="stock-group">
          <template #title>
            <el-icon><Box /></el-icon>
            <span>库存管理</span>
          </template>
          <el-menu-item index="/stock/overview">库存总览</el-menu-item>
          <el-menu-item index="/stock/items">物品管理</el-menu-item>
          <el-menu-item index="/stock/transactions">库存流水</el-menu-item>
          <el-menu-item index="/stock/check">库房盘点</el-menu-item>
          <el-menu-item index="/stock/purchases">采购入库</el-menu-item>
          <el-menu-item index="/stock/reports">进销存报表</el-menu-item>
          <el-menu-item index="/stock/suppliers">供应商管理</el-menu-item>
          <el-menu-item index="/stock/options">库存选项</el-menu-item>
        </el-sub-menu>

        <el-menu-item index="/knowledge">
          <el-icon><Search /></el-icon>
          <template #title>知识检索</template>
        </el-menu-item>

        <el-menu-item v-if="auth.can('dict:write')" index="/book-library">
          <el-icon><Reading /></el-icon>
          <template #title>医籍文库</template>
        </el-menu-item>

        <el-menu-item index="/diagnosis">
          <el-icon><ChatDotRound /></el-icon>
          <template #title>智能问诊</template>
        </el-menu-item>

        <el-menu-item v-if="auth.can('system:write')" index="/settings">
          <el-icon><Setting /></el-icon>
          <template #title>系统设置</template>
        </el-menu-item>
        <el-menu-item v-if="auth.can('log:read')" index="/system/logs">
          <el-icon><Document /></el-icon>
          <template #title>操作日志</template>
        </el-menu-item>
        <el-menu-item v-if="auth.can('user:write')" index="/system/users">
          <el-icon><UserFilled /></el-icon>
          <template #title>账号管理</template>
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
          <el-icon v-show="isMobile" class="menu-hamburger" @click="mobileOpen = !mobileOpen"><Expand /></el-icon>
          <el-breadcrumb separator="/">
            <el-breadcrumb-item v-if="currentPageTitle">{{ currentPageTitle }}</el-breadcrumb-item>
          </el-breadcrumb>
        </div>
        <div class="header-right">
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
                <el-dropdown-item command="theme" divided>界面风格</el-dropdown-item>
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

    <!-- 界面风格：预设主题切换 -->
    <el-dialog v-model="themeVisible" title="界面风格" width="440px" append-to-body>
      <div class="theme-grid">
        <div
          v-for="t in THEMES"
          :key="t.key"
          class="theme-card"
          :class="{ active: currentTheme === t.key }"
          @click="onSelectTheme(t.key)"
        >
          <div class="theme-swatches">
            <span v-for="c in t.swatches" :key="c" :style="{ background: c }"></span>
          </div>
          <div class="theme-meta">
            <div class="theme-label">{{ t.label }}</div>
            <div class="theme-desc">{{ t.desc }}</div>
          </div>
          <el-icon v-if="currentTheme === t.key" class="theme-check"><Check /></el-icon>
        </div>
      </div>
    </el-dialog>

    <!-- 个人中心：账号信息 + 修改密码 -->
    <el-dialog v-model="profileVisible" title="个人中心" width="440px" append-to-body>
      <el-descriptions :column="1" border class="profile-desc">
        <el-descriptions-item label="用户名">{{ auth.user?.username }}</el-descriptions-item>
        <el-descriptions-item label="显示名称">{{ auth.user?.display_name || '—' }}</el-descriptions-item>
        <el-descriptions-item label="角色">{{ auth.roleLabel }}</el-descriptions-item>
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
import { ref, computed, onMounted, onBeforeUnmount } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  HomeFilled, User, FirstAidKit, Document, Search,
  ChatDotRound, Setting, Fold, Expand, Box, DataAnalysis, Reading,
  UserFilled, ArrowDown, Check, Money,
} from '@element-plus/icons-vue'
import { ElMessage, type FormInstance, type FormRules } from 'element-plus'
import { useAuthStore } from '@/store/auth'
import { THEMES, applyTheme, getStoredTheme, type ThemeKey } from '@/utils/theme'
import api from '@/utils/api'
import type { AppConfig } from '@/types'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const isCollapsed = ref(false)
const clinicName = ref('')
const clinicLogo = ref('')

// ---- 移动端抽屉适配 ----
const isMobile = ref(false)
const mobileOpen = ref(false)

function updateViewport() {
  isMobile.value = window.innerWidth < 768
  if (!isMobile.value) mobileOpen.value = false
}

function closeMobileSidebar() {
  if (isMobile.value) mobileOpen.value = false
}

// 手动处理菜单导航（不再依赖 el-menu 的 router 模式，规避其 hash 路由下点击不跳转/跳一半的已知问题）
function onMenuSelect(index: string) {
  if (index) router.push(index)
  closeMobileSidebar()
}

onMounted(() => {
  updateViewport()
  window.addEventListener('resize', updateViewport)
  // 拉取诊所信息用于侧边栏展示（诊所名/logo 对所有角色开放；失败静默，不打扰用户）
  api.get<AppConfig>('/config', { silent: true }).then((res) => {
    clinicName.value = res.clinic_name?.trim() || ''
    clinicLogo.value = res.clinic_logo || ''
  }).catch(() => {})
})
onBeforeUnmount(() => window.removeEventListener('resize', updateViewport))

const currentRoute = computed(() => route.path)
const currentPageTitle = computed(() => (route.meta.title as string) || '')

// 个人中心 / 修改密码
const profileVisible = ref(false)
const pwdFormRef = ref<FormInstance>()
const pwdLoading = ref(false)
const pwdForm = ref({ oldPassword: '', newPassword: '', confirmPassword: '' })

// 界面风格
const themeVisible = ref(false)
const currentTheme = ref<ThemeKey>(getStoredTheme())

async function onSelectTheme(key: ThemeKey) {
  applyTheme(key)
  currentTheme.value = key
  // 同步到服务端：同一诊所多终端共享同一风格；无 system:write 权限时静默失败（仅本机生效）
  try {
    await api.put('/config', { ui_theme: key })
    ElMessage.success(`已切换到「${THEMES.find((t) => t.key === key)?.label}」风格`)
  } catch {
    /* 无权限或后端不可用：本地已生效，不回滚 */
  }
}

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
      // 后端已保留当前会话，刷新用户信息即可（must_change_password 已置否）
      // 响应拦截器已返回 response.data，故此处直接取用户对象（勿再 .data，否则得到 undefined）
      const me = await api.get('/auth/me')
      auth.setUser(me)
      ElMessage.success('密码已修改')
      profileVisible.value = false
      pwdForm.value.oldPassword = ''
      pwdForm.value.newPassword = ''
      pwdForm.value.confirmPassword = ''
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
  } else if (command === 'theme') {
    themeVisible.value = true
  }
}
</script>

<style scoped lang="scss">
.main-layout {
  height: 100vh;
  background-color: var(--tcm-bg);
}

.profile-desc {
  :deep(.el-descriptions__label) {
    width: 90px;
    color: #8a7563;
  }
}

/* 界面风格选择 */
.theme-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
}

.theme-card {
  position: relative;
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 12px;
  border: 2px solid #e8e0d8;
  border-radius: 10px;
  cursor: pointer;
  transition: border-color 0.2s, box-shadow 0.2s;

  &:hover {
    border-color: var(--tcm-accent);
  }

  &.active {
    border-color: var(--tcm-primary);
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
  }

  .theme-swatches {
    display: flex;
    gap: 6px;

    span {
      width: 28px;
      height: 28px;
      border-radius: 6px;
    }
  }

  .theme-label {
    font-size: 14px;
    font-weight: 600;
    color: var(--tcm-primary);
  }

  .theme-desc {
    font-size: 12px;
    color: #8a7563;
    line-height: 1.4;
  }

  .theme-check {
    position: absolute;
    top: 10px;
    right: 10px;
    color: var(--tcm-primary);
  }
}

.sidebar {
  background-color: var(--tcm-sidebar-bg);
  overflow-y: auto;
  overflow-x: hidden;
  transition: width 0.2s;
  display: flex;
  flex-direction: column;
  /* 强制独立合成层：Chromium/Edge 在滚动容器内对复杂 SVG 路径（如齿轮图标）偶发光栅化丢失 */
  transform: translateZ(0);
  backface-visibility: hidden;

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

    .logo-img {
      width: 30px;
      height: 30px;
      object-fit: contain;
      border-radius: 4px;
    }

    .logo-text {
      color: var(--tcm-sidebar-text);
      font-size: 16px;
      font-weight: 600;
      margin-left: 8px;
      white-space: nowrap;
    }
  }

  :deep(.el-menu) {
    border-right: none;
    flex: 1;
    background-color: transparent;
  }

  /* 菜单配色统一由主题变量驱动（原先是 el-menu 的颜色 props，无法被主题覆盖） */
  :deep(.el-menu-item),
  :deep(.el-sub-menu__title) {
    color: var(--tcm-sidebar-text);
    background-color: transparent;
  }

  :deep(.el-menu-item:hover),
  :deep(.el-sub-menu__title:hover) {
    background-color: rgba(255, 255, 255, 0.06);
    color: var(--tcm-sidebar-active);
  }

  :deep(.el-menu-item.is-active) {
    color: var(--tcm-sidebar-active);
    background-color: rgba(255, 255, 255, 0.08);
  }

  .sidebar-toggle {
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 12px;
    cursor: pointer;
    color: var(--tcm-sidebar-text);
    border-top: 1px solid rgba(232, 213, 196, 0.1);

    &:hover {
      color: var(--tcm-sidebar-active);
    }
  }
}

.main-container {
  background-color: var(--tcm-bg);
}

.main-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  background: var(--tcm-card-bg);
  border-bottom: 1px solid #e8e0d8;
  padding: 0 20px;
  height: 48px;

  .header-left {
    display: flex;
    align-items: center;
    min-width: 0;
  }

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
    color: var(--tcm-primary);
    font-size: 14px;
    outline: none;

    .user-name {
      margin: 0 2px;
    }
    &:hover {
      color: var(--tcm-primary-dark);
    }
  }
}

.main-content {
  padding: 20px;
  overflow-y: auto;
}

/* 手机端顶部导航汉堡图标 */
.menu-hamburger {
  font-size: 20px;
  cursor: pointer;
  color: var(--tcm-primary);
  margin-right: 8px;
}

/* ---------- 移动端适配（窄屏） ---------- */
@media (max-width: 767px) {
  .main-layout {
    position: relative;
  }

  /* 侧边栏：默认移到屏幕外，开抽屉时滑入 */
  .sidebar {
    position: fixed;
    top: 0;
    left: 0;
    bottom: 0;
    width: 176px !important;
    transform: translateX(-100%);
    transition: transform 0.25s ease;
    z-index: 2000;
    box-shadow: 2px 0 12px rgba(0, 0, 0, 0.35);
    overflow-x: hidden;

    :deep(.el-menu) {
      width: 100% !important;
      overflow-x: hidden;
    }

    /* Element Plus 内联子菜单默认 min-width:200px，是弹出过宽的主因，强制解除 */
    :deep(.el-menu--inline) {
      min-width: 0 !important;
      width: 100% !important;
    }

    :deep(.el-menu-item),
    :deep(.el-sub-menu__title) {
      padding-left: 12px !important;
      padding-right: 8px !important;
      height: 46px;
      line-height: 46px;
    }

    /* 子菜单展开层级：缩小左侧缩进，避免与父级标题相隔过远 */
    :deep(.el-sub-menu .el-menu-item) {
      padding-left: 36px !important;
      min-width: 0;
      height: 42px;
      line-height: 42px;
      font-size: 13px;
    }

    /* 子菜单标题右侧箭头紧贴文字，压缩整体宽度 */
    :deep(.el-sub-menu__title span) {
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }
  }

  .sidebar.sidebar-mobile-open {
    transform: translateX(0);
  }

  .sidebar-toggle {
    display: none;
  }

  .mobile-mask {
    position: fixed;
    inset: 0;
    background: rgba(0, 0, 0, 0.45);
    z-index: 1990;
  }

  .main-header {
    padding: 0 12px;
  }

  .main-content {
    padding: 12px;
  }

  .header-right {
    gap: 8px;
  }
}
</style>