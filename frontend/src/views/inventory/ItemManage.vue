<template>
  <div class="item-manage">
    <!-- 顶部操作栏 -->
    <el-card shadow="hover">
      <template #header>
        <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:8px;">
          <span>📋 物品管理</span>
          <div style="display:flex;gap:8px;">
            <el-select v-model="typeFilter" placeholder="类别筛选" clearable @change="loadItems(true)" style="width:140px">
              <el-option label="全部" value="" />
              <el-option label="中药" value="中药" />
              <el-option label="针灸针" value="针灸针" />
              <el-option label="艾灸耗材" value="艾灸耗材" />
              <el-option label="外治耗材" value="外治耗材" />
              <el-option label="其他" value="其他" />
            </el-select>
            <el-button v-if="editable" type="primary" size="small" @click="openCreate">
              <el-icon><Plus /></el-icon> 新增物品
            </el-button>
          </div>
        </div>
      </template>

      <el-form :inline="true" @submit.prevent="loadItems">
        <el-form-item>
          <el-input v-model="searchText" placeholder="搜索名称/规格" clearable @clear="loadItems(true)" style="width:220px">
            <template #prefix><el-icon><Search /></el-icon></template>
          </el-input>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="loadItems(true)">查询</el-button>
        </el-form-item>
      </el-form>

      <el-table v-if="!isMobile" class="stock-item-table" :data="filteredItems" stripe style="width:100%" empty-text="暂无物品">
        <el-table-column prop="item_type" label="类别" width="110">
          <template #default="{ row }"><el-tag size="small">{{ row.item_type }}</el-tag></template>
        </el-table-column>
        <el-table-column prop="name" label="名称" min-width="140" show-overflow-tooltip />
        <el-table-column prop="barcode" label="条码" width="120" show-overflow-tooltip>
          <template #default="{ row }"><span class="mono">{{ row.barcode || '-' }}</span></template>
        </el-table-column>
        <el-table-column prop="spec" label="规格" width="120" show-overflow-tooltip>
          <template #default="{ row }">{{ row.spec || '-' }}</template>
        </el-table-column>
        <el-table-column prop="unit" label="单位" width="70" />
        <el-table-column prop="total_quantity" label="当前库存" width="110">
          <template #default="{ row }">
            <span :class="{ 'low-stock': isLow(row) }">{{ row.total_quantity }} {{ row.unit }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="min_stock" label="最低库存" width="100">
          <template #default="{ row }">{{ row.min_stock != null ? row.min_stock + ' ' + row.unit : '-' }}</template>
        </el-table-column>
        <el-table-column prop="sell_price" label="默认售价" width="110">
          <template #default="{ row }">{{ row.sell_price != null ? row.sell_price.toFixed(2) + ' 元' : '-' }}</template>
        </el-table-column>
        <el-table-column label="操作" width="220" fixed="right">
          <template #default="{ row }">
            <el-button v-if="editable" link type="primary" size="small" @click="openEdit(row)">编辑</el-button>
            <el-button v-if="editable" link type="danger" size="small" @click="removeItem(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>

      <!-- 移动端卡片 -->
      <div v-if="isMobile" class="cards">
        <div v-for="row in filteredItems" :key="row.id" class="card">
          <div class="card-head">
            <span class="card-name">{{ row.name }}</span>
            <el-tag size="small">{{ row.item_type }}</el-tag>
          </div>
          <div class="card-body">
            <div class="card-row"><span class="label">规格</span><span class="value">{{ row.spec || '-' }}</span></div>
            <div class="card-row"><span class="label">库存</span>
              <span class="value" :class="{ 'low-stock': isLow(row) }">{{ row.total_quantity }} {{ row.unit }} / 最低 {{ row.min_stock != null ? row.min_stock + row.unit : '-' }}</span>
            </div>
            <div class="card-row"><span class="label">售价</span><span class="value">{{ row.sell_price != null ? row.sell_price.toFixed(2) + ' 元/' + row.unit : '-' }}</span></div>
          </div>
          <div v-if="editable" class="card-actions">
            <el-button link type="primary" size="small" @click="openEdit(row)">编辑</el-button>
            <el-button link type="danger" size="small" @click="removeItem(row)">删除</el-button>
          </div>
        </div>
        <el-empty v-if="!filteredItems.length" description="暂无物品" />
      </div>

      <el-pagination
        v-if="total > pageSize"
        style="margin-top:14px;justify-content:center;"
        layout="total, prev, pager, next"
        :total="total" :page-size="pageSize" :current-page="page"
        @current-change="(p: number) => { page = p; loadItems() }"
      />
    </el-card>

    <!-- 新增 / 编辑 物品对话框 -->
    <el-dialog v-model="itemVisible" :title="isEdit ? '✏️ 编辑物品' : '➕ 新增物品'" width="520px" destroy-on-close>
      <el-form :model="itemForm" label-width="92px" :rules="itemRules" ref="itemFormRef">
        <el-form-item label="类别" prop="item_type">
          <el-select v-model="itemForm.item_type" style="width:100%">
            <el-option label="中药" value="中药" />
            <el-option label="针灸针" value="针灸针" />
            <el-option label="艾灸耗材" value="艾灸耗材" />
            <el-option label="外治耗材" value="外治耗材" />
            <el-option label="其他" value="其他" />
          </el-select>
        </el-form-item>
        <el-form-item label="名称" prop="name">
          <el-input v-model="itemForm.name" placeholder="如：黄芪 / 一次性针灸针" />
        </el-form-item>
        <el-form-item label="规格">
          <el-input v-model="itemForm.spec" placeholder="如：0.30×40mm / 五年陈" />
        </el-form-item>
        <el-form-item label="计量单位" prop="unit">
          <el-select v-model="itemForm.unit" style="width:100%" filterable allow-create>
            <el-option label="g（克）" value="g" />
            <el-option label="盒" value="盒" />
            <el-option label="支" value="支" />
            <el-option label="根" value="根" />
            <el-option label="贴" value="贴" />
            <el-option label="包" value="包" />
          </el-select>
        </el-form-item>
        <el-form-item label="默认售价">
          <el-input-number v-model="itemForm.sell_price" :min="0" :precision="2" :controls="false" style="width:100%" />
        </el-form-item>
        <el-form-item label="最低库存">
          <el-input-number v-model="itemForm.min_stock" :min="0" :precision="1" :controls="false" style="width:100%" />
        </el-form-item>
        <el-form-item label="关联药材" v-if="itemForm.item_type === '中药'">
          <el-select v-model="itemForm.herb_id" filterable clearable placeholder="可选（仅中药）" style="width:100%">
            <el-option v-for="h in herbs" :key="h.id" :label="h.name" :value="h.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="默认供应商">
          <el-select v-model="itemForm.default_supplier_id" filterable clearable placeholder="可选" style="width:100%">
            <el-option v-for="s in suppliers" :key="s.id" :label="s.name" :value="s.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="条码">
          <el-input v-model="itemForm.barcode" placeholder="留空自动生成（IT+ID）" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="itemVisible = false">取消</el-button>
        <el-button type="primary" @click="saveItem" :loading="submitting">保存</el-button>
      </template>
    </el-dialog>

  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onBeforeUnmount } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, Search } from '@element-plus/icons-vue'
