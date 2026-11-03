<template>
  <div class="op-log">
    <el-card shadow="hover" class="main-card">
      <template #header>
        <div class="tcm-head">
          <div class="tcm-head__title">
            <span class="tcm-head__icon">📋</span>
            <span class="tcm-head__text">操作日志</span>
            <el-tag size="small" effect="light" round class="tcm-head__count">{{ stats.total }} 条今日</el-tag>
          </div>
          <div class="tcm-head__actions">
            <el-button type="primary" @click="exportCsv"><el-icon><Download /></el-icon> 导出 CSV</el-button>
            <div class="clean-group">
              <el-input-number v-model="keepDays" :min="1" :max="3650" controls-position="right" class="keep-days" />
              <span class="clean-unit">天</span>
              <el-popconfirm title="确认清理旧日志？" @confirm="clean">
                <template #reference>
                  <el-button type="danger" plain><el-icon><Delete /></el-icon> 清理</el-button>
                </template>
              </el-popconfirm>
            </div>
          </div>
        </div>
      </template>

      <div class="stats-bar">
        <div class="stat-item"><span class="num">{{ stats.total }}</span><span class="lbl">今日操作</span></div>
        <div class="stat-item" :class="{ warn: stats.abnormal > 0 }"><span class="num">{{ stats.abnormal }}</span><span class="lbl">异常告警</span></div>
        <div class="stat-item" :class="{ fail: stats.failed > 0 }"><span class="num">{{ stats.failed }}</span><span class="lbl">失败请求</span></div>
        <div class="stat-item"><span class="num">{{ stats.active_users }}</span><span class="lbl">活跃用户</span></div>
      </div>

      <div class="tcm-filter">
        <el-radio-group v-model="tab" @change="load">
          <el-radio-button label="关键操作" value="write" />
          <el-radio-button label="仅异常" value="error" />
          <el-radio-button label="全部" value="all" />
        </el-radio-group>
        <el-select v-model="level" placeholder="全部级别" clearable class="filter-mini" @change="load">
          <el-option label="INFO" value="INFO" />
          <el-option label="WARN" value="WARN" />
          <el-option label="ERROR" value="ERROR" />
        </el-select>
        <el-select v-model="userId" placeholder="全部用户" clearable filterable class="filter-small" @change="load">
          <el-option v-for="u in userOptions" :key="u.id" :label="u.name" :value="String(u.id)" />
        </el-select>
        <el-select v-model="action" placeholder="全部动作" clearable filterable class="filter-small" @change="load">
          <el-option v-for="a in actionOptions" :key="a" :label="a" :value="a" />
        </el-select>
        <el-input v-model="keyword" placeholder="用户名/对象/接口/消息" clearable class="filter-search" @clear="load" />
        <el-date-picker v-model="range" type="daterange" value-format="YYYY-MM-DD" range-separator="至" start-placeholder="起始" end-placeholder="结束" class="filter-range" />
        <div class="filter-actions">
          <el-button type="primary" @click="load">查询</el-button>
        </div>
      </div>

      <el-table v-if="!isMobile" :data="logs" class="tcm-table" size="small" style="width:100%" empty-text="暂无日志"
                :row-class-name="rowCls" @expand-change="() => {}">
        <el-table-column type="expand">
          <template #default="{ row }">
            <div class="detail-box">
              <div class="detail-line"><span class="k">接口</span><span class="v">{{ row.method }} {{ row.endpoint }}</span></div>
              <div class="detail-line"><span class="k">结果</span><span class="v">{{ row.status_code }} {{ row.success ? '成功' : '失败' }}</span></div>
              <div v-if="row.target" class="detail-line"><span class="k">对象</span><span class="v">{{ row.target }}</span></div>
              <div class="detail-line"><span class="k">耗时</span><span class="v">{{ row.duration_ms != null ? row.duration_ms + ' ms' : '-' }}</span></div>
              <div v-if="row.message" class="detail-line"><span class="k">消息</span><span class="v">{{ row.message }}</span></div>
              <pre v-if="row.error_detail" class="err-detail">{{ row.error_detail }}</pre>
            </div>
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="时间 / 耗时" width="180">
          <template #default="{ row }">
            <div>{{ formatTime(row.created_at) }}</div>
            <span v-if="row.duration_ms != null" class="dur" :class="{ slow: row.duration_ms > 500 }">{{ row.duration_ms }} ms</span>
          </template>
        </el-table-column>
        <el-table-column prop="username" label="操作人" width="100">
          <template #default="{ row }">{{ row.username || '匿名' }}</template>
        </el-table-column>
        <el-table-column label="做了什么" min-width="220" show-overflow-tooltip>
          <template #default="{ row }">
            <span class="level-dot" :class="row.level.toLowerCase()"></span>
            <span class="summary">{{ humanize(row) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="对象" min-width="160" show-overflow-tooltip>
          <template #default="{ row }">
            <span v-if="row.target" class="target">{{ row.target }}</span>
            <span v-else class="muted">-</span>
          </template>
        </el-table-column>
        <el-table-column label="结果" width="130">
          <template #default="{ row }">
            <span :class="row.success ? 'ok' : 'fail'">
              {{ row.success ? '✓ 成功' : '✗ ' + (statusText(row.status_code, row.action)) }}
            </span>
          </template>
        </el-table-column>
        <el-table-column prop="message" label="消息" min-width="160" show-overflow-tooltip />
      </el-table>

      <div v-if="isMobile" class="log-cards">
        <div v-for="row in logs" :key="row.id" class="log-card" :class="rowCls({ row })" @click="toggle(row.id)">
          <div class="log-head">
            <span class="log-summary">{{ humanize(row) }}</span>
            <el-tag :type="row.level === 'ERROR' ? 'danger' : row.level === 'WARN' ? 'warning' : 'info'" size="small">{{ row.level }}</el-tag>
          </div>
          <div class="log-meta">
            <span :class="row.success ? 'ok' : 'fail'">{{ row.success ? '✓ 成功' : '✗ ' + statusText(row.status_code, row.action) }}</span>
            <span class="dot">·</span>
            <span>{{ row.username || '匿名' }}</span>
            <span class="dot">·</span>
            <span>{{ formatTime(row.created_at) }}</span>
            <span v-if="row.duration_ms != null" class="dot">·</span>
            <span v-if="row.duration_ms != null" :class="{ slow: row.duration_ms > 500 }">{{ row.duration_ms }} ms</span>
          </div>
          <div v-if="row.target" class="log-target">📌 {{ row.target }}</div>
          <div v-if="row.message" class="log-msg">{{ row.message }}</div>
          <div v-if="expandedId === row.id" class="log-detail">
            <div class="detail-line"><span class="k">接口</span><span class="v">{{ row.method }} {{ row.endpoint }}</span></div>
            <div class="detail-line"><span class="k">结果</span><span class="v">{{ row.status_code }} {{ row.success ? '成功' : '失败' }}</span></div>
            <div class="detail-line"><span class="k">耗时</span><span class="v">{{ row.duration_ms != null ? row.duration_ms + ' ms' : '-' }}</span></div>
            <pre v-if="row.error_detail" class="err-detail">{{ row.error_detail }}</pre>
          </div>
        </div>
        <el-empty v-if="!logs.length" description="暂无日志" />
      </div>

      <div v-if="logs.length" class="load-more">
        <el-button v-if="hasMore" size="small" :loading="loadingMore" @click="loadMore">加载更多</el-button>
        <span v-else class="no-more">已加载全部 {{ logs.length }} 条</span>
      </div>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onBeforeUnmount } from 'vue'
import { ElMessage } from 'element-plus'
import { Download, Delete } from '@element-plus/icons-vue'
import api from '@/utils/api'
import type { OperationLog as LogEntry } from '@/types'

const logs = ref<LogEntry[]>([])
const isMobile = ref(false)
const hasMore = ref(false)
const loadingMore = ref(false)
const expandedId = ref<number | null>(null)
function toggle(id: number) { expandedId.value = expandedId.value === id ? null : id }
function syncMobile() { isMobile.value = window.innerWidth < 768 }
const tab = ref<'write' | 'error' | 'all'>('write')
const level = ref('')
const userId = ref('')
const action = ref('')
const keyword = ref('')
const range = ref<any>(null)
const keepDays = ref(90)

const stats = ref({ total: 0, abnormal: 0, failed: 0, active_users: 0 })
const userOptions = ref<{ id: number; name: string }[]>([])
const actionOptions = ref<string[]>([])

async function loadMeta() {
  try {
    const m = await api.get<Record<string, unknown>>('/system/logs/meta')
    userOptions.value = m?.users || []
    actionOptions.value = m?.actions || []
  } catch { /* 元数据失败不阻塞主列表 */ }
}

async function loadStats() {
  try {
    const s = await api.get<Record<string, unknown>>('/system/logs/stats')
    if (s) stats.value = s
  } catch { /* 统计失败不阻塞主列表 */ }
}

function buildParams() {
  const p: any = {}
  // 「关键操作」默认只看写请求，避免 GET 访问日志淹没真正有价值的操作
  if (tab.value === 'write') { p.method = 'POST,PUT,PATCH,DELETE'; if (level.value) p.level = level.value }
  else if (tab.value === 'error') p.level = 'WARN,ERROR'
  else if (level.value) p.level = level.value
  if (userId.value) p.user_id = userId.value
  if (action.value) p.action = action.value
  if (keyword.value) p.keyword = keyword.value
  if (range.value && range.value.length === 2) { p.start = range.value[0]; p.end = range.value[1] }
  return p
}

function formatTime(s: string) {
  if (!s) return '-'
  const d = new Date(s)
  if (Number.isNaN(d.getTime())) return s
  const p = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}:${p(d.getSeconds())}`
}

const METHOD_VERB: Record<string, string> = { GET: '查看', POST: '新增', PUT: '修改', PATCH: '修改', DELETE: '删除' }

const FULL_ACTIONS = new Set(['登录', '登录失败', '登出', '登出失败', '重建索引', '导入', '导出'])

function humanize(row: any) {
  const verb = METHOD_VERB[row.method] || row.method || ''
  const action = row.action || ''
  if (!action) return `${verb} ${row.endpoint || ''}`
  // 「登录失败」「登出」等本身即完整动作，不再叠加「新增/修改/删除」前缀
  if (FULL_ACTIONS.has(action) || action.startsWith('登录') || action.startsWith('登出')) return action
  if (/^\w+(\/\w+)+$/.test(action)) return `${verb} ${action}`
  if (action.startsWith(verb)) return action
  return `${verb}${action}`
}

function statusText(code: number, action?: string) {
  if (!code) return '未知错误'
  // 登录失败返回的 401 是凭据错误，而非会话过期，避免管理员误判
  if (code === 401) return (action || '').includes('登录失败') ? '认证失败' : '未登录/登录失效'
  if (code === 403) return '权限不足'
  if (code === 404) return '资源不存在'
  if (code === 422) return '参数不合法'
  if (code >= 500) return `服务异常 ${code}`
  return `失败 ${code}`
}
const PAGE_SIZE = 50
async function load() {
  try {
    expandedId.value = null
    const params = { ...buildParams(), limit: PAGE_SIZE, offset: 0 }
    const rows = (await api.get<LogEntry[]>('/system/logs', { params })) || []
    logs.value = rows
    hasMore.value = rows.length >= PAGE_SIZE
    loadStats()
    loadMeta()
  } catch (e: any) { ElMessage.error('加载失败：' + (e?.response?.data?.detail || e?.message)) }
}
async function loadMore() {
  if (loadingMore.value || !hasMore.value) return
  loadingMore.value = true
  try {
    const params = { ...buildParams(), limit: PAGE_SIZE, offset: logs.value.length }
    const rows = (await api.get<LogEntry[]>('/system/logs', { params })) || []
    // 追加前按 id 去重，避免期间有新日志写入导致 offset 偏移重复
    const seen = new Set(logs.value.map((r: any) => r.id))
    logs.value.push(...rows.filter((r: any) => !seen.has(r.id)))
    hasMore.value = rows.length >= PAGE_SIZE
  } catch (e: any) { ElMessage.error('加载失败：' + (e?.response?.data?.detail || e?.message)) }
  finally { loadingMore.value = false }
}
async function exportCsv() {
  try {
    const res = await api.get<Blob>('/system/logs/export', { params: buildParams(), responseType: 'blob' })
    const url = window.URL.createObjectURL(new Blob([res]))
    const link = document.createElement('a')
    link.href = url
    link.download = `operation_logs_${new Date().toISOString().slice(0, 10)}.csv`
    link.click()
    window.URL.revokeObjectURL(url)
    ElMessage.success('已导出 CSV')
  } catch (e: any) { ElMessage.error('导出失败：' + (e?.response?.data?.detail || e?.message)) }
}
async function clean() {
  try {
    const r = await api.delete<{ message?: string }>(`/system/logs/clean?days=${keepDays.value}`)
    ElMessage.success(r.message || '已清理')
    load()
  } catch (e: any) { ElMessage.error('清理失败：' + (e?.response?.data?.detail || e?.message)) }
}
function rowCls({ row }: any) {
  return row.level === 'ERROR' ? 'row-error' : row.level === 'WARN' ? 'row-warn' : ''
}
function onScroll() {
  if (!isMobile.value || !hasMore.value || loadingMore.value) return
  const doc = document.documentElement
  if (doc.scrollHeight - doc.scrollTop - doc.clientHeight < 120) loadMore()
}
onMounted(() => {
  syncMobile()
  window.addEventListener('resize', syncMobile)
  window.addEventListener('scroll', onScroll, { passive: true })
  load()
})
onBeforeUnmount(() => {
  window.removeEventListener('resize', syncMobile)
  window.removeEventListener('scroll', onScroll)
})
</script>

<style scoped lang="scss">
.op-log {
  .main-card {
    border-radius: 12px;
    border: 1px solid #f0e4d6;
  }
  .clean-group { display: flex; align-items: center; gap: 6px; }
  .keep-days { width: 100px; }
  .clean-unit { font-size: 12px; color: #a08b76; }
  .filter-mini { width: 110px; }
  .filter-small { width: 150px; }
  .filter-search { width: 200px; }
  .filter-range { width: 240px; }
  .stats-bar {
    display: flex; flex-wrap: wrap; gap: 10px; margin-bottom: 14px;
  }
  .stat-item {
    flex: 1 1 120px; min-width: 110px; padding: 10px 14px; border-radius: 8px;
    background: #faf7f2; border: 1px solid #eee4d8; display: flex; flex-direction: column; gap: 2px;
  }
  .stat-item .num { font-size: 22px; font-weight: 700; color: #2C1810; line-height: 1.2; }
  .stat-item .lbl { font-size: 12px; color: #9a8b7c; }
  .stat-item.warn { background: #fdf6ec; border-color: #f5dab1; }
  .stat-item.warn .num { color: #e6a23c; }
  .stat-item.fail { background: #fef0f0; border-color: #fbc4c4; }
  .stat-item.fail .num { color: #f56c6c; }
  .level-dot {
    display: inline-block; width: 8px; height: 8px; border-radius: 50%;
    margin-right: 6px; vertical-align: middle; background: #c0c4cc;
  }
  .level-dot.warn { background: #e6a23c; }
  .level-dot.error { background: #f56c6c; }
  .level-dot.debug { background: #dcdfe6; }
  .dur { font-size: 11px; color: #b0a89f; }
  .dur.slow { color: #e6a23c; font-weight: 700; }
  .target { color: #5e4b3a; }
  .log-target { margin-top: 6px; font-size: 13px; color: #5e4b3a; }
  .ok { color: #67c23a; }
  .fail { color: #f56c6c; font-weight: 700; }
  .slow { color: #e6a23c; font-weight: 700; }
  .summary { color: #303133; }
  .detail-box { padding: 8px 4px; font-size: 12px; }
  .detail-line { display: flex; gap: 8px; line-height: 1.9; }
  .detail-line .k { color: #909399; min-width: 40px; }
  .detail-line .v { color: #303133; word-break: break-all; }
  .muted { color: #999; }
  .err-detail {
    background: #2c1810; color: #ffd9c0; padding: 10px 12px; border-radius: 6px;
    font-size: 12px; white-space: pre-wrap; word-break: break-all; max-height: 300px; overflow: auto; margin: 0;
  }
  :deep(.row-error) { background: #fef0f0; }
  :deep(.row-warn) { background: #fdf6ec; }
  .load-more { display: flex; justify-content: center; align-items: center; padding: 16px 0 4px; }
  .load-more .el-button { min-width: 140px; }
  .load-more .no-more { font-size: 13px; color: #b0a89f; }
  .log-cards { display: flex; flex-direction: column; gap: 10px; }
  .log-card {
    background: #fff; border: 1px solid #e8e0d8; border-radius: 10px; padding: 12px 14px;
    box-shadow: 0 1px 3px rgba(0,0,0,0.05); cursor: pointer;
  }
  .log-card.row-error { border-left: 4px solid #f56c6c; background: #fef0f0; }
  .log-card.row-warn { border-left: 4px solid #e6a23c; background: #fdf6ec; }
  .log-head { display: flex; align-items: center; justify-content: space-between; gap: 8px; margin-bottom: 8px; }
  .log-summary { font-size: 16px; font-weight: 600; color: #2C1810; word-break: break-all; }
  .log-meta { display: flex; flex-wrap: wrap; align-items: center; gap: 4px; font-size: 13px; color: #8a7563; line-height: 1.6; }
  .log-meta .dot { color: #d4c8bc; }
  .log-msg { margin-top: 8px; font-size: 13px; color: #666; line-height: 1.5; word-break: break-all; }
  .log-detail { margin-top: 10px; padding-top: 8px; border-top: 1px dashed #eadfd4; }
  .log-detail .detail-line { display: flex; gap: 8px; font-size: 12px; line-height: 1.9; color: #606266; }
  .log-detail .detail-line .k { flex-shrink: 0; width: 40px; color: #909399; }
  .log-detail .detail-line .v { flex: 1; word-break: break-all; }
}

@media (max-width: 767px) {
  .op-log {
    :deep(.el-form--inline .el-form-item) { display: block; margin-right: 0; margin-bottom: 8px; }
    :deep(.el-form--inline .el-form-item__label) { display: block; padding: 0 0 4px; }
    :deep(.el-form--inline .el-form-item__content) { display: block; max-width: 100%; }
    :deep(.el-form--inline .el-input), :deep(.el-form--inline .el-select), :deep(.el-form--inline .el-date-editor) { width: 100% !important; }
    :deep(.el-radio-group) { display: flex; }
    :deep(.el-radio-button) { flex: 1; }
    :deep(.el-radio-button__inner) { width: 100%; padding: 8px 6px; }
  }
}
</style>