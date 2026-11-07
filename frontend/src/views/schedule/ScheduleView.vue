<script setup lang="ts">
import { ref, computed, onMounted, onBeforeUnmount } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import api, { errMsg } from '@/utils/api'
import { useAuthStore } from '@/store/auth'

const auth = useAuthStore()
const canEdit = computed(() => auth.can('schedule:write'))

// 窄屏改用「选一天 → 逐位医师设时段」的卡片视图，避免 8 列周网格横向溢出
const isMobile = ref(false)
function syncMobile() { isMobile.value = window.innerWidth < 768 }

interface Doctor { id: number; name: string; department: string }
const doctors = ref<Doctor[]>([])
const weekStart = ref<string>(mondayOf(new Date()))
const grid = ref<Record<number, Record<string, string>>>({})
const activeDate = ref('')   // 手机端当前编辑的日期
const dirty = ref(false)     // 有未保存修改
const loading = ref(false)
const saving = ref(false)

const WEEK_LABELS = ['周一', '周二', '周三', '周四', '周五', '周六', '周日']
const periodOptions = [
  { value: 'off', label: '休诊' },
  { value: 'morning', label: '上午' },
  { value: 'afternoon', label: '下午' },
  { value: 'full', label: '全天' },
]
function periodLabel(p: string | undefined): string {
  return periodOptions.find(o => o.value === p)?.label || '休诊'
}

const weekDates = computed<string[]>(() => {
  const arr: string[] = []
  for (let i = 0; i < 7; i++) arr.push(addDays(weekStart.value, i))
  return arr
})
const weekRangeText = computed(() => `${weekStart.value} ~ ${addDays(weekStart.value, 6)}`)

// 手机端日期条：顺带显示当日出诊人数，一眼看出哪天还没排
const dayChips = computed(() => weekDates.value.map((date, i) => ({
  date,
  label: WEEK_LABELS[i],
  isToday: date === toISO(new Date()),
  onDuty: doctors.value.filter(d => {
    const p = grid.value[d.id]?.[date]
    return !!p && p !== 'off'
  }).length,
})))

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

// 按当前周预置整张网格，保证 v-model 绑定 grid[doc.id][date] 永远有值（含切周瞬间）
function resetGrid() {
  const g: Record<number, Record<string, string>> = {}
  for (const doc of doctors.value) {
    g[doc.id] = {}
    for (const dt of weekDates.value) g[doc.id][dt] = 'off'
  }
  grid.value = g
}

async function loadDoctors() {
  const r = await api.get<Doctor[]>('/schedule/doctors')
  doctors.value = r || []
  resetGrid()
}
async function loadWeek() {
  loading.value = true
  resetGrid()   // 先建好本周空网格，避免切周时读到旧周的日期键
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
    dirty.value = false
  } finally {
    loading.value = false
  }
}

async function changeWeek(delta: number) {
  if (dirty.value) {
    try {
      await ElMessageBox.confirm(
        '本周有未保存的修改，切换周次会丢弃这些修改。是否继续？',
        '未保存的修改', { type: 'warning', confirmButtonText: '继续切换', cancelButtonText: '留在本周' },
      )
    } catch { return }
  }
  const idx = Math.max(0, weekDates.value.indexOf(activeDate.value))
  weekStart.value = addDays(weekStart.value, delta)
  activeDate.value = weekDates.value[idx] || weekStart.value
  await loadWeek()
}
function prevWeek() { changeWeek(-7) }
function nextWeek() { changeWeek(7) }

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
    dirty.value = false
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
  syncMobile()
  window.addEventListener('resize', syncMobile)
  const today = toISO(new Date())
  activeDate.value = weekDates.value.includes(today) ? today : weekStart.value
  await loadDoctors()
  await loadWeek()
})
onBeforeUnmount(() => window.removeEventListener('resize', syncMobile))
</script>

