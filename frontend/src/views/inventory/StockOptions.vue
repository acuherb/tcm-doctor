<template>
  <div class="stock-options">
    <el-card shadow="hover" class="opt-card">
      <template #header>
        <div class="opt-head">
          <span>🏷️ 物品类别</span>
          <el-button type="primary" size="small" @click="openCreate('category')">
            <el-icon><Plus /></el-icon> 新增类别
          </el-button>
        </div>
      </template>
      <el-table :data="categories" stripe empty-text="暂无类别">
        <el-table-column prop="name" label="名称" min-width="160" />
        <el-table-column label="启用" width="90">
          <template #default="{ row }">
            <el-switch v-model="row.is_active" @change="(v: any) => toggle(row, v)" />
          </template>
        </el-table-column>
        <el-table-column label="操作" width="140" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" size="small" @click="openEdit(row)">编辑</el-button>
            <el-button link type="danger" size="small" @click="remove(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-card shadow="hover" class="opt-card">
      <template #header>
        <div class="opt-head">
          <span>📐 计量单位</span>
          <el-button type="primary" size="small" @click="openCreate('unit')">
            <el-icon><Plus /></el-icon> 新增单位
          </el-button>
        </div>
      </template>
      <el-table :data="units" stripe empty-text="暂无单位">
        <el-table-column prop="name" label="名称" min-width="160" />
        <el-table-column label="启用" width="90">
          <template #default="{ row }">
            <el-switch v-model="row.is_active" @change="(v: any) => toggle(row, v)" />
          </template>
        </el-table-column>
        <el-table-column label="操作" width="140" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" size="small" @click="openEdit(row)">编辑</el-button>
            <el-button link type="danger" size="small" @click="remove(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-dialog v-model="visible" :title="editing ? '编辑选项' : '新增选项'" width="420px" destroy-on-close>
      <el-form label-width="80px">
        <el-form-item label="类型">
          <el-input :model-value="form.opt_type === 'category' ? '物品类别' : '计量单位'" disabled />
        </el-form-item>
        <el-form-item label="名称" required>
          <el-input v-model="form.name" placeholder="如：理疗耗材 / 袋" maxlength="60" show-word-limit />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="visible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="save">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus } from '@element-plus/icons-vue'
import api from '@/utils/api'

const categories = ref<any[]>([])
const units = ref<any[]>([])
const visible = ref(false)
const editing = ref<number | null>(null)
const saving = ref(false)
const form = ref<{ opt_type: 'category' | 'unit'; name: string }>({ opt_type: 'category', name: '' })

async function load() {
  try {
    const res = (await api.get('/stock/options') as any) || []
    categories.value = res.filter((o: any) => o.opt_type === 'category')
    units.value = res.filter((o: any) => o.opt_type === 'unit')
  } catch {
    /* 错误提示由拦截器处理 */
  }
}
function openCreate(type: 'category' | 'unit') {
  editing.value = null
  form.value = { opt_type: type, name: '' }
  visible.value = true
}
function openEdit(row: any) {
  editing.value = row.id
  form.value = { opt_type: row.opt_type, name: row.name }
  visible.value = true
}
async function save() {
  const name = form.value.name.trim()
  if (!name) { ElMessage.warning('请输入名称'); return }
  saving.value = true
  try {
    if (editing.value) {
      await api.put(`/stock/options/${editing.value}`, { name })
      ElMessage.success('已更新')
    } else {
      await api.post('/stock/options', { opt_type: form.value.opt_type, name })
      ElMessage.success('已添加')
    }
    visible.value = false
    load()
  } catch {
    /* 错误提示由拦截器处理 */
  } finally {
    saving.value = false
  }
}
async function toggle(row: any, v: any) {
  const val = Boolean(v)
  try {
    await api.put(`/stock/options/${row.id}`, { is_active: val })
    ElMessage.success('已更新')
  } catch {
    row.is_active = !val // 失败回滚
  }
}
async function remove(row: any) {
  try {
    await ElMessageBox.confirm(
      `确认删除选项「${row.name}」？已使用该选项的物品不受影响（仅不再作为下拉候选）。`,
      '删除确认', { type: 'warning' },
    )
  } catch {
    return
  }
  try {
    await api.delete(`/stock/options/${row.id}`)
    ElMessage.success('已删除')
    load()
  } catch {
    /* 错误提示由拦截器处理 */
  }
}
onMounted(load)
</script>

<style scoped lang="scss">
.stock-options { display: flex; flex-direction: column; gap: 16px; }
.opt-head { display: flex; justify-content: space-between; align-items: center; }
</style>
