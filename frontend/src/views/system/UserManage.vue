🤖 AI 配置<template>
  <div class="user-manage">
    <el-card shadow="hover" class="main-card">
      <template #header>
        <div class="card-head-bar">
          <div class="card-head-title">
            <span class="head-icon">👥</span>
            <span class="head-text">账号管理</span>
            <el-tag v-if="users.length > 0" size="small" type="info" effect="plain" round class="head-count">
              {{ users.length }} 个
            </el-tag>
          </div>
          <div class="card-actions">
            <el-button type="primary" @click="openCreate">
              <el-icon><Plus /></el-icon>新建账号
            </el-button>
          </div>
        </div>
      </template>

      <div class="notice-bar">
        <el-icon class="notice-icon"><InfoFilled /></el-icon>
        <span>新账号首次登录需修改初始密码；修改显示名称不影响登录，修改角色或停用后该账号将被强制重新登录。</span>
      </div>

      <el-table :data="users" class="user-table" style="width:100%" empty-text="暂无账号">
        <el-table-column label="账号" min-width="180">
          <template #default="{ row }">
            <div class="user-cell">
              <div class="user-avatar" :class="`is-${row.role}`">{{ avatarText(row) }}</div>
              <div class="user-id">
                <div class="user-display">
                  {{ row.display_name || row.username }}
                  <el-tag v-if="row.id === auth.user?.id" size="small" type="warning" effect="light" round class="self-tag">
                    当前登录
                  </el-tag>
                </div>
                <div class="user-username">@{{ row.username }}</div>
              </div>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="角色" width="110">
          <template #default="{ row }">
            <el-tag :type="roleTagType(row.role)" size="small" effect="light" round>{{ roleLabelOf(row.role) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="权限" min-width="240">
          <template #default="{ row }">
            <el-tooltip v-if="row.permissions?.length" :content="row.permissions.map(permLabel).join('、')" placement="top">
              <span class="perm-summary">{{ row.permissions.map(permLabel).join('、') }}</span>
            </el-tooltip>
            <span v-else class="perm-inherit">继承角色模板</span>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="86">
          <template #default="{ row }">
            <el-tag :type="row.is_active ? 'success' : 'info'" size="small" effect="light" round>
              {{ row.is_active ? '启用' : '停用' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="252" fixed="right">
          <template #default="{ row }">
            <div class="user-ops">
              <el-button link type="primary" size="small" :disabled="isGuest(row)" @click="openEdit(row)">编辑</el-button>
              <el-button link type="primary" size="small" :disabled="isGuest(row)" @click="openReset(row)">重置密码</el-button>
              <el-button link type="primary" size="small" :disabled="isGuest(row)" @click="toggleActive(row)">
                {{ row.is_active ? '停用' : '启用' }}
              </el-button>
              <el-popconfirm title="确认删除该账号？此操作不可恢复" @confirm="removeUser(row)">
                <template #reference>
                  <el-button link type="danger" size="small"
                             :disabled="isGuest(row) || row.id === auth.user?.id">删除</el-button>
                </template>
              </el-popconfirm>
            </div>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-dialog v-model="dialogVisible" :title="isEdit ? '编辑账号' : '新建账号'" width="620px" append-to-body>
      <el-form ref="formRef" :model="form" :rules="rules" label-width="90px">
        <el-form-item label="用户名" prop="username">
          <el-input v-model="form.username" :disabled="isEdit" placeholder="登录用，至少 2 个字符" />
        </el-form-item>
        <el-form-item label="显示名称" prop="display_name">
          <el-input v-model="form.display_name" placeholder="如 张医生（可留空）" />
        </el-form-item>
        <el-form-item label="角色模板" prop="role">
          <el-select v-model="form.role" style="width:100%" @change="onRoleChange">
            <el-option v-for="r in roleOptions" :key="r.value" :label="r.label" :value="r.value">
              <span>{{ r.label }}</span>
              <span class="opt-hint-right">{{ r.hint }}</span>
            </el-option>
          </el-select>
        </el-form-item>
        <el-form-item v-if="!isEdit" label="初始密码" prop="password">
          <el-input v-model="form.password" type="password" show-password autocomplete="new-password"
                    placeholder="至少 6 位，首次登录需更改" />
        </el-form-item>
        <el-form-item v-if="!isEdit" label="强制改密">
          <el-switch v-model="form.must_change_password" />
          <span class="opt-hint">首次登录必须修改初始密码</span>
        </el-form-item>

        <el-divider content-position="left">权限分配（在角色模板基础上自由勾选）</el-divider>
        <div class="perm-panel">
          <div v-for="g in permCatalog.groups" :key="g.group" class="perm-group">
            <div class="perm-group-title">{{ g.group }}</div>
            <el-checkbox-group v-model="form.permissions">
              <el-checkbox v-for="p in g.perms" :key="p.key" :label="p.key" border size="small">
                {{ p.label }}
              </el-checkbox>
            </el-checkbox-group>
          </div>
        </div>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取 消</el-button>
        <el-button type="primary" :loading="saving" @click="save">保 存</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="resetVisible" title="重置密码" width="420px" append-to-body>
      <div class="notice-bar is-warn">
        <el-icon class="notice-icon"><WarningFilled /></el-icon>
        <span>将为账号 <b>{{ resetTarget?.username }}</b> 设置新密码，该账号会被强制重新登录。</span>
      </div>
      <el-form label-width="80px">
        <el-form-item label="新密码">
          <el-input v-model="resetPassword" type="password" show-password autocomplete="new-password"
                    placeholder="至少 6 位" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="resetVisible = false">取 消</el-button>
        <el-button type="primary" :loading="resetting" @click="doReset">确 定</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, type FormInstance } from 'element-plus'
import { Plus, InfoFilled, WarningFilled } from '@element-plus/icons-vue'
import api, { errMsg } from '@/utils/api'
import type { TcmUser } from '@/types'
import { useAuthStore } from '@/store/auth'

interface AccountRow {
  id: number
  username: string
  display_name: string | null
  role: string
  permissions: string[]
  is_active: boolean
}

const auth = useAuthStore()
const users = ref<AccountRow[]>([])
const dialogVisible = ref(false)
const isEdit = ref(false)
const saving = ref(false)
const editId = ref<number | null>(null)
const formRef = ref<FormInstance | null>(null)
const resetVisible = ref(false)
const resetting = ref(false)
const resetTarget = ref<AccountRow | null>(null)
const resetPassword = ref('')

const roleOptions = [
  { value: 'admin', label: '管理员', hint: '全部权限，含账号管理' },
  { value: 'doctor', label: '医生', hint: '患者/病历/处方/库存可写' },
  { value: 'pharmacist', label: '药房', hint: '库存可写，患者只读' },
  { value: 'viewer', label: '只读', hint: '全局只读' },
  { value: 'custom', label: '自定义', hint: '自由勾选权限' },
]

// 权限目录（来自后端 /auth/permissions），用于渲染权限勾选表
const permCatalog = ref<{ groups: Array<{ perms?: Array<{ key?: string; label?: string }> }>; role_defaults: Record<string, string[]> }>({ groups: [], role_defaults: {} })

function permLabel(key: string) {
  for (const g of permCatalog.value.groups) {
    const p = (g.perms || []).find((x: { key?: string; label?: string }) => x.key === key)
    if (p) return p.label
  }
  return key
}

const form = reactive({
  username: '',
  display_name: '',
  role: 'viewer',
  password: '',
  must_change_password: true,
  permissions: [] as string[],
})

// 选择角色模板时，预填其默认权限集（自定义角色不覆盖已勾选权限）
function onRoleChange(role: string) {
  if (role !== 'custom') {
    form.permissions = [...(permCatalog.value.role_defaults[role] || [])]
  }
}

const rules = {
  username: [{ required: true, message: '请输入用户名', trigger: 'blur' }],
  role: [{ required: true, message: '请选择角色', trigger: 'change' }],
  password: [{ validator: (_r: unknown, v: string, cb: (msg?: string) => void) => {
    if (!isEdit.value && !v) return cb(new Error('请输入初始密码'))
    if (v && v.length < 6) return cb(new Error('密码至少 6 位'))
    cb()
  }, trigger: 'blur' }],
}

function roleLabelOf(role: string) {
  return roleOptions.find(r => r.value === role)?.label || role
}

function roleTagType(role: string) {
  const map: Record<string, string> = {
    admin: 'danger', doctor: 'success', pharmacist: 'warning', viewer: 'info',
  }
  return (map[role] || 'info') as string
}

function isGuest(row: AccountRow) {
  return row.username === 'guest'
}

// 头像文字：优先显示名称首字，其次用户名首字
function avatarText(row: AccountRow) {
  const src = (row.display_name || row.username || '').trim()
  return src ? src.charAt(0).toUpperCase() : '?'
}

async function load() {
  try {
    users.value = (await api.get<TcmUser[]>('/auth/users'))
  } catch (e) {
    ElMessage.error(errMsg(e) || '加载账号失败')
  }
}

// 权限目录（权限点分组 + 角色默认集），仅用于渲染勾选表，失败不影响账号列表
async function loadCatalog() {
  try {
    const res = (await api.get<Record<string, unknown>>('/auth/permissions'))
    permCatalog.value = { groups: res.groups || [], role_defaults: res.role_defaults || {} }
  } catch {
    /* 权限目录加载失败不影响账号管理 */
  }
}

function resetForm() {
  form.username = ''
  form.display_name = ''
  form.role = 'viewer'
  form.password = ''
  form.must_change_password = true
}

function openCreate() {
  isEdit.value = false
  editId.value = null
  resetForm()
  dialogVisible.value = true
}

function openEdit(row: AccountRow) {
  isEdit.value = true
  editId.value = row.id
  form.username = row.username
  form.display_name = row.display_name || ''
  form.role = row.role
  form.permissions = row.permissions ? [...row.permissions] : [...(permCatalog.value.role_defaults[row.role] || [])]
  dialogVisible.value = true
}

async function save() {
  if (!formRef.value) return
  const valid = await formRef.value.validate().catch(() => false)
  if (!valid) return
  saving.value = true
  try {
    if (isEdit.value && editId.value !== null) {
      await api.put(`/auth/users/${editId.value}`, {
        display_name: form.display_name,
        role: form.role,
        permissions: form.permissions,
      })
      if (editId.value === auth.user?.id) {
        const me = (await api.get<TcmUser>('/auth/me'))
        auth.setUser(me)
      }
      ElMessage.success('账号已更新')
    } else {
      await api.post('/auth/users', {
        username: form.username,
        display_name: form.display_name,
        role: form.role,
        password: form.password,
        must_change_password: form.must_change_password,
        permissions: form.permissions,
      })
      ElMessage.success('账号已创建')
    }
    dialogVisible.value = false
    await load()
  } catch (e) {
    ElMessage.error(errMsg(e) || '保存失败')
  } finally {
    saving.value = false
  }
}

function openReset(row: AccountRow) {
  resetTarget.value = row
  resetPassword.value = ''
  resetVisible.value = true
}

async function doReset() {
  if (!resetTarget.value) return
  if (resetPassword.value.length < 6) {
    ElMessage.error('密码至少 6 位')
    return
  }
  resetting.value = true
  try {
    await api.put(`/auth/users/${resetTarget.value.id}`, {
      reset_password: true,
      password: resetPassword.value,
    })
    ElMessage.success('密码已重置')
    resetVisible.value = false
    await load()
  } catch (e) {
    ElMessage.error(errMsg(e) || '重置失败')
  } finally {
    resetting.value = false
  }
}

async function toggleActive(row: AccountRow) {
  try {
    await api.put(`/auth/users/${row.id}`, { is_active: !row.is_active })
    ElMessage.success(row.is_active ? '账号已停用' : '账号已启用')
    await load()
  } catch (e) {
    ElMessage.error(errMsg(e) || '操作失败')
  }
}

async function removeUser(row: AccountRow) {
  try {
    await api.delete(`/auth/users/${row.id}`)
    ElMessage.success('账号已删除')
    await load()
  } catch (e) {
    ElMessage.error(errMsg(e) || '删除失败')
  }
}

onMounted(() => {
  load()
  loadCatalog()
})
</script>

<style scoped lang="scss">
.user-manage {
  .main-card {
    :deep(.el-card__header) {
      padding: 14px 18px;
      background: linear-gradient(135deg, #fdf8f3 0%, #f7efe6 100%);
      border-bottom: 1px solid #f0e4d6;
    }
  }
  .card-head-bar {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 12px;
    flex-wrap: wrap;
  }
  .card-head-title { display: flex; align-items: center; gap: 8px; min-width: 0; }
  .head-icon { font-size: 18px; line-height: 1; }
  .head-text { font-size: 16px; font-weight: 600; color: #2c1810; letter-spacing: .5px; }
  .head-count { margin-left: 2px; background: #fff; border-color: #e6d9c9; color: #907a63; }
  .card-actions { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }

  .notice-bar {
    display: flex;
    align-items: flex-start;
    gap: 6px;
    padding: 8px 12px;
    margin-bottom: 14px;
    border: 1px dashed #e6d9c9;
    border-radius: 8px;
    background: #fdfaf7;
    font-size: 12px;
    line-height: 1.7;
    color: #8a7a68;

    .notice-icon { flex: none; margin-top: 2px; color: #b89a76; font-size: 13px; }

    &.is-warn {
      border-color: #f0dcc0;
      background: #fffaf2;
      color: #97704a;
      .notice-icon { color: #d19a5c; }
      b { color: #8b5e34; }
    }
  }

  .user-table {
    :deep(th.el-table__cell) {
      background: #faf6f1;
      color: #7a6553;
      font-weight: 600;
    }
    :deep(td.el-table__cell) { vertical-align: middle; padding: 9px 0; }

    .is-disabled-row { opacity: .55; }
  }

  .user-cell {
    display: flex;
    align-items: center;
    gap: 10px;
    min-width: 0;
  }

  .user-avatar {
    flex: none;
    width: 32px;
    height: 32px;
    border-radius: 8px;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 14px;
    font-weight: 600;
    color: #fff;
    background: #a39484;
    letter-spacing: 0;

    &.is-admin { background: linear-gradient(135deg, #c0764f, #a35d38); }
    &.is-doctor { background: linear-gradient(135deg, #8fa983, #6d8c61); }
    &.is-pharmacist { background: linear-gradient(135deg, #c2a06a, #a5834e); }
    &.is-viewer { background: linear-gradient(135deg, #a9a09a, #8b827c); }
    &.is-custom { background: linear-gradient(135deg, #9b8ba6, #77687f); }
  }

  .user-id { min-width: 0; }

  .user-display {
    display: flex;
    align-items: center;
    gap: 6px;
    font-size: 14px;
    font-weight: 600;
    color: #2c1810;
    line-height: 1.4;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;

    .self-tag { flex: none; transform: scale(.9); transform-origin: left center; }
  }

  .user-username {
    font-size: 12px;
    color: #a39484;
    line-height: 1.4;
  }

  .perm-summary {
    font-size: 12px;
    color: #5c4a3a;
    line-height: 1.6;
    display: -webkit-box;
    -webkit-line-clamp: 2;
    -webkit-box-orient: vertical;
    overflow: hidden;
  }

  .perm-inherit {
    font-size: 12px;
    color: #bdb0a2;
  }

  .user-ops {
    display: flex;
    flex-wrap: wrap;
    gap: 0 6px;

    :deep(.el-button) {
      margin-left: 0;
      padding: 2px 0;
    }
  }
}

.opt-hint {
  font-size: 12px;
  color: #a39484;
  margin-left: 8px;
}

.opt-hint-right {
  display: block;
  font-size: 12px;
  color: #b8956a;
  line-height: 1.6;
}

.perm-panel {
  width: 100%;
  max-height: 320px;
  overflow-y: auto;
  padding-right: 6px;
}
.perm-group { margin-bottom: 10px; }
.perm-group-title {
  font-size: 13px;
  font-weight: 600;
  color: #6b5644;
  margin-bottom: 6px;
}
.perm-group :deep(.el-checkbox.is-bordered) {
  margin-right: 8px;
  margin-bottom: 8px;
  border-radius: 6px;

  &.is-checked {
    background: #fdf3e7;
    border-color: #ebcfab;
  }
}

@media (max-width: 767px) {
  .user-manage {
    .card-head-bar { align-items: stretch; }
    .card-actions { justify-content: flex-start; }
    .notice-bar { font-size: 12px; }
  }
}
</style>