<template>
  <div class="schedule-page">
    <div class="page-head">
      <div class="head-title">
        <h2 class="page-title">排班管理</h2>
        <p class="page-sub">
          按周为每位医师设定每日出诊时段；保存后<strong>挂号台仅显示当日出诊医师</strong>。
        </p>
      </div>
      <div class="head-actions">
        <div class="week-nav">
          <el-button @click="prevWeek">上一周</el-button>
          <el-button @click="nextWeek">下一周</el-button>
        </div>
        <div v-show="!isMobile" class="week-save">
          <el-button v-if="canEdit" :loading="saving" @click="copyLastWeek">复制上周</el-button>
          <el-button v-if="canEdit" type="primary" :loading="saving" @click="saveWeek">
            保存本周<span v-if="dirty" class="dirty-dot"></span>
          </el-button>
          <el-tag v-else type="info" effect="plain">只读（无排班维护权限）</el-tag>
        </div>
      </div>
    </div>

    <el-alert :title="`当前周：${weekRangeText}`" type="info" :closable="false" show-icon class="week-alert" />
    <el-alert v-if="dirty" title="有未保存的修改，请点「保存本周」生效" type="warning" :closable="false" show-icon class="dirty-alert" />

    <!-- 桌面端：整周网格 -->
    <el-table v-if="!isMobile" :data="doctors" v-loading="loading" border stripe class="sched-table"
              empty-text="暂无可排班医师（请在账号管理启用医生/管理员账号）">
      <el-table-column label="医师 / 科室" min-width="150" fixed>
        <template #default="{ row }">
          <div class="doc-name">{{ row.name }}</div>
          <div class="doc-dept">{{ row.department || '—' }}</div>
        </template>
      </el-table-column>
      <el-table-column v-for="(dt, i) in weekDates" :key="dt"
                       :label="`${WEEK_LABELS[i]} ${dt.slice(5)}`" align="center" min-width="104">
        <template #default="{ row }">
          <el-select v-model="grid[row.id][dt]" :disabled="!canEdit" size="small" style="width: 88px"
                     @change="dirty = true">
            <el-option v-for="o in periodOptions" :key="o.value" :label="o.label" :value="o.value" />
          </el-select>
        </template>
      </el-table-column>
    </el-table>

    <!-- 手机端：先选日期，再逐位医师点时段 -->
    <div v-else class="mobile-view" v-loading="loading">
      <div class="day-strip">
        <button v-for="d in dayChips" :key="d.date" type="button" class="day-chip"
                :class="{ 'is-active': activeDate === d.date, 'is-today': d.isToday }"
                @click="activeDate = d.date">
          <span class="dc-week">{{ d.label }}</span>
          <span class="dc-date">{{ d.date.slice(5) }}</span>
          <span class="dc-count" :class="{ 'is-zero': d.onDuty === 0 }">{{ d.onDuty }} 人</span>
        </button>
      </div>

      <div class="m-date-head">
        <span class="m-date-title">{{ activeDate }} {{ dayChips.find(d => d.date === activeDate)?.label || '' }}</span>
        <el-tag v-if="!canEdit" type="info" effect="plain" size="small">只读</el-tag>
      </div>

      <div class="m-doc-cards">
        <div v-for="doc in doctors" :key="doc.id" class="m-doc-card">
          <div class="m-doc-head">
            <span class="m-doc-name">{{ doc.name }}</span>
            <span class="m-doc-dept">{{ doc.department || '—' }}</span>
          </div>
          <el-radio-group v-model="grid[doc.id][activeDate]" :disabled="!canEdit" size="small"
                          class="period-group" @change="dirty = true">
            <el-radio-button v-for="o in periodOptions" :key="o.value" :value="o.value">{{ o.label }}</el-radio-button>
          </el-radio-group>
        </div>
        <el-empty v-if="!doctors.length" description="暂无可排班医师" :image-size="60" />
      </div>

      <div v-if="canEdit" class="mobile-save-bar">
        <el-button :loading="saving" @click="copyLastWeek">复制上周</el-button>
        <el-button type="primary" :loading="saving" @click="saveWeek">
          保存本周<span v-if="dirty" class="dirty-dot"></span>
        </el-button>
      </div>
    </div>
  </div>
