<template>
  <div class="dashboard">
    <!-- 统计卡片 -->
    <el-row :gutter="20">
      <el-col :xs="12" :span="4" v-for="card in statCards" :key="card.title">
        <el-card shadow="hover" class="stat-card">
          <div class="stat-card-body">
            <div class="stat-icon" :style="{ backgroundColor: card.color + '20', color: card.color }">
              <el-icon :size="28"><component :is="card.icon" /></el-icon>
            </div>
            <div class="stat-info">
              <div class="stat-value">{{ card.value }}</div>
              <div class="stat-title">{{ card.title }}</div>
            </div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 图表区 -->
    <el-row :gutter="20" class="section-row">
      <el-col :xs="24" :span="14">
        <el-card shadow="hover" class="main-card">
          <template #header>
            <div class="tcm-head">
              <div class="tcm-head__title">
                <span class="tcm-head__icon">📈</span>
                <span class="tcm-head__text">近7日就诊趋势</span>
              </div>
            </div>
          </template>
          <div ref="visitChartRef" class="chart-box"></div>
        </el-card>
      </el-col>
      <el-col :xs="24" :span="10">
        <el-card shadow="hover" class="main-card">
          <template #header>
            <div class="tcm-head">
              <div class="tcm-head__title">
                <span class="tcm-head__icon">⚠️</span>
                <span class="tcm-head__text">库存预警</span>
              </div>
              <div class="tcm-head__actions">
                <el-tag :type="alerts.length > 0 ? 'danger' : 'success'" size="small" effect="light" round>
                  {{ alerts.length > 0 ? `${alerts.length} 项预警` : '库存正常' }}
                </el-tag>
              </div>
            </div>
          </template>
          <el-empty v-if="alerts.length === 0" description="暂无预警" :image-size="60" />
          <div v-else class="alert-list">
            <div v-for="alert in alerts" :key="alert.item_id" class="alert-item">
              <el-tag type="danger" size="small">{{ alert.alert_type }}</el-tag>
              <span class="alert-herb">{{ alert.item_name }}</span>
              <span class="alert-qty">{{ alert.current_quantity }}{{ alert.unit }} / 最低{{ alert.min_stock }}{{ alert.unit }}</span>
              <el-button link type="primary" size="small" @click="$router.push('/stock/overview')">处理</el-button>
            </div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 快捷操作 + 待办 -->
    <el-row :gutter="20" class="section-row">
      <el-col :xs="24" :span="14">
        <el-card shadow="hover" class="main-card">
          <template #header>
            <div class="tcm-head">
              <div class="tcm-head__title">
                <span class="tcm-head__icon">🏥</span>
                <span class="tcm-head__text">快捷操作</span>
              </div>
            </div>
          </template>
          <el-row :gutter="16">
            <el-col :xs="12" :span="6" v-for="action in quickActions" :key="action.title">
              <div class="quick-action" @click="$router.push(action.route)">
                <el-icon :size="28" :color="action.color"><component :is="action.icon" /></el-icon>
                <div class="action-title">{{ action.title }}</div>
                <div class="action-desc">{{ action.desc }}</div>
              </div>
            </el-col>
          </el-row>
        </el-card>
      </el-col>
      <el-col :xs="24" :span="10">
        <el-card shadow="hover" class="main-card">
          <template #header>
            <div class="tcm-head">
              <div class="tcm-head__title">
                <span class="tcm-head__icon">📋</span>
                <span class="tcm-head__text">待办事项</span>
              </div>
            </div>
          </template>
          <div class="todo-list">
            <div v-if="pendingCount > 0" class="todo-item">
              <el-tag type="warning" size="small">待审核</el-tag>
              <span>{{ pendingCount }} 张处方待审核</span>
              <el-button link type="primary" size="small" @click="$router.push('/prescriptions')">去处理</el-button>
            </div>
            <div v-if="alerts.length > 0" class="todo-item">
              <el-tag type="danger" size="small">库存预警</el-tag>
              <span>{{ alerts.length }} 种物品库存不足</span>
              <el-button link type="primary" size="small" @click="$router.push('/stock/overview')">去处理</el-button>
            </div>
            <div v-if="pendingFollowups > 0" class="todo-item">
              <el-tag type="primary" size="small">待回访</el-tag>
              <span>{{ pendingFollowups }} 位患者需随访</span>
            </div>
            <div
              v-for="r in followupReminders"
              :key="r.id"
              class="todo-item todo-followup"
              @click="goPatient(r.patient_id)"
            >
              <el-tag :type="r.overdue ? 'danger' : 'primary'" size="small">{{ r.overdue ? '已逾期' : '待回访' }}</el-tag>
              <span class="todo-name">{{ r.patient_name }}</span>
              <span class="todo-date">{{ r.due_date }}</span>
              <span v-if="r.note" class="todo-note">{{ r.note }}</span>
            </div>
            <el-empty v-if="pendingCount === 0 && alerts.length === 0 && pendingFollowups === 0" description="暂无待办事项" :image-size="60" />
          </div>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted, nextTick } from 'vue'
