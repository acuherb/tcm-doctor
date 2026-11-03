<template>
  <div class="stock-check">
    <el-card shadow="hover" class="main-card">
      <template #header>
        <div class="tcm-head">
          <div class="tcm-head__title">
            <span class="tcm-head__icon">{{ mode === 'check' ? '🧮' : '🛠' }}</span>
            <span class="tcm-head__text">{{ mode === 'check' ? '库房盘点' : '批次属性纠错' }}</span>
            <el-tag v-if="selectedItem" size="small" effect="light" round class="tcm-head__count">{{ selectedItem.name }}</el-tag>
          </div>
          <div class="tcm-head__actions">
            <el-radio-group v-if="editable" v-model="mode">
              <el-radio-button value="check">库房盘点</el-radio-button>
              <el-radio-button value="fix">批次纠错</el-radio-button>
            </el-radio-group>
            <el-select v-model="selectedItemId" filterable :placeholder="mode === 'check' ? '选择盘点物品' : '选择物品'" clearable class="filter-sel" @change="loadBatches">
              <el-option v-for="i in items" :key="i.id" :label="`${i.name}（${i.unit}）`" :value="i.id" />
            </el-select>
            <el-button type="primary" :disabled="!selectedItemId" @click="loadBatches">加载批次</el-button>
          </div>
        </div>
      </template>

      <el-alert
        v-if="selectedItem && mode === 'check'"
        :title="`盘点物品：${selectedItem.name}（${selectedItem.unit}）  当前总库存 ${totalBefore } ${selectedItem.unit}`"
        type="info" :closable="false" class="page-alert" />

      <el-alert
        v-if="mode === 'fix'"
        title="此处仅纠正批次属性（批号/效期/进价/供应商/货位/状态），不修改库存数量。数量有误请切回「库房盘点」按实盘数提交，确保流水口径统一。"
        type="warning" :closable="false" class="page-alert" />

      <el-empty v-if="!selectedItemId" :description="mode === 'check' ? '请先选择要盘点的物品' : '请先选择物品'" />
      <template v-else-if="mode === 'check'">
        <el-form label-width="120px" style="max-width:440px">
          <el-form-item label="当前总库存">
            <span><b>{{ totalBefore }} {{ unit }}</b></span>
          </el-form-item>
          <el-form-item :label="`实盘总数（${unit}）`">
            <el-input-number v-model="itemCounted" :min="0" :precision="2" style="width:100%" />
          </el-form-item>
          <el-form-item label="差异">
            <b :class="diffClass({ quantity: totalBefore, counted: itemCounted })">
              {{ diffOf({ quantity: totalBefore, counted: itemCounted }) > 0 ? '+' : '' }}{{ diffOf({ quantity: totalBefore, counted: itemCounted }) }} {{ unit }}
            </b>
          </el-form-item>
        </el-form>
        <div class="submit-bar">
          <el-input v-model="checkNote" placeholder="盘点备注（可选）" class="note-input" />
          <el-button type="primary" :loading="submitting" :disabled="!selectedItemId" @click="submitCheck">
            <el-icon><Check /></el-icon> 提交盘点
          </el-button>
        </div>
      </template>

      <!-- 批次属性纠错 -->
      <template v-else>
        <el-table v-if="!isMobile" :data="batchRows" class="tcm-table" style="width:100%" empty-text="该物品暂无批次">
          <el-table-column label="批号" min-width="130">
            <template #default="{ row }">{{ row.batch_number || '批' + row.id }}</template>
          </el-table-column>
          <el-table-column label="数量" width="110">
            <template #default="{ row }">{{ row.quantity }} {{ unit }}</template>
          </el-table-column>
          <el-table-column label="进价" width="100">
            <template #default="{ row }">{{ row.unit_price != null ? '¥' + Number(row.unit_price).toFixed(2) : '-' }}</template>
          </el-table-column>
          <el-table-column label="有效期" width="120">
            <template #default="{ row }">{{ row.expiry_date || '-' }}</template>
          </el-table-column>
          <el-table-column label="货位" width="110">
            <template #default="{ row }">{{ row.location || '-' }}</template>
          </el-table-column>
          <el-table-column prop="status" label="状态" width="90">
            <template #default="{ row }"><el-tag size="small" :type="statusTag(row.status)">{{ row.status }}</el-tag></template>
          </el-table-column>
          <el-table-column label="操作" width="110" fixed="right">
            <template #default="{ row }">
              <el-button link type="primary" size="small" @click="openFix(row)">纠错</el-button>
            </template>
          </el-table-column>
        </el-table>

        <div v-if="isMobile" class="cards">
          <div v-for="row in pagedBatches" :key="row.id" class="card">
            <div class="card-head">
              <span class="card-name">{{ row.batch_number || '批' + row.id }}</span>
              <el-tag size="small" :type="statusTag(row.status)">{{ row.status }}</el-tag>
            </div>
            <div class="card-body">
              <div class="card-row"><span class="label">数量</span><span class="value">{{ row.quantity }} {{ unit }}</span></div>
              <div class="card-row"><span class="label">进价</span><span class="value">{{ row.unit_price != null ? '¥' + Number(row.unit_price).toFixed(2) : '-' }}</span></div>
              <div class="card-row"><span class="label">有效期</span><span class="value">{{ row.expiry_date || '-' }}</span></div>
              <div class="card-row"><span class="label">货位</span><span class="value">{{ row.location || '-' }}</span></div>
            </div>
            <div class="card-actions">
              <el-button link type="primary" size="small" @click="openFix(row)">纠错</el-button>
            </div>
          </div>
          <el-empty v-if="!batchRows.length" description="该物品暂无批次" />
        </div>

        <div v-if="isMobile && batchRows.length > fixPageSize" class="load-more">
          <el-button v-if="fixShown < batchRows.length" size="small" @click="loadMoreFix">加载更多</el-button>
          <span v-else class="no-more">已显示全部 {{ batchRows.length }} 个批次</span>
        </div>
      </template>
    </el-card>

    <el-dialog v-model="fixVisible" title="🛠 批次属性纠错" :width="isMobile ? '92%' : '520px'" destroy-on-close>
      <el-alert
        :title="`数量 ${fixForm.quantity ?? '-'} ${unit} 不在此修改；如需调整数量请使用「库房盘点」`"
        type="info" :closable="false" style="margin-bottom:12px" />
      <el-form :model="fixForm" label-width="90px">
        <el-form-item label="批号">
          <el-input v-model="fixForm.batch_number" placeholder="批次批号" />
        </el-form-item>
        <el-form-item label="进价">
          <el-input-number v-model="fixForm.unit_price" :min="0" :precision="2" :controls="false" style="width:100%" />
        </el-form-item>
        <el-form-item label="有效期">
          <el-date-picker v-model="fixForm.expiry_date" type="date" value-format="YYYY-MM-DD" style="width:100%" placeholder="选择有效期" />
        </el-form-item>
        <el-form-item label="供应商">
          <el-select v-model="fixForm.supplier_id" filterable clearable placeholder="选择供应商" style="width:100%">
            <el-option v-for="s in suppliers" :key="s.id" :label="s.name" :value="s.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="货位">
          <el-input v-model="fixForm.location" placeholder="如 A-01-02" />
        </el-form-item>
        <el-form-item label="状态">
          <el-select v-model="fixForm.status" style="width:100%">
            <el-option label="正常" value="正常" />
            <el-option label="近效期" value="近效期" />
            <el-option label="停用" value="停用" />
          </el-select>
        </el-form-item>
        <el-form-item label="纠错说明">
          <el-input v-model="fixForm.reason" type="textarea" :rows="2" placeholder="填写纠错原因，便于日后追溯" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="fixVisible = false">取消</el-button>
        <el-button type="primary" :loading="fixSubmitting" @click="submitFix">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onBeforeUnmount, watch } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Check } from '@element-plus/icons-vue'
