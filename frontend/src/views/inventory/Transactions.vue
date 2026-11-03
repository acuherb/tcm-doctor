<template>
  <div class="stock-txn">
    <el-card shadow="hover" class="main-card">
      <template #header>
        <div class="tcm-head">
          <div class="tcm-head__title">
            <span class="tcm-head__icon">🔄</span>
            <span class="tcm-head__text">库存流水</span>
            <el-tag size="small" effect="light" round class="tcm-head__count">{{ total }} 条</el-tag>
          </div>
          <div class="tcm-head__actions">
            <el-button v-if="editable" @click="openStockIn"
              title="零星到货 / 期初建账 / 库存调账登记（向供应商批量采购请走「采购入库」）">
              <el-icon><Upload /></el-icon> 手动入库
            </el-button>
            <el-button v-if="editable" type="warning" plain @click="openStockOut">
              <el-icon><Download /></el-icon> 出库
            </el-button>
            <el-button v-if="editable" type="danger" plain @click="openStockWriteoff">
              <el-icon><Delete /></el-icon> 报损
            </el-button>
          </div>
        </div>
      </template>

      <div class="tcm-filter">
        <el-select v-model="typeFilter" placeholder="全部类型" clearable class="filter-mini" @change="loadTransactions">
          <el-option label="全部" value="" />
          <el-option label="入库" value="入库" />
          <el-option label="出库" value="出库" />
          <el-option label="盘点" value="盘点" />
          <el-option label="调整" value="调整" />
          <el-option label="报损" value="损耗" />
        </el-select>
        <el-select v-model="refFilter" placeholder="全部来源" clearable class="filter-mini" @change="loadTransactions">
          <el-option label="全部" value="" />
          <el-option label="手动" value="手动" />
          <el-option label="处方" value="处方" />
          <el-option label="盘点" value="盘点" />
        </el-select>
        <el-input v-model="searchText" placeholder="按物品名称搜索" clearable class="filter-search" @clear="loadTransactions(true)">
          <template #prefix><el-icon><Search /></el-icon></template>
        </el-input>
        <div class="filter-actions">
          <el-button type="primary" @click="loadTransactions(true)">查询</el-button>
        </div>
      </div>

      <el-table v-if="!isMobile" :data="transactions" class="tcm-table" style="width:100%" empty-text="暂无流水">
        <el-table-column prop="created_at" label="时间" width="160" class-name="tcm-num" />
        <el-table-column prop="item_name" label="物品" min-width="130" show-overflow-tooltip />
        <el-table-column prop="transaction_type" label="类型" width="90">
          <template #default="{ row }">
            <el-tag :type="typeTag(row.transaction_type)" size="small">{{ row.transaction_type }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="quantity" label="变动量" width="110">
          <template #default="{ row }">
            <span :class="row.transaction_type === '出库' ? 'out-qty' : 'in-qty'">
              {{ row.transaction_type === '出库' ? '-' : '+' }}{{ row.quantity }} {{ row.unit }}
            </span>
          </template>
        </el-table-column>
        <el-table-column prop="before_quantity" label="变动前" width="100">
          <template #default="{ row }">{{ row.before_quantity != null ? row.before_quantity + ' ' + row.unit : '-' }}</template>
        </el-table-column>
        <el-table-column prop="after_quantity" label="变动后" width="100">
          <template #default="{ row }">{{ row.after_quantity != null ? row.after_quantity + ' ' + row.unit : '-' }}</template>
        </el-table-column>
        <el-table-column prop="batch_number" label="批号" width="120">
          <template #default="{ row }">{{ row.batch_number || '-' }}</template>
        </el-table-column>
        <el-table-column label="成本金额" width="120">
          <template #default="{ row }">
            <span v-if="row.cost_amount != null" :class="Number(row.cost_amount) < 0 ? 'out-qty' : 'in-qty'">
              {{ Number(row.cost_amount) < 0 ? '-' : '' }}¥{{ Math.abs(Number(row.cost_amount)).toFixed(2) }}
            </span>
            <span v-else>-</span>
          </template>
        </el-table-column>
        <el-table-column label="收入金额" width="120">
          <template #default="{ row }">
            <span v-if="row.revenue_amount != null && Number(row.revenue_amount) > 0" class="in-qty">¥{{ Number(row.revenue_amount).toFixed(2) }}</span>
            <span v-else>-</span>
          </template>
        </el-table-column>
        <el-table-column prop="reference_type" label="来源" width="90">
          <template #default="{ row }"><el-tag size="small" type="info">{{ row.reference_type || '-' }}</el-tag></template>
        </el-table-column>
        <el-table-column prop="operator" label="操作人" width="90" />
        <el-table-column prop="note" label="备注" min-width="120" show-overflow-tooltip />
      </el-table>

      <div v-if="isMobile" class="cards">
        <div v-for="row in transactions" :key="row.id" class="card">
          <div class="card-head">
            <span class="card-name">{{ row.item_name }}</span>
            <el-tag :type="typeTag(row.transaction_type)" size="small">{{ row.transaction_type }}</el-tag>
          </div>
          <div class="card-body">
            <div class="card-row"><span class="label">变动</span>
              <span class="value" :class="row.transaction_type === '出库' ? 'out-qty' : 'in-qty'">
                {{ row.transaction_type === '出库' ? '-' : '+' }}{{ row.quantity }} {{ row.unit }}（前{{ row.before_quantity ?? '-' }}→后{{ row.after_quantity ?? '-' }} {{ row.unit }}）
              </span>
            </div>
            <div class="card-row"><span class="label">批号</span><span class="value">{{ row.batch_number || '-' }}</span></div>
            <div class="card-row" v-if="row.cost_amount != null"><span class="label">成本</span><span class="value" :class="Number(row.cost_amount) < 0 ? 'out-qty' : 'in-qty'">{{ Number(row.cost_amount) < 0 ? '-' : '+' }}¥{{ Math.abs(Number(row.cost_amount)).toFixed(2) }}</span></div>
            <div class="card-row" v-if="row.revenue_amount != null && Number(row.revenue_amount) > 0"><span class="label">收入</span><span class="value in-qty">¥{{ Number(row.revenue_amount).toFixed(2) }}</span></div>
            <div class="card-row"><span class="label">来源</span><span class="value">{{ row.reference_type || '-' }} / {{ row.operator || '-' }} / {{ row.created_at }}</span></div>
            <div class="card-row" v-if="row.note"><span class="label">备注</span><span class="value">{{ row.note }}</span></div>
          </div>
        </div>
        <el-empty v-if="!transactions.length" description="暂无流水" />
      </div>

      <div v-if="isMobile && total > 0" class="load-more">
        <el-button v-if="transactions.length < total" size="small" :loading="loadingMore" @click="loadMoreTransactions">加载更多</el-button>
        <span v-else class="no-more">已加载全部 {{ total }} 条</span>
      </div>

      <el-pagination
        v-if="!isMobile && total > pageSize"
        style="margin-top:14px;justify-content:center;"
        layout="total, prev, pager, next"
        :total="total" :page-size="pageSize" :current-page="page"
        @current-change="(p: number) => { page = p; loadTransactions() }"
      />
    </el-card>

    <!-- 入库对话框 -->
    <el-dialog v-model="stockInVisible" title="📥 手动入库" width="520px" destroy-on-close>
      <el-form :model="stockInForm" label-width="92px" :rules="stockInRules" ref="stockInFormRef">
        <el-form-item label="物品" prop="item_id">
          <el-select v-model="stockInForm.item_id" filterable placeholder="搜索物品" style="width:100%" @change="onItemSelect">
            <el-option v-for="i in items" :key="i.id" :label="`${i.name}（${i.unit}）`" :value="i.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="入库量" prop="quantity">
          <div style="display:flex;align-items:center;gap:8px;width:100%">
            <el-input-number v-model="stockInForm.quantity" :min="0.01" :precision="2" style="flex:1" />
            <span style="white-space:nowrap;color:#8a7563;font-size:13px;flex-shrink:0">{{ stockInUnit || '（选物品后显示）' }}</span>
          </div>
        </el-form-item>
        <el-row :gutter="12">
          <el-col :span="12">
            <el-form-item label="进价">
              <div style="display:flex;align-items:center;gap:8px;width:100%">
                <el-input-number v-model="stockInForm.unit_price" :min="0" :precision="2" :controls="false" style="flex:1" />
                <span style="white-space:nowrap;color:#8a7563;font-size:13px;flex-shrink:0">{{ stockInUnit ? '元/' + stockInUnit : '（选物品后显示）' }}</span>
              </div>
              <div v-if="stockInAmount" style="font-size:12px;color:#8a7563;margin-top:4px">合计金额：¥{{ stockInAmount }}</div>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="供应商">
              <el-select v-model="stockInForm.supplier_id" filterable clearable placeholder="选供应商" style="width:100%">
                <el-option v-for="s in suppliers" :key="s.id" :label="s.name" :value="s.id" />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item label="批号">
          <el-input v-model="stockInForm.batch_number" placeholder="留空则按当天日期" />
        </el-form-item>
        <el-row :gutter="12">
          <el-col :span="12">
            <el-form-item label="购入日期">
              <el-date-picker v-model="stockInForm.purchase_date" type="date" value-format="YYYY-MM-DD" placeholder="选择日期" style="width:100%" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="有效期">
              <el-date-picker v-model="stockInForm.expiry_date" type="date" value-format="YYYY-MM-DD" placeholder="选择日期" style="width:100%" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item label="备注">
          <el-input v-model="stockInForm.note" type="textarea" :rows="2" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="stockInVisible = false">取消</el-button>
        <el-button type="primary" @click="submitStockIn" :loading="submitting">确认入库</el-button>
      </template>
    </el-dialog>

    <!-- 出库对话框 -->
    <el-dialog v-model="stockOutVisible" title="📤 出库" width="500px" destroy-on-close>
      <el-form :model="stockOutForm" label-width="92px" :rules="stockOutRules" ref="stockOutFormRef">
        <el-form-item label="物品" prop="item_id">
          <el-select v-model="stockOutForm.item_id" filterable placeholder="搜索物品" style="width:100%" @change="onOutItemSelect">
            <el-option v-for="i in items" :key="i.id" :label="`${i.name}（${i.unit}）`" :value="i.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="当前库存">
          <span style="color:var(--tcm-primary);font-weight:600;">{{ outAvailable }} {{ outUnit }}</span>
        </el-form-item>
        <el-form-item label="指定批次">
          <el-select v-model="stockOutForm.batch_id" clearable placeholder="留空则按 FIFO 顺序扣减" style="width:100%">
            <el-option v-for="b in outBatches" :key="b.id" :label="`${b.batch_number || '批' + b.id}（余 ${b.quantity} ${outUnit}）`" :value="b.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="出库量" prop="quantity">
          <el-input-number v-model="stockOutForm.quantity" :min="0.01" :precision="2" style="width:100%" />
        </el-form-item>
        <el-form-item label="出库价格">
          <div style="display:flex;align-items:center;gap:8px;width:100%">
            <el-input-number v-model="stockOutForm.unit_price" :min="0" :precision="2" :controls="false" style="flex:1" />
            <span style="color:#8a7563;font-size:13px;white-space:nowrap">元/{{ outUnit || '单位' }}</span>
          </div>
          <div style="font-size:12px;color:#8a7563;margin-top:2px">0 或留空 = 赠送/内部领用（仅记去向，不计收入）；填价 = 销售（记收入）</div>
        </el-form-item>
        <el-form-item label="备注/去向">
          <el-input v-model="stockOutForm.note" type="textarea" :rows="2" placeholder="出库原因 / 去向，如：卖给张三 / 赠送 / 样品" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="stockOutVisible = false">取消</el-button>
        <el-button type="primary" @click="submitStockOut" :loading="submitting">确认出库</el-button>
      </template>
    </el-dialog>

    <!-- 报损对话框 -->
    <el-dialog v-model="writeoffVisible" title="🗑 报损/核销" width="500px" destroy-on-close>
      <el-form :model="writeoffForm" label-width="92px" :rules="stockOutRules" ref="writeoffFormRef">
        <el-form-item label="物品" prop="item_id">
          <el-select v-model="writeoffForm.item_id" filterable placeholder="搜索物品" style="width:100%" @change="onOutItemSelect">
            <el-option v-for="i in items" :key="i.id" :label="`${i.name}（${i.unit}）`" :value="i.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="当前库存">
          <span style="color:var(--tcm-primary);font-weight:600;">{{ outAvailable }} {{ outUnit }}</span>
        </el-form-item>
        <el-form-item label="指定批次">
          <el-select v-model="writeoffForm.batch_id" clearable placeholder="留空则按 FIFO 顺序扣减" style="width:100%">
            <el-option v-for="b in outBatches" :key="b.id" :label="`${b.batch_number || '批' + b.id}（余 ${b.quantity} ${outUnit}）`" :value="b.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="报损量" prop="quantity">
          <el-input-number v-model="writeoffForm.quantity" :min="0.01" :precision="2" style="width:100%" />
        </el-form-item>
        <el-form-item label="原因">
          <el-input v-model="writeoffForm.note" type="textarea" :rows="2" placeholder="过期/变质/损耗原因" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="writeoffVisible = false">取消</el-button>
        <el-button type="danger" @click="submitStockWriteoff" :loading="submitting">确认报损</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onBeforeUnmount } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Upload, Download, Search, Delete } from '@element-plus/icons-vue'
