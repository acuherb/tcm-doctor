<template>
  <div class="op-log">
    <el-card shadow="hover">
      <template #header>
        <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:8px;">
          <span>📋 操作日志</span>
          <div style="display:flex;gap:8px;align-items:center;">
            <span style="font-size:12px;color:#999;">清理保留(天)</span>
            <el-input-number v-model="keepDays" :min="0" :max="3650" controls-position="right" size="small" style="width:120px" />
            <el-button size="small" type="primary" @click="exportCsv"><el-icon><Download /></el-icon> 导出CSV</el-button>
            <el-popconfirm title="确认清理旧日志？" @confirm="clean">
              <template #reference>
                <el-button size="small" type="danger"><el-icon><Delete /></el-icon> 清理</el-button>
              </template>
            </el-popconfirm>
          </div>
        </div>
      </template>

      <el-form :inline="true" @submit.prevent="load">
        <el-form-item>
          <el-radio-group v-model="tab" @change="load">
            <el-radio-button label="全部" value="all" />
            <el-radio-button label="仅异常" value="error" />
          </el-radio-group>
        </el-form-item>
        <el-form-item>
          <el-select v-model="level" placeholder="级别" clearable style="width:110px" @change="load">
            <el-option label="INFO" value="INFO" />
            <el-option label="WARN" value="WARN" />
            <el-option label="ERROR" value="ERROR" />
          </el-select>
        </el-form-item>
        <el-form-item label="用户ID">
          <el-input v-model="userId" placeholder="按用户查" clearable style="width:110px" @clear="load" />
        </el-form-item>
        <el-form-item label="动作">
          <el-input v-model="action" placeholder="如 入库/登录" clearable style="width:140px" @clear="load" />
        </el-form-item>
        <el-form-item>
          <el-input v-model="keyword" placeholder="用户名/接口/消息" clearable @clear="load" style="width:200px" />
        </el-form-item>
        <el-form-item>
          <el-date-picker v-model="range" type="daterange" value-format="YYYY-MM-DD" range-separator="至" start-placeholder="起始" end-placeholder="结束" style="width:240px" />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="load">查询</el-button>
        </el-form-item>
      </el-form>

      <el-table :data="logs" stripe size="small" style="width:100%" empty-text="暂无日志"
                :row-class-name="rowCls" @expand-change="() => {}">
        <el-table-column type="expand">
          <template #default="{ row }">
            <pre v-if="row.error_detail" class="err-detail">{{ row.error_detail }}</pre>
            <span v-else class="muted">无异常明细</span>
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="时间" width="170" />
        <el-table-column label="级别" width="90">
          <template #default="{ row }">
            <el-tag :type="row.level === 'ERROR' ? 'danger' : row.level === 'WARN' ? 'warning' : 'info'" size="small">{{ row.level }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="username" label="用户" width="110" />
        <el-table-column prop="action" label="动作" width="120" />
        <el-table-column prop="endpoint" label="接口" min-width="180" show-overflow-tooltip />
        <el-table-column prop="method" label="方法" width="80" />
        <el-table-column label="状态" width="90">
          <template #default="{ row }">
            <span :class="row.success ? 'ok' : 'fail'">{{ row.status_code }}</span>
          </template>
        </el-table-column>
        <el-table-column label="耗时" width="90">
          <template #default="{ row }">{{ row.duration_ms != null ? row.duration_ms + ' ms' : '-' }}</template>
        </el-table-column>
        <el-table-column prop="message" label="消息" min-width="200" show-overflow-tooltip />
      </el-table>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { Download, Delete } from '@element-plus/icons-vue'
import api from '@/utils/api'

const logs = ref<any[]>([])
const tab = ref<'all' | 'error'>('all')
const level = ref('')
const userId = ref('')
const action = ref('')
const keyword = ref('')
const range = ref<any>(null)
const keepDays = ref(90)

function buildParams() {
  const p: any = {}
  // 「仅异常」tab 改由后端按 WARN/ERROR 过滤，避免前端 limit 截断导致漏数据
  if (tab.value === 'error') p.level = 'WARN,ERROR'
  else if (level.value) p.level = level.value
  if (userId.value) p.user_id = userId.value
  if (action.value) p.action = action.value
  if (keyword.value) p.keyword = keyword.value
  if (range.value && range.value.length === 2) { p.start = range.value[0]; p.end = range.value[1] }
  return p
}
async function load() {
  try {
    const params = buildParams()
    logs.value = (await api.get('/system/logs', { params }) as any) || []
  } catch (e: any) { ElMessage.error('加载失败：' + (e?.response?.data?.detail || e?.message)) }
}
async function exportCsv() {
  try {
    const res = await api.get('/system/logs/export', { params: buildParams(), responseType: 'blob' }) as any
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
    const r = await api.delete(`/system/logs/clean?days=${keepDays.value}`) as any
    ElMessage.success(r.message || '已清理')
    load()
  } catch (e: any) { ElMessage.error('清理失败：' + (e?.response?.data?.detail || e?.message)) }
}
function rowCls({ row }: any) {
  return row.level === 'ERROR' ? 'row-error' : row.level === 'WARN' ? 'row-warn' : ''
}
onMounted(load)
</script>

<style scoped lang="scss">
.op-log {
  .ok { color: #67c23a; }
  .fail { color: #f56c6c; font-weight: 700; }
  .muted { color: #999; }
  .err-detail {
    background: #2c1810; color: #ffd9c0; padding: 10px 12px; border-radius: 6px;
    font-size: 12px; white-space: pre-wrap; word-break: break-all; max-height: 300px; overflow: auto; margin: 0;
  }
  :deep(.row-error) { background: #fef0f0; }
  :deep(.row-warn) { background: #fdf6ec; }
}
</style>
