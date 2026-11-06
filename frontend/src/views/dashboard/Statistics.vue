<template>
  <div class="statistics-page">
    <el-card shadow="hover" class="main-card">
      <template #header>
        <div class="tcm-head">
          <div class="tcm-head__title">
            <span class="tcm-head__icon">📊</span>
            <span class="tcm-head__text">统计报表</span>
            <el-tag size="small" effect="light" round class="tcm-head__count">近 {{ period }} 天</el-tag>
          </div>
          <div class="tcm-head__actions">
            <el-radio-group v-model="period" size="small" @change="loadAll">
              <el-radio-button :value="7">近7天</el-radio-button>
              <el-radio-button :value="30">近30天</el-radio-button>
              <el-radio-button :value="90">近90天</el-radio-button>
            </el-radio-group>
          </div>
        </div>
      </template>

      <el-tabs v-model="activeTab" @tab-change="onTabChange">
        <!-- 就诊统计 -->
        <el-tab-pane label="就诊趋势" name="visits">
          <div ref="visitChartRef" class="chart-lg"></div>
          <div class="tcm-section-title section-gap">
            <span class="tcm-section-title__dot"></span>
            <span>常见证型 TOP10</span>
          </div>
          <el-table :data="syndromeStats" class="tcm-table" size="small" v-if="syndromeStats.length">
            <el-table-column type="index" label="排名" width="60" class-name="tcm-num" />
            <el-table-column prop="name" label="证型" />
            <el-table-column prop="count" label="频次" width="80" class-name="tcm-num" />
          </el-table>
          <el-empty v-else description="暂无数据" :image-size="60" />
        </el-tab-pane>

        <!-- 用药统计 -->
        <el-tab-pane label="用药分析" name="herbs">
          <div ref="herbChartRef" class="chart-lg"></div>
          <div class="tcm-section-title section-gap">
            <span class="tcm-section-title__dot"></span>
            <span>药材使用明细</span>
          </div>
          <el-table :data="herbUsage" class="tcm-table" size="small">
            <el-table-column type="index" label="排名" width="60" class-name="tcm-num" />
            <el-table-column prop="name" label="药味" width="120" />
            <el-table-column prop="usage_count" label="使用次数" width="100" class-name="tcm-num" />
            <el-table-column prop="total_dose" label="总用量(g)" width="100" class-name="tcm-num" />
          </el-table>
        </el-tab-pane>

        <!-- 处方统计 -->
        <el-tab-pane label="处方统计" name="prescriptions">
          <el-row :gutter="20">
            <el-col :xs="24" :span="12">
              <div ref="prescriptionStatusRef" class="chart-md"></div>
            </el-col>
            <el-col :xs="24" :span="12">
              <div ref="formulaChartRef" class="chart-md"></div>
            </el-col>
          </el-row>
          <div class="tcm-section-title section-gap">
            <span class="tcm-section-title__dot"></span>
            <span>统计汇总</span>
          </div>
          <el-descriptions :column="3" border class="stat-desc">
            <el-descriptions-item label="统计周期">近{{ period }}天</el-descriptions-item>
            <el-descriptions-item label="处方总数">{{ prescriptionStats.total || 0 }}</el-descriptions-item>
          </el-descriptions>
        </el-tab-pane>

        <!-- 挂号收费统计 -->
        <el-tab-pane label="挂号收费" name="registration">
          <el-descriptions :column="2" border class="stat-desc">
            <el-descriptions-item label="挂号总数">{{ regStats.total || 0 }} 单</el-descriptions-item>
            <el-descriptions-item label="就诊完成率">{{ regStats.completion_rate || 0 }}%</el-descriptions-item>
            <el-descriptions-item label="净营收">¥{{ (chargeStats.totals?.net_amount || 0).toFixed(2) }}</el-descriptions-item>
            <el-descriptions-item label="待收金额">¥{{ (chargeStats.totals?.pending_amount || 0).toFixed(2) }}</el-descriptions-item>
          </el-descriptions>

          <el-row :gutter="20" class="section-gap">
            <el-col :xs="24" :span="16"><div ref="regTrendRef" class="chart-lg"></div></el-col>
            <el-col :xs="24" :span="8"><div ref="regKindRef" class="chart-lg"></div></el-col>
          </el-row>

          <el-row :gutter="20" class="section-gap">
            <el-col :xs="24" :span="8">
              <div class="tcm-section-title"><span class="tcm-section-title__dot"></span><span>科室分布</span></div>
              <el-table :data="regStats.department_stats || []" size="small" class="tcm-table">
                <el-table-column prop="name" label="科室" />
                <el-table-column prop="count" label="挂号数" width="80" class-name="tcm-num" />
              </el-table>
            </el-col>
            <el-col :xs="24" :span="8">
              <div class="tcm-section-title"><span class="tcm-section-title__dot"></span><span>医师接诊量</span></div>
              <el-table :data="regStats.doctor_stats || []" size="small" class="tcm-table">
                <el-table-column prop="name" label="医师" />
                <el-table-column prop="count" label="挂号数" width="80" class-name="tcm-num" />
              </el-table>
            </el-col>
            <el-col :xs="24" :span="8">
              <div class="tcm-section-title"><span class="tcm-section-title__dot"></span><span>收款方式</span></div>
              <el-table :data="chargeStats.payment_stats || []" size="small" class="tcm-table">
                <el-table-column prop="name" label="方式" />
                <el-table-column label="金额" width="100" class-name="tcm-num">
                  <template #default="{ row }">¥{{ Number(row.amount || 0).toFixed(2) }}</template>
                </el-table-column>
              </el-table>
            </el-col>
          </el-row>
          <div class="tcm-section-title section-gap">
            <span class="tcm-section-title__dot"></span><span>挂号状态</span>
          </div>
          <div class="tag-row">
            <el-tag v-for="st in regStats.status_stats || []" :key="st.name" effect="light" round>
              {{ st.name }} {{ st.count }}
            </el-tag>
            <el-tag effect="light" round>退费率 {{ chargeStats.totals?.refund_rate || 0 }}%</el-tag>
          </div>
        </el-tab-pane>

        <!-- 患者统计 -->
        <el-tab-pane label="患者统计" name="patients">
          <el-descriptions :column="2" border class="stat-desc">
            <el-descriptions-item label="患者总数">{{ patientStats.total_patients || 0 }} 位</el-descriptions-item>
            <el-descriptions-item label="本月新增">{{ patientStats.new_this_month || 0 }} 位</el-descriptions-item>
            <el-descriptions-item label="复诊率">{{ patientStats.returning_rate || 0 }}%</el-descriptions-item>
            <el-descriptions-item label="统计周期">近 {{ period }} 天</el-descriptions-item>
          </el-descriptions>

          <el-row :gutter="20" class="section-gap">
            <el-col :xs="24" :span="12"><div ref="patientTrendRef" class="chart-md"></div></el-col>
            <el-col :xs="24" :span="12"><div ref="patientAgeRef" class="chart-md"></div></el-col>
          </el-row>

          <el-row :gutter="20" class="section-gap">
            <el-col :xs="24" :span="12">
              <div class="tcm-section-title"><span class="tcm-section-title__dot"></span><span>性别分布</span></div>
              <el-table :data="patientStats.gender_stats || []" size="small" class="tcm-table">
                <el-table-column prop="name" label="性别" />
                <el-table-column prop="count" label="人数" width="90" class-name="tcm-num" />
              </el-table>
            </el-col>
            <el-col :xs="24" :span="12">
              <div class="tcm-section-title"><span class="tcm-section-title__dot"></span><span>体质分布</span></div>
              <el-table :data="patientStats.constitution_stats || []" size="small" class="tcm-table">
                <el-table-column prop="name" label="体质" />
                <el-table-column prop="count" label="人数" width="90" class-name="tcm-num" />
              </el-table>
            </el-col>
          </el-row>
        </el-tab-pane>
      </el-tabs>
    </el-card>
  </div>
