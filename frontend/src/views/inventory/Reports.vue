<template>
  <div class="reports">
    <el-card shadow="hover">
      <template #header>
        <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:8px;">
          <span>📊 进销存报表</span>
          <div style="display:flex;gap:8px;align-items:center;">
            <el-date-picker v-model="range" type="daterange" value-format="YYYY-MM-DD" range-separator="至" start-placeholder="起始" end-placeholder="结束" style="width:240px" />
            <el-button type="primary" size="small" @click="loadAll">查询</el-button>
          </div>
        </div>
      </template>

      <!-- 汇总 -->
      <el-descriptions title="期间进销存汇总" :column="3" border size="small" style="margin-bottom:16px">
        <el-descriptions-item label="采购成本">¥{{ Number(summary.purchase_cost || 0).toFixed(2) }}</el-descriptions-item>
        <el-descriptions-item label="销售收入">¥{{ Number(summary.sales_revenue || 0).toFixed(2) }}</el-descriptions-item>
        <el-descriptions-item label="销售成本(COGS)">¥{{ Number(summary.cogs || 0).toFixed(2) }}</el-descriptions-item>
        <el-descriptions-item label="毛利">¥{{ Number(summary.gross_profit || 0).toFixed(2) }}</el-descriptions-item>
        <el-descriptions-item label="毛利率">{{ ((summary.gross_margin || 0) * 100).toFixed(1) }}%</el-descriptions-item>
        <el-descriptions-item label="期末库存金额">¥{{ Number(summary.ending_inventory_value || 0).toFixed(2) }}</el-descriptions-item>
      </el-descriptions>

      <el-tabs v-model="tab">
        <el-tab-pane label="毛利明细(按物品)" name="profit">
          <el-table :data="profit" stripe size="small" empty-text="暂无数据">
            <el-table-column prop="item_name" label="物品" min-width="140" />
            <el-table-column prop="unit" label="单位" width="70" />
            <el-table-column label="收入" width="120"><template #default="{ row }">¥{{ Number(row.revenue).toFixed(2) }}</template></el-table-column>
            <el-table-column label="成本" width="120"><template #default="{ row }">¥{{ Number(row.cogs).toFixed(2) }}</template></el-table-column>
            <el-table-column label="毛利" width="120"><template #default="{ row }">¥{{ Number(row.gross_profit).toFixed(2) }}</template></el-table-column>
            <el-table-column label="毛利率" width="100"><template #default="{ row }">{{ (row.gross_margin * 100).toFixed(1) }}%</template></el-table-column>
          </el-table>
        </el-tab-pane>
        <el-tab-pane label="ABC 分类(按库存金额)" name="abc">
          <el-table :data="abc" stripe size="small" empty-text="暂无数据">
            <el-table-column prop="item_name" label="物品" min-width="140" />
            <el-table-column prop="unit" label="单位" width="70" />
            <el-table-column label="库存金额" width="130"><template #default="{ row }">¥{{ Number(row.stock_value).toFixed(2) }}</template></el-table-column>
            <el-table-column label="占比" width="100"><template #default="{ row }">{{ (row.value_ratio * 100).toFixed(1) }}%</template></el-table-column>
            <el-table-column label="累计" width="100"><template #default="{ row }">{{ (row.cumulative_ratio * 100).toFixed(1) }}%</template></el-table-column>
            <el-table-column label="分类" width="90"><template #default="{ row }"><el-tag :type="row.category === 'A' ? 'danger' : row.category === 'B' ? 'warning' : 'info'" size="small">{{ row.category }}</el-tag></template></el-table-column>
          </el-table>
        </el-tab-pane>
        <el-tab-pane label="周转率" name="turnover">
          <el-table :data="turnover" stripe size="small" empty-text="暂无数据">
            <el-table-column prop="item_name" label="物品" min-width="140" />
            <el-table-column prop="unit" label="单位" width="70" />
            <el-table-column label="COGS" width="120"><template #default="{ row }">¥{{ Number(row.cogs).toFixed(2) }}</template></el-table-column>
            <el-table-column label="平均库存金额" width="140"><template #default="{ row }">¥{{ Number(row.avg_inventory_value).toFixed(2) }}</template></el-table-column>
            <el-table-column label="周转率" width="100"><template #default="{ row }">{{ Number(row.turnover).toFixed(2) }}</template></el-table-column>
          </el-table>
        </el-tab-pane>
        <el-tab-pane label="供应商比价" name="price">
          <el-table :data="prices" stripe size="small" empty-text="暂无数据">
            <el-table-column prop="item_name" label="物品" min-width="140" />
            <el-table-column prop="unit" label="单位" width="70" />
            <el-table-column prop="supplier_name" label="供应商" width="140" />
            <el-table-column label="最低进价" width="110"><template #default="{ row }">¥{{ Number(row.min_cost).toFixed(2) }}</template></el-table-column>
            <el-table-column label="最高进价" width="110"><template #default="{ row }">¥{{ Number(row.max_cost).toFixed(2) }}</template></el-table-column>
            <el-table-column label="平均进价" width="110"><template #default="{ row }">¥{{ Number(row.avg_cost).toFixed(2) }}</template></el-table-column>
            <el-table-column label="最近进价" width="110"><template #default="{ row }">¥{{ Number(row.last_cost).toFixed(2) }}</template></el-table-column>
          </el-table>
        </el-tab-pane>
      </el-tabs>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import api from '@/utils/api'

const range = ref<any>(null)
const tab = ref('profit')
const summary = ref<any>({})
const profit = ref<any[]>([])
const abc = ref<any[]>([])
const turnover = ref<any[]>([])
const prices = ref<any[]>([])

async function loadAll() {
  const params: any = {}
  if (range.value && range.value.length === 2) { params.start = range.value[0]; params.end = range.value[1] }
  try {
    const [s, p, a, t, pr] = await Promise.all([
      api.get('/stock/report/summary', { params }),
      api.get('/stock/report/profit', { params }),
      api.get('/stock/report/abc'),
      api.get('/stock/report/turnover', { params }),
      api.get('/stock/report/supplier-price'),
    ])
    summary.value = s as any
    profit.value = (p as any) || []
    abc.value = (a as any) || []
    turnover.value = (t as any) || []
    prices.value = (pr as any) || []
  } catch (e: any) { ElMessage.error('加载失败：' + (e?.response?.data?.detail || e?.message)) }
}

onMounted(loadAll)
</script>

<style scoped lang="scss">
.reports { .el-descriptions { margin-top: 4px; } }
</style>
