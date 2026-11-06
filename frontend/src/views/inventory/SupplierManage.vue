<template>
  <div class="supplier-manage">
    <el-card shadow="hover" class="main-card">
      <template #header>
        <div class="tcm-head">
          <div class="tcm-head__title">
            <span class="tcm-head__icon">🏭</span>
            <span class="tcm-head__text">供应商管理</span>
            <el-tag size="small" effect="light" round class="tcm-head__count">{{ suppliers.length }} 家</el-tag>
          </div>
          <div class="tcm-head__actions">
            <el-input v-model="searchText" placeholder="搜索名称/联系人" clearable class="filter-search" @clear="load">
              <template #prefix><el-icon><Search /></el-icon></template>
            </el-input>
            <el-button type="primary" @click="load">查询</el-button>
            <el-button v-if="editable" @click="openCreate"><el-icon><Plus /></el-icon> 新增</el-button>
          </div>
        </div>
      </template>

      <el-table v-if="!isMobile" :data="suppliers" class="tcm-table" style="width:100%" empty-text="暂无供应商">
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

      <div v-if="isMobile" class="cards">
        <div v-for="row in pagedSuppliers" :key="row.id" class="card">
          <div class="card-head">
            <span class="card-name">{{ row.name }}</span>
            <el-tag :type="row.is_active ? 'success' : 'info'" size="small">{{ row.is_active ? '启用' : '停用' }}</el-tag>
          </div>
          <div class="card-body">
            <div class="card-row"><span class="label">联系人</span><span class="value">{{ row.contact || '-' }}</span></div>
            <div class="card-row"><span class="label">电话</span><span class="value">{{ row.phone || '-' }}</span></div>
            <div class="card-row"><span class="label">地址</span><span class="value">{{ row.address || '-' }}</span></div>
            <div class="card-row" v-if="row.note"><span class="label">备注</span><span class="value">{{ row.note }}</span></div>
          </div>
          <div v-if="editable" class="card-actions">
            <el-button link type="primary" size="small" @click="openEdit(row)">编辑</el-button>
            <el-button link type="danger" size="small" @click="remove(row)" :disabled="row._inuse">删除</el-button>
          </div>
        </div>
        <el-empty v-if="!suppliers.length" description="暂无供应商" />
      </div>

      <div v-if="isMobile && suppliers.length > cardPageSize" class="load-more">
        <el-button v-if="shownCount < suppliers.length" size="small" @click="loadMoreSuppliers">加载更多</el-button>
        <span v-else class="no-more">已显示全部 {{ suppliers.length }} 个供应商</span>
      </div>
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
import { ref, onMounted, computed, onBeforeUnmount } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, Search } from '@element-plus/icons-vue'
import api, { errMsg } from '@/utils/api'
import { useAuthStore } from '@/store/auth'
import type { Supplier } from '@/types'

const auth = useAuthStore()
const isMobile = ref(false)
function updateViewport() { isMobile.value = window.innerWidth < 768 }
const editable = computed(() => auth.canWrite('stock'))
const suppliers = ref<Supplier[]>([])
const cardPageSize = 20
const shownCount = ref(cardPageSize)
const pagedSuppliers = computed(() => (isMobile.value ? suppliers.value.slice(0, shownCount.value) : suppliers.value))
function loadMoreSuppliers() {
  shownCount.value = Math.min(shownCount.value + cardPageSize, suppliers.value.length)
}
const searchText = ref('')
const visible = ref(false)
const isEdit = ref(false)
const activeId = ref<number | null>(null)
const submitting = ref(false)

const form = ref({ name: '', contact: '', phone: '', address: '', note: '', is_active: true })
const rules = { name: [{ required: true, message: '请输入名称', trigger: 'blur' }] }

async function load() {
  try {
    const params: Record<string, any> = {}
    if (searchText.value) params.search = searchText.value
    const list = (await api.get<Supplier[]>('/stock/suppliers', { params })) || []
    // 标记是否已被进货使用（前端无法精确判断，交给后端删除校验）
    suppliers.value = list
    shownCount.value = cardPageSize
  } catch (e) { ElMessage.error('加载失败：' + errMsg(e)) }
}
function openCreate() {
  isEdit.value = false; activeId.value = null
  form.value = { name: '', contact: '', phone: '', address: '', note: '', is_active: true }
  visible.value = true
}
function openEdit(row: Supplier) {
  isEdit.value = true; activeId.value = row.id ?? null
  form.value = { name: row.name || '', contact: row.contact || '', phone: row.phone || '', address: row.address || '', note: row.note || '', is_active: row.is_active }
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
  } catch (e) { ElMessage.error('保存失败：' + errMsg(e)) }
  finally { submitting.value = false }
}
async function remove(row: Supplier) {
  try {
    await ElMessageBox.confirm(`确认删除供应商「${row.name}」？`, '提示', { type: 'warning' })
    await api.delete(`/stock/suppliers/${row.id}`)
    ElMessage.success('已删除')
    load()
  } catch (e) { if (e !== 'cancel') ElMessage.error('删除失败：' + errMsg(e)) }
}

onMounted(() => {
  updateViewport()
  window.addEventListener('resize', updateViewport)
  load()
})
onBeforeUnmount(() => window.removeEventListener('resize', updateViewport))
</script>

<style scoped lang="scss">
.supplier-manage {
  .main-card {
    border-radius: 12px;
    border: 1px solid #f0e4d6;

    :deep(.el-card__header) {
      padding: 0;
      border-bottom: none;
    }
  }

  .filter-search { width: 200px; }

  @media (max-width: 767px) {
    .tcm-head__actions {
      flex-wrap: nowrap;
      gap: 6px;
    }
    .tcm-head__actions .filter-search {
      width: auto;
      flex: 1 1 0;
      min-width: 0;
    }
    .tcm-head__actions .el-button {
      flex: 0 0 auto;
      margin-left: 0;
      padding: 8px 10px;
    }
  }

  .cards { display: flex; flex-direction: column; gap: 10px; margin-top: 8px; }
  .card { border: 1px solid #f0e4d6; border-radius: 10px; padding: 12px; background: #fff; box-shadow: 0 1px 3px rgba(44,24,16,.04); }
  .card .card-head { display: flex; justify-content: space-between; align-items: center; gap: 8px; margin-bottom: 8px; }
  .card .card-name { font-size: 16px; font-weight: 600; color: #2c1810; word-break: break-all; }
  .card .card-row { display: flex; align-items: flex-start; font-size: 14px; line-height: 1.5; }
  .card .card-row .label { flex-shrink: 0; width: 54px; color: #8a7563; }
  .card .card-row .value { flex: 1; color: #4a3628; word-break: break-all; }
  .card .card-actions { display: flex; justify-content: flex-end; gap: 4px; margin-top: 8px; padding-top: 8px; border-top: 1px dashed #f0e4d6; }

  .load-more { display: flex; flex-direction: column; align-items: center; gap: 6px; padding: 14px 0 2px; }
  .load-more .el-button { min-width: 140px; }
  .load-more .no-more { font-size: 12px; color: #a08b76; font-variant-numeric: tabular-nums; }
}
</style>