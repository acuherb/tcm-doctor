<template>
  <div class="item-manage">
    <!-- 顶部操作栏 -->
    <el-card shadow="hover" class="main-card">
      <template #header>
        <div class="tcm-head">
          <div class="tcm-head__title">
            <span class="tcm-head__icon">📋</span>
            <span class="tcm-head__text">物品管理</span>
            <el-tag size="small" effect="light" round class="tcm-head__count">{{ filteredItems.length }} 项</el-tag>
          </div>
          <div class="tcm-head__actions">
            <el-select v-model="typeFilter" placeholder="全部类别" clearable class="filter-sel" @change="loadItems(true)">
              <el-option label="全部" value="" />
              <el-option v-for="c in categories" :key="c.id" :label="c.name" :value="c.name">
                <span class="opt-dot" :style="{ backgroundColor: categoryColor(c.name) }" />{{ c.name }}
              </el-option>
            </el-select>
            <el-button v-if="editable" type="primary" @click="openCreate">
              <el-icon><Plus /></el-icon> 新增物品
            </el-button>
          </div>
        </div>
      </template>

      <div class="tcm-filter">
        <el-input v-model="searchText" placeholder="搜索名称/规格/条码" clearable class="filter-search" @clear="loadItems(true)">
          <template #prefix><el-icon><Search /></el-icon></template>
        </el-input>
        <div class="filter-actions">
          <el-button type="primary" @click="loadItems(true)">查询</el-button>
        </div>
      </div>

      <el-table v-if="!isMobile" class="tcm-table" :data="filteredItems" style="width:100%" empty-text="暂无物品">
        <el-table-column prop="item_type" label="类别" width="110">
          <template #default="{ row }">
            <span class="xw-tag" :style="categoryChipStyle(row.item_type)">{{ row.item_type }}</span>
          </template>
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
            <span class="xw-tag" :style="categoryChipStyle(row.item_type)">{{ row.item_type }}</span>
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

      <div v-if="isMobile && total > 0" class="load-more">
        <el-button v-if="items.length < total" size="small" :loading="loadingMore" @click="loadMoreItems">加载更多</el-button>
        <span v-else class="no-more">已加载全部 {{ total }} 条</span>
      </div>

      <el-pagination
        v-if="!isMobile && total > pageSize"
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
          <el-select v-model="itemForm.item_type" filterable style="width:100%">
            <el-option v-for="c in categories" :key="c.id" :label="c.name" :value="c.name">
              <span class="opt-dot" :style="{ backgroundColor: categoryColor(c.name) }" />{{ c.name }}
            </el-option>
          </el-select>
        </el-form-item>
        <el-form-item label="名称" prop="name">
          <el-input v-model="itemForm.name" placeholder="如：黄芪 / 一次性针灸针" />
        </el-form-item>
        <el-form-item label="规格">
          <el-input v-model="itemForm.spec" placeholder="如：0.30×40mm / 五年陈" />
        </el-form-item>
        <el-form-item label="计量单位" prop="unit">
          <el-select v-model="itemForm.unit" filterable style="width:100%">
            <el-option v-for="u in units" :key="u.id" :label="u.name" :value="u.name" />
          </el-select>
        </el-form-item>
        <el-form-item label="默认售价">
          <div style="display:flex;align-items:center;gap:8px;width:100%">
            <el-input-number v-model="itemForm.sell_price" :min="0" :precision="2" :controls="false" style="flex:1" />
            <span style="white-space:nowrap;color:#8a7563;font-size:13px;flex-shrink:0">元/{{ itemForm.unit }}</span>
          </div>
        </el-form-item>
        <el-form-item label="最低库存">
          <div style="display:flex;align-items:center;gap:8px;width:100%">
            <el-input-number v-model="itemForm.min_stock" :min="0" :precision="1" :controls="false" style="flex:1" />
            <span style="white-space:nowrap;color:#8a7563;font-size:13px;flex-shrink:0">{{ itemForm.unit }}</span>
          </div>
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
import api, { errMsg } from '@/utils/api'
import { useAuthStore } from '@/store/auth'
import type { StockItem, Herb, Supplier, Paginated, StockOption } from '@/types'
import { useStockOptionColors } from '@/utils/dictColors'

const { categoryColor, categoryChipStyle } = useStockOptionColors()

const auth = useAuthStore()
const editable = computed(() => auth.canWrite('stock'))

const items = ref<StockItem[]>([])
const herbs = ref<Herb[]>([])
const suppliers = ref<Supplier[]>([])
const searchText = ref('')
const typeFilter = ref('')
const submitting = ref(false)
const page = ref(1)
const pageSize = ref(50)
const total = ref(0)

// 后端已按 类别/搜索 过滤并分页，前端不再二次过滤
const filteredItems = computed(() => items.value)

function isLow(row: StockItem) {
  return row.min_stock != null && row.min_stock > 0 && Number(row.total_quantity) < Number(row.min_stock)
}

const isMobile = ref(false)
const loadingMore = ref(false)
function updateViewport() { isMobile.value = window.innerWidth < 768 }
onMounted(() => { updateViewport(); window.addEventListener('resize', updateViewport) })
onBeforeUnmount(() => window.removeEventListener('resize', updateViewport))

