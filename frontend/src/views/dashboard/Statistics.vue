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

const dailyStats = ref<Array<{ date: string; count: number }>>([])
const syndromeStats = ref<unknown[]>([])
const herbUsage = ref<Array<{ name: string; usage_count: number }>>([])
interface PrescriptionStats { total: number; status_stats: Array<{ status: string; count: number }>; formula_stats: Array<{ name: string; count: number }> }
const prescriptionStats = ref<PrescriptionStats>({ total: 0, status_stats: [], formula_stats: [] })

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
  ])
}

async function loadVisitStats() {
  try {
    const res = await api.get<Record<string, unknown>>('/stats/visits', { params: { days: period.value } })
    dailyStats.value = res.daily_stats || []
    syndromeStats.value = res.syndrome_stats || []
    await nextTick()
    renderVisitChart()
  } catch {}
}

async function loadHerbStats() {
  try {
    const res = await api.get<Record<string, unknown>>('/stats/herbs', { params: { days: period.value } })
    herbUsage.value = res.herb_usage || []
    if (activeTab.value === 'herbs') {
      await nextTick()
      renderHerbChart()
    }
  } catch {}
}

async function loadPrescriptionStats() {
  try {
    const res = await api.get<Record<string, unknown>>('/stats/prescriptions', { params: { days: period.value } })
    prescriptionStats.value = res || {}
    if (activeTab.value === 'prescriptions') {
      await nextTick()
      renderPrescriptionCharts()
    }
  } catch {}
}

function onTabChange(tab: string) {
  nextTick(() => {
    if (tab === 'herbs') renderHerbChart()
    if (tab === 'prescriptions') renderPrescriptionCharts()
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