import api from '@/utils/api'
import { useAuthStore } from '@/store/auth'
import type { StockTransaction, StockItem, Supplier, StockBatch, Paginated } from '@/types'

const auth = useAuthStore()
const editable = computed(() => auth.canWrite('stock'))
const route = useRoute()

const transactions = ref<StockTransaction[]>([])
const items = ref<StockItem[]>([])
const suppliers = ref<Supplier[]>([])
const typeFilter = ref('')
const refFilter = ref('')
const searchText = ref('')
const submitting = ref(false)
const page = ref(1)
const pageSize = ref(100)
const total = ref(0)

const isMobile = ref(false)
const loadingMore = ref(false)
function updateViewport() { isMobile.value = window.innerWidth < 768 }
onMounted(() => { updateViewport(); window.addEventListener('resize', updateViewport) })
onBeforeUnmount(() => window.removeEventListener('resize', updateViewport))

function typeTag(t: string) {
  if (t === '入库') return 'success'
  if (t === '出库') return 'warning'
  if (t === '盘点') return 'danger'
  return 'info'
}

async function loadTransactions(resetPage = false) {
  if (resetPage) { page.value = 1; loadingMore.value = false }
  try {
    const params: Record<string, unknown> = { page: page.value, page_size: pageSize.value }
    if (route.query.item_id) params.item_id = Number(route.query.item_id)
    if (typeFilter.value) params.transaction_type = typeFilter.value
    if (refFilter.value) params.reference_type = refFilter.value
    if (searchText.value) params.search = searchText.value
    const res = (await api.get<Paginated<StockTransaction>>('/stock/transactions', { params })) || []
    // 后端返回分页信封 {items,total,...}
    if (Array.isArray(res)) { transactions.value = res; total.value = res.length }
    else { transactions.value = res.items || []; total.value = res.total || 0 }
  } catch (e: any) {
    ElMessage.error('流水加载失败：' + (e?.response?.data?.detail || e?.message || '未知错误'))
  }
}
async function loadMoreTransactions() {
  if (loadingMore.value || transactions.value.length >= total.value) return
  loadingMore.value = true
  try {
    const next = page.value + 1
    const params: any = { page: next, page_size: pageSize.value }
    if (route.query.item_id) params.item_id = Number(route.query.item_id)
    if (typeFilter.value) params.transaction_type = typeFilter.value
    if (refFilter.value) params.reference_type = refFilter.value
    if (searchText.value) params.search = searchText.value
    const res = (await api.get<Paginated<StockTransaction>>('/stock/transactions', { params })) || []
    const rows = Array.isArray(res) ? res : (res.items || [])
    const seen = new Set(transactions.value.map((r: any) => r.id))
    transactions.value.push(...rows.filter((r: any) => !seen.has(r.id)))
    page.value = next
  } catch (e: any) {
    ElMessage.error('加载失败：' + (e?.response?.data?.detail || e?.message || '未知错误'))
  } finally { loadingMore.value = false }
}
async function loadItems() {
  try { items.value = (await api.get<StockItem[]>('/stock/items')) || [] } catch {}
}
async function loadSuppliers() {
  try { suppliers.value = (await api.get<Supplier[]>('/stock/suppliers')) || [] } catch {}
}

