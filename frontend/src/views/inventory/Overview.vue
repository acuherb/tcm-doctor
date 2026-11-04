<template>
  <div class="stock-overview">
    <!-- 预警概览 -->
    <el-card shadow="hover" class="main-card">
      <template #header>
        <div class="tcm-head">
          <div class="tcm-head__title">
            <span class="tcm-head__icon">⚠️</span>
            <span class="tcm-head__text">库存预警</span>
            <el-tag size="small" effect="light" round class="tcm-head__count">{{ alerts.length }} 项</el-tag>
          </div>
          <div class="tcm-head__actions">
            <el-tag :type="alerts.length > 0 ? 'danger' : 'success'" size="small" effect="light" round>
              {{ alerts.length > 0 ? '需处理' : '库存正常' }}
            </el-tag>
          </div>
        </div>
      </template>
      <el-empty v-if="alerts.length === 0" description="暂无预警" :image-size="60" />
      <el-table v-else-if="!isMobile" :data="pagedAlerts" class="tcm-table" size="small">
        <el-table-column prop="item_name" label="物品" min-width="140" show-overflow-tooltip />
        <el-table-column prop="item_type" label="类别" width="100">
          <template #default="{ row }">
            <span class="xw-tag" :style="chipStyleOf(row.item_type)">{{ row.item_type }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="alert_type" label="预警类型" width="120">
          <template #default="{ row }">
            <el-tag :type="row.alert_type === '近效期' ? 'warning' : row.alert_type === '高价值积压' ? 'info' : 'danger'" size="small">{{ row.alert_type }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="current_quantity" label="当前库存" width="120">
          <template #default="{ row }"><span class="low-stock">{{ row.current_quantity }} {{ row.unit }}</span></template>
        </el-table-column>
        <el-table-column prop="min_stock" label="最低库存" width="120">
          <template #default="{ row }">{{ row.min_stock != null ? row.min_stock + ' ' + row.unit : '-' }}</template>
        </el-table-column>
        <el-table-column label="附加信息" min-width="160">
          <template #default="{ row }">
            <span v-if="row.alert_type === '近效期'">效期剩 {{ row.days_to_expiry }} 天</span>
            <span v-else-if="row.alert_type === '呆滞'">静止 {{ row.last_move_days }} 天</span>
            <span v-else-if="row.alert_type === '高价值积压'">占用 ¥{{ row.stock_value?.toFixed(0) }}</span>
            <span v-else>低于最低</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="120">
          <template #default="{ row }">
            <el-button link type="primary" size="small" @click="goItems(row.item_id)">去入库</el-button>
          </template>
        </el-table-column>
      </el-table>

      <div v-if="isMobile" class="cards alert-cards">
        <div v-for="(row, i) in pagedAlerts" :key="i" class="card alert-card" :class="'alert-' + (row.alert_type === '近效期' ? 'warn' : row.alert_type === '高价值积压' ? 'info' : 'danger')">
          <div class="card-head">
            <span class="card-name">{{ row.item_name }}</span>
            <el-tag :type="row.alert_type === '近效期' ? 'warning' : row.alert_type === '高价值积压' ? 'info' : 'danger'" size="small">{{ row.alert_type }}</el-tag>
          </div>
          <div class="card-body">
            <div class="card-row"><span class="label">当前库存</span><span class="value low-stock">{{ row.current_quantity }} {{ row.unit }}</span></div>
            <div class="card-row"><span class="label">最低库存</span><span class="value">{{ row.min_stock != null ? row.min_stock + ' ' + row.unit : '-' }}</span></div>
            <div class="card-row"><span class="label">说明</span>
              <span class="value">
                <template v-if="row.alert_type === '近效期'">效期剩 {{ row.days_to_expiry }} 天</template>
                <template v-else-if="row.alert_type === '呆滞'">静止 {{ row.last_move_days }} 天</template>
                <template v-else-if="row.alert_type === '高价值积压'">占用 ¥{{ row.stock_value?.toFixed(0) }}</template>
                <template v-else>低于最低</template>
              </span>
            </div>
          </div>
          <div class="card-actions">
            <el-button link type="primary" size="small" @click="goItems(row.item_id)">去入库</el-button>
          </div>
        </div>
      </div>

      <div v-if="alerts.length > alertPageSize" class="load-more">
        <el-button size="small" :loading="alertLoadingMore" @click="loadMoreAlerts">加载更多</el-button>
        <span class="no-more">已显示 {{ pagedAlerts.length }} / {{ alerts.length }}</span>
      </div>
    </el-card>

    <!-- 库存总览 -->
    <el-card shadow="hover" class="main-card">
      <template #header>
        <div class="tcm-head">
          <div class="tcm-head__title">
            <span class="tcm-head__icon">📦</span>
            <span class="tcm-head__text">库存总览</span>
            <el-tag size="small" effect="light" round class="tcm-head__count">{{ filteredOverview.length }} 项</el-tag>
          </div>
          <div class="tcm-head__actions">
            <el-select v-model="typeFilter" placeholder="全部类别" clearable class="filter-sel" @change="loadOverview">
              <el-option label="全部" value="" />
              <el-option v-for="c in categories" :key="c.id" :label="c.name" :value="c.name">
                <span class="opt-dot" :style="{ backgroundColor: dotColorOf(c.name) }"></span>{{ c.name }}
              </el-option>
            </el-select>
            <el-checkbox v-model="alertOnly" border size="small" class="alert-check" @change="loadOverview">仅看预警</el-checkbox>
            <el-input v-model="searchText" placeholder="搜索名称" clearable class="filter-search" @clear="loadOverview" @keyup.enter="loadOverview">
              <template #prefix><el-icon><Search /></el-icon></template>
            </el-input>
            <el-button type="primary" @click="loadOverview">查询</el-button>
          </div>
        </div>
      </template>

      <div class="bulk-bar">
        <el-checkbox v-if="isMobile" class="bulk-all" :model-value="mobileAllSelected" :disabled="!pagedOverview.length" @change="toggleSelectAllMobile">
          全选
        </el-checkbox>
        <el-button type="primary" plain :disabled="!selectedList.length" @click="openBulkIn">批量入库（已选 {{ selectedList.length }}）</el-button>
        <el-button type="warning" plain :disabled="!selectedList.length" @click="openBulkCheck">批量盘点（已选 {{ selectedList.length }}）</el-button>
      </div>

      <el-table v-if="!isMobile" ref="overviewTableRef" row-key="item_id" :data="filteredOverview" class="tcm-table" style="width:100%" empty-text="暂无库存" @selection-change="onSelectionChange">
        <el-table-column type="selection" width="45" />
        <el-table-column prop="item_name" label="物品" min-width="140" show-overflow-tooltip />
        <el-table-column prop="item_type" label="类别" width="100">
          <template #default="{ row }">
            <span class="xw-tag" :style="chipStyleOf(row.item_type)">{{ row.item_type }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="unit" label="单位" width="70" />
        <el-table-column prop="total_quantity" label="当前库存" width="130">
          <template #default="{ row }">
            <span :class="{ 'low-stock': row.has_alert }">{{ row.total_quantity }} {{ row.unit }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="batch_count" label="批次数" width="90" />
        <el-table-column label="库存金额" width="120">
          <template #default="{ row }">¥{{ (row.stock_value || 0).toFixed(2) }}</template>
        </el-table-column>
        <el-table-column prop="min_stock" label="最低库存" width="110">
          <template #default="{ row }">{{ row.min_stock != null ? row.min_stock + ' ' + row.unit : '-' }}</template>
        </el-table-column>
        <el-table-column label="状态" width="90">
          <template #default="{ row }">
            <el-tag :type="row.has_alert ? 'danger' : 'success'" size="small">{{ row.has_alert ? '预警' : '正常' }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="180" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" size="small" @click="goTransactions(row.item_id)">流水</el-button>
            <el-button link type="warning" size="small" @click="goCheck(row.item_id)">盘点</el-button>
          </template>
        </el-table-column>
      </el-table>

      <!-- 移动端卡片 -->
      <div v-if="isMobile" class="cards">
        <div v-for="row in pagedOverview" :key="row.item_id" class="card">
          <div class="card-head">
            <el-checkbox :model-value="selectedIds.has(row.item_id)" @change="(v:any)=>toggleSel(row, v)" />
            <span class="card-name">{{ row.item_name }}</span>
            <span class="xw-tag" :style="categoryChipStyle(row.item_type)">{{ row.item_type }}</span>
          </div>
          <div class="card-body">
            <div class="card-row"><span class="label">库存</span>
              <span class="value" :class="{ 'low-stock': row.has_alert }">{{ row.total_quantity }} {{ row.unit }}（{{ row.batch_count }} 批）</span>
            </div>
            <div class="card-row"><span class="label">金额</span><span class="value">¥{{ (row.stock_value || 0).toFixed(2) }}</span></div>
            <div class="card-row"><span class="label">最低</span><span class="value">{{ row.min_stock != null ? row.min_stock + row.unit : '-' }}</span></div>
          </div>
          <div class="card-actions">
            <el-button link type="primary" size="small" @click="goTransactions(row.item_id)">流水</el-button>
            <el-button link type="warning" size="small" @click="goCheck(row.item_id)">盘点</el-button>
          </div>
        </div>
        <el-empty v-if="!filteredOverview.length" description="暂无库存" />
      </div>

      <div v-if="filteredOverview.length > overviewPageSize" class="load-more">
        <el-button size="small" :loading="overviewLoadingMore" @click="loadMoreOverview">加载更多</el-button>
        <span class="no-more">已显示 {{ pagedOverview.length }} / {{ filteredOverview.length }}</span>
      </div>
    </el-card>

    <!-- 批量入库 -->
    <el-dialog v-model="bulkInVisible" title="📥 批量入库" width="760px" destroy-on-close>
      <div style="margin-bottom:10px;color:#8a7563;font-size:13px">已选 {{ bulkInItems.length }} 项；单位为各物品自身单位，进价按「元/单位」。下方(供应商/采购日期/有效期)对本次所有物品统一生效。</div>
      <div style="margin-bottom:12px;display:flex;flex-wrap:wrap;gap:14px;align-items:flex-end">
        <div>
          <div style="font-size:12px;color:#8a7563;margin-bottom:4px">供应商</div>
          <el-select v-model="bulkInSupplier" filterable clearable placeholder="可选" style="width:200px">
            <el-option v-for="s in supplierOptions" :key="s.id" :label="s.name" :value="s.id" />
          </el-select>
        </div>
        <div>
          <div style="font-size:12px;color:#8a7563;margin-bottom:4px">采购日期</div>
          <el-date-picker v-model="bulkInPurchaseDate" type="date" value-format="YYYY-MM-DD" placeholder="采购日期" style="width:170px" />
        </div>
        <div>
          <div style="font-size:12px;color:#8a7563;margin-bottom:4px">有效期至</div>
          <el-date-picker v-model="bulkInExpiry" type="date" value-format="YYYY-MM-DD" placeholder="可选" style="width:170px" />
        </div>
      </div>
      <el-table :data="bulkInItems" max-height="420" border>
        <el-table-column label="物品" min-width="160">
          <template #default="{ row }">{{ row.item_name }}（{{ row.unit }}）</template>
        </el-table-column>
        <el-table-column label="当前库存" width="110">
          <template #default="{ row }">{{ row.total_quantity }} {{ row.unit }}</template>
        </el-table-column>
        <el-table-column label="入库数量" width="150">
          <template #default="{ row }"><el-input-number v-model="row.qty" :min="0" :precision="2" style="width:100%" /></template>
        </el-table-column>
        <el-table-column label="进价(元/单位)" width="170">
          <template #default="{ row }"><el-input-number v-model="row.unit_price" :min="0" :precision="2" :controls="false" style="width:100%" /></template>
        </el-table-column>
      </el-table>
      <template #footer>
        <el-button @click="bulkInVisible = false">取消</el-button>
        <el-button @click="fillToMin">一键补齐到最低库存</el-button>
        <el-button type="primary" :loading="bulkSubmitting" @click="submitBulkIn">确认入库</el-button>
      </template>
    </el-dialog>

    <!-- 批量盘点（按物品） -->
    <el-dialog v-model="bulkCheckVisible" title="📋 批量盘点" width="760px" destroy-on-close>
      <div style="margin-bottom:10px;color:#8a7563;font-size:13px">已选 {{ bulkCheckItems.length }} 项；填写实盘总数，系统按差额自动调账（盘盈入库 / 盘亏扣减），不暴露批次。</div>
      <div style="margin-bottom:12px">
        <div style="font-size:12px;color:#8a7563;margin-bottom:4px">盘点说明（可选，记到每条流水备注）</div>
        <el-input v-model="bulkCheckNote" type="textarea" :rows="2" placeholder="如：月度盘点 / 报损原因" style="width:100%" />
      </div>
      <el-table :data="bulkCheckItems" max-height="420" border>
        <el-table-column label="物品" min-width="160">
          <template #default="{ row }">{{ row.item_name }}（{{ row.unit }}）</template>
        </el-table-column>
        <el-table-column label="账面库存" width="120">
          <template #default="{ row }">{{ row.total_quantity }} {{ row.unit }}</template>
        </el-table-column>
        <el-table-column label="实盘数量" width="190">
          <template #default="{ row }"><el-input-number v-model="row.counted" :min="0" :precision="2" style="width:100%" /></template>
        </el-table-column>
      </el-table>
      <template #footer>
        <el-button @click="bulkCheckVisible = false">取消</el-button>
        <el-button type="primary" :loading="bulkSubmitting" @click="submitBulkCheck">确认盘点</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onBeforeUnmount } from 'vue'
import { useRouter } from 'vue-router'
import { Search } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import api from '@/utils/api'
import type { StockOption } from '@/types'
import { useStockOptionColors } from '@/utils/dictColors'

const { categoryChipStyle, categoryColor, stockOptionVersion } = useStockOptionColors()

// 读取选项版本号，使类别标签色在「库存选项」改自定义色后即时重算
function chipStyleOf(name: string) {
  void stockOptionVersion.value
  return categoryChipStyle(name)
}

// 下拉色点只需要纯色值，不能直接给 categoryChipStyle 的复合样式
function dotColorOf(name: string) {
  void stockOptionVersion.value
  return categoryColor(name)
}

const router = useRouter()
const overview = ref<any[]>([])
const alerts = ref<any[]>([])
const typeFilter = ref('')
const alertOnly = ref(false)
const searchText = ref('')
const categories = ref<any[]>([])
async function loadOptions() {
  try {
    const res = (await api.get<StockOption[]>('/stock/options')) || []
    categories.value = res.filter((o: any) => o.opt_type === 'category')
  } catch {}
}

const filteredOverview = computed(() => {
  let list = overview.value
  if (searchText.value) {
    const s = searchText.value.toLowerCase()
    list = list.filter((o: any) => (o.item_name || '').toLowerCase().includes(s))
  }
  return list
})

const overviewPageSize = 20
const overviewShown = ref(overviewPageSize)
const overviewLoadingMore = ref(false)
const pagedOverview = computed(() => filteredOverview.value.slice(0, overviewShown.value))
async function loadMoreOverview() {
  if (overviewLoadingMore.value || overviewShown.value >= filteredOverview.value.length) return
  overviewLoadingMore.value = true
  await new Promise((r) => setTimeout(r, 120))
  overviewShown.value = Math.min(overviewShown.value + overviewPageSize, filteredOverview.value.length)
  overviewLoadingMore.value = false
}

const alertPageSize = 20
const alertShown = ref(alertPageSize)
const alertLoadingMore = ref(false)
const pagedAlerts = computed(() => alerts.value.slice(0, alertShown.value))
async function loadMoreAlerts() {
  if (alertLoadingMore.value || alertShown.value >= alerts.value.length) return
  alertLoadingMore.value = true
  // 轻微延迟让按钮有反馈，纯前端切片无需请求后端
  await new Promise((r) => setTimeout(r, 120))
  alertShown.value = Math.min(alertShown.value + alertPageSize, alerts.value.length)
  alertLoadingMore.value = false
}

const isMobile = ref(false)
function updateViewport() { isMobile.value = window.innerWidth < 768 }
onMounted(() => {
  updateViewport()
  window.addEventListener('resize', updateViewport)
  loadOverview(); loadAlerts(); loadOptions()
})
onBeforeUnmount(() => window.removeEventListener('resize', updateViewport))

async function loadOverview() {
  try {
    const params: Record<string, unknown> = {}
    if (typeFilter.value) params.item_type = typeFilter.value
    if (alertOnly.value) params.alert_only = true
    if (searchText.value) params.search = searchText.value
    overview.value = (await api.get<Record<string, unknown>>('/stock/overview', { params })) || {}
    overviewShown.value = overviewPageSize
  } catch (e: any) {
    console.error(e)
  }
}
async function loadAlerts() {
  try {
    alerts.value = (await api.get<Array<Record<string, unknown>>>('/stock/alerts')) || []
    alertShown.value = alertPageSize
  } catch {}
}

function goItems(id: number) { router.push({ path: '/stock/transactions', query: { item_id: String(id), open: 'in' } }) }
function goTransactions(id: number) { router.push({ path: '/stock/transactions', query: { item_id: String(id) } }) }
function goCheck(id: number) { router.push({ path: '/stock/check', query: { item_id: String(id) } }) }

// ── 批量操作（勾选 → 批量入库 / 批量盘点）──
const overviewTableRef = ref()
const selectedRows = ref<any[]>([])
const selectedIds = ref<Set<number>>(new Set())
function onSelectionChange(rows: any[]) { selectedRows.value = rows }
function toggleSel(row: any, val: boolean) {
  const s = new Set(selectedIds.value)
  if (val) s.add(row.item_id); else s.delete(row.item_id)
  selectedIds.value = s
}
// 移动端全选：仅作用于当前已加载（分页展示）的卡片，避免选中未加载项
const mobileAllSelected = computed(() =>
  pagedOverview.value.length > 0 && pagedOverview.value.every((o: any) => selectedIds.value.has(o.item_id))
)
function toggleSelectAllMobile(val: boolean) {
  const s = new Set(selectedIds.value)
  pagedOverview.value.forEach((o: any) => {
    if (val) s.add(o.item_id); else s.delete(o.item_id)
  })
  selectedIds.value = s
}
// 桌面端走表格勾选(selectedRows)，移动端走卡片勾选(selectedIds)，统一出口
const selectedList = computed(() =>
  isMobile.value
    ? overview.value.filter((o: any) => selectedIds.value.has(o.item_id))
    : selectedRows.value
)
function clearSelection() {
  selectedRows.value = []
  selectedIds.value = new Set()
  overviewTableRef.value?.clearSelection()
}

const bulkInVisible = ref(false)
const bulkInItems = ref<any[]>([])
const bulkInSupplier = ref<number | undefined>(undefined)
const bulkInPurchaseDate = ref<string>('')
const bulkInExpiry = ref<string>('')
const supplierOptions = ref<any[]>([])
const bulkCheckVisible = ref(false)
const bulkCheckItems = ref<any[]>([])
const bulkCheckNote = ref<string>('')
const bulkSubmitting = ref(false)

function todayStr(): string {
  const d = new Date()
  const p = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`
}

async function loadSuppliers() {
  try {
    const r = await api.get('/stock/suppliers')
    supplierOptions.value = Array.isArray(r.data) ? r.data : (r.data?.items || [])
  } catch { supplierOptions.value = [] }
}

function openBulkIn() {
  bulkInItems.value = selectedList.value.map((o: any) => ({
    item_id: o.item_id, item_name: o.item_name, unit: o.unit,
    total_quantity: o.total_quantity, min_stock: o.min_stock,
    qty: 0, unit_price: null,
  }))
  bulkInSupplier.value = undefined
  bulkInPurchaseDate.value = todayStr()
  bulkInExpiry.value = ''
  loadSuppliers()
  bulkInVisible.value = true
}
function fillToMin() {
  bulkInItems.value.forEach((it: any) => {
    const min = Number(it.min_stock || 0)
    it.qty = Math.max(0, +(min - Number(it.total_quantity)).toFixed(2))
  })
}
async function submitBulkIn() {
  const payload = bulkInItems.value
    .filter((it: any) => it.qty && it.qty > 0)
    .map((it: any) => ({
      item_id: it.item_id, quantity: it.qty, unit_price: it.unit_price,
      supplier_id: bulkInSupplier.value,
      purchase_date: bulkInPurchaseDate.value || undefined,
      expiry_date: bulkInExpiry.value || undefined,
      note: '批量入库',
    }))
  if (!payload.length) { ElMessage.warning('请至少填写一项入库数量'); return }
  bulkSubmitting.value = true
  try {
    await api.post('/stock/batches/in/bulk', payload)
    ElMessage.success(`批量入库成功（${payload.length} 项）`)
    bulkInVisible.value = false
    clearSelection()
    loadOverview()
  } catch (e: any) {
    ElMessage.error('批量入库失败：' + (e?.response?.data?.detail || e?.message || '未知错误'))
  } finally { bulkSubmitting.value = false }
}

async function openBulkCheck() {
  bulkCheckItems.value = selectedList.value.map((o: any) => ({
    item_id: o.item_id, item_name: o.item_name, unit: o.unit,
    total_quantity: o.total_quantity, counted: Number(o.total_quantity),
  }))
  bulkCheckNote.value = ''
  bulkCheckVisible.value = true
}
async function submitBulkCheck() {
  const payload = bulkCheckItems.value.map((it: any) => ({ item_id: it.item_id, counted: it.counted, note: bulkCheckNote.value || '批量盘点' }))
  bulkSubmitting.value = true
  try {
    await api.post('/stock/adjust/bulk', payload)
    ElMessage.success(`批量盘点成功（${payload.length} 项）`)
    bulkCheckVisible.value = false
    clearSelection()
    loadOverview()
  } catch (e: any) {
    ElMessage.error('批量盘点失败：' + (e?.response?.data?.detail || e?.message || '未知错误'))
  } finally { bulkSubmitting.value = false }
}
</script>

<style scoped lang="scss">
.stock-overview {
  display: flex;
  flex-direction: column;
  gap: 16px;

  .main-card {
    border-radius: 12px;
    border: 1px solid #f0e4d6;

    :deep(.el-card__header) {
      padding: 0;
      border-bottom: none;
    }
  }

  .filter-sel { width: 130px; }
  .filter-search { width: 170px; }
  .alert-check { margin: 0; }

  .bulk-bar {
    display: flex;
    gap: 8px;
    justify-content: flex-end;
    margin-bottom: 12px;
    flex-wrap: wrap;
  }

  .bulk-all { margin-right: auto; height: 32px; }

  .low-stock { color: #b5624f; font-weight: 700; font-variant-numeric: tabular-nums; }
}
.xw-tag {
  display: inline-block;
  padding: 2px 12px;
  font-size: 13px;
  line-height: 22px;
  border: 1px solid;
  border-radius: 4px;
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

.alert-card { border-left-width: 4px; border-left-style: solid; }
.alert-card.alert-danger { border-left-color: #c0764f; background: #fdf6f3; }
.alert-card.alert-warn { border-left-color: #c2a06a; background: #fdfaf3; }
.alert-card.alert-info { border-left-color: #a9a09a; background: #faf9f8; }

.load-more {
  display: flex; flex-direction: column; align-items: center; gap: 6px; padding: 14px 0 2px;
}
.load-more .el-button { min-width: 140px; }
.load-more .no-more { font-size: 12px; color: #a08b76; font-variant-numeric: tabular-nums; }
</style>