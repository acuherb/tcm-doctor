<template>
  <div class="prescription-list">
    <el-card shadow="hover" class="main-card">
      <template #header>
        <div class="card-head-bar">
          <div class="card-head-title">
            <span class="head-icon">📋</span>
            <span class="head-text">处方列表</span>
            <el-tag v-if="prescriptions.length > 0" size="small" type="info" effect="plain" round class="head-count">
              {{ prescriptions.length }} 张
            </el-tag>
          </div>
          <div class="card-actions">
            <el-button v-if="editable" type="primary" @click="$router.push('/prescriptions/new')">
              <el-icon><Plus /></el-icon>开具处方
            </el-button>
          </div>
        </div>
      </template>

      <div class="filter-bar">
        <el-select v-model="patientFilter" filterable remote reserve-keyword
          :remote-method="searchPatients" :loading="patientsLoading" clearable
          placeholder="按患者筛选" class="filter-patient" @change="loadPrescriptions">
          <el-option v-for="p in patients" :key="p.id" :label="p.name" :value="p.id" />
        </el-select>
        <el-select v-model="statusFilter" placeholder="全部状态" clearable class="filter-status" @change="loadPrescriptions">
          <el-option label="已开" value="已开" />
          <el-option label="已审核" value="已审核" />
          <el-option label="已发药" value="已发药" />
          <el-option label="已取消" value="已取消" />
        </el-select>
        <el-button type="primary" @click="loadPrescriptions">查询</el-button>
        <el-button v-if="patientFilter || statusFilter" text class="reset-btn" @click="resetFilter">重置</el-button>
      </div>

      <el-table v-if="!isMobile" :data="prescriptions" class="rx-table" style="width:100%" empty-text="暂无处方记录">
        <el-table-column prop="id" label="编号" width="76">
          <template #default="{ row }">
            <span class="rx-no">#{{ row.id }}</span>
          </template>
        </el-table-column>
        <el-table-column label="患者" width="118">
          <template #default="{ row }">
            <span class="rx-patient">{{ row.patient_name || '-' }}</span>
            <span v-if="row.patient_id" class="rx-patient-id">#{{ row.patient_id }}</span>
          </template>
        </el-table-column>
        <el-table-column label="中药方" min-width="240">
          <template #default="{ row }">
            <template v-if="(row.items && row.items.length) || row.formula_name">
              <div v-if="row.formula_name" class="rx-formula-name">
                <span class="rx-dot is-herb"></span>{{ row.formula_name }}
              </div>
              <div class="herb-tags">
                <el-tag v-for="item in (row.items || [])" :key="item.id" size="small" round
                  effect="plain" class="herb-tag" :class="{ 'is-king': item.is_king_herb }">
                  {{ item.herb_name }}<em>{{ item.dose }}g</em>
                  <span v-if="item.special_method" class="herb-method">（{{ item.special_method }}）</span>
                </el-tag>
              </div>
              <div v-if="row.preparation_method || row.doses || row.administration" class="rx-meta">
                <span v-if="row.preparation_method">{{ row.preparation_method }}</span>
                <span v-if="row.doses"> · {{ row.doses }} 剂</span>
                <span v-if="row.administration"> · {{ row.administration }}</span>
              </div>
            </template>
            <span v-else class="rx-none">—</span>
          </template>
        </el-table-column>
        <el-table-column label="针灸方" min-width="240">
          <template #default="{ row }">
            <template v-if="(row.acupoints && row.acupoints.length) || row.acupoint_formula_name">
              <div v-if="row.acupoint_formula_name" class="rx-formula-name">
                <span class="rx-dot is-acu"></span>{{ row.acupoint_formula_name }}
              </div>
              <div class="acu-tags">
                <el-tag v-for="a in (row.acupoints || [])" :key="a.id" size="small" round
                  effect="plain" class="acu-tag">
                  {{ a.acupoint_name }}
                </el-tag>
              </div>
              <div v-if="row.treatment_frequency || row.treatment_days || row.acupoint_technique" class="rx-meta">
                <span v-if="row.acupoint_technique">{{ row.acupoint_technique }}</span>
                <span v-if="row.treatment_frequency"> · {{ row.treatment_frequency }}</span>
                <span v-if="row.treatment_days"> · {{ row.treatment_days }} 天</span>
              </div>
            </template>
            <span v-else class="rx-none">—</span>
          </template>
        </el-table-column>
        <el-table-column label="开方医师" width="96">
          <template #default="{ row }">
            <span v-if="row.doctor_name" class="rx-doctor">{{ row.doctor_name }}</span>
            <span v-else class="rx-none">—</span>
          </template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="86">
          <template #default="{ row }">
            <el-tag :type="statusType(row.status)" size="small" effect="light" round>{{ row.status }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="开具时间" width="150">
          <template #default="{ row }">
            <span class="rx-time">{{ formatTime(row.created_at) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="金额" width="104" align="right">
          <template #default="{ row }">
            <span class="rx-price" v-if="row.total_price != null">¥{{ Number(row.total_price).toFixed(2) }}</span>
            <span v-else class="rx-none">—</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="184" fixed="right">
          <template #default="{ row }">
            <div class="rx-ops">
              <el-button link type="primary" size="small" @click="viewDetail(row)">详情</el-button>
              <el-button v-if="editable && row.status !== '已发药' && row.status !== '已取消'" link type="primary" size="small" @click="$router.push(`/prescriptions/new?id=${row.id}`)">编辑</el-button>
              <el-button v-if="editable && row.status === '已开'" link type="success" size="small" @click="reviewPrescription(row)">审核</el-button>
              <el-button v-if="editable && row.status === '已审核'" link type="warning" size="small" @click="dispensePrescription(row)">发药</el-button>
              <el-button v-if="editable && row.status !== '已取消'" link type="danger" size="small" @click="voidPrescription(row)">作废</el-button>
              <el-button link type="info" size="small" @click="printPrescription(row)">打印</el-button>
            </div>
          </template>
        </el-table-column>
      </el-table>

      <!-- 移动端卡片视图 -->
      <div v-if="isMobile" class="rx-cards">
        <div v-for="row in prescriptions" :key="row.id" class="rx-card">
          <div class="card-head">
            <span class="card-no">#{{ row.id }}</span>
            <el-tag :type="statusType(row.status)" size="small">{{ row.status }}</el-tag>
          </div>
          <div class="card-patient">{{ row.patient_name || '-' }}<span v-if="row.patient_id" class="rx-patient-id">#{{ row.patient_id }}</span></div>
          <div class="card-time">{{ formatTime(row.created_at) }}</div>

          <div v-if="row.formula_name || (row.items && row.items.length)" class="card-section">
            <div class="rx-formula-name"><span class="rx-dot is-herb"></span>{{ row.formula_name || '自拟方' }}</div>
            <div class="herb-tags">
              <el-tag v-for="item in (row.items || [])" :key="item.id" size="small" round
                effect="plain" class="herb-tag" :class="{ 'is-king': item.is_king_herb }">
                {{ item.herb_name }}<em>{{ item.dose }}g</em>
                <span v-if="item.special_method" class="herb-method">（{{ item.special_method }}）</span>
              </el-tag>
            </div>
            <div v-if="row.preparation_method || row.doses || row.administration" class="rx-meta">
              <span v-if="row.preparation_method">{{ row.preparation_method }}</span>
              <span v-if="row.doses"> · {{ row.doses }} 剂</span>
              <span v-if="row.administration"> · {{ row.administration }}</span>
            </div>
          </div>

          <div v-if="row.acupoint_formula_name || (row.acupoints && row.acupoints.length)" class="card-section">
            <div class="rx-formula-name"><span class="rx-dot is-acu"></span>{{ row.acupoint_formula_name || '针灸方' }}</div>
            <div class="acu-tags">
              <el-tag v-for="a in (row.acupoints || [])" :key="a.id" size="small" round
                effect="plain" class="acu-tag">
                {{ a.acupoint_name }}
              </el-tag>
            </div>
            <div v-if="row.treatment_frequency || row.treatment_days || row.acupoint_technique" class="rx-meta">
              <span v-if="row.acupoint_technique">{{ row.acupoint_technique }}</span>
              <span v-if="row.treatment_frequency"> · {{ row.treatment_frequency }}</span>
              <span v-if="row.treatment_days"> · {{ row.treatment_days }} 天</span>
            </div>
          </div>

          <div class="card-actions">
            <el-button link type="primary" size="small" @click="viewDetail(row)">详情</el-button>
            <el-button v-if="editable && row.status !== '已发药' && row.status !== '已取消'" link type="primary" size="small" @click="$router.push(`/prescriptions/new?id=${row.id}`)">编辑</el-button>
            <el-button v-if="editable && row.status === '已开'" link type="success" size="small" @click="reviewPrescription(row)">审核</el-button>
            <el-button v-if="editable && row.status === '已审核'" link type="warning" size="small" @click="dispensePrescription(row)">发药</el-button>
            <el-button v-if="editable && row.status !== '已取消'" link type="danger" size="small" @click="voidPrescription(row)">作废</el-button>
            <el-button link type="info" size="small" @click="printPrescription(row)">打印</el-button>
          </div>
        </div>
        <el-empty v-if="!prescriptions.length" description="暂无处方记录" />
      </div>
    </el-card>

    <!-- 处方详情对话框 -->
    <el-dialog v-model="detailVisible" title="处方详情" width="640px" destroy-on-close>
      <template v-if="currentPrescription">
        <!-- 顶部：患者 + 状态 -->
        <el-descriptions :column="2" border>
          <el-descriptions-item label="患者">{{ currentPrescription.patient_name || '-' }}<span v-if="currentPrescription.patient_id" class="rx-patient-id">#{{ currentPrescription.patient_id }}</span></el-descriptions-item>
          <el-descriptions-item label="状态">
            <el-tag :type="statusType(currentPrescription.status)">{{ currentPrescription.status }}</el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="开方医师">{{ currentPrescription.doctor_name || '-' }}</el-descriptions-item>
          <el-descriptions-item label="开具时间">{{ formatTime(currentPrescription.created_at) }}</el-descriptions-item>
        </el-descriptions>

        <!-- 中药方 -->
        <template v-if="(currentPrescription.items || []).length">
          <el-divider content-position="left">🌿 中药方</el-divider>
          <el-descriptions :column="2" border>
            <el-descriptions-item label="方名">{{ currentPrescription.formula_name || '自拟方' }}</el-descriptions-item>
            <el-descriptions-item label="剂数">{{ currentPrescription.doses }}剂</el-descriptions-item>
            <el-descriptions-item label="煎法">{{ currentPrescription.preparation_method }}</el-descriptions-item>
            <el-descriptions-item label="服法">{{ currentPrescription.administration || '-' }}</el-descriptions-item>
          </el-descriptions>
          <el-table :data="currentPrescription.items || []" class="tcm-table" style="margin-top:12px;" size="small">
            <el-table-column prop="herb_name" label="药味" width="100" />
            <el-table-column prop="dose" label="剂量(g)" width="90" />
            <el-table-column prop="special_method" label="煎法" width="80">
              <template #default="{ row }">{{ row.special_method || '-' }}</template>
            </el-table-column>
            <el-table-column prop="is_king_herb" label="君药" width="60">
              <template #default="{ row }">
                <el-icon v-if="row.is_king_herb" color="#D4A574"><Star /></el-icon>
              </template>
            </el-table-column>
            <el-table-column prop="note" label="备注" show-overflow-tooltip>
              <template #default="{ row }">{{ row.note || '-' }}</template>
            </el-table-column>
          </el-table>
        </template>

        <!-- 针灸方 -->
        <template v-if="currentPrescription.acupoint_formula_name || currentPrescription.acupoint_technique || currentPrescription.treatment_frequency || currentPrescription.treatment_days || (currentPrescription.acupoints || []).length">
          <el-divider content-position="left">🪡 针灸方</el-divider>
          <el-descriptions :column="2" border>
            <el-descriptions-item v-if="currentPrescription.acupoint_formula_name" label="方案名">{{ currentPrescription.acupoint_formula_name }}</el-descriptions-item>
            <el-descriptions-item v-if="currentPrescription.acupoint_technique" label="针法">{{ currentPrescription.acupoint_technique }}</el-descriptions-item>
            <el-descriptions-item v-if="currentPrescription.treatment_frequency" label="操作频次">{{ currentPrescription.treatment_frequency }}</el-descriptions-item>
            <el-descriptions-item v-if="currentPrescription.treatment_days" label="疗程天数">{{ currentPrescription.treatment_days }} 天</el-descriptions-item>
          </el-descriptions>
          <el-table v-if="(currentPrescription.acupoints || []).length" :data="currentPrescription.acupoints || []" class="tcm-table" size="small" style="margin-top:12px;">
            <el-table-column type="index" label="#" width="50" />
            <el-table-column prop="acupoint_name" label="穴位" width="120" />
            <el-table-column prop="technique" label="针法" width="120">
              <template #default="{ row }">{{ row.technique || '-' }}</template>
            </el-table-column>
            <el-table-column prop="retention" label="留针" width="80">
              <template #default="{ row }">{{ formatRetention(row.retention) || '-' }}</template>
            </el-table-column>
            <el-table-column prop="note" label="备注" show-overflow-tooltip>
              <template #default="{ row }">{{ row.note || '-' }}</template>
            </el-table-column>
          </el-table>
        </template>

        <!-- 医嘱 -->
        <el-divider content-position="left">医嘱</el-divider>
        <div style="padding:2px 4px;line-height:1.8;">{{ currentPrescription.doctor_notes || '无' }}</div>
      </template>
      <template #footer>
        <el-button @click="detailVisible = false">关闭</el-button>
        <el-button v-if="editable && currentPrescription && currentPrescription.status !== '已取消'"
          type="danger" plain @click="voidPrescription(currentPrescription)">作废处方</el-button>
      </template>
    </el-dialog>

    <!-- 打印预览 -->
    <el-dialog v-model="printVisible" title="处方打印" width="860px" destroy-on-close>
      <div ref="printRef" class="prescription-print">
        <div class="print-header">
          <div class="print-clinic">{{ clinicName || '中医诊所' }}</div>
          <h2>中医处方笺</h2>
        </div>
        <template v-if="currentPrescription">
          <div class="print-info">
            <span>患者: {{ currentPrescription.patient_name || '-' }}</span>
            <span>处方编号: #{{ currentPrescription.id }}</span>
            <span>日期: {{ formatTime(currentPrescription.created_at) }}</span>
          </div>

          <!-- 中药方 -->
          <template v-if="(currentPrescription.items || []).length">
            <div class="print-section-title">🌿 中药方</div>
            <div class="print-meta">
              <span>方名: {{ currentPrescription.formula_name || '自拟方' }}</span>
              <span>剂数: {{ currentPrescription.doses }}剂</span>
              <span>煎法: {{ currentPrescription.preparation_method }}</span>
              <span v-if="currentPrescription.administration">服法: {{ currentPrescription.administration }}</span>
            </div>
            <table class="print-herb-table">
              <thead>
                <tr><th>药味</th><th>剂量(g)</th><th>煎法</th><th>备注</th></tr>
              </thead>
              <tbody>
                <tr v-for="item in (currentPrescription.items || [])" :key="item.id">
                  <td>{{ item.herb_name }}{{ item.is_king_herb ? ' ★' : '' }}</td>
                  <td>{{ item.dose }}</td>
                  <td>{{ item.special_method || '' }}</td>
                  <td>{{ item.note || '' }}</td>
                </tr>
              </tbody>
            </table>
          </template>

          <!-- 针灸方 -->
          <template v-if="(currentPrescription.acupoints || []).length || currentPrescription.acupoint_formula_name || currentPrescription.acupoint_technique || currentPrescription.treatment_frequency || currentPrescription.treatment_days">
            <div class="print-section-title">🪡 针灸方</div>
            <div v-if="currentPrescription.acupoint_formula_name || currentPrescription.acupoint_technique || currentPrescription.treatment_frequency || currentPrescription.treatment_days" class="print-meta">
              <span v-if="currentPrescription.acupoint_formula_name">方案: {{ currentPrescription.acupoint_formula_name }}</span>
              <span v-if="currentPrescription.acupoint_technique">针法: {{ currentPrescription.acupoint_technique }}</span>
              <span v-if="currentPrescription.treatment_frequency">频次: {{ currentPrescription.treatment_frequency }}</span>
              <span v-if="currentPrescription.treatment_days">疗程: {{ currentPrescription.treatment_days }}天</span>
            </div>
            <table v-if="(currentPrescription.acupoints || []).length" class="print-herb-table">
              <thead>
                <tr><th>穴位</th><th>针法</th><th>留针</th><th>备注</th></tr>
              </thead>
              <tbody>
                <tr v-for="a in (currentPrescription.acupoints || [])" :key="a.id">
                  <td>{{ a.acupoint_name }}</td>
                  <td>{{ a.technique || '' }}</td>
                  <td>{{ formatRetention(a.retention) }}</td>
                  <td>{{ a.note || '' }}</td>
                </tr>
              </tbody>
            </table>
          </template>

          <div class="print-footer">
            <p v-if="currentPrescription.total_price != null" class="print-total">
              合计金额: ￥{{ Number(currentPrescription.total_price).toFixed(2) }}
              <span v-if="currentPrescription.acupuncture_fee" style="color:#999;font-size:12px;">
                （含针灸 ￥{{ Number(currentPrescription.acupuncture_fee).toFixed(2) }}）
              </span>
            </p>
            <p v-if="currentPrescription.doctor_notes">医嘱: {{ currentPrescription.doctor_notes }}</p>
            <p v-if="printDoctor" class="print-doctor">医师: {{ printDoctor }}</p>
          </div>
        </template>
      </div>
      <template #footer>
        <el-button @click="printVisible = false">关闭</el-button>
        <el-button type="primary" @click="doPrint">打印</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onBeforeUnmount } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, Star } from '@element-plus/icons-vue'
import api from '@/utils/api'
import type { Patient, Prescription, AppConfig } from '@/types'
import { useAuthStore } from '@/store/auth'

// 游客只读：隐藏所有写操作
const auth = useAuthStore()
const editable = computed(() => auth.canWrite('prescriptions'))

// ---- 移动端适配 ----
const isMobile = ref(false)
function updateViewport() {
  isMobile.value = window.innerWidth < 768
}
onMounted(updateViewport)
onMounted(() => window.addEventListener('resize', updateViewport))
onBeforeUnmount(() => window.removeEventListener('resize', updateViewport))

const prescriptions = ref<any[]>([])
const statusFilter = ref('')
const patientFilter = ref<number | null>(null)
const patients = ref<any[]>([])
const patientsLoading = ref(false)
const detailVisible = ref(false)
const printVisible = ref(false)
const currentPrescription = ref<any>(null)
const printRef = ref<HTMLElement>()
const clinicName = ref('')
const doctorName = ref('')

// 打印署名：优先用处方记录的开方医师（谁开的方打印谁），存量处方回退到系统设置中的旧配置
const printDoctor = computed(() => currentPrescription.value?.doctor_name || doctorName.value || '')

function statusType(status: string) {
  if (status === '已开') return 'info'
  if (status === '已审核') return 'warning'
  if (status === '已发药') return 'success'
  if (status === '已取消') return 'danger'
  return 'info'
}

function formatTime(t: string) {
  if (!t) return '-'
  return new Date(t).toLocaleString('zh-CN')
}

// 留针时间：数据里可能已带「分钟/分」，避免重复拼出「20分钟 分钟」
function formatRetention(v: any) {
  if (v === null || v === undefined) return ''
  const s = String(v).trim()
  if (!s) return ''
  if (/分/.test(s)) return s
  return s + ' 分钟'
}

async function loadPrescriptions() {
  try {
    const params: Record<string, unknown> = { limit: 100 }
    if (statusFilter.value) params.status = statusFilter.value
    if (patientFilter.value) params.patient_id = patientFilter.value
    prescriptions.value = (await api.get<Paginated<Prescription>>('/prescriptions', { params }))
  } catch {}
}

function resetFilter() {
  patientFilter.value = null
  statusFilter.value = ''
  loadPrescriptions()
}

async function loadPatients() {
  patientsLoading.value = true
  try {
    const res = await api.get<Patient[]>(`/patients`, { params: { page_size: 100 } })
    patients.value = res.items || res || []
  } catch {}
  patientsLoading.value = false
}

async function searchPatients(query: string) {
  if (!query.trim()) { loadPatients(); return }
  patientsLoading.value = true
  try {
    const res = await api.get<Patient[]>(`/patients`, { params: { search: query, page_size: 50 } })
    patients.value = res.items || res || []
  } catch {}
  patientsLoading.value = false
}

function viewDetail(row: any) {
  currentPrescription.value = row
  detailVisible.value = true
}

async function reviewPrescription(row: any) {
  try {
    await ElMessageBox.confirm(`确认审核处方 #${row.id}「${row.formula_name || '自拟方'}」？`, '审核确认', {
      confirmButtonText: '确认审核',
      cancelButtonText: '取消',
      type: 'warning',
    })
    await api.put(`/prescriptions/${row.id}/review`)
    ElMessage.success('处方已审核')
    loadPrescriptions()
  } catch {}
}

async function dispensePrescription(row: any) {
  try {
    await ElMessageBox.confirm(
      `确认发药？将自动扣减库存。处方 #${row.id}「${row.formula_name || '自拟方'}」`,
      '发药确认',
      { confirmButtonText: '确认发药', cancelButtonText: '取消', type: 'warning' }
    )
    await api.put(`/prescriptions/${row.id}/dispense`)
    ElMessage.success('发药成功，库存已扣减')
    loadPrescriptions()
  } catch {}
}

async function voidPrescription(row: any) {
  const msg = row.status === '已发药'
    ? `确认作废处方 #${row.id}「${row.formula_name || '自拟方'}」？已发药的处方将退回库存并生成冲红记录。`
    : `确认作废处方 #${row.id}「${row.formula_name || '自拟方'}」？`
  try {
    await ElMessageBox.confirm(msg, '作废确认', {
      confirmButtonText: '确认作废', cancelButtonText: '取消', type: 'warning',
    })
  } catch { return }
  try {
    await api.post(`/prescriptions/${row.id}/void`)
    ElMessage.success('处方已作废')
    detailVisible.value = false
    loadPrescriptions()
    } catch {}
}

function printPrescription(row: any) {
  currentPrescription.value = row
  printVisible.value = true
}

function doPrint() {
  const content = printRef.value
  if (!content) return
  const win = window.open('', '_blank')
  if (!win) { ElMessage.error('无法打开打印窗口'); return }
  win.document.write(`
  <html><head><title>中医处方笺</title>
  <style>
    body { font-family: 'SimSun', serif; margin: 0; background: #eee; }
    .prescription-print { width: 794px; max-width: 100%; margin: 24px auto; padding: 32px 28px; background: #fff; box-sizing: border-box; }
    h2 { text-align: center; margin-bottom: 20px; }
    .print-clinic { text-align: center; font-size: 16px; font-weight: bold; margin-bottom: 4px; }
    .print-info { display: flex; justify-content: space-between; margin-bottom: 10px; font-size: 14px; }
    .print-section-title { font-size: 17px; font-weight: bold; color: #8B4513; margin: 16px 0 8px; padding-bottom: 4px; border-bottom: 1px solid #8B4513; }
    .print-meta { display: flex; flex-wrap: wrap; gap: 4px 18px; font-size: 13px; color: #333; margin-bottom: 8px; }
    table { width: 100%; border-collapse: collapse; margin: 10px 0; }
    th, td { border: 1px solid #333; padding: 6px 10px; text-align: center; font-size: 14px; }
    th { background: #f5f0eb; }
    .print-footer { margin-top: 16px; font-size: 14px; line-height: 1.8; }
    .print-doctor { text-align: right; margin-top: 12px; font-weight: bold; }
    @media screen { .prescription-print { box-shadow: 0 2px 16px rgba(0,0,0,0.12); } }
    @media print { body { background: #fff; } .prescription-print { margin: 0; box-shadow: none; } }
  </style></head><body>${content.innerHTML}</body></html>
  `)
  win.document.close()
  win.print()
}

onMounted(async () => {
  try {
    const res = await api.get<AppConfig>('/config')
    clinicName.value = res.clinic_name || ''
    doctorName.value = res.doctor_name || ''
  } catch {}
  loadPatients()
  loadPrescriptions()
})
</script>

<style scoped lang="scss">
.prescription-list {
  .main-card {
    :deep(.el-card__header) {
      padding: 14px 18px;
      background: linear-gradient(135deg, #fdf8f3 0%, #f7efe6 100%);
      border-bottom: 1px solid #f0e4d6;
    }
  }
  .card-head-bar {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 12px;
    flex-wrap: wrap;
  }
  .card-head-title { display: flex; align-items: center; gap: 8px; min-width: 0; }
  .head-icon { font-size: 18px; line-height: 1; }
  .head-text { font-size: 16px; font-weight: 600; color: #2c1810; letter-spacing: .5px; }
  .head-count { margin-left: 2px; background: #fff; border-color: #e6d9c9; color: #907a63; }
  .card-actions { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }

  .filter-bar {
    display: flex;
    gap: 10px;
    align-items: center;
    margin-bottom: 16px;
    flex-wrap: wrap;
    .filter-patient { width: 200px; }
    .filter-status { width: 150px; }
    .reset-btn { margin-left: -2px; }
  }

  .rx-table {
    :deep(th.el-table__cell) {
      background: #faf6f1;
      color: #7a6553;
      font-weight: 600;
    }
    :deep(.el-table__row) { transition: background .15s ease; }
    :deep(td.el-table__cell) { vertical-align: top; padding: 10px 0; }
  }

  .rx-no {
    font-size: 13px;
    color: #a39484;
    font-variant-numeric: tabular-nums;
  }

  .rx-patient {
    font-size: 14px;
    font-weight: 600;
    color: #2c1810;
  }

  .rx-patient-id {
    margin-left: 4px;
    font-size: 11px;
    font-weight: 400;
    color: #a39484;
    font-variant-numeric: tabular-nums;
  }

  .rx-doctor {
    font-size: 13px;
    color: #8b5e34;
  }

  .rx-time {
    font-size: 13px;
    color: #a39484;
    font-variant-numeric: tabular-nums;
  }

  .rx-price {
    font-size: 14px;
    font-weight: 600;
    color: var(--tcm-primary);
    font-variant-numeric: tabular-nums;
  }

  .rx-none {
    color: #c8bcae;
    font-size: 13px;
  }

  .rx-formula-name {
    display: flex;
    align-items: center;
    gap: 5px;
    font-size: 13px;
    font-weight: 600;
    color: #6b5644;
    margin-bottom: 5px;

    .rx-dot {
      flex: none;
      width: 6px;
      height: 6px;
      border-radius: 50%;
      &.is-herb { background: #a97b4f; }
      &.is-acu { background: #7fa07c; }
    }
  }

  .herb-tags,
  .acu-tags {
    display: flex;
    flex-wrap: wrap;
    gap: 4px;
  }

  .herb-tag {
    background: #faf6f1;
    border-color: #eddfd0;
    color: #8b5e34;

    em {
      font-style: normal;
      font-size: 11px;
      color: #b08b62;
      margin-left: 1px;
    }

    .herb-method { font-size: 11px; color: #b8956a; }

    &.is-king {
      background: #fdf3e7;
      border-color: #ebcfab;
      color: #a05c1f;
      font-weight: 600;
    }
  }

  .acu-tag {
    background: #f7f9f6;
    border-color: #dde8db;
    color: #5f7f5c;
  }

  .rx-meta {
    font-size: 12px;
    color: #a39484;
    margin-top: 4px;
  }

  .rx-ops {
    display: flex;
    flex-wrap: wrap;
    gap: 0 6px;

    :deep(.el-button) {
      margin-left: 0;
      padding: 2px 0;
    }
  }
}

.prescription-print {
  font-family: 'SimSun', serif;
  width: 794px;
  max-width: 100%;
  margin: 0 auto;
  padding: 32px 28px;
  background: #fff;
  color: #222;
  box-sizing: border-box;

  @media screen {
    box-shadow: 0 2px 16px rgba(0, 0, 0, 0.12);
  }

  .print-header {
    text-align: center;
    border-bottom: 2px solid #8B4513;
    padding-bottom: 12px;
    .print-clinic { font-size: 15px; font-weight: bold; color: #8B4513; margin-bottom: 2px; }
    h2 { margin: 0; color: #8B4513; }
  }

  .print-info {
    display: flex;
    justify-content: space-between;
    margin: 12px 0;
    font-size: 13px;
    color: #666;
  }

  .print-section-title {
    font-size: 17px;
    font-weight: bold;
    color: #8B4513;
    margin: 16px 0 8px;
    padding-bottom: 4px;
    border-bottom: 1px solid #8B4513;
  }

  .print-meta {
    display: flex;
    flex-wrap: wrap;
    gap: 4px 18px;
    font-size: 13px;
    color: #333;
    margin-bottom: 8px;
  }

  .print-herb-table {
    width: 100%;
    border-collapse: collapse;
    margin: 10px 0;

    th, td {
      border: 1px solid #ccc;
      padding: 6px 10px;
      text-align: center;
      font-size: 13px;
    }

    th { background: #f5f0eb; }
  }

  .print-footer {
    margin-top: 16px;
    font-size: 13px;
    line-height: 1.8;
    .print-doctor { text-align: right; margin-top: 12px; font-weight: bold; }
  }
}

/* ---- 移动端卡片视图 ---- */
.rx-cards {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.rx-card {
  background: #fff;
  border: 1px solid #e8e0d8;
  border-radius: 10px;
  padding: 12px 14px;
  box-shadow: 0 1px 3px rgba(0,0,0,0.05);
}
.rx-card .card-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 6px;
}
.rx-card .card-no {
  font-size: 15px;
  font-weight: 600;
  color: #8a7563;
}
.rx-card .card-patient {
  font-size: 17px;
  font-weight: 600;
  color: #2C1810;
}
.rx-card .card-time {
  font-size: 13px;
  color: #a89a8a;
  margin-bottom: 8px;
}
.rx-card .card-section {
  margin-top: 8px;
  padding-top: 8px;
  border-top: 1px dashed #eee;
}
.rx-card .card-actions {
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: 2px 6px;
  margin-top: 8px;
  padding-top: 8px;
  border-top: 1px dashed #eee;
}

/* ---- 移动端：搜索/筛选改为全宽纵向堆叠 ---- */
@media (max-width: 767px) {
  .prescription-list {
    .card-head-bar { align-items: stretch; }
    .card-actions { justify-content: flex-start; }

    .filter-bar {
      flex-direction: column;
      align-items: stretch;
      gap: 8px;

      .filter-patient,
      .filter-status { width: 100%; }
      .reset-btn { margin-left: 0; }
    }
  }
}
</style>