import api from '@/utils/api'
import type { StockItem, Supplier, StockBatch } from '@/types'
import { useAuthStore } from '@/store/auth'

const auth = useAuthStore()
const editable = computed(() => auth.canWrite('stock'))
const route = useRoute()

const mode = ref<'check' | 'fix'>('check')
const items = ref<StockItem[]>([])
const selectedItemId = ref<number | null>(null)
const batchRows = ref<StockBatch[]>([])
const itemCounted = ref(0)
const checkNote = ref('')
const submitting = ref(false)

const selectedItem = computed(() => items.value.find((i: any) => i.id === selectedItemId.value) || null)
const unit = computed(() => selectedItem.value?.unit || '')
const totalBefore = computed(() => batchRows.value.reduce((s: number, b: any) => s + Number(b.quantity || 0), 0))

const fixPageSize = 20
const fixShown = ref(fixPageSize)
const pagedBatches = computed(() => batchRows.value.slice(0, fixShown.value))
function loadMoreFix() {
  fixShown.value = Math.min(fixShown.value + fixPageSize, batchRows.value.length)
}

function diffOf(row: any) {
  return Math.round((Number(row.counted ?? 0) - Number(row.quantity || 0)) * 100) / 100
}
function diffClass(row: any) {
  const d = diffOf(row)
  if (d > 0) return 'in-qty'
  if (d < 0) return 'out-qty'
  return ''
}
function statusTag(s: string) {
  if (s === '正常') return 'success'
  if (s === '近效期') return 'warning'
  return 'info'
}

const isMobile = ref(false)
function updateViewport() { isMobile.value = window.innerWidth < 768 }
onMounted(() => { updateViewport(); window.addEventListener('resize', updateViewport) })
onBeforeUnmount(() => window.removeEventListener('resize', updateViewport))

