import { createRouter, createWebHashHistory } from 'vue-router'
import type { RouteRecordRaw } from 'vue-router'

const routes: RouteRecordRaw[] = [
  {
    path: '/login',
    name: 'Login',
    component: () => import('@/views/auth/Login.vue'),
    meta: { title: '登录', public: true },
  },
  {
    path: '/',
    component: () => import('@/layouts/MainLayout.vue'),
    redirect: '/dashboard',
    children: [
      {
        path: 'dashboard',
        name: 'Dashboard',
        component: () => import('@/views/dashboard/Dashboard.vue'),
        meta: { title: '工作台', icon: 'HomeFilled' },
      },
      {
        path: 'statistics',
        name: 'Statistics',
        component: () => import('@/views/dashboard/Statistics.vue'),
        meta: { title: '统计报表', icon: 'DataAnalysis' },
      },
      {
        path: 'patients',
        name: 'PatientList',
        component: () => import('@/views/patient/PatientList.vue'),
        meta: { title: '患者列表', icon: 'User' },
      },
      {
        path: 'patients/:id',
        name: 'PatientDetail',
        component: () => import('@/views/patient/PatientDetail.vue'),
        meta: { title: '患者详情', hidden: true },
      },
      {
        path: 'patients/:id/visit',
        name: 'VisitRecord',
        component: () => import('@/views/patient/VisitRecord.vue'),
        meta: { title: '就诊记录', hidden: true },
      },
      {
        path: 'constitution/:id?',
        name: 'ConstitutionScale',
        component: () => import('@/views/patient/ConstitutionScale.vue'),
        meta: { title: '体质辨识', icon: 'TrendCharts' },
      },
      {
        path: 'herbs',
        name: 'HerbList',
        component: () => import('@/views/herb/HerbList.vue'),
        meta: { title: '药材字典', icon: 'FirstAidKit' },
      },
      {
        path: 'herbs/inventory',
        name: 'InventoryManage',
        component: () => import('@/views/herb/InventoryManage.vue'),
        meta: { title: '库存管理', icon: 'Box' },
      },
      {
        path: 'acupoints',
        name: 'AcupointList',
        component: () => import('@/views/acupoint/AcupointList.vue'),
        meta: { title: '针灸穴位', icon: 'Aim' },
      },
      {
        path: 'prescriptions',
        name: 'PrescriptionList',
        component: () => import('@/views/prescription/PrescriptionList.vue'),
        meta: { title: '处方列表', icon: 'Document' },
      },
      {
        path: 'prescriptions/new',
        name: 'PrescriptionEditor',
        component: () => import('@/views/prescription/PrescriptionEditor.vue'),
        meta: { title: '开具处方', hidden: true },
      },
      {
        path: 'classic-formulas',
        name: 'ClassicFormulaLib',
        component: () => import('@/views/prescription/ClassicFormulaLib.vue'),
        meta: { title: '经典方库', icon: 'Notebook' },
      },
      {
        path: 'acupoint-formulas',
        name: 'AcupointFormulaLib',
        component: () => import('@/views/acupoint/AcupointFormulaLib.vue'),
        meta: { title: '针灸方库', icon: 'Aim' },
      },
      {
        path: 'knowledge',
        name: 'KnowledgeSearch',
        component: () => import('@/views/knowledge/KnowledgeSearch.vue'),
        meta: { title: '知识检索', icon: 'Search' },
      },
      {
        path: 'book-library',
        name: 'BookLibrary',
        component: () => import('@/views/knowledge/BookLibrary.vue'),
        meta: { title: '医籍文库', icon: 'Reading' },
      },
      {
        path: 'diagnosis',
        name: 'DiagnosisChat',
        component: () => import('@/views/diagnosis/DiagnosisChat.vue'),
        meta: { title: '智能问诊', icon: 'ChatDotRound' },
      },
      {
        path: 'dictionaries',
        name: 'DictionaryManage',
        component: () => import('@/views/dictionary/DictionaryManage.vue'),
        meta: { title: '主数据字典', icon: 'Coin' },
      },
      {
        path: 'settings',
        name: 'Settings',
        component: () => import('@/views/settings/Settings.vue'),
        meta: { title: '系统设置', icon: 'Setting' },
      },
    ],
  },
]

const router = createRouter({
  history: createWebHashHistory(),
  routes,
})

// 全局前置守卫：未登录一律跳转登录页
router.beforeEach((to) => {
  const token = localStorage.getItem('tcm_token')
  if (to.meta.public) {
    return true
  }
  if (!token) {
    return { path: '/login', query: to.fullPath !== '/' ? { redirect: to.fullPath } : {} }
  }
  return true
})

export default router