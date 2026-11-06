<template>
  <div class="reports">
    <el-card shadow="hover" class="main-card">
      <template #header>
        <div class="tcm-head">
          <div class="tcm-head__title">
            <span class="tcm-head__icon">📊</span>
            <span class="tcm-head__text">进销存报表</span>
            <el-tag v-if="range" size="small" effect="light" round class="tcm-head__count">{{ range[0] }} ~ {{ range[1] }}</el-tag>
          </div>
          <div class="tcm-head__actions">
            <el-date-picker v-model="range" type="daterange" value-format="YYYY-MM-DD" range-separator="至" start-placeholder="起始" end-placeholder="结束" class="filter-range" />
            <el-button type="primary" @click="loadAll">查询</el-button>
          </div>
        </div>
      </template>

      <!-- 汇总 -->
      <el-descriptions title="期间进销存汇总" :column="isMobile ? 1 : 3" border size="small" class="summary-box">
        <el-descriptions-item label="采购成本">¥{{ Number(summary.purchase_cost || 0).toFixed(2) }}</el-descriptions-item>
        <el-descriptions-item label="销售收入">¥{{ Number(summary.sales_revenue || 0).toFixed(2) }}</el-descriptions-item>
        <el-descriptions-item label="销售成本(COGS)">¥{{ Number(summary.cogs || 0).toFixed(2) }}</el-descriptions-item>
        <el-descriptions-item label="毛利">¥{{ Number(summary.gross_profit || 0).toFixed(2) }}</el-descriptions-item>
        <el-descriptions-item label="毛利率">{{ ((summary.gross_margin || 0) * 100).toFixed(1) }}%</el-descriptions-item>
        <el-descriptions-item label="期末库存金额">¥{{ Number(summary.ending_inventory_value || 0).toFixed(2) }}</el-descriptions-item>
      </el-descriptions>

      <el-tabs v-model="tab">
        <el-tab-pane label="毛利明细(按物品)" name="profit">
          <el-table v-if="!isMobile" :data="profit" class="tcm-table" size="small" empty-text="暂无数据">
            <el-table-column prop="item_name" label="物品" min-width="140" />
            <el-table-column prop="unit" label="单位" width="70" />
            <el-table-column label="收入" width="120"><template #default="{ row }">¥{{ Number(row.revenue).toFixed(2) }}</template></el-table-column>
            <el-table-column label="成本" width="120"><template #default="{ row }">¥{{ Number(row.cogs).toFixed(2) }}</template></el-table-column>
            <el-table-column label="毛利" width="120"><template #default="{ row }">¥{{ Number(row.gross_profit).toFixed(2) }}</template></el-table-column>
            <el-table-column label="毛利率" width="100"><template #default="{ row }">{{ (row.gross_margin * 100).toFixed(1) }}%</template></el-table-column>
          </el-table>
          <div v-if="isMobile" class="cards">
            <div v-for="(row, i) in cardsOf('profit', profit)" :key="i" class="card">
              <div class="card-head">
                <span class="card-name">{{ row.item_name }}</span>
                <el-tag :type="row.gross_profit >= 0 ? 'success' : 'danger'" size="small">{{ (row.gross_margin * 100).toFixed(1) }}%</el-tag>
              </div>
              <div class="card-row"><span class="label">收入</span><span class="value">¥{{ Number(row.revenue).toFixed(2) }}</span></div>
              <div class="card-row"><span class="label">成本</span><span class="value">¥{{ Number(row.cogs).toFixed(2) }}</span></div>
              <div class="card-row"><span class="label">毛利</span><span class="value" :class="row.gross_profit >= 0 ? 'pos' : 'neg'">¥{{ Number(row.gross_profit).toFixed(2) }}</span></div>
            </div>
            <el-empty v-if="!profit.length" description="暂无数据" />
          </div>
          <div v-if="hasMoreCards('profit', profit)" class="load-more">
            <el-button size="small" @click="loadMoreCards('profit', profit)">加载更多</el-button>
            <span class="no-more">已显示 {{ shownOf('profit') }} / {{ profit.length }}</span>
          </div>
        </el-tab-pane>
        <el-tab-pane label="ABC 分类(按库存金额)" name="abc">
          <el-table v-if="!isMobile" :data="abc" class="tcm-table" size="small" empty-text="暂无数据">
            <el-table-column prop="item_name" label="物品" min-width="140" />
            <el-table-column prop="unit" label="单位" width="70" />
            <el-table-column label="库存金额" width="130"><template #default="{ row }">¥{{ Number(row.stock_value).toFixed(2) }}</template></el-table-column>
            <el-table-column label="占比" width="100"><template #default="{ row }">{{ (row.value_ratio * 100).toFixed(1) }}%</template></el-table-column>
            <el-table-column label="累计" width="100"><template #default="{ row }">{{ (row.cumulative_ratio * 100).toFixed(1) }}%</template></el-table-column>
            <el-table-column label="分类" width="90"><template #default="{ row }"><el-tag :type="row.category === 'A' ? 'danger' : row.category === 'B' ? 'warning' : 'info'" size="small">{{ row.category }}</el-tag></template></el-table-column>
          </el-table>
          <div v-if="isMobile" class="cards">
            <div v-for="(row, i) in cardsOf('abc', abc)" :key="i" class="card">
              <div class="card-head">
                <span class="card-name">{{ row.item_name }}</span>
                <el-tag :type="row.category === 'A' ? 'danger' : row.category === 'B' ? 'warning' : 'info'" size="small">{{ row.category }}</el-tag>
              </div>
              <div class="card-row"><span class="label">库存金额</span><span class="value">¥{{ Number(row.stock_value).toFixed(2) }}</span></div>
              <div class="card-row"><span class="label">占比</span><span class="value">{{ (row.value_ratio * 100).toFixed(1) }}% / 累计 {{ (row.cumulative_ratio * 100).toFixed(1) }}%</span></div>
            </div>
            <el-empty v-if="!abc.length" description="暂无数据" />
          </div>
          <div v-if="hasMoreCards('abc', abc)" class="load-more">
            <el-button size="small" @click="loadMoreCards('abc', abc)">加载更多</el-button>
            <span class="no-more">已显示 {{ shownOf('abc') }} / {{ abc.length }}</span>
          </div>
        </el-tab-pane>
        <el-tab-pane label="周转率" name="turnover">
          <el-table v-if="!isMobile" :data="turnover" class="tcm-table" size="small" empty-text="暂无数据">
            <el-table-column prop="item_name" label="物品" min-width="140" />
            <el-table-column prop="unit" label="单位" width="70" />
            <el-table-column label="COGS" width="120"><template #default="{ row }">¥{{ Number(row.cogs).toFixed(2) }}</template></el-table-column>
            <el-table-column label="平均库存金额" width="140"><template #default="{ row }">¥{{ Number(row.avg_inventory_value).toFixed(2) }}</template></el-table-column>
            <el-table-column label="周转率" width="100"><template #default="{ row }">{{ Number(row.turnover).toFixed(2) }}</template></el-table-column>
          </el-table>
          <div v-if="isMobile" class="cards">
            <div v-for="(row, i) in cardsOf('turnover', turnover)" :key="i" class="card">
              <div class="card-head">
                <span class="card-name">{{ row.item_name }}</span>
                <el-tag size="small">周转 {{ Number(row.turnover).toFixed(2) }}</el-tag>
              </div>
              <div class="card-row"><span class="label">COGS</span><span class="value">¥{{ Number(row.cogs).toFixed(2) }}</span></div>
              <div class="card-row"><span class="label">平均库存</span><span class="value">¥{{ Number(row.avg_inventory_value).toFixed(2) }}</span></div>
            </div>
            <el-empty v-if="!turnover.length" description="暂无数据" />
          </div>
          <div v-if="hasMoreCards('turnover', turnover)" class="load-more">
            <el-button size="small" @click="loadMoreCards('turnover', turnover)">加载更多</el-button>
            <span class="no-more">已显示 {{ shownOf('turnover') }} / {{ turnover.length }}</span>
          </div>
        </el-tab-pane>
        <el-tab-pane label="供应商比价" name="price">
          <el-table v-if="!isMobile" :data="prices" class="tcm-table" size="small" empty-text="暂无数据">
            <el-table-column prop="item_name" label="物品" min-width="140" />
            <el-table-column prop="unit" label="单位" width="70" />
            <el-table-column prop="supplier_name" label="供应商" width="140" />
            <el-table-column label="最低进价" width="110"><template #default="{ row }">¥{{ Number(row.min_cost).toFixed(2) }}</template></el-table-column>
            <el-table-column label="最高进价" width="110"><template #default="{ row }">¥{{ Number(row.max_cost).toFixed(2) }}</template></el-table-column>
            <el-table-column label="平均进价" width="110"><template #default="{ row }">¥{{ Number(row.avg_cost).toFixed(2) }}</template></el-table-column>
            <el-table-column label="最近进价" width="110"><template #default="{ row }">¥{{ Number(row.last_cost).toFixed(2) }}</template></el-table-column>
          </el-table>
          <div v-if="isMobile" class="cards">
            <div v-for="(row, i) in cardsOf('price', prices)" :key="i" class="card">
              <div class="card-head">
                <span class="card-name">{{ row.item_name }}</span>
                <span class="card-amount">¥{{ Number(row.last_cost).toFixed(2) }}</span>
              </div>
              <div class="card-row"><span class="label">供应商</span><span class="value">{{ row.supplier_name || '-' }}</span></div>
              <div class="card-row"><span class="label">进价区间</span><span class="value">¥{{ Number(row.min_cost).toFixed(2) }} ~ ¥{{ Number(row.max_cost).toFixed(2) }}</span></div>
              <div class="card-row"><span class="label">平均进价</span><span class="value">¥{{ Number(row.avg_cost).toFixed(2) }}</span></div>
              <div class="card-row"><span class="label">最近进价</span><span class="value">¥{{ Number(row.last_cost).toFixed(2) }}</span></div>
            </div>
            <el-empty v-if="!prices.length" description="暂无数据" />
          </div>
          <div v-if="hasMoreCards('price', prices)" class="load-more">
            <el-button size="small" @click="loadMoreCards('price', prices)">加载更多</el-button>
            <span class="no-more">已显示 {{ shownOf('price') }} / {{ prices.length }}</span>
          </div>
        </el-tab-pane>
      </el-tabs>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onBeforeUnmount } from 'vue'