async function loadItems() {
  try { items.value = (await api.get<StockItem[]>('/stock/items')) || [] } catch {}
}
const suppliers = ref<Supplier[]>([])
async function loadSuppliers() {
  try { suppliers.value = (await api.get<Supplier[]>('/stock/suppliers')) || [] } catch {}
}
async function loadBatches() {
  if (!selectedItemId.value) { batchRows.value = []; return }
  fixShown.value = fixPageSize
  try {
    const rows = (await api.get<StockBatch[]>('/stock/batches', { params: { item_id: selectedItemId.value, include_inactive: true } })) || []
    batchRows.value = rows.map((b: any) => ({ ...b, counted: Number(b.quantity || 0) }))
    itemCounted.value = totalBefore.value
  } catch (e: any) {
    ElMessage.error('批次加载失败：' + (e?.response?.data?.detail || e?.message || '未知错误'))
  }
}
async function submitCheck() {
  if (!editable.value) { ElMessage.warning('无操作权限'); return }
  if (!selectedItemId.value) return
  const counted = Number(itemCounted.value ?? totalBefore.value)
  submitting.value = true
  try {
    await api.post('/stock/adjust/bulk', [{ item_id: selectedItemId.value, counted, note: checkNote.value }])
    ElMessage.success('盘点完成，已按实盘调整库存')
    loadBatches()
  } catch (e: any) {
    ElMessage.error('盘点失败：' + (e?.response?.data?.detail || e?.message || '未知错误'))
  } finally {
    submitting.value = false
  }
}

const fixVisible = ref(false)
const fixSubmitting = ref(false)
const fixBatchId = ref<number | null>(null)
const fixForm = ref<any>({
  batch_number: '', unit_price: null, expiry_date: '', supplier_id: null,
  location: '', status: '正常', reason: '', quantity: null,
})
function openFix(row: any) {
  if (!editable.value) { ElMessage.warning('无操作权限'); return }
  fixBatchId.value = row.id
  fixForm.value = {
    batch_number: row.batch_number || '',
    unit_price: row.unit_price != null ? Number(row.unit_price) : null,
    expiry_date: row.expiry_date || '',
    supplier_id: row.supplier_id ?? null,
    location: row.location || '',
    status: row.status || '正常',
    reason: '',
    quantity: row.quantity,
  }
  fixVisible.value = true
}
async function submitFix() {
  if (!fixBatchId.value) return
  if (!fixForm.value.reason?.trim()) { ElMessage.warning('请填写纠错说明'); return }
  const payload: Record<string, unknown> = {
    batch_number: fixForm.value.batch_number || null,
    unit_price: fixForm.value.unit_price,
    expiry_date: fixForm.value.expiry_date || null,
    supplier_id: fixForm.value.supplier_id,
    location: fixForm.value.location || null,
    status: fixForm.value.status,
  }
  Object.keys(payload).forEach((k) => { if (payload[k] === null) delete payload[k] })
  fixSubmitting.value = true
  try {
    await api.put(`/stock/batches/${fixBatchId.value}`, payload)
    ElMessage.success('批次属性已更正')
    fixVisible.value = false
    loadBatches()
  } catch (e: any) {
    ElMessage.error('纠错失败：' + (e?.response?.data?.detail || e?.message || '未知错误'))
  } finally {
    fixSubmitting.value = false
  }
}

// 从总览/预警跳转带入 item_id
watch(() => route.query.item_id, (v) => {
  if (v) { selectedItemId.value = Number(v); loadBatches() }
}, { immediate: true })

onMounted(() => { loadItems(); loadSuppliers() })
</script>

<style scoped lang="scss">
.stock-check {
  .main-card {
    border-radius: 12px;
    border: 1px solid #f0e4d6;

    :deep(.el-card__header) {
      padding: 0;
      border-bottom: none;
    }
  }

  .filter-sel { width: 240px; }
  .page-alert { margin-bottom: 12px; }

  .submit-bar {
    display: flex;
    gap: 12px;
    align-items: center;
    flex-wrap: wrap;
    margin-top: 8px;
  }
  .note-input { width: 260px; }

  .in-qty { color: #5f8b56; font-weight: 600; font-variant-numeric: tabular-nums; }
  .out-qty { color: #b5624f; font-weight: 600; font-variant-numeric: tabular-nums; }
}
.cards { display: flex; flex-direction: column; gap: 10px; }
.card {
  background: #fff; border: 1px solid #f0e4d6; border-radius: 10px; padding: 12px 14px;
  box-shadow: 0 1px 3px rgba(44,24,16,.04);
}
.card .card-head { display: flex; align-items: center; justify-content: space-between; margin-bottom: 8px; gap: 8px; }
.card .card-name { font-size: 16px; font-weight: 600; color: #2c1810; }
.card .card-body { display: flex; flex-direction: column; gap: 6px; }
.card .card-row { display: flex; align-items: center; font-size: 14px; line-height: 1.5; }
.card .card-row .label { flex-shrink: 0; width: 54px; color: #8a7563; }
.card .card-row .value { flex: 1; color: #4a3628; word-break: break-all; }
.card .card-actions { display: flex; justify-content: flex-end; margin-top: 8px; padding-top: 8px; border-top: 1px dashed #f0e4d6; }
.load-more { display: flex; flex-direction: column; align-items: center; gap: 6px; padding: 14px 0 2px; }
.load-more .el-button { min-width: 140px; }
.load-more .no-more { font-size: 12px; color: #a08b76; font-variant-numeric: tabular-nums; }
</style>