</template>

<style scoped>
.statistics-page {
  .main-card {
    border-radius: 12px;
    border: 1px solid #f0e4d6;

    :deep(.el-card__header) {
      padding: 0;
      border-bottom: none;
    }
  }

  .chart-lg { height: 350px; }
  .chart-md { height: 300px; }

  .section-gap { margin-top: 18px; }

  :deep(.el-tabs__item) {
    color: #7a6553;
  }
  :deep(.el-tabs__item.is-active) {
    color: var(--tcm-primary);
    font-weight: 600;
  }
  :deep(.el-tabs__active-bar) {
    background-color: var(--tcm-primary);
  }

  :deep(.stat-desc .el-descriptions__label) {
    background: #faf6f1;
    color: #7a6553;
    font-weight: 600;
  }
  :deep(.stat-desc .el-descriptions__content) {
    color: #4a3628;
  }

  .tag-row { display: flex; flex-wrap: wrap; gap: 8px; }
}

@media (max-width: 767px) {
  .statistics-page {
    .chart-lg { height: 240px; }
    .chart-md { height: 220px; }
    .chart-md + * { margin-top: 8px; }
  }
}
</style>

<script setup lang="ts">
import { ref, onMounted, onUnmounted, nextTick } from 'vue'
import api from '@/utils/api'
import { onThemeChange, themeVar } from '@/utils/theme'
import type { ECharts } from 'echarts'