import { ElMessage } from 'element-plus'
import api, { errMsg } from '@/utils/api'

const isMobile = ref(false)
function updateViewport() { isMobile.value = window.innerWidth < 768 }

const cardPageSize = 20
const shownCounts = ref<Record<string, number>>({})
function shownOf(k: string) { return shownCounts.value[k] ?? cardPageSize }
function cardsOf(k: string, list: any[]) {
  return isMobile.value ? list.slice(0, shownOf(k)) : list
}
function hasMoreCards(k: string, list: any[]) {
  return shownOf(k) < list.length
}
function loadMoreCards(k: string, list: any[]) {
  shownCounts.value[k] = Math.min(shownOf(k) + cardPageSize, list.length)
}

const range = ref<any>(null)
const tab = ref('profit')
const summary = ref<any>({})
const profit = ref<any[]>([])
const abc = ref<any[]>([])
const turnover = ref<any[]>([])
const prices = ref<any[]>([])

async function loadAll() {
  const params: Record<string, any> = {}
  if (range.value && range.value.length === 2) { params.start = range.value[0]; params.end = range.value[1] }
  try {
    const [s, p, a, t, pr] = await Promise.all([
      api.get<Record<string, any>>('/stock/report/summary', { params }),
      api.get<unknown[]>('/stock/report/profit', { params }),
      api.get<unknown[]>('/stock/report/abc'),
      api.get<unknown[]>('/stock/report/turnover', { params }),
      api.get<unknown[]>('/stock/report/supplier-price'),
    ])
    summary.value = s
    profit.value = p || []
    abc.value = a || []
    turnover.value = t || []
    prices.value = pr || []
    shownCounts.value = {}
  } catch (e: any) { ElMessage.error('加载失败：' + errMsg(e)) }
}