</template>

<style lang="scss" scoped>
.schedule-page { padding: 4px 2px; }
.page-head {
  display: flex; justify-content: space-between; align-items: flex-start;
  flex-wrap: wrap; gap: 12px; margin-bottom: 12px;
}
.page-title { margin: 0 0 4px; font-size: 18px; }
.page-sub { margin: 0; color: var(--el-text-color-secondary); font-size: 13px; }
.head-actions { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.week-nav, .week-save { display: flex; gap: 8px; }
.week-alert { margin-bottom: 12px; }
.dirty-alert { margin-bottom: 12px; }
.dirty-dot {
  display: inline-block; width: 6px; height: 6px; margin-left: 6px;
  border-radius: 50%; background: var(--el-color-warning); vertical-align: middle;
}
.sched-table { margin-top: 4px; }
.doc-name { font-weight: 600; }
.doc-dept { font-size: 12px; color: var(--el-text-color-secondary); }

/* ---------- 手机端 ---------- */
@media (max-width: 767px) {
  .page-head { flex-direction: column; gap: 10px; }
  .head-title { width: 100%; }
  .page-title { font-size: 16px; }
  .page-sub { font-size: 12px; line-height: 1.5; }
  .head-actions { width: 100%; flex-direction: column; gap: 8px; }
  .week-nav { width: 100%;
    :deep(.el-button) { flex: 1; margin-left: 0; }
  }
  .week-alert, .dirty-alert { margin-bottom: 10px; font-size: 12px; }

  .mobile-view { padding-bottom: 4px; }
  .day-strip {
    display: flex; gap: 6px; overflow-x: auto; padding: 2px 0 8px;
    scrollbar-width: none;
    &::-webkit-scrollbar { display: none; }
  }
  .day-chip {
    flex: 1 1 0; min-width: 44px; display: flex; flex-direction: column;
    align-items: center; gap: 2px; padding: 8px 2px; cursor: pointer;
    border: 1px solid var(--el-border-color-lighter); border-radius: 8px;
    background: var(--el-bg-color); color: var(--el-text-color-regular);
    font-size: 12px; line-height: 1.3;
    .dc-week { font-weight: 600; }
    .dc-date { color: var(--el-text-color-secondary); font-size: 11px; }
    .dc-count { font-size: 10px; color: var(--el-color-success); white-space: nowrap; }
    .dc-count.is-zero { color: var(--el-text-color-placeholder); }
  }
  .day-chip.is-today { border-color: var(--el-color-primary); }
  .day-chip.is-active {
    background: var(--el-color-primary); border-color: var(--el-color-primary); color: #fff;
    .dc-date, .dc-count, .dc-count.is-zero { color: rgba(255, 255, 255, .85); }
  }

  .m-date-head {
    display: flex; align-items: center; gap: 8px; margin: 4px 0 10px;
    .m-date-title { font-size: 14px; font-weight: 600; }
  }
  .m-doc-cards { display: flex; flex-direction: column; gap: 8px; }
  .m-doc-card {
    border: 1px solid var(--el-border-color-lighter); border-radius: 8px;
    padding: 10px 12px; background: var(--el-bg-color);
  }
  .m-doc-head { display: flex; align-items: baseline; gap: 8px; margin-bottom: 8px; }
  .m-doc-name { font-size: 14px; font-weight: 600; }
  .m-doc-dept { font-size: 12px; color: var(--el-text-color-secondary); }
  .period-group { display: flex; width: 100%;
    :deep(.el-radio-button) { flex: 1; }
    :deep(.el-radio-button__inner) { width: 100%; padding: 8px 2px; font-size: 12px; }
  }

  .mobile-save-bar {
    position: sticky; bottom: 0; z-index: 5; display: flex; gap: 8px;
    margin-top: 12px; padding: 10px 0 4px;
    background: var(--el-bg-color); border-top: 1px solid var(--el-border-color-lighter);
    :deep(.el-button) { flex: 1; margin-left: 0; }
  }
}
</style>
