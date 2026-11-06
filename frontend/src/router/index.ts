import { createRouter, createWebHashHistory } from 'vue-router'
import type { RouteRecordRaw } from 'vue-router'
import { useAuthStore } from '@/store/auth'

// 全部改为静态引入：避免 dev 模式下按需编译/依赖重新预打包导致的
// 「首次访问某菜单卡顿」以及「客户端跳转被中止、地址变但视图不切换、需刷新」的问题。
import Login from '@/views/auth/Login.vue'
import MainLayout from '@/layouts/MainLayout.vue'
import Dashboard from '@/views/dashboard/Dashboard.vue'
import Statistics from '@/views/dashboard/Statistics.vue'
import PatientList from '@/views/patient/PatientList.vue'
import PatientDetail from '@/views/patient/PatientDetail.vue'
import ConstitutionScale from '@/views/patient/ConstitutionScale.vue'
import RegistrationView from '@/views/registration/RegistrationView.vue'
import HerbList from '@/views/herb/HerbList.vue'
import AcupointList from '@/views/acupoint/AcupointList.vue'
import StockOverview from '@/views/inventory/Overview.vue'
import StockItems from '@/views/inventory/ItemManage.vue'
import StockTransactions from '@/views/inventory/Transactions.vue'
import StockCheck from '@/views/inventory/Check.vue'
import StockSuppliers from '@/views/inventory/SupplierManage.vue'
import StockOptions from '@/views/inventory/StockOptions.vue'
import StockPurchases from '@/views/inventory/PurchaseInbound.vue'
import StockReports from '@/views/inventory/Reports.vue'
import PrescriptionList from '@/views/prescription/PrescriptionList.vue'
import PrescriptionEditor from '@/views/prescription/PrescriptionEditor.vue'
import ClassicFormulaLib from '@/views/prescription/ClassicFormulaLib.vue'
import BillingView from '@/views/billing/BillingView.vue'
import AcupointFormulaLib from '@/views/acupoint/AcupointFormulaLib.vue'
import KnowledgeSearch from '@/views/knowledge/KnowledgeSearch.vue'
import BookLibrary from '@/views/knowledge/BookLibrary.vue'
import DiagnosisChat from '@/views/diagnosis/DiagnosisChat.vue'
import DictionaryManage from '@/views/dictionary/DictionaryManage.vue'
import Settings from '@/views/settings/Settings.vue'
import OperationLog from '@/views/system/OperationLog.vue'
import UserManage from '@/views/system/UserManage.vue'