// ── 入库 ──
const stockInVisible = ref(false)
const stockInForm = ref({
  item_id: null as number | null, quantity: 1,
  unit_price: null as number | null, supplier_id: null as number | null,
  batch_number: '', purchase_date: '', expiry_date: '', supplier: '', note: '',
})
const stockInUnit = ref('')  // 选中物品后带出其单位，用于数量/进价提示
const stockInAmount = computed(() => {
  const q = stockInForm.value.quantity
  const p = stockInForm.value.unit_price
  return q && p ? +(q * p).toFixed(2) : 0
})
const stockInRules = {
  item_id: [{ required: true, message: '请选择物品', trigger: 'change' }],
  quantity: [{ required: true, message: '请输入入库量', trigger: 'blur' }],
}
function openStockIn(presetItemId: number | null = null) {
  stockInForm.value = { item_id: presetItemId, quantity: 1, unit_price: null, supplier_id: null, batch_number: '', purchase_date: '', expiry_date: '', supplier: '', note: '' }
  stockInUnit.value = ''
  if (presetItemId) onItemSelect(presetItemId)
  stockInVisible.value = true
}
function onItemSelect(id: number) {
  const i = items.value.find((x: any) => x.id === id)
  if (i) { stockInForm.value.supplier_id = i.default_supplier_id || null; stockInUnit.value = i.unit || '' }
}
async function submitStockIn() {
  if (!stockInForm.value.item_id) { ElMessage.warning('请选择物品'); return }
  // 用下拉选中的供应商回填 supplier 快照，避免与采购流程不一致
  const sel = suppliers.value.find((s: any) => s.id === stockInForm.value.supplier_id)
  stockInForm.value.supplier = sel ? sel.name : null
  submitting.value = true
  try {
    await api.post('/stock/batches/in', stockInForm.value)
    ElMessage.success('入库成功')
    stockInVisible.value = false
    loadTransactions()
  } catch (e: any) {
    ElMessage.error('入库失败：' + (e?.response?.data?.detail || e?.message || '未知错误'))
  } finally {
    submitting.value = false
  }
}