const period = ref(30)
const activeTab = ref('visits')

const visitChartRef = ref<HTMLElement>()
const herbChartRef = ref<HTMLElement>()
const prescriptionStatusRef = ref<HTMLElement>()
const formulaChartRef = ref<HTMLElement>()
const regTrendRef = ref<HTMLElement>()
const regKindRef = ref<HTMLElement>()
const patientTrendRef = ref<HTMLElement>()
const patientAgeRef = ref<HTMLElement>()

const dailyStats = ref<Array<{ date: string; count: number }>>([])
const syndromeStats = ref<unknown[]>([])
const herbUsage = ref<Array<{ name: string; usage_count: number }>>([])
interface PrescriptionStats { total: number; status_stats: Array<{ status: string; count: number }>; formula_stats: Array<{ name: string; count: number }> }
const prescriptionStats = ref<PrescriptionStats>({ total: 0, status_stats: [], formula_stats: [] })
const regStats = ref<Record<string, any>>({})
const chargeStats = ref<Record<string, any>>({})
const patientStats = ref<Record<string, any>>({})

const chartInstances: unknown[] = []

// 按容器复用图表实例：主题切换时只需 setOption 重绘，避免重复 init 与 resize 监听累积
const chartMap = new Map<HTMLElement, ECharts>()
let resizeBound = false

function getOrInitChart(echarts: typeof import('echarts'), el: HTMLElement): ECharts {
  const existing = chartMap.get(el)
  if (existing) return existing
  const chart = echarts.init(el)
  chartMap.set(el, chart)
  chartInstances.push(chart)
  return chart
}

// #RRGGBB → rgba()，用于面积渐变透明度
function hexToRgba(hex: string, alpha: number): string {
  const m = hex.replace('#', '')
  if (m.length !== 6) return `rgba(139,69,19,${alpha})`
  const r = parseInt(m.slice(0, 2), 16)
  const g = parseInt(m.slice(2, 4), 16)
  const b = parseInt(m.slice(4, 6), 16)
  return `rgba(${r},${g},${b},${alpha})`
}

function resizeAllCharts() {
  chartMap.forEach((c) => c?.resize())
}

