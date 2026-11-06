<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useRouter } from 'vue-router'
import api, { errMsg } from '@/utils/api'
import { useAuthStore } from '@/store/auth'

const auth = useAuthStore()
const router = useRouter()
const canClear = computed(() => auth.can('system:write'))

const days = ref(30)
const loading = ref(false)
const pricingConfigured = ref(false)
const totals = ref<Record<string, number>>({})
const trend = ref<Array<{ date: string; calls: number; tokens: number; cost: number }>>([])
const byModel = ref<any[]>([])
const byScene = ref<any[]>([])
const byUser = ref<any[]>([])
const metric = ref<'cost' | 'calls' | 'tokens'>('cost')

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

onMounted(loadAll)
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
            <el-radio-group v-model="days" size="small" @change="loadAll">
              <el-radio-button :value="7">近7天</el-radio-button>
              <el-radio-button :value="30">近30天</el-radio-button>
              <el-radio-button :value="90">近90天</el-radio-button>
            </el-radio-group>
            <el-button size="small" @click="exportCsv">导出 CSV</el-button>
            <el-button v-if="canClear" size="small" type="danger" plain @click="clearLogs">清空记录</el-button>
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
        <div class="trend-chart">
          <div v-for="t in trend" :key="t.date" class="trend-col" :title="tooltip(t)">
            <div class="trend-bar" :style="{ height: barHeight(t) }"></div>
          </div>
        </div>
        <div class="trend-axis">
          <span>{{ trend[0]?.date || '' }}</span>
          <span>{{ trend[trend.length - 1]?.date || '' }}</span>
        </div>
      </div>

      <div class="tcm-section-title section-gap">
        <span class="tcm-section-title__dot"></span><span>分组统计</span>
      </div>
      <el-tabs>
        <el-tab-pane label="按模型">
          <el-table :data="byModel" size="small" class="tcm-table" empty-text="暂无数据">
            <el-table-column prop="model" label="模型" min-width="160" />
            <el-table-column label="类型" width="90"><template #default="{ row }">{{ row.is_vision ? 'Vision' : '对话' }}</template></el-table-column>
            <el-table-column prop="calls" label="调用" width="90" />
            <el-table-column label="Token" width="120"><template #default="{ row }">{{ num(row.tokens) }}</template></el-table-column>
            <el-table-column label="估算费用" width="130"><template #default="{ row }">{{ money(row.cost) }}</template></el-table-column>
          </el-table>
        </el-tab-pane>
        <el-tab-pane label="按场景">
          <el-table :data="byScene" size="small" class="tcm-table" empty-text="暂无数据">
            <el-table-column prop="scene_label" label="场景" min-width="160" />
            <el-table-column prop="calls" label="调用" width="90" />
            <el-table-column label="Token" width="120"><template #default="{ row }">{{ num(row.tokens) }}</template></el-table-column>
            <el-table-column label="估算费用" width="130"><template #default="{ row }">{{ money(row.cost) }}</template></el-table-column>
          </el-table>
        </el-tab-pane>
        <el-tab-pane label="按账号">
          <el-table :data="byUser" size="small" class="tcm-table" empty-text="暂无数据">
            <el-table-column prop="username" label="账号" min-width="160" />
            <el-table-column prop="calls" label="调用" width="90" />
            <el-table-column label="Token" width="120"><template #default="{ row }">{{ num(row.tokens) }}</template></el-table-column>
            <el-table-column label="估算费用" width="130"><template #default="{ row }">{{ money(row.cost) }}</template></el-table-column>
          </el-table>
        </el-tab-pane>
      </el-tabs>

      <div class="tcm-section-title section-gap">
        <span class="tcm-section-title__dot"></span><span>调用明细</span>
      </div>
      <el-table :data="logs" size="small" class="tcm-table" empty-text="暂无 AI 调用记录">
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
      <el-pagination
        v-model:current-page="page" :page-size="pageSize" :total="logTotal"
        layout="total, prev, pager, next" background class="usage-pager"
        @current-change="loadLogs"
      />
    </el-card>
  </div>
</template>

<style scoped>
.ai-usage-page { padding: 2px; }
.tcm-head { display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 10px; }
.tcm-head__title { display: flex; align-items: center; gap: 8px; font-size: 16px; font-weight: 600; }
.tcm-head__icon { font-size: 18px; }
.tcm-head__actions { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
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
.trend-col { flex: 1 1 0; min-width: 3px; height: 100%; display: flex; align-items: flex-end; }
.trend-bar { width: 100%; background: var(--el-color-primary); opacity: .78; border-radius: 2px 2px 0 0; transition: height .3s; }
.trend-bar:hover { opacity: 1; }
.trend-axis { display: flex; justify-content: space-between; font-size: 12px; color: var(--el-text-color-secondary); margin-top: 6px; }
.usage-pager { margin-top: 14px; justify-content: flex-end; }
</style>
