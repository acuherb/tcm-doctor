<template>
  <div class="stock-txn">
    <el-card shadow="hover">
      <template #header>
        <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:8px;">
          <span>🔄 出入库流水</span>
          <div style="display:flex;gap:8px;">
            <el-button v-if="editable" type="success" size="small" @click="openStockIn">
              <el-icon><Upload /></el-icon> 入库
            </el-button>
            <el-button v-if="editable" type="warning" size="small" @click="openStockOut">
              <el-icon><Download /></el-icon> 出库
            </el-button>
          </div>
        </div>
      </template>

      <el-form :inline="true" @submit.prevent="loadTransactions">
        <el-form-item>
          <el-select v-model="typeFilter" placeholder="类型" clearable @change="loadTransactions" style="width:120px">
            <el-option label="全部" value="" />
            <el-option label="入库" value="入库" />
            <el-option label="出库" value="出库" />
            <el-option label="盘点" value="盘点" />
            <el-option label="调整" value="调整" />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-select v-model="refFilter" placeholder="来源" clearable @change="loadTransactions" style="width:120px">
            <el-option label="全部" value="" />
            <el-option label="手动" value="手动" />
            <el-option label="处方" value="处方" />
            <el-option label="盘点" value="盘点" />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-input v-model="searchText" placeholder="物品名称" clearable @clear="loadTransactions" style="width:180px">
            <template #prefix><el-icon><Search /></el-icon></template>
          </el-input>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="loadTransactions">查询</el-button>
        </el-form-item>
      </el-form>

      <el-table v-if="!isMobile" :data="transactions" stripe style="width:100%" empty-text="暂无流水">
        <el-table-column prop="created_at" label="时间" width="160" />
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
          <template #default="{ row }">{{ row.before_quantity != null ? row.before_quantity : '-' }}</template>
        </el-table-column>
        <el-table-column prop="after_quantity" label="变动后" width="100">
          <template #default="{ row }">{{ row.after_quantity != null ? row.after_quantity : '-' }}</template>
        </el-table-column>
        <el-table-column prop="batch_number" label="批号" width="120">
          <template #default="{ row }">{{ row.batch_number || '-' }}</template>
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
                {{ row.transaction_type === '出库' ? '-' : '+' }}{{ row.quantity }} {{ row.unit }}（前{{ row.before_quantity ?? '-' }}→后{{ row.after_quantity ?? '-' }}）
              </span>
            </div>
            <div class="card-row"><span class="label">批号</span><span class="value">{{ row.batch_number || '-' }}</span></div>
            <div class="card-row"><span class="label">来源</span><span class="value">{{ row.reference_type || '-' }} / {{ row.operator || '-' }} / {{ row.created_at }}</span></div>
            <div class="card-row" v-if="row.note"><span class="label">备注</span><span class="value">{{ row.note }}</span></div>
          </div>
        </div>
        <el-empty v-if="!transactions.length" description="暂无流水" />
      </div>
    </el-card>

    <!-- 入库对话框 -->
    <el-dialog v-model="stockInVisible" title="📥 入库" width="520px" destroy-on-close>
      <el-form :model="stockInForm" label-width="92px" :rules="stockInRules" ref="stockInFormRef">
        <el-form-item label="物品" prop="item_id">
          <el-select v-model="stockInForm.item_id" filterable placeholder="搜索物品" style="width:100%" @change="onItemSelect">
            <el-option v-for="i in items" :key="i.id" :label="`${i.name}（${i.unit}）`" :value="i.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="入库量" prop="quantity">
          <el-input-number v-model="stockInForm.quantity" :min="0.01" :precision="2" style="width:100%" />
        </el-form-item>
        <el-row :gutter="12">
          <el-col :span="12">
            <el-form-item label="进价">
              <el-input-number v-model="stockInForm.unit_price" :min="0" :precision="2" :controls="false" style="width:100%" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="售价">
              <el-input-number v-model="stockInForm.sale_price" :min="0" :precision="2" :controls="false" style="width:100%" />
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
        <el-form-item label="供应商">
          <el-input v-model="stockInForm.supplier" placeholder="供应商名称" />
        </el-form-item>
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
          <span style="color:#8B4513;font-weight:600;">{{ outAvailable }} {{ outUnit }}</span>
        </el-form-item>
        <el-form-item label="指定批次">
          <el-select v-model="stockOutForm.batch_id" clearable placeholder="留空则按 FIFO 顺序扣减" style="width:100%">
            <el-option v-for="b in outBatches" :key="b.id" :label="`${b.batch_number || '批' + b.id}（余 ${b.quantity} ${outUnit}）`" :value="b.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="出库量" prop="quantity">
          <el-input-number v-model="stockOutForm.quantity" :min="0.01" :precision="2" style="width:100%" />
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="stockOutForm.note" type="textarea" :rows="2" placeholder="出库原因" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="stockOutVisible = false">取消</el-button>
        <el-button type="primary" @click="submitStockOut" :loading="submitting">确认出库</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onBeforeUnmount } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Upload, Download, Search } from '@element-plus/icons-vue'
