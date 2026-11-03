<template>
  <div class="purchase-inbound">
    <el-card shadow="hover" class="main-card">
      <template #header>
        <div class="tcm-head">
          <div class="tcm-head__title">
            <span class="tcm-head__icon">🛒</span>
            <span class="tcm-head__text">采购入库</span>
            <el-tag size="small" effect="light" round class="tcm-head__count">{{ orders.length }} 单</el-tag>
          </div>
          <div class="tcm-head__actions">
            <el-button v-if="editable" type="primary" @click="openCreate"><el-icon><Plus /></el-icon> 新建采购单</el-button>
          </div>
        </div>
      </template>

      <el-alert type="info" :closable="false" show-icon class="page-alert"
        title="采购入库（正规采购流程）"
        description="向供应商批量采购、生成采购单并自动入库时，请用本页「新建采购单」。零星到货、期初建账或库存调账，请到「库存流水」页使用【手动入库】。" />

      <el-table v-if="!isMobile" :data="orders" class="tcm-table" style="width:100%" empty-text="暂无采购单">
        <el-table-column type="expand">
          <template #default="{ row }">
            <el-table :data="row.items || []" size="small" :border="false">
              <el-table-column prop="item_name" label="物品" min-width="120" />
              <el-table-column prop="batch_number" label="批号" width="120" />
              <el-table-column label="数量" width="90"><template #default="{ row }">{{ row.quantity }} {{ row.unit }}</template></el-table-column>
              <el-table-column label="进价" width="100"><template #default="{ row }">¥{{ Number(row.unit_price).toFixed(2) }}</template></el-table-column>
              <el-table-column label="金额" width="110"><template #default="{ row }">¥{{ Number(row.amount).toFixed(2) }}</template></el-table-column>
              <el-table-column prop="expiry_date" label="有效期" width="120" />
            </el-table>
          </template>
        </el-table-column>
        <el-table-column prop="order_no" label="单号" width="170" />
        <el-table-column prop="supplier_name" label="供应商" min-width="120" />
        <el-table-column prop="order_date" label="采购日期" width="120" />
        <el-table-column label="总金额" width="130"><template #default="{ row }">¥{{ Number(row.total_amount).toFixed(2) }}</template></el-table-column>
        <el-table-column prop="operator" label="操作人" width="100" />
        <el-table-column prop="note" label="备注" min-width="120" show-overflow-tooltip />
      </el-table>

      <div v-if="isMobile" class="cards">
        <div v-for="row in orders" :key="row.id" class="card">
          <div class="card-head">
            <span class="card-name">{{ row.order_no }}</span>
            <span class="card-amount">¥{{ Number(row.total_amount).toFixed(2) }}</span>
          </div>
          <div class="card-body">
            <div class="card-row"><span class="label">供应商</span><span class="value">{{ row.supplier_name || '-' }}</span></div>
            <div class="card-row"><span class="label">日期</span><span class="value">{{ row.order_date || '-' }}</span></div>
            <div class="card-row"><span class="label">操作人</span><span class="value">{{ row.operator || '-' }}</span></div>
            <div class="card-row" v-if="row.note"><span class="label">备注</span><span class="value">{{ row.note }}</span></div>
          </div>
          <div v-if="(row.items || []).length" class="card-items">
            <div v-for="(it, i) in row.items" :key="i" class="card-item">
              <span class="ci-name">{{ it.item_name }}</span>
              <span class="ci-meta">{{ it.quantity }} {{ it.unit }} × ¥{{ Number(it.unit_price).toFixed(2) }}</span>
              <span class="ci-meta" v-if="it.batch_number">批号 {{ it.batch_number }}</span>
              <span class="ci-meta" v-if="it.expiry_date">效期 {{ it.expiry_date }}</span>
            </div>
          </div>
        </div>
        <el-empty v-if="!orders.length" description="暂无采购单" />
      </div>

      <div v-if="isMobile && orders.length" class="load-more">
        <el-button v-if="hasMore" size="small" :loading="loadingMore" @click="loadMore">加载更多</el-button>
        <span v-else class="no-more">已加载全部 {{ orders.length }} 张采购单</span>
      </div>

      <el-pagination
        v-if="!isMobile && total > pageSize"
        style="margin-top:14px;justify-content:center;"
        layout="total, prev, pager, next"
        :total="total" :page-size="pageSize" :current-page="page"
        @current-change="(p: number) => { page = p; load() }"
      />
    </el-card>

    <el-dialog v-model="visible" title="🛒 新建采购单" width="760px" destroy-on-close>
      <el-form :model="form" label-width="84px" :rules="rules" ref="formRef">
        <el-row :gutter="12">
          <el-col :xs="24" :sm="12">
            <el-form-item label="供应商" prop="supplier_id">
              <el-select v-model="form.supplier_id" filterable clearable placeholder="选择供应商" style="width:100%">
                <el-option v-for="s in suppliers" :key="s.id" :label="s.name" :value="s.id" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :xs="24" :sm="12">
            <el-form-item label="采购日期">
              <el-date-picker v-model="form.order_date" type="date" value-format="YYYY-MM-DD" placeholder="选择日期" style="width:100%" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-divider content-position="left">采购明细</el-divider>
        <div v-for="(it, idx) in form.items" :key="idx" class="po-item">
          <div class="po-item-main">
            <el-select v-model="it.item_id" filterable placeholder="物品" class="f-item" @change="onItemPick(it)">
              <el-option v-for="i in items" :key="i.id" :label="`${i.name}（${i.unit}）`" :value="i.id" />
            </el-select>
            <div class="po-item-nums">
              <el-input-number v-model="it.quantity" :min="0.01" :precision="2" controls-position="right" class="f-num" :placeholder="unitOf(it) ? '数量(' + unitOf(it) + ')' : '数量'" />
              <span class="f-unit" v-if="unitOf(it)">{{ unitOf(it) }}</span>
              <el-input-number v-model="it.unit_price" :min="0" :precision="2" controls-position="right" class="f-num" :placeholder="unitOf(it) ? '进价(元/' + unitOf(it) + ')' : '进价'" />
              <span class="f-unit" v-if="unitOf(it)">元/{{ unitOf(it) }}</span>
            </div>
            <el-button link type="danger" class="f-del" @click="removeItem(idx)"><el-icon><Delete /></el-icon></el-button>
          </div>
          <div class="po-item-sub">
            <el-input v-model="it.batch_number" placeholder="批号" class="f-batch" />
            <el-date-picker v-model="it.expiry_date" type="date" value-format="YYYY-MM-DD" placeholder="效期" class="f-date" />
          </div>
        </div>
        <el-button link type="primary" @click="addItem"><el-icon><Plus /></el-icon> 添加明细</el-button>
        <div class="po-total">采购总额：<b>¥{{ poTotal.toFixed(2) }}</b></div>
        <el-form-item label="备注" style="margin-top:8px"><el-input v-model="form.note" type="textarea" :rows="2" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="visible = false">取消</el-button>
        <el-button type="primary" @click="submit" :loading="submitting">提交入库</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted, onBeforeUnmount } from 'vue'
