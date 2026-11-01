<template>
  <div class="stock-check">
    <el-card shadow="hover">
      <template #header>
        <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:8px;">
          <span>🧮 库房盘点</span>
          <div style="display:flex;gap:8px;">
            <el-select v-model="selectedItemId" filterable placeholder="选择盘点物品" clearable style="width:240px" @change="loadBatches">
              <el-option v-for="i in items" :key="i.id" :label="`${i.name}（${i.unit}）`" :value="i.id" />
            </el-select>
            <el-button type="primary" :disabled="!selectedItemId" @click="loadBatches">加载批次</el-button>
          </div>
        </div>
      </template>

      <el-alert
        v-if="selectedItem"
        :title="`盘点物品：${selectedItem.name}（${selectedItem.unit}）  当前总库存 ${totalBefore } ${selectedItem.unit}`"
        type="info" :closable="false" style="margin-bottom:12px" />

      <el-empty v-if="!selectedItemId" description="请先选择要盘点的物品" />
      <template v-else>
        <el-table v-if="!isMobile" :data="batchRows" stripe style="width:100%" empty-text="该物品暂无批次">
          <el-table-column prop="batch_number" label="批号" min-width="120">
            <template #default="{ row }">{{ row.batch_number || '批' + row.id }}</template>
          </el-table-column>
          <el-table-column prop="quantity" label="账面数量" width="120">
            <template #default="{ row }">{{ row.quantity }} {{ unit }}</template>
          </el-table-column>
          <el-table-column prop="status" label="状态" width="90">
            <template #default="{ row }"><el-tag size="small" :type="statusTag(row.status)">{{ row.status }}</el-tag></template>
          </el-table-column>
          <el-table-column label="实盘数量" width="200">
            <template #default="{ row, $index }">
              <el-input-number v-model="batchRows[$index].counted" :min="0" :precision="2" :controls="false" style="width:100%" />
            </template>
          </el-table-column>
          <el-table-column label="差异" width="120">
            <template #default="{ row }">
              <span :class="diffClass(row)">{{ diffOf(row) > 0 ? '+' : '' }}{{ diffOf(row) }} {{ unit }}</span>
            </template>
          </el-table-column>
        </el-table>

        <div v-if="isMobile" class="cards">
          <div v-for="(row, idx) in batchRows" :key="row.id" class="card">
            <div class="card-head">
              <span class="card-name">{{ row.batch_number || '批' + row.id }}</span>
              <el-tag size="small" :type="statusTag(row.status)">{{ row.status }}</el-tag>
            </div>
            <div class="card-body">
              <div class="card-row"><span class="label">账面</span><span class="value">{{ row.quantity }} {{ unit }}</span></div>
              <div class="card-row"><span class="label">实盘</span>
                <span class="value"><el-input-number v-model="batchRows[idx].counted" :min="0" :precision="2" :controls="false" /></span>
              </div>
              <div class="card-row"><span class="label">差异</span><span class="value" :class="diffClass(row)">{{ diffOf(row) > 0 ? '+' : '' }}{{ diffOf(row) }} {{ unit }}</span></div>
            </div>
          </div>
          <el-empty v-if="!batchRows.length" description="该物品暂无批次" />
        </div>

        <div style="margin-top:16px;display:flex;gap:12px;align-items:center;flex-wrap:wrap;">
          <el-input v-model="checkNote" placeholder="盘点备注（可选）" style="width:260px" />
          <el-button type="primary" :loading="submitting" :disabled="!batchRows.length" @click="submitCheck">
            <el-icon><Check /></el-icon> 提交盘点
          </el-button>
          <span style="color:#8a7563;">盘后总库存：<b>{{ totalAfter }} {{ unit }}</b></span>
        </div>
      </template>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onBeforeUnmount, watch } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Check } from '@element-plus/icons-vue'
import api from '@/utils/api'
import { useAuthStore } from '@/store/auth'

const auth = useAuthStore()
const editable = computed(() => !!auth.user?.is_admin)
const route = useRoute()

const items = ref<any[]>([])
const selectedItemId = ref<number | null>(null)
const batchRows = ref<any[]>([])
const checkNote = ref('')
const submitting = ref(false)

const selectedItem = computed(() => items.value.find((i: any) => i.id === selectedItemId.value) || null)
const unit = computed(() => selectedItem.value?.unit || '')
const totalBefore = computed(() => batchRows.value.reduce((s: number, b: any) => s + Number(b.quantity || 0), 0))
const totalAfter = computed(() => batchRows.value.reduce((s: number, b: any) => s + Number(b.counted ?? b.quantity ?? 0), 0))

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
  try { items.value = (await api.get('/stock/items') as any) || [] } catch {}
}
async function loadBatches() {
  if (!selectedItemId.value) { batchRows.value = []; return }
  try {
    const rows = (await api.get('/stock/batches', { params: { item_id: selectedItemId.value } }) as any) || []
    batchRows.value = rows.map((b: any) => ({ ...b, counted: Number(b.quantity || 0) }))
  } catch (e: any) {
    ElMessage.error('批次加载失败：' + (e?.response?.data?.detail || e?.message || '未知错误'))
  }
}
async function submitCheck() {
  if (!editable.value) { ElMessage.warning('无操作权限'); return }
  if (!selectedItemId.value || !batchRows.value.length) return
  const adjustments = batchRows.value.map((b: any) => ({ batch_id: b.id, counted: Number(b.counted ?? b.quantity ?? 0) }))
  submitting.value = true
  try {
    await api.post('/stock/check', { item_id: selectedItemId.value, note: checkNote.value, adjustments })
    ElMessage.success('盘点完成，已按实盘调整库存')
    loadBatches()
  } catch (e: any) {
    ElMessage.error('盘点失败：' + (e?.response?.data?.detail || e?.message || '未知错误'))
  } finally {
    submitting.value = false
  }
}

// 从总览/预警跳转带入 item_id
watch(() => route.query.item_id, (v) => {
  if (v) { selectedItemId.value = Number(v); loadBatches() }
}, { immediate: true })

onMounted(() => { loadItems() })
</script>

<style scoped lang="scss">
.stock-check {
  .in-qty { color: #67c23a; font-weight: 600; }
  .out-qty { color: #f56c6c; font-weight: 600; }
}
.cards { display: flex; flex-direction: column; gap: 10px; }
.card {
  background: #fff; border: 1px solid #e8e0d8; border-radius: 10px; padding: 12px 14px;
  box-shadow: 0 1px 3px rgba(0,0,0,0.05);
}
.card .card-head { display: flex; align-items: center; justify-content: space-between; margin-bottom: 8px; }
.card .card-name { font-size: 17px; font-weight: 600; color: #2C1810; }
.card .card-body { display: flex; flex-direction: column; gap: 6px; }
.card .card-row { display: flex; align-items: center; font-size: 14px; line-height: 1.5; }
.card .card-row .label { flex-shrink: 0; width: 54px; color: #8a7563; }
.card .card-row .value { flex: 1; color: #333; word-break: break-all; }

@media (max-width: 767px) {
  :deep(.el-form--inline .el-form-item) { display: block; margin-right: 0; margin-bottom: 8px; }
  :deep(.el-form--inline .el-form-item__content) { display: block; max-width: 100%; }
}
</style>