// ── 出库 ──
const stockOutVisible = ref(false)
const stockOutForm = ref({ item_id: null as number | null, batch_id: null as number | null, quantity: 1, unit_price: 0, note: '' })
const stockOutRules = {
  item_id: [{ required: true, message: '请选择物品', trigger: 'change' }],
  quantity: [{ required: true, message: '请输入出库量', trigger: 'blur' }],
}
const outBatches = ref<StockBatch[]>([])
const outAvailable = ref(0)
const outUnit = ref('')

function openStockOut() {
  stockOutForm.value = { item_id: null, batch_id: null, quantity: 1, unit_price: 0, note: '' }
  outBatches.value = []; outAvailable.value = 0; outUnit.value = ''
  stockOutVisible.value = true
}
async function onOutItemSelect(id: number) {
  const item = items.value.find((x: any) => x.id === id)
  outUnit.value = item?.unit || ''
  stockOutForm.value.batch_id = null
  try {
    outBatches.value = (await api.get<StockBatch[]>('/stock/batches', { params: { item_id: id } })) || []
    outAvailable.value = outBatches.value
      .filter((b: any) => ['正常', '近效期'].includes(b.status))
      .reduce((s: number, b: any) => s + Number(b.quantity || 0), 0)
  } catch { outBatches.value = []; outAvailable.value = 0 }
}
async function submitStockOut() {
  if (!stockOutForm.value.item_id) { ElMessage.warning('请选择物品'); return }
  if (!stockOutForm.value.quantity || stockOutForm.value.quantity <= 0) { ElMessage.warning('请输入大于 0 的出库量'); return }
  submitting.value = true
  try {
    await api.post('/stock/batches/out', stockOutForm.value)
    ElMessage.success('出库成功')
    stockOutVisible.value = false
    loadTransactions()
  } catch (e: any) {
    ElMessage.error('出库失败：' + (e?.response?.data?.detail || e?.message || '未知错误'))
  } finally {
    submitting.value = false
  }
}