import { useRouter } from 'vue-router'
import api from '@/utils/api'
import { onThemeChange, themeVar } from '@/utils/theme'

const router = useRouter()
function goPatient(id: number) {
  if (id) router.push(`/patients/${id}`)
}

const statCards = ref([
  { title: '今日就诊', value: 0, icon: 'User', color: themeVar('--tcm-primary') || '#8B4513' },
  { title: '患者总数', value: 0, icon: 'User', color: '#52C41A' },
  { title: '今日处方', value: 0, icon: 'Document', color: '#1890FF' },
  { title: '药品总数', value: 0, icon: 'FirstAidKit', color: '#13C2C2' },
  { title: '待审核', value: 0, icon: 'Warning', color: '#FAAD14' },
  { title: '库存预警', value: 0, icon: 'Warning', color: '#F5222D' },
])

const quickActions = ref([
  { title: '新增患者', desc: '录入信息', route: '/patients', icon: 'User', color: themeVar('--tcm-primary') || '#8B4513' },
  { title: '开具处方', desc: '选方/自拟', route: '/prescriptions/new', icon: 'Document', color: '#1890FF' },
  { title: '智能问诊', desc: 'AI辨证', route: '/diagnosis', icon: 'ChatDotRound', color: '#722ED1' },
  { title: '字典管理', desc: '证候脉象词条', route: '/dictionaries', icon: 'Collection', color: '#13C2C2' },
  { title: '药材入库', desc: '入库登记', route: '/stock/transactions', icon: 'Box', color: '#52C41A' },
  { title: '知识检索', desc: '典籍查询', route: '/knowledge', icon: 'Search', color: '#FAAD14' },
  { title: '中药方库', desc: '方剂浏览', route: '/classic-formulas', icon: 'Notebook', color: themeVar('--tcm-primary') || '#8B4513' },
  { title: '系统设置', desc: '配置管理', route: '/settings', icon: 'Setting', color: '#999' },
])

const alerts = ref<Array<Record<string, unknown>>>([])
const pendingCount = ref(0)
const pendingFollowups = ref(0)
const followupReminders = ref<unknown[]>([])
const visitChartRef = ref<HTMLElement>()
const visitTrend = ref<unknown[]>([])

async function loadDashboard() {
  try {
    const [dashData, alertsData] = await Promise.all([
      api.get<Record<string, unknown>>('/stats/dashboard'),
      api.get<Array<Record<string, unknown>>>('/stock/alerts'),
    ])
    statCards.value[0].value = dashData.today_visits || 0
    statCards.value[1].value = dashData.total_patients || 0
    statCards.value[2].value = dashData.today_prescriptions || 0
    statCards.value[3].value = dashData.total_herbs || 0
    statCards.value[4].value = dashData.pending_prescriptions || 0
    statCards.value[5].value = dashData.low_stock_count || 0

    pendingCount.value = dashData.pending_prescriptions || 0
    alerts.value = alertsData || []
    pendingFollowups.value = dashData.pending_followups || 0
    followupReminders.value = dashData.followup_reminders || []
    visitTrend.value = dashData.visit_trend || []

    // 绘制图表
    await nextTick()
    renderVisitChart()
  } catch {
    // 后端未启动
  }
}

let visitChart: any = null
let echartsLib: any = null
let chartResizeHandler: (() => void) | null = null