async function loadItems(resetPage = false) {
  if (resetPage) { page.value = 1; loadingMore.value = false }
  try {
    const params: Record<string, unknown> = { page: page.value, page_size: pageSize.value }
    if (typeFilter.value) params.item_type = typeFilter.value
    if (searchText.value) params.search = searchText.value
    const res = (await api.get<Paginated<StockItem>>('/stock/items', { params })) || []
    // 兼容：分页接口返回 {items,total,...}；旧全量接口返回数组
    if (Array.isArray(res)) {
      items.value = res
      total.value = res.length
    } else {
      items.value = res.items || []
      total.value = res.total || 0
    }
  } catch (e) {
    ElMessage.error('物品加载失败：' + errMsg(e))
  }
}
async function loadMoreItems() {
  if (loadingMore.value || items.value.length >= total.value) return
  loadingMore.value = true
  try {
    const next = page.value + 1
    const params: Record<string, unknown> = { page: next, page_size: pageSize.value }
    if (typeFilter.value) params.item_type = typeFilter.value
    if (searchText.value) params.search = searchText.value
    const res = (await api.get<Paginated<StockItem>>('/stock/items', { params })) || []
    const rows = Array.isArray(res) ? res : (res.items || [])
    const seen = new Set(items.value.map((r: StockItem) => r.id))
    items.value.push(...rows.filter((r: StockItem) => !seen.has(r.id)))
    page.value = next
  } catch (e) {
    ElMessage.error('加载失败：' + errMsg(e))
  } finally { loadingMore.value = false }
}
async function loadHerbs() {
  try { herbs.value = (await api.get<Herb[]>('/herbs')) || [] } catch {}
}
async function loadSuppliers() {
  try { suppliers.value = (await api.get<Supplier[]>('/stock/suppliers')) || [] } catch {}
}

// 物品类别 / 计量单位 改为从「库存选项」表读取（受控，可在界面增删，不再硬编码）
const categories = ref<StockOption[]>([])
const units = ref<StockOption[]>([])
async function loadOptions() {
  try {
    const res = (await api.get<StockOption[]>('/stock/options')) || []
    categories.value = res.filter((o: StockOption) => o.opt_type === 'category')
    units.value = res.filter((o: StockOption) => o.opt_type === 'unit')
  } catch {}
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
function openEdit(row: StockItem) {
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
    } catch (e) {
      ElMessage.error('保存失败：' + errMsg(e))
    } finally {
      submitting.value = false
    }
  })
}
async function removeItem(row: StockItem) {
  try {
    await ElMessageBox.confirm(`确认删除物品「${row.name}」？其下批次与流水将一并删除，且不可恢复。`, '删除确认', { type: 'warning' })
  } catch { return }
  try {
    await api.delete(`/stock/items/${row.id}`)
    ElMessage.success('已删除')
    loadItems()
  } catch (e) {
    ElMessage.error('删除失败：' + errMsg(e))
  }
}

onMounted(() => { loadItems(true); loadHerbs(); loadSuppliers(); loadOptions() })
</script>

<style scoped lang="scss">
.item-manage {
  .main-card {
    border-radius: 12px;
    border: 1px solid #f0e4d6;

    :deep(.el-card__header) {
      padding: 0;
      border-bottom: none;
    }
  }

  .filter-sel { width: 140px; }
  .filter-search { width: 240px; }
  .filter-actions { display: flex; gap: 8px; }

  .low-stock { color: #b5624f; font-weight: 700; font-variant-numeric: tabular-nums; }
  .mono { font-family: ui-monospace, Menlo, Consolas, monospace; font-size: 12px; color: #8a7563; }
}
.xw-tag {
  display: inline-block;
  padding: 0 8px;
  font-size: 12px;
  line-height: 20px;
  border: 1px solid;
  border-radius: 10px;
  white-space: nowrap;
}
.opt-dot {
  display: inline-block;
  width: 8px;
  height: 8px;
  border-radius: 50%;
  margin-right: 6px;
  vertical-align: middle;
}
.cards { display: flex; flex-direction: column; gap: 10px; }
.card {
  background: #fff; border: 1px solid #f0e4d6; border-radius: 10px; padding: 12px 14px;
  box-shadow: 0 1px 3px rgba(44,24,16,.04);
}
.card .card-head { display: flex; align-items: center; justify-content: space-between; margin-bottom: 8px; gap: 8px; }
.card .card-name { font-size: 16px; font-weight: 600; color: #2c1810; }
.card .card-body { display: flex; flex-direction: column; gap: 6px; }
.card .card-row { display: flex; align-items: flex-start; font-size: 14px; line-height: 1.5; }
.card .card-row .label { flex-shrink: 0; width: 54px; color: #8a7563; }
.card .card-row .value { flex: 1; color: #4a3628; word-break: break-all; }
.card .card-actions { display: flex; justify-content: flex-end; gap: 4px; margin-top: 8px; padding-top: 8px; border-top: 1px dashed #f0e4d6; }

.load-more { display: flex; flex-direction: column; align-items: center; gap: 6px; padding: 14px 0 2px; }
.load-more .el-button { min-width: 140px; }
.load-more .no-more { font-size: 12px; color: #a08b76; font-variant-numeric: tabular-nums; }
</style>