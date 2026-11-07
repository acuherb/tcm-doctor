<script setup lang="ts">
import { ref, computed, onMounted, onBeforeUnmount } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useRouter } from 'vue-router'
import api, { errMsg } from '@/utils/api'
import { useAuthStore } from '@/store/auth'

const auth = useAuthStore()
const router = useRouter()
const canClear = computed(() => auth.can('system:write'))

// 窄屏：表格改卡片列表（与操作日志 / 药材字典等页面一致）
const isMobile = ref(false)
function syncMobile() { isMobile.value = window.innerWidth < 768 }

const days = ref(30)
const loading = ref(false)
const pricingConfigured = ref(false)
const totals = ref<Record<string, number>>({})
const trend = ref<Array<{ date: string; calls: number; tokens: number; cost: number }>>([])
const byModel = ref<any[]>([])
const byScene = ref<any[]>([])
const byUser = ref<any[]>([])
const metric = ref<'cost' | 'calls' | 'tokens'>('cost')
const selectedDay = ref('')
const groupTab = ref<'model' | 'scene' | 'user'>('model')

const logs = ref<any[]>([])
const logTotal = ref(0)
const page = ref(1)
const pageSize = ref(20)

interface Summary {
  days: number
  pricing_configured: boolean
  totals: Record<string, number>
  trend: Array<{ date: string; calls: number; tokens: number; cost: number }>
  by_model: any[]
  by_scene: any[]
  by_user: any[]
}

async function loadSummary() {
  loading.value = true
  try {
    const r = await api.get<Summary>('/ai-usage/summary', { params: { days: days.value } })
    pricingConfigured.value = r.pricing_configured
    totals.value = r.totals || {}
    trend.value = r.trend || []
    byModel.value = r.by_model || []
    byScene.value = r.by_scene || []
    byUser.value = r.by_user || []
    // 默认选中「今天」：手机端无 hover，下方详情条直接给出当日数据
    selectedDay.value = trend.value.length ? trend.value[trend.value.length - 1].date : ''
  } catch (e) {
    ElMessage.error(errMsg(e) || '加载 AI 用量失败')
  } finally {
    loading.value = false
  }
}

async function loadLogs() {
  try {
    const r = await api.get<{ items: any[]; total: number }>('/ai-usage/logs', {
      params: { page: page.value, page_size: pageSize.value },
    })
    logs.value = r.items || []
    logTotal.value = r.total || 0
  } catch { /* 拦截器已提示 */ }
}

function loadAll() { loadSummary(); page.value = 1; loadLogs() }

function money(v: number | undefined): string {
  if (!pricingConfigured.value) return '—'
  return `¥${Number(v || 0).toFixed(4)}`
}
function num(v: number | undefined): string {
  return Number(v || 0).toLocaleString('zh-CN')
}
function metricValue(t: { calls: number; tokens: number; cost: number }): number {
  return t[metric.value]
}
const maxMetric = computed(() => Math.max(1, ...trend.value.map(metricValue)))
function barHeight(t: { calls: number; tokens: number; cost: number }): string {
  return `${Math.max(2, (metricValue(t) / maxMetric.value) * 100)}%`
}
function tooltip(t: { date: string; calls: number; tokens: number; cost: number }): string {
  return `${t.date}　调用 ${t.calls} 次　${num(t.tokens)} tokens　${money(t.cost)}`
}
// 手机端按天数撑开画布并允许横向滚动，柱子至少 8px 才点得到
const chartStyle = computed<Record<string, string>>(() =>
  isMobile.value ? { minWidth: `${Math.max(280, trend.value.length * 8)}px` } : {},
)
const selectedTrend = computed(() => trend.value.find(t => t.date === selectedDay.value) || null)

// 分组统计：单一列表 + 切换器，避免窄屏下三张宽表格
const groupNameKey = computed(() => (
  { model: 'model', scene: 'scene_label', user: 'username' } as const
)[groupTab.value])
const groupLabel = computed(() => (
  { model: '模型', scene: '场景', user: '账号' } as const
)[groupTab.value])
const groupRows = computed<any[]>(() => (
  { model: byModel.value, scene: byScene.value, user: byUser.value }
)[groupTab.value])

