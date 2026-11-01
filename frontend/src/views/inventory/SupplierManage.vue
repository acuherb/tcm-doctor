<template>
  <div class="supplier-manage">
    <el-card shadow="hover">
      <template #header>
        <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:8px;">
          <span>🏭 供应商管理</span>
          <div style="display:flex;gap:8px;">
            <el-input v-model="searchText" placeholder="搜索名称/联系人" clearable @clear="load" style="width:180px" />
            <el-button type="primary" size="small" @click="openCreate" v-if="editable"><el-icon><Plus /></el-icon> 新增</el-button>
          </div>
        </div>
      </template>

      <el-table :data="suppliers" stripe style="width:100%" empty-text="暂无供应商">
        <el-table-column prop="name" label="名称" min-width="140" />
        <el-table-column prop="contact" label="联系人" width="110" />
        <el-table-column prop="phone" label="电话" width="140" />
        <el-table-column prop="address" label="地址" min-width="160" show-overflow-tooltip />
        <el-table-column label="状态" width="90">
          <template #default="{ row }"><el-tag :type="row.is_active ? 'success' : 'info'" size="small">{{ row.is_active ? '启用' : '停用' }}</el-tag></template>
        </el-table-column>
        <el-table-column label="操作" width="150" v-if="editable">
          <template #default="{ row }">
            <el-button link type="primary" size="small" @click="openEdit(row)">编辑</el-button>
            <el-button link type="danger" size="small" @click="remove(row)" :disabled="row._inuse">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-dialog v-model="visible" :title="isEdit ? '编辑供应商' : '新增供应商'" width="480px" destroy-on-close>
      <el-form :model="form" label-width="80px" :rules="rules" ref="formRef">
        <el-form-item label="名称" prop="name">
          <el-input v-model="form.name" />
        </el-form-item>
        <el-form-item label="联系人"><el-input v-model="form.contact" /></el-form-item>
        <el-form-item label="电话"><el-input v-model="form.phone" /></el-form-item>
        <el-form-item label="地址"><el-input v-model="form.address" /></el-form-item>
        <el-form-item label="备注"><el-input v-model="form.note" type="textarea" :rows="2" /></el-form-item>
        <el-form-item label="状态">
          <el-switch v-model="form.is_active" active-text="启用" inactive-text="停用" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="visible = false">取消</el-button>
        <el-button type="primary" @click="submit" :loading="submitting">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus } from '@element-plus/icons-vue'
import api from '@/utils/api'
import { useAuthStore } from '@/store/auth'

const auth = useAuthStore()
const editable = computed(() => !!auth.user?.is_admin)
const suppliers = ref<any[]>([])
const searchText = ref('')
const visible = ref(false)
const isEdit = ref(false)
const activeId = ref<number | null>(null)
const submitting = ref(false)
const formRef = ref()

const form = ref({ name: '', contact: '', phone: '', address: '', note: '', is_active: true })
const rules = { name: [{ required: true, message: '请输入名称', trigger: 'blur' }] }

async function load() {
  try {
    const params: any = {}
    if (searchText.value) params.search = searchText.value
    const list = (await api.get('/stock/suppliers', { params }) as any) || []
    // 标记是否已被进货使用（前端无法精确判断，交给后端删除校验）
    suppliers.value = list
  } catch (e: any) { ElMessage.error('加载失败：' + (e?.response?.data?.detail || e?.message)) }
}
function openCreate() {
  isEdit.value = false; activeId.value = null
  form.value = { name: '', contact: '', phone: '', address: '', note: '', is_active: true }
  visible.value = true
}
function openEdit(row: any) {
  isEdit.value = true; activeId.value = row.id
  form.value = { name: row.name, contact: row.contact || '', phone: row.phone || '', address: row.address || '', note: row.note || '', is_active: row.is_active }
  visible.value = true
}
async function submit() {
  submitting.value = true
  try {
    if (isEdit.value) await api.put(`/stock/suppliers/${activeId.value}`, form.value)
    else await api.post('/stock/suppliers', form.value)
    ElMessage.success('已保存')
    visible.value = false
    load()
  } catch (e: any) { ElMessage.error('保存失败：' + (e?.response?.data?.detail || e?.message)) }
  finally { submitting.value = false }
}
async function remove(row: any) {
  try {
    await ElMessageBox.confirm(`确认删除供应商「${row.name}」？`, '提示', { type: 'warning' })
    await api.delete(`/stock/suppliers/${row.id}`)
    ElMessage.success('已删除')
    load()
  } catch (e: any) { if (e !== 'cancel') ElMessage.error('删除失败：' + (e?.response?.data?.detail || e?.message)) }
}

onMounted(load)
</script>

<style scoped lang="scss">
.supplier-manage { .el-table { margin-top: 8px; } }
</style>