import api from '@/utils/api'
import { useAuthStore } from '@/store/auth'

const auth = useAuthStore()
const editable = computed(() => !!auth.user?.is_admin)

const items = ref<any[]>([])
const herbs = ref<any[]>([])
const suppliers = ref<any[]>([])
const searchText = ref('')
const typeFilter = ref('')
const submitting = ref(false)
const page = ref(1)
const pageSize = ref(50)
const total = ref(0)

// 后端已按 类别/搜索 过滤并分页，前端不再二次过滤
const filteredItems = computed(() => items.value)

function isLow(row: any) {
  return row.min_stock != null && row.min_stock > 0 && Number(row.total_quantity) < Number(row.min_stock)
}

const isMobile = ref(false)
function updateViewport() { isMobile.value = window.innerWidth < 768 }
onMounted(() => { updateViewport(); window.addEventListener('resize', updateViewport) })
onBeforeUnmount(() => window.removeEventListener('resize', updateViewport))

async function loadItems(resetPage = false) {
  if (resetPage) page.value = 1
  try {
    const params: any = { page: page.value, page_size: pageSize.value }
    if (typeFilter.value) params.item_type = typeFilter.value
    if (searchText.value) params.search = searchText.value
    const res = (await api.get('/stock/items', { params }) as any) || []
    // 兼容：分页接口返回 {items,total,...}；旧全量接口返回数组
    if (Array.isArray(res)) {
      items.value = res
      total.value = res.length
    } else {
      items.value = res.items || []
      total.value = res.total || 0
    }
  } catch (e: any) {
    ElMessage.error('物品加载失败：' + (e?.response?.data?.detail || e?.message || '未知错误'))
  }
}
async function loadHerbs() {
  try { herbs.value = (await api.get('/herbs') as any) || [] } catch {}
}
async function loadSuppliers() {
  try { suppliers.value = (await api.get('/stock/suppliers') as any) || [] } catch {}
}

