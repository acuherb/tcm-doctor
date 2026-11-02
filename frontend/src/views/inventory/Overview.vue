<template>
  <div class="stock-overview">
    <!-- 预警概览 -->
    <el-card shadow="hover" style="margin-bottom:16px;">
      <template #header>
        <div style="display:flex;justify-content:space-between;align-items:center;">
          <span>⚠️ 库存预警</span>
          <el-tag :type="alerts.length > 0 ? 'danger' : 'success'" size="small">
            {{ alerts.length > 0 ? `${alerts.length} 项预警` : '库存正常' }}
          </el-tag>
        </div>
      </template>
      <el-empty v-if="alerts.length === 0" description="暂无预警" :image-size="60" />
      <el-table v-else :data="alerts" stripe size="small">
        <el-table-column prop="item_name" label="物品" min-width="140" show-overflow-tooltip />
        <el-table-column prop="item_type" label="类别" width="100">
          <template #default="{ row }"><el-tag size="small">{{ row.item_type }}</el-tag></template>
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
    </el-card>

    <!-- 库存总览 -->
    <el-card shadow="hover">
      <template #header>
        <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:8px;">
          <span>📦 库存总览（按物品聚合）</span>
          <div style="display:flex;gap:8px;">
            <el-select v-model="typeFilter" placeholder="类别" clearable @change="loadOverview" style="width:130px">
              <el-option label="全部" value="" />
              <el-option v-for="c in categories" :key="c.id" :label="c.name" :value="c.name" />
            </el-select>
            <el-checkbox v-model="alertOnly" @change="loadOverview" border size="small">仅看预警</el-checkbox>
            <el-input v-model="searchText" placeholder="搜索名称" clearable @clear="loadOverview" style="width:160px" @keyup.enter="loadOverview">
              <template #prefix><el-icon><Search /></el-icon></template>
            </el-input>
            <el-button type="primary" @click="loadOverview">查询</el-button>
          </div>
        </div>
      </template>

      <el-table v-if="!isMobile" :data="filteredOverview" stripe style="width:100%" empty-text="暂无库存">
        <el-table-column prop="item_name" label="物品" min-width="140" show-overflow-tooltip />
        <el-table-column prop="item_type" label="类别" width="100">
          <template #default="{ row }"><el-tag size="small">{{ row.item_type }}</el-tag></template>
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
        <div v-for="row in filteredOverview" :key="row.item_id" class="card">
          <div class="card-head">
            <span class="card-name">{{ row.item_name }}</span>
            <el-tag size="small">{{ row.item_type }}</el-tag>
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
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onBeforeUnmount } from 'vue'
import { useRouter } from 'vue-router'
import { Search } from '@element-plus/icons-vue'
import api from '@/utils/api'

const router = useRouter()
const overview = ref<any[]>([])
const alerts = ref<any[]>([])
const typeFilter = ref('')
const alertOnly = ref(false)
const searchText = ref('')
const categories = ref<any[]>([])
async function loadOptions() {
  try {
    const res = (await api.get('/stock/options') as any) || []
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

const isMobile = ref(false)
function updateViewport() { isMobile.value = window.innerWidth < 768 }
onMounted(() => { updateViewport(); window.addEventListener('resize', updateViewport) })
onBeforeUnmount(() => window.removeEventListener('resize', updateViewport))

async function loadOverview() {
  try {
    const params: any = {}
    if (typeFilter.value) params.item_type = typeFilter.value
    if (alertOnly.value) params.alert_only = true
    if (searchText.value) params.search = searchText.value
    overview.value = (await api.get('/stock/overview', { params }) as any) || []
  } catch (e: any) {
    console.error(e)
  }
}
async function loadAlerts() {
  try { alerts.value = (await api.get('/stock/alerts') as any) || [] } catch {}
}

function goItems(id: number) { router.push({ path: '/stock/transactions', query: { item_id: String(id) } }) }
function goTransactions(id: number) { router.push({ path: '/stock/transactions', query: { item_id: String(id) } }) }
function goCheck(id: number) { router.push({ path: '/stock/check', query: { item_id: String(id) } }) }

onMounted(() => { loadOverview(); loadAlerts(); loadOptions() })
</script>

<style scoped lang="scss">
.stock-overview {
  .low-stock { color: #f56c6c; font-weight: 700; }
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