// ── 报损 ──
const writeoffVisible = ref(false)
const writeoffForm = ref({ item_id: null as number | null, batch_id: null as number | null, quantity: 1, note: '' })
function openStockWriteoff() {
  writeoffForm.value = { item_id: null, batch_id: null, quantity: 1, note: '' }
  outBatches.value = []; outAvailable.value = 0; outUnit.value = ''
  writeoffVisible.value = true
}
async function submitStockWriteoff() {
  if (!writeoffForm.value.item_id) { ElMessage.warning('请选择物品'); return }
  if (!writeoffForm.value.quantity || writeoffForm.value.quantity <= 0) { ElMessage.warning('请输入大于 0 的报损量'); return }
  submitting.value = true
  try {
    await api.post('/stock/batches/writeoff', writeoffForm.value)
    ElMessage.success('报损成功')
    writeoffVisible.value = false
    loadTransactions()
  } catch (e: any) {
    ElMessage.error('报损失败：' + (e?.response?.data?.detail || e?.message || '未知错误'))
  } finally {
    submitting.value = false
  }
}

onMounted(async () => {
  await loadTransactions(true)
  await loadItems()
  loadSuppliers()
  const presetId = route.query.item_id ? Number(route.query.item_id) : null
  if (route.query.open === 'in' && editable.value) {
    openStockIn(presetId)
  }
})
</script>

<style scoped lang="scss">
.stock-txn {
  .main-card {
    border-radius: 12px;
    border: 1px solid #f0e4d6;

    :deep(.el-card__header) {
      padding: 0;
      border-bottom: none;
    }
  }

  .filter-mini { width: 130px; }
  .filter-search { width: 200px; }
  .filter-actions { display: flex; gap: 8px; }

  .in-qty { color: #5f8b56; font-weight: 600; font-variant-numeric: tabular-nums; }
  .out-qty { color: #c0764f; font-weight: 600; font-variant-numeric: tabular-nums; }
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

.load-more { display: flex; flex-direction: column; align-items: center; gap: 6px; padding: 14px 0 2px; }
.load-more .el-button { min-width: 140px; }
.load-more .no-more { font-size: 12px; color: #a08b76; font-variant-numeric: tabular-nums; }
</style>