const routes: RouteRecordRaw[] = [
  {
    path: '/login',
    name: 'Login',
    component: Login,
    meta: { title: '登录', public: true },
  },
  {
    path: '/',
    component: MainLayout,
    redirect: '/dashboard',
    children: [
      {
        path: 'dashboard',
        name: 'Dashboard',
        component: Dashboard,
        meta: { title: '工作台', icon: 'HomeFilled' },
      },
      {
        path: 'statistics',
        name: 'Statistics',
        component: Statistics,
        meta: { title: '统计报表', icon: 'DataAnalysis' },
      },
      {
        path: 'patients',
        name: 'PatientList',
        component: PatientList,
        meta: { title: '患者列表', icon: 'User' },
      },
      {
        path: 'patients/:id',
        name: 'PatientDetail',
        component: PatientDetail,
        meta: { title: '患者详情', hidden: true },
      },
      {
        path: 'registration',
        name: 'RegistrationView',
        component: RegistrationView,
        meta: { title: '挂号台', icon: 'Ticket', perm: 'patient:write' },
      },
      {
        path: 'constitution/:id?',
        name: 'ConstitutionScale',
        component: ConstitutionScale,
        meta: { title: '十问辨证', icon: 'TrendCharts' },
      },
      {
        path: 'herbs',
        name: 'HerbList',
        component: HerbList,
        meta: { title: '药材字典', icon: 'FirstAidKit' },
      },
      {
        path: 'acupoints',
        name: 'AcupointList',
        component: AcupointList,
        meta: { title: '针灸穴位', icon: 'Aim' },
      },
      {
        path: 'stock/overview',
        name: 'StockOverview',
        component: StockOverview,
        meta: { title: '库存总览', icon: 'Box' },
      },
      {
        path: 'stock/items',
        name: 'StockItems',
        component: StockItems,
        meta: { title: '物品管理', icon: 'Goods' },
      },
      {
        path: 'stock/transactions',
        name: 'StockTransactions',
        component: StockTransactions,
        meta: { title: '库存流水', icon: 'Tickets' },
      },
      {
        path: 'stock/check',
        name: 'StockCheck',
        component: StockCheck,
        meta: { title: '库房盘点', icon: 'Checked' },
      },
      {
        path: 'stock/suppliers',
        name: 'StockSuppliers',
        component: StockSuppliers,
        meta: { title: '供应商', icon: 'OfficeBuilding' },
      },
      {
        path: 'stock/options',
        name: 'StockOptions',
        component: StockOptions,
        meta: { title: '库存选项', icon: 'Collection' },
      },
      {
        path: 'stock/purchases',
        name: 'StockPurchases',
        component: StockPurchases,
        meta: { title: '采购入库', icon: 'ShoppingCart' },
      },
      {
        path: 'stock/reports',
        name: 'StockReports',
        component: StockReports,
        meta: { title: '进销存报表', icon: 'DataLine' },
      },
      {
        path: 'prescriptions',
        name: 'PrescriptionList',
        component: PrescriptionList,
        meta: { title: '处方列表', icon: 'Document' },
      },
      {
        path: 'prescriptions/new',
        name: 'PrescriptionEditor',
        component: PrescriptionEditor,
        meta: { title: '开具处方', hidden: true },
      },
      {
        path: 'billing',
        name: 'BillingView',
        component: BillingView,
        meta: { title: '收费管理', icon: 'Money', perm: 'billing:read' },
      },
      {
        path: 'classic-formulas',
        name: 'ClassicFormulaLib',
        component: ClassicFormulaLib,
        meta: { title: '中药方库', icon: 'Notebook' },
      },
      {
        path: 'acupoint-formulas',
        name: 'AcupointFormulaLib',
        component: AcupointFormulaLib,
        meta: { title: '针灸方库', icon: 'Aim' },
      },
      {
        path: 'knowledge',
        name: 'KnowledgeSearch',
        component: KnowledgeSearch,
        meta: { title: '知识检索', icon: 'Search' },
      },
      {
        path: 'book-library',
        name: 'BookLibrary',
        component: BookLibrary,
        meta: { title: '医籍文库', icon: 'Reading', perm: 'dict:write' },
      },
      {
        path: 'diagnosis',
        name: 'DiagnosisChat',
        component: DiagnosisChat,
        meta: { title: '智能问诊', icon: 'ChatDotRound' },
      },
      {
        path: 'dictionaries',
        name: 'DictionaryManage',
        component: DictionaryManage,
        meta: { title: '数据字典', icon: 'Coin' },
      },
      {
        path: 'settings',
        name: 'Settings',
        component: Settings,
        meta: { title: '系统设置', icon: 'Setting', perm: 'system:write' },
        },
      {
        path: 'system/logs',
        name: 'OperationLog',
        component: OperationLog,
        meta: { title: '操作日志', icon: 'Document', perm: 'log:read' },
        },
      {
        path: 'system/users',
        name: 'UserManage',
        component: UserManage,
        meta: { title: '账号管理', icon: 'UserFilled', perm: 'user:read' },
      },
    ],
  },
  // 未知路径统一回工作台，避免 <router-view> 空白且无任何反馈
  { path: '/:pathMatch(.*)*', redirect: '/dashboard' },
]

const router = createRouter({
  history: createWebHashHistory(),
  routes,
})

// ── 轻量顶部加载条（无第三方依赖）：导航超过 150ms 才显示，结束/出错隐藏，避免瞬间切换闪一下 ──
let barEl: HTMLDivElement | null = null
let barTimer: number | null = null

function ensureBar(): HTMLDivElement {
  if (!barEl) {
    barEl = document.createElement('div')
    barEl.style.cssText =
      'position:fixed;top:0;left:0;height:3px;width:0;z-index:99999;' +
      'background:linear-gradient(90deg,#D4A574,#E8C9A0);transition:width .2s ease;opacity:.9;'
    document.body.appendChild(barEl)
  }
  return barEl
}

function showBar() {
  if (typeof document === 'undefined' || barTimer !== null) return
  barTimer = window.setTimeout(() => {
    barTimer = null
    const el = ensureBar()
    el.style.transition = 'width .2s ease'
    el.style.width = '30%'
  }, 150)
}

function hideBar() {
  if (barTimer !== null) {
    clearTimeout(barTimer)
    barTimer = null
  }
  if (!barEl) return
  const el = barEl
  barEl = null
  el.style.transition = 'width .25s ease, opacity .25s ease'
  el.style.width = '100%'
  el.style.opacity = '0'
  setTimeout(() => el.remove(), 300)
}

// 全局前置守卫：未登录一律跳转登录页
router.beforeEach((to) => {
  showBar()
  // 用 localStorage 中的 user 作为「是否曾登录」的同步提示（令牌本身已移入内存/Cookie，不落 localStorage）
  const token = localStorage.getItem('tcm_user')
  if (to.meta.public) {
    return true
  }
  if (!token) {
    return { path: '/login', query: to.fullPath !== '/' ? { redirect: to.fullPath } : {} }
  }
  // 细粒度权限页：user 加载完成后无权限则回退（未加载时不拦截，避免首屏误判）
  if (to.meta.perm) {
    const auth = useAuthStore()
    if (auth.user && !auth.can(to.meta.perm as string)) {
      return { path: '/dashboard' }
    }
  }
  return true
})

router.afterEach(() => {
  hideBar()
})

// 导航异常时仅记录，避免自动 reload 造成刷新循环（路由已改为静态引入，无动态导入失败场景）
router.onError((err: unknown) => {
  hideBar()
  console.error('[router] 导航出错：', err)
})

export default router