async function renderVisitChart() {
  if (!visitChartRef.value || visitTrend.value.length === 0) return

  if (!echartsLib) {
    echartsLib = await import('echarts')
  }
  const echarts = echartsLib

  if (!visitChart) {
    visitChart = echarts.init(visitChartRef.value)
    // 响应式（只注册一次，避免主题切换重绘时重复绑定）
    chartResizeHandler = () => visitChart?.resize()
    window.addEventListener('resize', chartResizeHandler)
  }

  const primary = themeVar('--tcm-primary') || '#8B4513'
  const accent = themeVar('--tcm-accent') || '#D4A574'

  visitChart.setOption({
    tooltip: { trigger: 'axis' },
    grid: { left: 40, right: 20, top: 20, bottom: 30 },
    xAxis: {
      type: 'category',
      data: visitTrend.value.map((d: any) => d.date),
      axisLabel: { color: '#666' },
    },
    yAxis: {
      type: 'value',
      minInterval: 1,
      axisLabel: { color: '#666' },
    },
    series: [{
      type: 'bar',
      data: visitTrend.value.map((d: any) => d.count),
      itemStyle: {
        color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
          { offset: 0, color: primary },
          { offset: 1, color: accent },
        ]),
        borderRadius: [4, 4, 0, 0],
      },
      barWidth: '40%',
    }],
  })
}

onMounted(loadDashboard)

// 主题切换后重绘图表（ECharts 读不到 CSS 变量，必须重新取色）
onThemeChange(() => {
  const primary = themeVar('--tcm-primary') || '#8B4513'
  statCards.value[0].color = primary
  quickActions.value[0].color = primary
  const formulaAction = quickActions.value.find((a) => a.route === '/classic-formulas')
  if (formulaAction) formulaAction.color = primary
  renderVisitChart()
})
onUnmounted(() => {
  if (chartResizeHandler) window.removeEventListener('resize', chartResizeHandler)
  visitChart?.dispose()
  visitChart = null
})
</script>

<style scoped lang="scss">
.dashboard {
  .section-row {
    margin-top: 20px;
    row-gap: 20px;
  }

  .main-card {
    height: 100%;
    border-radius: 12px;
    border: 1px solid #f0e4d6;

    :deep(.el-card__header) {
      padding: 0;
      border-bottom: none;
    }
  }

  .chart-box {
    height: 280px;
  }

  .stat-card {
    border-radius: 12px;
    border: 1px solid #f0e4d6;
    transition: transform .2s ease, box-shadow .2s ease;

    &:hover {
      transform: translateY(-2px);
      box-shadow: 0 6px 18px rgba(139, 69, 19, .08);
    }

    .stat-card-body {
      display: flex;
      align-items: center;
      gap: 12px;

      .stat-icon {
        width: 48px;
        height: 48px;
        border-radius: 10px;
        display: flex;
        align-items: center;
        justify-content: center;
        flex-shrink: 0;
      }

      .stat-info {
        min-width: 0;

        .stat-value {
          font-size: 24px;
          font-weight: 700;
          color: #2c1810;
          line-height: 1.2;
          font-variant-numeric: tabular-nums;
        }
        .stat-title {
          font-size: 12px;
          color: #907a63;
          margin-top: 4px;
        }
      }
    }
  }

  .quick-action {
    display: flex;
    flex-direction: column;
    align-items: center;
    padding: 16px 8px;
    border-radius: 10px;
    cursor: pointer;
    transition: all 0.2s;

    &:hover {
      background: #fdf8f3;
      transform: translateY(-2px);
    }

    .action-title {
      font-size: 13px;
      font-weight: 600;
      color: #3d2a1c;
      margin-top: 6px;
    }

    .action-desc {
      font-size: 11px;
      color: #a08b76;
      margin-top: 2px;
    }
  }

  .alert-list,
  .todo-list {
    .alert-item,
    .todo-item {
      display: flex;
      align-items: center;
      gap: 8px;
      padding: 9px 0;
      border-bottom: 1px dashed #f0e4d6;

      &:last-child {
        border-bottom: none;
      }

      .alert-herb,
      span:nth-child(2) {
        font-weight: 500;
        color: #3d2a1c;
        flex: 1;
      }

      .alert-qty {
        font-size: 13px;
        color: #907a63;
        font-variant-numeric: tabular-nums;
      }
    }

    .todo-followup {
      cursor: pointer;
      border-radius: 6px;

      .todo-name {
        font-weight: 500;
        color: #3d2a1c;
      }
      .todo-date {
        font-size: 13px;
        color: #7a6553;
        font-variant-numeric: tabular-nums;
      }
      .todo-note {
        font-size: 12px;
        color: #a08b76;
      }

      &:hover {
        background: #fdf8f3;
      }
    }
  }
}

@media (max-width: 767px) {
  .dashboard {
    .section-row {
      margin-top: 12px;
      row-gap: 12px;
    }

    .chart-box {
      height: 220px;
    }

    .stat-card .stat-card-body .stat-info .stat-value {
      font-size: 20px;
    }
  }
}
</style>