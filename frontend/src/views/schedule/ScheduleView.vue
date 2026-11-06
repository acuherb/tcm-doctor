<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import api, { errMsg } from '@/utils/api'
import { useAuthStore } from '@/store/auth'

const auth = useAuthStore()
const canEdit = computed(() => auth.can('schedule:write'))

interface Doctor { id: number; name: string; department: string }
const doctors = ref<Doctor[]>([])
const weekStart = ref<string>(mondayOf(new Date()))
const grid = ref<Record<number, Record<string, string>>>({})
const loading = ref(false)
const saving = ref(false)

const WEEK_LABELS = ['周一', '周二', '周三', '周四', '周五', '周六', '周日']
const periodOptions = [
  { value: 'off', label: '休诊' },
  { value: 'morning', label: '上午' },
  { value: 'afternoon', label: '下午' },
  { value: 'full', label: '全天' },
]

const weekDates = computed<string[]>(() => {
  const arr: string[] = []
  for (let i = 0; i < 7; i++) arr.push(addDays(weekStart.value, i))
  return arr
})

const weekRangeText = computed(() =>
  `${weekStart.value} ~ ${addDays(weekStart.value, 6)}`
)

function toISO(d: Date): string {
  const y = d.getFullYear()
  const m = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  return `${y}-${m}-${day}`
}
function mondayOf(d: Date): string {
  const x = new Date(d)
  const wd = x.getDay() // 0=周日
  x.setDate(x.getDate() + (wd === 0 ? -6 : 1 - wd))
  return toISO(x)
}
function addDays(iso: string, n: number): string {
  const [y, m, d] = iso.split('-').map(Number)
  const dt = new Date(y, m - 1, d)
  dt.setDate(dt.getDate() + n)
  return toISO(dt)
}

async function loadDoctors() {
  const r = await api.get<Doctor[]>('/schedule/doctors')
  doctors.value = r || []
  // 预置 grid，避免医师行渲染时 grid[row.id] 尚未初始化导致访问 undefined
  const g: Record<number, Record<string, string>> = {}
  for (const doc of doctors.value) {
    g[doc.id] = {}
    for (const dt of weekDates.value) g[doc.id][dt] = 'off'
  }
  grid.value = g
}
async function loadWeek() {
  loading.value = true
  try {
    const r = await api.get<{ items: Array<{ doctor_id: number; schedule_date: string; period: string }> }>(
      '/schedule/week', { params: { start: weekStart.value } },
    )
    const g: Record<number, Record<string, string>> = {}
    for (const doc of doctors.value) {
      g[doc.id] = {}
      for (const dt of weekDates.value) g[doc.id][dt] = 'off'
    }
    for (const it of (r?.items || [])) {
      if (!g[it.doctor_id]) g[it.doctor_id] = {}
      g[it.doctor_id][it.schedule_date] = it.period
    }
    grid.value = g
  } finally {
    loading.value = false
  }
}

function prevWeek() { weekStart.value = addDays(weekStart.value, -7); loadWeek() }
function nextWeek() { weekStart.value = addDays(weekStart.value, 7); loadWeek() }

async function saveWeek() {
  if (!canEdit.value) return
  const items: Array<{ doctor_id: number; date: string; period: string }> = []
  for (const doc of doctors.value) {
    const row = grid.value[doc.id] || {}
    for (const dt of weekDates.value) {
      const p = row[dt]
      if (p && p !== 'off') items.push({ doctor_id: doc.id, date: dt, period: p })
    }
  }
  saving.value = true
  try {
    await api.post('/schedule/week', { start: weekStart.value, items })
    ElMessage.success('本周排班已保存')
  } catch (e) {
    ElMessage.error(errMsg(e) || '保存失败')
  } finally {
    saving.value = false
  }
}

async function copyLastWeek() {
  if (!canEdit.value) return
  saving.value = true
  try {
    await api.post('/schedule/copy-week', {
      source_start: addDays(weekStart.value, -7),
      target_start: weekStart.value,
    })
    ElMessage.success('已复制上周排班到本周')
    await loadWeek()
  } catch (e) {
    ElMessage.error(errMsg(e) || '复制失败')
  } finally {
    saving.value = false
  }
}

onMounted(async () => {
  await loadDoctors()
  await loadWeek()
})
</script>

<template>
  <div class="schedule-page">
    <div class="page-head">
      <div>
        <h2 class="page-title">排班管理</h2>
        <p class="page-sub">
          按周为每位医师设定每日出诊时段；保存后<strong>挂号台仅显示当日出诊医师</strong>。
        </p>
      </div>
      <div class="head-actions">
        <el-button-group>
          <el-button @click="prevWeek">上一周</el-button>
          <el-button @click="nextWeek">下一周</el-button>
        </el-button-group>
        <el-button v-if="canEdit" :loading="saving" @click="copyLastWeek">复制上周</el-button>
        <el-button v-if="canEdit" type="primary" :loading="saving" @click="saveWeek">保存本周</el-button>
        <el-tag v-else type="info" effect="plain">只读（无排班维护权限）</el-tag>
      </div>
    </div>

    <el-alert
      :title="`当前周：${weekRangeText}`"
      type="info" :closable="false" show-icon class="week-alert"
    />

    <el-table :data="doctors" v-loading="loading" border stripe class="sched-table" empty-text="暂无可排班医师（请在账号管理启用医生/管理员账号）">
      <el-table-column label="医师 / 科室" min-width="150" fixed>
        <template #default="{ row }">
          <div class="doc-name">{{ row.name }}</div>
          <div class="doc-dept">{{ row.department || '—' }}</div>
        </template>
      </el-table-column>
      <el-table-column
        v-for="(dt, i) in weekDates" :key="dt"
        :label="`${WEEK_LABELS[i]} ${dt.slice(5)}`"
        align="center" min-width="104"
      >
        <template #default="{ row }">
          <el-select
            v-model="grid[row.id][dt]"
            :disabled="!canEdit"
            size="small"
            style="width: 88px"
          >
            <el-option v-for="o in periodOptions" :key="o.value" :label="o.label" :value="o.value" />
          </el-select>
        </template>
      </el-table-column>
    </el-table>
  </div>
</template>

<style scoped>
.schedule-page { padding: 4px 2px; }
.page-head {
  display: flex; justify-content: space-between; align-items: flex-start;
  flex-wrap: wrap; gap: 12px; margin-bottom: 12px;
}
.page-title { margin: 0 0 4px; font-size: 18px; }
.page-sub { margin: 0; color: var(--el-text-color-secondary); font-size: 13px; }
.head-actions { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.week-alert { margin-bottom: 12px; }
.sched-table { margin-top: 4px; }
.doc-name { font-weight: 600; }
.doc-dept { font-size: 12px; color: var(--el-text-color-secondary); }
</style>