import { ElMessage } from 'element-plus'
import { Plus, Delete } from '@element-plus/icons-vue'
import api, { errMsg } from '@/utils/api'
import type { Supplier, StockItem, PurchaseOrder, PurchaseItem } from '@/types'
import { useAuthStore } from '@/store/auth'

const auth = useAuthStore()
const isMobile = ref(false)
function updateViewport() { isMobile.value = window.innerWidth < 768 }
const editable = computed(() => auth.canWrite('stock'))
const orders = ref<PurchaseOrder[]>([])
const suppliers = ref<Supplier[]>([])
const items = ref<StockItem[]>([])
const visible = ref(false)
const submitting = ref(false)
const page = ref(1)
const pageSize = ref(20)
const total = ref(0)
const hasMore = ref(false)
const loadingMore = ref(false)

const form = reactive({ supplier_id: null as number | null, order_date: '', note: '', items: [] as PurchaseItem[] })
const rules = { supplier_id: [{ required: false }] }
const poTotal = computed(() => form.items.reduce((s: number, it: PurchaseItem) => s + (Number(it.quantity) || 0) * (Number(it.unit_price) || 0), 0))

async function load() {
  loadingMore.value = false
  page.value = 1
  hasMore.value = true
  try {
    const res = (await api.get<Paginated<PurchaseOrder>>('/stock/purchases', { params: { page: page.value, page_size: pageSize.value } })) || []
    if (Array.isArray(res)) {
      orders.value = res
      total.value = res.length
      hasMore.value = false
    } else {
      orders.value = res.items || []
      total.value = res.total || 0
      hasMore.value = orders.value.length < total.value
    }
    suppliers.value = (await api.get<Supplier[]>('/stock/suppliers')) || []
    items.value = (await api.get<StockItem[]>('/stock/items')) || []
  } catch (e) { ElMessage.error('加载失败：' + (e?.response?.data?.detail || e?.message)) }
}
async function loadMore() {
  if (loadingMore.value || !hasMore.value) return
  loadingMore.value = true
  try {
    const next = page.value + 1
    const res = (await api.get<Paginated<PurchaseOrder>>('/stock/purchases', { params: { page: next, page_size: pageSize.value } })) || []
    const rows = Array.isArray(res) ? res : (res.items || [])
    const seen = new Set(orders.value.map((o: PurchaseOrder) => o.id))
    orders.value.push(...rows.filter((r: PurchaseOrder) => !seen.has(r.id)))
    page.value = next
    hasMore.value = orders.value.length < total.value
  } catch (e) { ElMessage.error('加载失败：' + (e?.response?.data?.detail || e?.message)) }
  finally { loadingMore.value = false }
}
function addItem() { form.items.push({ item_id: null, batch_number: '', quantity: 1, unit_price: null, expiry_date: '' }) }
function removeItem(idx: number) { form.items.splice(idx, 1) }
function onItemPick(it: PurchaseItem) {
  const i = items.value.find((x: StockItem) => x.id === it.item_id)
  if (i && it.unit_price == null) it.unit_price = i.sell_price ? Number(i.sell_price) * 0.6 : null
}
function unitOf(it: PurchaseItem) {
  const i = items.value.find((x: StockItem) => x.id === it.item_id)
  return i ? i.unit : ''
}
function openCreate() {
  form.supplier_id = null; form.order_date = new Date().toISOString().slice(0, 10)
  form.note = ''; form.items = []
  visible.value = true
}
async function submit() {
  if (!form.items.length) { ElMessage.warning('请至少添加一条明细'); return }
  if (form.items.some((it: PurchaseItem) => !it.item_id || !(it.quantity > 0) || !(it.unit_price >= 0))) {
    ElMessage.warning('明细需填写物品、数量与进价'); return
  }
  submitting.value = true
  try {
    await api.post('/stock/purchases', { supplier_id: form.supplier_id, order_date: form.order_date, note: form.note, items: form.items })
    ElMessage.success('采购入库成功')
    visible.value = false
    page.value = 1
    load()
  } catch (e) { ElMessage.error('提交失败：' + (e?.response?.data?.detail || e?.message)) }
  finally { submitting.value = false }
}