async function loadAll() {
  await Promise.all([
    loadVisitStats(),
    loadHerbStats(),
    loadPrescriptionStats(),
    loadRegistrationStats(),
    loadChargeStats(),
    loadPatientStats(),
  ])
}

async function loadVisitStats() {
  try {
    const res = await api.get<Record<string, any>>('/stats/visits', { params: { days: period.value } })
    dailyStats.value = res.daily_stats || []
    syndromeStats.value = res.syndrome_stats || []
    await nextTick()
    renderVisitChart()
  } catch {}
}

async function loadHerbStats() {
  try {
    const res = await api.get<Record<string, any>>('/stats/herbs', { params: { days: period.value } })
    herbUsage.value = res.herb_usage || []
    if (activeTab.value === 'herbs') {
      await nextTick()
      renderHerbChart()
    }
  } catch {}
}

async function loadPrescriptionStats() {
  try {
    const res = await api.get<Record<string, any>>('/stats/prescriptions', { params: { days: period.value } })
    prescriptionStats.value = (res || {}) as PrescriptionStats
    if (activeTab.value === 'prescriptions') {
      await nextTick()
      renderPrescriptionCharts()
    }
  } catch {}
}

async function loadRegistrationStats() {
  try {
    regStats.value = await api.get<Record<string, any>>('/stats/registration', { params: { days: period.value } })
    if (activeTab.value === 'registration') { await nextTick(); renderRegistrationCharts() }
  } catch {}
}

async function loadChargeStats() {
  try {
    chargeStats.value = await api.get<Record<string, any>>('/stats/charges', { params: { days: period.value } })
    if (activeTab.value === 'registration') { await nextTick(); renderRegistrationCharts() }
  } catch {}
}

async function loadPatientStats() {
  try {
    patientStats.value = await api.get<Record<string, any>>('/stats/patients', { params: { days: period.value } })
    if (activeTab.value === 'patients') { await nextTick(); renderPatientCharts() }
  } catch {}
}

function renderRegistrationCharts() {
  import('echarts').then((echarts) => {
    const primary = themeVar('--tcm-primary') || '#8B4513'
    const accent = themeVar('--tcm-accent') || '#D4A574'
    const regRows: any[] = regStats.value.daily_stats || []
    const chargeRows: any[] = chargeStats.value.daily_stats || []
    const dates = (regRows.length ? regRows : chargeRows).map((d) => String(d.date).slice(5))
    if (regTrendRef.value && dates.length) {
      const regMap = new Map(regRows.map((d) => [d.date, Number(d.count || 0)]))
      const netMap = new Map(chargeRows.map((d) => [d.date, Number(d.net || 0)]))
      const axisDates = (regRows.length ? regRows : chargeRows).map((d) => d.date)
      const chart = getOrInitChart(echarts, regTrendRef.value!)
      chart.setOption({
        tooltip: { trigger: 'axis' },
        legend: { data: ['挂号数', '净营收'], top: 0 },
        grid: { left: 45, right: 60, top: 30, bottom: 45 },
        xAxis: { type: 'category', data: dates, axisLabel: { rotate: 45, color: '#666', fontSize: 10 } },
        yAxis: [
          { type: 'value', name: '单', minInterval: 1 },
          { type: 'value', name: '¥' },
        ],
        series: [
          { name: '挂号数', type: 'bar', data: axisDates.map((d) => regMap.get(d) || 0),
            itemStyle: { color: primary, borderRadius: [3, 3, 0, 0] } },
          { name: '净营收', type: 'line', yAxisIndex: 1, smooth: true,
            data: axisDates.map((d) => netMap.get(d) || 0),
            lineStyle: { color: accent, width: 2 }, itemStyle: { color: accent } },
        ],
      })
      chart.resize()
    }
    const kinds: any[] = chargeStats.value.kind_stats || []
    if (regKindRef.value && kinds.length) {
      const chart = getOrInitChart(echarts, regKindRef.value!)
      chart.setOption({
        tooltip: { trigger: 'item' },
        legend: { bottom: 0 },
        series: [{
          type: 'pie', radius: ['40%', '65%'],
          data: kinds.map((k, i) => ({
            name: k.name, value: Number(k.net_amount || 0),
            itemStyle: { color: ['#8B4513', '#D4A574', '#A9B98A'][i % 3] },
          })),
          label: { formatter: '{b}\n¥{c}' },
        }],
      })
      chart.resize()
    }
  })
}