async function exportCsv() {
  try {
    const blob = await api.get<Blob>('/ai-usage/export', {
      params: { days: days.value }, responseType: 'blob',
    })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `ai-usage-${days.value}days.csv`
    a.click()
    URL.revokeObjectURL(url)
  } catch (e) {
    ElMessage.error(errMsg(e) || '导出失败')
  }
}

async function clearLogs() {
  try {
    await ElMessageBox.confirm(
      '将清空全部 AI 用量记录（不可恢复），用量与费用统计从零重新累计。是否继续？',
      '清空 AI 用量记录', { type: 'warning', confirmButtonText: '确认清空', cancelButtonText: '取消' },
    )
  } catch { return }
  try {
    await api.delete('/ai-usage/logs')
    ElMessage.success('已清空 AI 用量记录')
    loadAll()
  } catch (e) {
    ElMessage.error(errMsg(e) || '清空失败')
  }
}

onMounted(() => {
  syncMobile()
  window.addEventListener('resize', syncMobile)
  loadAll()
})
onBeforeUnmount(() => window.removeEventListener('resize', syncMobile))
</script>

<template>
  <div class="ai-usage-page">
    <el-card shadow="hover" class="main-card" v-loading="loading">
      <template #header>
        <div class="tcm-head">
          <div class="tcm-head__title">
            <span class="tcm-head__icon">🤖</span>
            <span class="tcm-head__text">AI 用量与成本</span>
            <el-tag size="small" effect="light" round class="tcm-head__count">近 {{ days }} 天</el-tag>
          </div>
          <div class="tcm-head__actions">
            <el-radio-group v-model="days" size="small" class="days-switch" @change="loadAll">
              <el-radio-button :value="7">近7天</el-radio-button>
              <el-radio-button :value="30">近30天</el-radio-button>
              <el-radio-button :value="90">近90天</el-radio-button>
            </el-radio-group>
            <div class="head-btns">
              <el-button size="small" @click="exportCsv">导出 CSV</el-button>
              <el-button v-if="canClear" size="small" type="danger" plain @click="clearLogs">清空记录</el-button>
            </div>
          </div>
        </div>
      </template>

      <el-alert v-if="!pricingConfigured" type="warning" :closable="false" show-icon class="usage-alert">
        <template #title>尚未配置 AI 单价，当前仅统计 token 用量，费用显示为「—」。</template>
        请到
        <el-link type="primary" :underline="false" @click="router.push('/settings')">系统设置 → AI 计费单价</el-link>
        按服务商实际价格填写后，费用才会估算。
      </el-alert>
      <el-alert v-else type="info" :closable="false" show-icon class="usage-alert">
        <template #title>费用为按所配置单价计算的估算值，最终以服务商账单为准。</template>
        仅统计本功能启用后的调用，历史用量无法回溯；记录费用按「调用当时」的单价计算，之后改价不会重算历史。
      </el-alert>

      <el-row :gutter="16" class="stat-row">
        <el-col :xs="12" :sm="6">
          <div class="stat-card"><div class="stat-label">调用次数</div><div class="stat-value">{{ num(totals.calls) }}</div><div class="stat-sub">失败 {{ num(totals.failed_calls) }} 次</div></div>
        </el-col>
        <el-col :xs="12" :sm="6">
          <div class="stat-card"><div class="stat-label">总 token</div><div class="stat-value">{{ num(totals.total_tokens) }}</div><div class="stat-sub">输入 {{ num(totals.prompt_tokens) }} / 输出 {{ num(totals.completion_tokens) }}</div></div>
        </el-col>
        <el-col :xs="12" :sm="6">
          <div class="stat-card"><div class="stat-label">缓存命中</div><div class="stat-value">{{ num(totals.cache_hit_tokens) }}</div><div class="stat-sub">输入 token 中命中缓存</div></div>
        </el-col>
        <el-col :xs="12" :sm="6">
          <div class="stat-card"><div class="stat-label">估算费用</div><div class="stat-value is-primary">{{ money(totals.cost) }}</div><div class="stat-sub">元（人民币）</div></div>
        </el-col>
      </el-row>

      <div class="tcm-section-title section-gap">
        <span class="tcm-section-title__dot"></span><span>每日趋势</span>
        <el-radio-group v-model="metric" size="small" class="metric-switch">
          <el-radio-button value="cost">费用</el-radio-button>
          <el-radio-button value="calls">次数</el-radio-button>
          <el-radio-button value="tokens">Token</el-radio-button>
        </el-radio-group>
      </div>
      <div class="trend-wrap">
        <div class="trend-chart" :style="chartStyle">
          <div v-for="t in trend" :key="t.date" class="trend-col"
               :class="{ 'is-active': selectedDay === t.date }"
               :title="tooltip(t)" @click="selectedDay = t.date">
            <div class="trend-bar" :style="{ height: barHeight(t) }"></div>
          </div>
        </div>
        <div class="trend-axis">
          <span>{{ trend[0]?.date || '' }}</span>
          <span>{{ trend[trend.length - 1]?.date || '' }}</span>
        </div>
        <div v-if="isMobile && selectedTrend" class="trend-detail">
          <span class="td-date">{{ selectedTrend.date }}</span>
          <span>调用 <b>{{ num(selectedTrend.calls) }}</b></span>
          <span><b>{{ num(selectedTrend.tokens) }}</b> tokens</span>
          <span class="td-cost">{{ money(selectedTrend.cost) }}</span>
        </div>
      </div>

      <div class="tcm-section-title section-gap">
        <span class="tcm-section-title__dot"></span><span>分组统计</span>
      </div>
      <div class="group-switch">
        <el-radio-group v-model="groupTab" size="small">
          <el-radio-button value="model">按模型</el-radio-button>
          <el-radio-button value="scene">按场景</el-radio-button>
          <el-radio-button value="user">按账号</el-radio-button>
        </el-radio-group>
      </div>

      <el-table v-if="!isMobile" :data="groupRows" size="small" class="tcm-table" empty-text="暂无数据">
        <el-table-column :label="groupLabel" min-width="160">
          <template #default="{ row }">
            {{ row[groupNameKey] }}
            <el-tag v-if="groupTab === 'model'" size="small" effect="plain">{{ row.is_vision ? 'Vision' : '对话' }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="calls" label="调用" width="90" />
        <el-table-column label="Token" width="120"><template #default="{ row }">{{ num(row.tokens) }}</template></el-table-column>
        <el-table-column label="估算费用" width="130"><template #default="{ row }">{{ money(row.cost) }}</template></el-table-column>
      </el-table>
      <div v-else class="group-cards">
        <div v-for="(row, i) in groupRows" :key="i" class="group-card">
          <div class="gc-top">
            <span class="gc-name">{{ row[groupNameKey] || '—' }}</span>
            <el-tag v-if="groupTab === 'model'" size="small" effect="plain">{{ row.is_vision ? 'Vision' : '对话' }}</el-tag>
            <span class="gc-cost">{{ money(row.cost) }}</span>
          </div>
          <div class="gc-meta">调用 {{ num(row.calls) }} 次<span class="dot">·</span>{{ num(row.tokens) }} tokens</div>
        </div>
        <el-empty v-if="!groupRows.length" description="暂无数据" :image-size="60" />
      </div>

      <div class="tcm-section-title section-gap">
        <span class="tcm-section-title__dot"></span><span>调用明细</span>
      </div>
      <el-table v-if="!isMobile" :data="logs" size="small" class="tcm-table" empty-text="暂无 AI 调用记录">
        <el-table-column label="时间" width="160"><template #default="{ row }">{{ (row.created_at || '').replace('T', ' ').slice(0, 19) }}</template></el-table-column>
        <el-table-column prop="username" label="账号" width="100" />
        <el-table-column prop="scene_label" label="场景" width="110" />
        <el-table-column prop="model" label="模型" min-width="140" />
        <el-table-column label="输入 / 输出" width="140"><template #default="{ row }">{{ num(row.prompt_tokens) }} / {{ num(row.completion_tokens) }}</template></el-table-column>
        <el-table-column label="缓存命中" width="100"><template #default="{ row }">{{ num(row.cache_hit_tokens) }}</template></el-table-column>
        <el-table-column label="费用" width="110"><template #default="{ row }">{{ money(row.cost) }}</template></el-table-column>
        <el-table-column label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="row.success ? 'success' : 'danger'" size="small" effect="plain">{{ row.success ? '成功' : '失败' }}</el-tag>
          </template>
        </el-table-column>
      </el-table>
      <div v-else class="log-cards">
        <div v-for="row in logs" :key="row.id" class="log-card" :class="{ 'is-fail': !row.success }">
          <div class="log-head">
            <span class="log-scene">{{ row.scene_label }}</span>
            <el-tag :type="row.success ? 'success' : 'danger'" size="small" effect="plain">{{ row.success ? '成功' : '失败' }}</el-tag>
            <span class="log-time">{{ (row.created_at || '').replace('T', ' ').slice(5, 16) }}</span>
          </div>
          <div class="log-model">{{ row.model || '—' }}<span class="log-user">· {{ row.username || '—' }}</span></div>
          <div class="log-metrics">
            <span>输入 <b>{{ num(row.prompt_tokens) }}</b></span>
            <span>输出 <b>{{ num(row.completion_tokens) }}</b></span>
            <span>缓存 <b>{{ num(row.cache_hit_tokens) }}</b></span>
            <span class="log-cost">{{ money(row.cost) }}</span>
          </div>
          <div v-if="row.error" class="log-error">{{ row.error }}</div>
        </div>
        <el-empty v-if="!logs.length" description="暂无 AI 调用记录" :image-size="60" />
      </div>
      <el-pagination
        v-model:current-page="page" :page-size="pageSize" :total="logTotal"
        :layout="isMobile ? 'prev, pager, next' : 'total, prev, pager, next'"
        :pager-count="isMobile ? 5 : 7" :small="isMobile"
        background class="usage-pager" @current-change="loadLogs"
      />
    </el-card>
  </div>
</template>

<style lang="scss" scoped>
.ai-usage-page { padding: 2px; }
.tcm-head { display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 10px; }
.tcm-head__title { display: flex; align-items: center; gap: 8px; font-size: 16px; font-weight: 600; }
.tcm-head__icon { font-size: 18px; }
.tcm-head__actions { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.head-btns { display: flex; gap: 8px; }
.usage-alert { margin-bottom: 16px; line-height: 1.6; }
.stat-row { margin-bottom: 8px; }
.stat-card {
  border: 1px solid var(--el-border-color-lighter); border-radius: 8px;
  padding: 14px 16px; margin-bottom: 12px; background: var(--el-bg-color);
}
.stat-label { font-size: 13px; color: var(--el-text-color-secondary); }
.stat-value { font-size: 24px; font-weight: 700; margin: 6px 0 2px; }
.stat-value.is-primary { color: var(--el-color-primary); }
.stat-sub { font-size: 12px; color: var(--el-text-color-secondary); }
.section-gap { margin: 18px 0 12px; display: flex; align-items: center; gap: 8px; }
.metric-switch { margin-left: auto; }
.trend-wrap { overflow-x: auto; }
.trend-chart { display: flex; align-items: flex-end; height: 140px; min-width: 320px; gap: 2px; padding: 0 2px; }
.trend-col { flex: 1 1 0; min-width: 3px; height: 100%; display: flex; align-items: flex-end; cursor: pointer; }
.trend-bar { width: 100%; background: var(--el-color-primary); opacity: .78; border-radius: 2px 2px 0 0; transition: height .3s; }
.trend-col:hover .trend-bar, .trend-col.is-active .trend-bar { opacity: 1; }
.trend-axis { display: flex; justify-content: space-between; font-size: 12px; color: var(--el-text-color-secondary); margin-top: 6px; min-width: 320px; }
.group-switch { margin-bottom: 10px; }
.usage-pager { margin-top: 14px; justify-content: flex-end; }

/* ---------- 手机端：卡片化 + 触控可读 ---------- */
@media (max-width: 767px) {
  :deep(.el-card__header) { padding: 12px; }
  :deep(.el-card__body) { padding: 12px; }

  .tcm-head { align-items: stretch; gap: 10px; }
  .tcm-head__title { font-size: 15px; }
  .tcm-head__actions { width: 100%; flex-direction: column; align-items: stretch; gap: 8px; }
  .days-switch { display: flex; width: 100%;
    :deep(.el-radio-button) { flex: 1; }
    :deep(.el-radio-button__inner) { width: 100%; padding: 8px 4px; }
  }
  .head-btns { width: 100%;
    :deep(.el-button) { flex: 1; margin-left: 0; }
  }

  .usage-alert { margin-bottom: 12px; font-size: 12px; }
  .stat-card { padding: 10px 12px; margin-bottom: 8px; }
  .stat-label { font-size: 12px; }
  .stat-value { font-size: 20px; margin: 4px 0 2px; }
  .stat-sub { font-size: 11px; line-height: 1.4; }

  .section-gap { margin: 16px 0 10px; flex-wrap: wrap; }
  .metric-switch { margin-left: 0; width: 100%; display: flex;
    :deep(.el-radio-button) { flex: 1; }
    :deep(.el-radio-button__inner) { width: 100%; padding: 8px 4px; }
  }
  .group-switch { :deep(.el-radio-group) { display: flex; width: 100%; }
    :deep(.el-radio-button) { flex: 1; }
    :deep(.el-radio-button__inner) { width: 100%; padding: 8px 4px; }
  }

  .trend-chart { height: 120px; }
  .trend-col { min-width: 7px; }
  .trend-axis { min-width: 0; }
  .trend-detail {
    display: flex; flex-wrap: wrap; align-items: center; gap: 4px 10px;
    margin-top: 10px; padding: 8px 10px; border-radius: 6px;
    background: var(--el-fill-color-light); font-size: 12px;
    color: var(--el-text-color-regular);
    b { color: var(--el-text-color-primary); }
    .td-date { font-weight: 600; }
    .td-cost { margin-left: auto; font-weight: 700; color: var(--el-color-primary); }
  }

  .group-cards, .log-cards { display: flex; flex-direction: column; gap: 8px; }
  .group-card, .log-card {
    border: 1px solid var(--el-border-color-lighter); border-radius: 8px;
    padding: 10px 12px; background: var(--el-bg-color);
  }
  .gc-top, .log-head { display: flex; align-items: center; gap: 6px; flex-wrap: wrap; }
  .gc-name, .log-scene { font-size: 14px; font-weight: 600; word-break: break-all; }
  .gc-cost, .log-cost { margin-left: auto; font-size: 13px; font-weight: 700; color: var(--el-color-primary); white-space: nowrap; }
  .gc-meta, .log-model, .log-metrics { font-size: 12px; color: var(--el-text-color-secondary); line-height: 1.6; }
  .gc-meta { margin-top: 6px; .dot { margin: 0 6px; color: var(--el-border-color); } }
  .log-time { margin-left: auto; font-size: 12px; color: var(--el-text-color-secondary); }
  .log-model { margin-top: 6px; word-break: break-all; .log-user { margin-left: 4px; } }
  .log-metrics { display: flex; flex-wrap: wrap; gap: 4px 12px; margin-top: 6px; b { color: var(--el-text-color-primary); } }
  .log-card.is-fail { border-left: 3px solid var(--el-color-danger); }
  .log-error { margin-top: 6px; font-size: 12px; color: var(--el-color-danger); word-break: break-all; }

  .usage-pager { justify-content: center; margin-top: 12px; }
}
</style>