import api from '@/utils/api'
import { useAuthStore } from '@/store/auth'

const auth = useAuthStore()
const editable = computed(() => !!auth.user?.is_admin)
const route = useRoute()

const transactions = ref<any[]>([])
const items = ref<any[]>([])
const typeFilter = ref('')
const refFilter = ref('')
const searchText = ref('')
const submitting = ref(false)

const isMobile = ref(false)
function updateViewport() { isMobile.value = window.innerWidth < 768 }
onMounted(() => { updateViewport(); window.addEventListener('resize', updateViewport) })
onBeforeUnmount(() => window.removeEventListener('resize', updateViewport))

function typeTag(t: string) {
  if (t === '入库') return 'success'
  if (t === '出库') return 'warning'
  if (t === '盘点') return 'danger'
  return 'info'
}

async function loadTransactions() {
  try {
    const params: any = { limit: 500 }
    if (route.query.item_id) params.item_id = Number(route.query.item_id)
    if (typeFilter.value) params.transaction_type = typeFilter.value
    if (refFilter.value) params.reference_type = refFilter.value
    if (searchText.value) params.search = searchText.value
    transactions.value = (await api.get('/stock/transactions', { params }) as any) || []
  } catch (e: any) {
    ElMessage.error('流水加载失败：' + (e?.response?.data?.detail || e?.message || '未知错误'))
  }
}
async function loadItems() {
  try { items.value = (await api.get('/stock/items') as any) || [] } catch {}
}

// ── 入库 ──
const stockInVisible = ref(false)
const stockInFormRef = ref()
const stockInForm = ref({
  item_id: null as number | null, quantity: 1,
  unit_price: null as number | null, sale_price: null as number | null,
  batch_number: '', purchase_date: '', expiry_date: '', supplier: '', note: '',
})
const stockInRules = {
  item_id: [{ required: true, message: '请选择物品', trigger: 'change' }],
  quantity: [{ required: true, message: '请输入入库量', trigger: 'blur' }],
}
function openStockIn() {
  stockInForm.value = { item_id: null, quantity: 1, unit_price: null, sale_price: null, batch_number: '', purchase_date: '', expiry_date: '', supplier: '', note: '' }
  stockInVisible.value = true
}
function onItemSelect(id: number) {
  const i = items.value.find((x: any) => x.id === id)
  if (i && i.sell_price != null) stockInForm.value.sale_price = Number(i.sell_price)
}
async function submitStockIn() {
  if (!stockInForm.value.item_id) { ElMessage.warning('请选择物品'); return }
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
const stockOutFormRef = ref()
const stockOutForm = ref({ item_id: null as number | null, batch_id: null as number | null, quantity: 1, note: '' })
const stockOutRules = {
  item_id: [{ required: true, message: '请选择物品', trigger: 'change' }],
  quantity: [{ required: true, message: '请输入出库量', trigger: 'blur' }],
}
const outBatches = ref<any[]>([])
const outAvailable = ref(0)
const outUnit = ref('')

function openStockOut() {
  stockOutForm.value = { item_id: null, batch_id: null, quantity: 1, note: '' }
  outBatches.value = []; outAvailable.value = 0; outUnit.value = ''
  stockOutVisible.value = true
}
async function onOutItemSelect(id: number) {
  const item = items.value.find((x: any) => x.id === id)
  outUnit.value = item?.unit || ''
  stockOutForm.value.batch_id = null
  try {
    outBatches.value = (await api.get('/stock/batches', { params: { item_id: id } }) as any) || []
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

onMounted(() => { loadTransactions(); loadItems() })
</script>

<style scoped lang="scss">
.stock-txn {
  .in-qty { color: #67c23a; font-weight: 600; }
  .out-qty { color: #e6a23c; font-weight: 600; }
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

@media (max-width: 767px) {
  :deep(.el-form--inline .el-form-item) { display: block; margin-right: 0; margin-bottom: 8px; }
  :deep(.el-form--inline .el-form-item__content) { display: block; max-width: 100%; }
  :deep(.el-form--inline .el-input), :deep(.el-form--inline .el-select) { width: 100% !important; }
}
</style>