// ── 新增 / 编辑 物品 ──
const itemVisible = ref(false)
const isEdit = ref(false)
const itemFormRef = ref()
const activeItemId = ref<number | null>(null)
const itemForm = ref({
  item_type: '中药', name: '', spec: '', unit: 'g',
  sell_price: null as number | null, min_stock: null as number | null, herb_id: null as number | null,
  default_supplier_id: null as number | null, barcode: '',
})
const itemRules = {
  item_type: [{ required: true, message: '请选择类别', trigger: 'change' }],
  name: [{ required: true, message: '请输入名称', trigger: 'blur' }],
  unit: [{ required: true, message: '请选择单位', trigger: 'change' }],
}

function openCreate() {
  isEdit.value = false
  activeItemId.value = null
  itemForm.value = { item_type: '中药', name: '', spec: '', unit: 'g', sell_price: null, min_stock: null, herb_id: null, default_supplier_id: null, barcode: '' }
  itemVisible.value = true
}
function openEdit(row: any) {
  isEdit.value = true
  activeItemId.value = row.id
  itemForm.value = {
    item_type: row.item_type, name: row.name, spec: row.spec || '', unit: row.unit,
    sell_price: row.sell_price != null ? Number(row.sell_price) : null,
    min_stock: row.min_stock != null ? Number(row.min_stock) : null,
    herb_id: row.herb_id || null, default_supplier_id: row.default_supplier_id || null,
    barcode: row.barcode || '',
  }
  itemVisible.value = true
}
async function saveItem() {
  if (!itemFormRef.value) return
  await itemFormRef.value.validate(async (valid: boolean) => {
    if (!valid) return
    submitting.value = true
    const payload = { ...itemForm.value }
    if (payload.item_type !== '中药') payload.herb_id = null
    try {
      if (isEdit.value) {
        await api.put(`/stock/items/${activeItemId.value}`, payload)
        ElMessage.success('物品已更新')
      } else {
        await api.post('/stock/items', payload)
        ElMessage.success('物品已新增')
      }
      itemVisible.value = false
      loadItems()
    } catch (e: any) {
      ElMessage.error('保存失败：' + (e?.response?.data?.detail || e?.message || '未知错误'))
    } finally {
      submitting.value = false
    }
  })
}
async function removeItem(row: any) {
  try {
    await ElMessageBox.confirm(`确认删除物品「${row.name}」？其下批次与流水将一并删除，且不可恢复。`, '删除确认', { type: 'warning' })
  } catch { return }
  try {
    await api.delete(`/stock/items/${row.id}`)
    ElMessage.success('已删除')
    loadItems()
  } catch (e: any) {
    ElMessage.error('删除失败：' + (e?.response?.data?.detail || e?.message || '未知错误'))
  }
}

onMounted(() => { loadItems(true); loadHerbs(); loadSuppliers() })
</script>

<style scoped lang="scss">
.item-manage {
  .low-stock { color: #f56c6c; font-weight: 700; }
  .mono { font-family: ui-monospace, Menlo, Consolas, monospace; font-size: 12px; color: #8a7563; }
}
.cards { display: flex; flex-direction: column; gap: 10px; }
.card {
  background: #fff; border: 1px solid #e8e0d8; border-radius: 10px; padding: 12px 14px;
  box-shadow: 0 1px 3px rgba(0,0,0,0.05);
}
.card .card-head { display: flex; align-items: center; justify-content: space-between; margin-bottom: 8px; }
.card .card-name { font-size: 17px; font-weight: 600; color: #2C1810; }
.card .card-body { display: flex; flex-direction: column; gap: 6px; }
.card .card-row { display: flex; align-items: flex-start; font-size: 14px; line-height: 1.5; }
.card .card-row .label { flex-shrink: 0; width: 54px; color: #8a7563; }
.card .card-row .value { flex: 1; color: #333; word-break: break-all; }
.card .card-actions { display: flex; justify-content: flex-end; gap: 4px; margin-top: 8px; padding-top: 8px; border-top: 1px dashed #eee; }

@media (max-width: 767px) {
  :deep(.el-form--inline .el-form-item) { display: block; margin-right: 0; margin-bottom: 8px; }
  :deep(.el-form--inline .el-form-item__content) { display: block; max-width: 100%; }
  :deep(.el-form--inline .el-input), :deep(.el-form--inline .el-select) { width: 100% !important; }
}
</style>