onMounted(() => {
  updateViewport()
  window.addEventListener('resize', updateViewport)
  load()
})
onBeforeUnmount(() => window.removeEventListener('resize', updateViewport))
</script>

<style scoped lang="scss">
.purchase-inbound {
  .main-card {
    border-radius: 12px;
    border: 1px solid #f0e4d6;

    :deep(.el-card__header) { padding: 0; border-bottom: none; }
  }

  .page-alert { margin-bottom: 12px; }

  .po-item { margin-bottom: 8px; }
  .po-item-main { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; }
  .po-item-nums { display: flex; gap: 8px; align-items: center; }
  .po-item-sub { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; margin-top: 8px; }
  .f-item { width: 200px; }
  .f-batch { width: 120px; }
  .f-num { width: 130px; }
  .f-date { width: 150px; }
  .f-unit { font-size: 12px; color: #8a7563; align-self: center; white-space: nowrap; }
  .po-total { margin: 8px 0; font-size: 15px; color: #2c1810; font-variant-numeric: tabular-nums; }

  .load-more { display: flex; flex-direction: column; align-items: center; gap: 6px; padding: 14px 0 2px; }
  .load-more .el-button { min-width: 140px; }
  .load-more .no-more { font-size: 12px; color: #a08b76; font-variant-numeric: tabular-nums; }

  .cards { display: flex; flex-direction: column; gap: 10px; }
  .card { border: 1px solid #f0e4d6; border-radius: 10px; padding: 12px; background: #fff; box-shadow: 0 1px 3px rgba(44,24,16,.04); }
  .card .card-head { display: flex; justify-content: space-between; align-items: baseline; gap: 8px; margin-bottom: 8px; }
  .card .card-name { font-size: 16px; font-weight: 600; color: #2c1810; word-break: break-all; font-variant-numeric: tabular-nums; }
  .card .card-amount { font-size: 15px; font-weight: 600; color: #8b5e34; flex-shrink: 0; font-variant-numeric: tabular-nums; }
  .card .card-row { display: flex; align-items: flex-start; font-size: 14px; line-height: 1.5; }
  .card .card-row .label { flex-shrink: 0; width: 62px; color: #8a7563; }
  .card .card-row .value { flex: 1; color: #4a3628; word-break: break-all; }
  .card .card-items { margin-top: 8px; padding-top: 8px; border-top: 1px dashed #f0e4d6; display: flex; flex-direction: column; gap: 6px; }
  .card .card-item { display: flex; flex-wrap: wrap; gap: 4px 10px; font-size: 13px; color: #6b5644; }
  .card .card-item .ci-name { font-weight: 600; color: #2c1810; width: 100%; }
}

@media (max-width: 767px) {
  .purchase-inbound {
    :deep(.el-card__header) { padding: 0; }
    :deep(.el-card__body) { padding: 12px; }
    :deep(.el-alert) { padding: 8px 10px; }
    :deep(.el-alert__description) { font-size: 12px; line-height: 1.5; }
    :deep(.el-pagination) { flex-wrap: wrap; row-gap: 6px; }

    .f-item { width: auto; flex: 1 1 0; min-width: 0; }
    .po-item-nums .f-num { width: auto; flex: 1 1 0; min-width: 0; }
    .f-batch { width: calc(50% - 4px); flex: 0 0 auto; min-width: 0; }
    .f-date { width: calc(50% - 4px); flex: 0 0 auto; min-width: 0; }
    .f-unit { display: none; }
    .f-del { flex: 0 0 auto; margin-left: 0; padding: 0 4px; }
    .po-item-main { row-gap: 6px; flex-wrap: wrap; }
    .po-item-nums { flex: 1 1 100%; gap: 8px; min-width: 0; }
    .po-item-sub { margin-top: 6px; flex-wrap: nowrap; }
    :deep(.po-item-nums .el-input-number) { width: 100%; }
    :deep(.po-item-sub > .el-date-editor) { min-width: 0; }
    :deep(.po-item-sub > .el-date-editor .el-input__wrapper) { padding-left: 6px; padding-right: 6px; }
    .po-item { margin-bottom: 12px; padding-bottom: 10px; border-bottom: 1px dashed #f0e4d6; }
  }
}
</style>