onMounted(() => {
  updateViewport()
  window.addEventListener('resize', updateViewport)
  loadAll()
})
onBeforeUnmount(() => window.removeEventListener('resize', updateViewport))
</script>

<style scoped lang="scss">
.reports {
  .main-card {
    border-radius: 12px;
    border: 1px solid #f0e4d6;

    :deep(.el-card__header) { padding: 0; border-bottom: none; }
  }

  .filter-range { width: 260px; }
  .summary-box { margin-bottom: 16px; }

  .cards { display: flex; flex-direction: column; gap: 8px; }
  .card { border: 1px solid #f0e4d6; border-radius: 10px; padding: 10px 12px; background: #fff; box-shadow: 0 1px 3px rgba(44,24,16,.04); }
  .card .card-head { display: flex; justify-content: space-between; align-items: center; gap: 8px; margin-bottom: 6px; }
  .card .card-name { font-size: 16px; font-weight: 600; color: #2c1810; word-break: break-all; }
  .card .card-amount { font-size: 15px; font-weight: 600; color: #8b5e34; flex-shrink: 0; font-variant-numeric: tabular-nums; }
  .card .card-row { display: flex; align-items: flex-start; font-size: 14px; line-height: 1.6; }
  .card .card-row .label { flex-shrink: 0; width: 70px; color: #8a7563; }
  .card .card-row .value { flex: 1; color: #4a3628; word-break: break-all; font-variant-numeric: tabular-nums; }
  .card .card-row .value.pos { color: #5f8b56; }
  .card .card-row .value.neg { color: #b5624f; }

  .load-more { display: flex; flex-direction: column; align-items: center; gap: 6px; padding: 14px 0 2px; }
  .load-more .el-button { min-width: 140px; }
  .load-more .no-more { font-size: 12px; color: #a08b76; font-variant-numeric: tabular-nums; }
}

@media (max-width: 767px) {
  .reports {
    :deep(.el-card__header) { padding: 0; }
    :deep(.el-card__body) { padding: 12px; }
    :deep(.el-descriptions__body .el-descriptions__table) { table-layout: fixed; }
    :deep(.el-tabs__item) { font-size: 13px; padding: 0 10px; }
  }
}
</style>