function renderPatientCharts() {
  import('echarts').then((echarts) => {
    const primary = themeVar('--tcm-primary') || '#8B4513'
    // 按年龄段名称固定配色：后端只返回非零桶，按名称取色才不会因某个桶缺失而整体串色
    const ageColors: Record<string, string> = {
      '0-18岁': '#A9C7A0', '19-35岁': '#7FAE77', '36-50岁': '#D4A574',
      '51-65岁': '#C07A46', '66岁以上': '#8B4513', '未填写': '#C9C2B6',
    }
    const ageFallback = ['#A9C7A0', '#7FAE77', '#D4A574', '#C07A46', '#8B4513', '#C9C2B6']
    const newRows: any[] = patientStats.value.daily_new || []
    if (patientTrendRef.value && newRows.length) {
      const chart = getOrInitChart(echarts, patientTrendRef.value!)
      chart.setOption({
        tooltip: { trigger: 'axis' },
        grid: { left: 45, right: 20, top: 25, bottom: 45 },
        xAxis: { type: 'category', data: newRows.map((d) => String(d.date).slice(5)),
          axisLabel: { rotate: 45, color: '#666', fontSize: 10 } },
        yAxis: { type: 'value', minInterval: 1 },
        series: [{
          name: '新增患者', type: 'line', smooth: true,
          data: newRows.map((d) => Number(d.count || 0)),
          lineStyle: { color: primary, width: 2 }, itemStyle: { color: primary },
          areaStyle: { color: hexToRgba(primary, 0.15) },
        }],
      })
      chart.resize()
    }
    const ages: any[] = patientStats.value.age_stats || []
    if (patientAgeRef.value && ages.length) {
      const chart = getOrInitChart(echarts, patientAgeRef.value!)
      chart.setOption({
        tooltip: { trigger: 'item' },
        legend: { bottom: 0 },
        series: [{
          type: 'pie', radius: ['38%', '62%'],
          data: ages.map((a: any, i: number) => ({
            name: a.name,
            value: Number(a.count || 0),
            itemStyle: { color: ageColors[a.name] || ageFallback[i % ageFallback.length] },
          })),
          label: { formatter: '{b}: {c}' },
        }],
      })
      chart.resize()
    }
  })
}

function onTabChange(tab: string) {
  nextTick(() => {
    if (tab === 'herbs') renderHerbChart()
    if (tab === 'prescriptions') renderPrescriptionCharts()
    if (tab === 'registration') renderRegistrationCharts()
    if (tab === 'patients') renderPatientCharts()
  })
}

function renderVisitChart() {
  if (!visitChartRef.value || dailyStats.value.length === 0) return
  import('echarts').then((echarts) => {
    const chart = getOrInitChart(echarts, visitChartRef.value!)
    const primary = themeVar('--tcm-primary') || '#8B4513'
    chart.setOption({
      tooltip: { trigger: 'axis' },
      grid: { left: 50, right: 20, top: 20, bottom: 40 },
      xAxis: {
        type: 'category',
        data: dailyStats.value.map((d) => d.date.slice(5)),
        axisLabel: { rotate: 45, color: '#666', fontSize: 11 },
      },
      yAxis: { type: 'value', minInterval: 1 },
      series: [{
        type: 'line',
        data: dailyStats.value.map((d) => d.count),
        smooth: true,
        areaStyle: {
          color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: hexToRgba(primary, 0.3) },
            { offset: 1, color: hexToRgba(primary, 0.05) },
          ]),
        },
        lineStyle: { color: primary, width: 2 },
        itemStyle: { color: primary },
      }],
    })
  })
}

function renderHerbChart() {
  if (!herbChartRef.value || herbUsage.value.length === 0) return
  import('echarts').then((echarts) => {
    const chart = getOrInitChart(echarts, herbChartRef.value!)
    const primary = themeVar('--tcm-primary') || '#8B4513'
    const accent = themeVar('--tcm-accent') || '#D4A574'
    const top15 = herbUsage.value.slice(0, 15)
    chart.setOption({
      tooltip: { trigger: 'axis' },
      grid: { left: 100, right: 20, top: 10, bottom: 20 },
      xAxis: { type: 'value' },
      yAxis: {
        type: 'category',
        data: top15.map((h) => h.name).reverse(),
        axisLabel: { color: '#333' },
      },
      series: [{
        type: 'bar',
        data: top15.map((h) => h.usage_count).reverse(),
        itemStyle: {
          color: new echarts.graphic.LinearGradient(0, 0, 1, 0, [
            { offset: 0, color: accent },
            { offset: 1, color: primary },
          ]),
          borderRadius: [0, 4, 4, 0],
        },
      }],
    })
  })
}

function renderPrescriptionCharts() {
  import('echarts').then((echarts) => {
    // 状态饼图（语义色：已开/已审核/已发药/已取消，不随主题变化）
    if (prescriptionStatusRef.value && prescriptionStats.value.status_stats?.length) {
      const chart1 = getOrInitChart(echarts, prescriptionStatusRef.value!)
      const colorMap: Record<string, string> = { '已开': '#FAAD14', '已审核': '#1890FF', '已发药': '#52C41A', '已取消': '#F5222D' }
      chart1.setOption({
        tooltip: { trigger: 'item' },
        legend: { bottom: 0 },
        series: [{
          type: 'pie',
          radius: ['40%', '65%'],
          data: prescriptionStats.value.status_stats.map((s) => ({
            name: s.status,
            value: s.count,
            itemStyle: { color: colorMap[s.status] || '#999' },
          })),
          label: { formatter: '{b}: {c}' },
        }],
      })
    }

    // 方剂柱图
    if (formulaChartRef.value && prescriptionStats.value.formula_stats?.length) {
      const chart2 = getOrInitChart(echarts, formulaChartRef.value!)
      chart2.setOption({
        tooltip: { trigger: 'axis' },
        grid: { left: 80, right: 20, top: 10, bottom: 20 },
        xAxis: { type: 'value' },
        yAxis: {
          type: 'category',
          data: prescriptionStats.value.formula_stats.map((f) => f.name).reverse(),
        },
        series: [{
          type: 'bar',
          data: prescriptionStats.value.formula_stats.map((f) => f.count).reverse(),
          itemStyle: {
            color: themeVar('--tcm-primary') || '#8B4513',
            borderRadius: [0, 4, 4, 0],
          },
        }],
      })
    }
  })
}

onMounted(() => {
  if (!resizeBound) {
    window.addEventListener('resize', resizeAllCharts)
    resizeBound = true
  }
  loadAll()
})

// 主题切换后重绘全部图表
const offThemeChange = onThemeChange(() => {
  renderVisitChart()
  renderHerbChart()
  if (activeTab.value === 'prescriptions') renderPrescriptionCharts()
  if (activeTab.value === 'registration') renderRegistrationCharts()
  if (activeTab.value === 'patients') renderPatientCharts()
})

onUnmounted(() => {
  offThemeChange()
  if (resizeBound) {
    window.removeEventListener('resize', resizeAllCharts)
    resizeBound = false
  }
  chartMap.forEach((c) => c?.dispose())
  chartMap.clear()
})
</script>