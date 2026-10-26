<template>
  <div class="prescription-list">
    <el-card shadow="hover">
      <template #header>
        <div style="display:flex;justify-content:space-between;align-items:center;">
          <span>📋 处方列表</span>
          <el-button v-if="editable" type="primary" size="small" @click="$router.push('/prescriptions/new')">
            <el-icon><Plus /></el-icon> 开具处方
          </el-button>
        </div>
      </template>

      <el-form :inline="true" @submit.prevent="loadPrescriptions">
        <el-form-item>
          <el-select v-model="patientFilter" filterable remote reserve-keyword
            :remote-method="searchPatients" :loading="patientsLoading" clearable
            placeholder="患者" style="width:150px" @change="loadPrescriptions">
            <el-option v-for="p in patients" :key="p.id" :label="p.name" :value="p.id" />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-select v-model="statusFilter" placeholder="状态筛选" clearable @change="loadPrescriptions" style="width:120px">
            <el-option label="已开" value="已开" />
            <el-option label="已审核" value="已审核" />
            <el-option label="已发药" value="已发药" />
            <el-option label="已取消" value="已取消" />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="loadPrescriptions">查询</el-button>
        </el-form-item>
      </el-form>

      <el-table :data="prescriptions" stripe style="width:100%" empty-text="暂无处方记录">
        <el-table-column prop="id" label="编号" width="70" />
        <el-table-column label="患者" width="90">
          <template #default="{ row }">{{ row.patient_name || '-' }}</template>
        </el-table-column>
        <el-table-column prop="formula_name" label="方名" width="160">
          <template #default="{ row }">{{ row.formula_name || '自拟方' }}</template>
        </el-table-column>
        <el-table-column label="药味" min-width="250">
          <template #default="{ row }">
            <div class="herb-tags">
              <el-tag v-for="item in (row.items || [])" :key="item.id" size="small" style="margin:2px;">
                {{ item.herb_name }} {{ item.dose }}g
                <span v-if="item.special_method" style="color:#8B4513;">({{ item.special_method }})</span>
              </el-tag>
            </div>
          </template>
        </el-table-column>
        <el-table-column prop="doses" label="剂数" width="70" />
        <el-table-column prop="preparation_method" label="煎法" width="80" />
        <el-table-column label="针灸方" min-width="230">
          <template #default="{ row }">
            <template v-if="(row.acupoints && row.acupoints.length) || row.acupoint_formula_name">
              <div v-if="row.acupoint_formula_name" class="acu-title">🪡 {{ row.acupoint_formula_name }}</div>
              <div class="acu-tags">
                <el-tag v-for="a in (row.acupoints || [])" :key="a.id" size="small" type="success" style="margin:2px;">
                  {{ a.acupoint_name }}
                </el-tag>
              </div>
              <div v-if="row.treatment_frequency || row.treatment_days || row.acupoint_technique" class="acu-meta">
                <span v-if="row.acupoint_technique">{{ row.acupoint_technique }}</span>
                <span v-if="row.treatment_frequency"> · {{ row.treatment_frequency }}</span>
                <span v-if="row.treatment_days"> · {{ row.treatment_days }}天</span>
              </div>
            </template>
            <span v-else style="color:#bbb;">—</span>
          </template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="90">
          <template #default="{ row }">
            <el-tag :type="statusType(row.status)" size="small">{{ row.status }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="开具时间" width="160">
          <template #default="{ row }">{{ formatTime(row.created_at) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="200" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" size="small" @click="viewDetail(row)">详情</el-button>
            <el-button v-if="editable && row.status === '已开'" link type="success" size="small" @click="reviewPrescription(row)">审核</el-button>
            <el-button v-if="editable && row.status === '已审核'" link type="warning" size="small" @click="dispensePrescription(row)">发药</el-button>
            <el-button link type="info" size="small" @click="printPrescription(row)">打印</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 处方详情对话框 -->
    <el-dialog v-model="detailVisible" title="处方详情" width="600px" destroy-on-close>
      <template v-if="currentPrescription">
        <el-descriptions :column="2" border>
          <el-descriptions-item label="方名">{{ currentPrescription.formula_name || '自拟方' }}</el-descriptions-item>
          <el-descriptions-item label="患者">{{ currentPrescription.patient_name || '-' }}</el-descriptions-item>
          <el-descriptions-item label="状态">
            <el-tag :type="statusType(currentPrescription.status)">{{ currentPrescription.status }}</el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="煎法">{{ currentPrescription.preparation_method }}</el-descriptions-item>
          <el-descriptions-item label="剂数">{{ currentPrescription.doses }}剂</el-descriptions-item>
          <el-descriptions-item label="服法" :span="2">{{ currentPrescription.administration || '-' }}</el-descriptions-item>
          <el-descriptions-item label="医嘱" :span="2">{{ currentPrescription.doctor_notes || '-' }}</el-descriptions-item>
        </el-descriptions>

        <el-table :data="currentPrescription.items || []" stripe style="margin-top:12px;" size="small">
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

        <template v-if="currentPrescription.acupoint_formula_name || currentPrescription.acupoint_technique || currentPrescription.treatment_frequency || currentPrescription.treatment_days">
          <el-divider content-position="left">🪡 针灸方</el-divider>
          <el-descriptions :column="2" border>
            <el-descriptions-item v-if="currentPrescription.acupoint_formula_name" label="方案名">{{ currentPrescription.acupoint_formula_name }}</el-descriptions-item>
            <el-descriptions-item v-if="currentPrescription.acupoint_technique" label="针法">{{ currentPrescription.acupoint_technique }}</el-descriptions-item>
            <el-descriptions-item v-if="currentPrescription.treatment_frequency" label="操作频次">{{ currentPrescription.treatment_frequency }}</el-descriptions-item>
            <el-descriptions-item v-if="currentPrescription.treatment_days" label="疗程天数">{{ currentPrescription.treatment_days }} 天</el-descriptions-item>
          </el-descriptions>
        </template>

        <template v-if="(currentPrescription.acupoints || []).length">
          <el-divider content-position="left">针灸配穴</el-divider>
          <el-table :data="currentPrescription.acupoints || []" stripe size="small">
            <el-table-column type="index" label="#" width="50" />
            <el-table-column prop="acupoint_name" label="穴位" width="120" />
            <el-table-column prop="technique" label="针法" width="120">
              <template #default="{ row }">{{ row.technique || '-' }}</template>
            </el-table-column>
            <el-table-column prop="retention" label="留针" width="80">
              <template #default="{ row }">{{ row.retention ? row.retention + ' 分钟' : '-' }}</template>
            </el-table-column>
            <el-table-column prop="note" label="备注" show-overflow-tooltip>
              <template #default="{ row }">{{ row.note || '-' }}</template>
            </el-table-column>
          </el-table>
        </template>
      </template>
    </el-dialog>

    <!-- 打印预览 -->
    <el-dialog v-model="printVisible" title="处方打印" width="600px" destroy-on-close>
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
          <div class="print-formula-name">{{ currentPrescription.formula_name || '自拟方' }}</div>
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
          <div class="print-footer" v-if="(currentPrescription.items || []).length">
            <p>剂数: {{ currentPrescription.doses }}剂</p>
            <p>煎法: {{ currentPrescription.preparation_method }}</p>
            <p v-if="currentPrescription.administration">服法: {{ currentPrescription.administration }}</p>
          </div>
          <template v-if="(currentPrescription.acupoints || []).length || currentPrescription.acupoint_formula_name || currentPrescription.acupoint_technique || currentPrescription.treatment_frequency || currentPrescription.treatment_days">
            <div class="print-formula-name">🪡 针灸方</div>
            <div v-if="currentPrescription.acupoint_formula_name || currentPrescription.acupoint_technique || currentPrescription.treatment_frequency || currentPrescription.treatment_days" class="print-acu-meta">
              <span v-if="currentPrescription.acupoint_formula_name">方案: {{ currentPrescription.acupoint_formula_name }}</span>
              <span v-if="currentPrescription.acupoint_technique"> · 针法: {{ currentPrescription.acupoint_technique }}</span>
              <span v-if="currentPrescription.treatment_frequency"> · 频次: {{ currentPrescription.treatment_frequency }}</span>
              <span v-if="currentPrescription.treatment_days"> · 疗程: {{ currentPrescription.treatment_days }}天</span>
            </div>
            <table v-if="(currentPrescription.acupoints || []).length" class="print-herb-table">
              <thead>
                <tr><th>穴位</th><th>针法</th><th>留针</th><th>备注</th></tr>
              </thead>
              <tbody>
                <tr v-for="a in (currentPrescription.acupoints || [])" :key="a.id">
                  <td>{{ a.acupoint_name }}</td>
                  <td>{{ a.technique || '' }}</td>
                  <td>{{ a.retention ? a.retention + ' 分钟' : '' }}</td>
                  <td>{{ a.note || '' }}</td>
                </tr>
              </tbody>
            </table>
          </template>
          <div class="print-footer">
            <p v-if="currentPrescription.doctor_notes">医嘱: {{ currentPrescription.doctor_notes }}</p>
            <p v-if="doctorName" class="print-doctor">医师: {{ doctorName }}</p>
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
import { ref, computed, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, Star } from '@element-plus/icons-vue'
import { useRouter } from 'vue-router'
import api from '@/utils/api'
import { useAuthStore } from '@/store/auth'

// 游客只读：隐藏所有写操作
const auth = useAuthStore()
const editable = computed(() => !!auth.user?.is_admin)

const router = useRouter()
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

async function loadPrescriptions() {
  try {
    const params: any = { limit: 100 }
    if (statusFilter.value) params.status = statusFilter.value
    if (patientFilter.value) params.patient_id = patientFilter.value
    prescriptions.value = (await api.get('/prescriptions', { params })) as any
  } catch {}
}

async function loadPatients() {
  patientsLoading.value = true
  try {
    const res = await api.get('/patients', { params: { page_size: 100 } }) as any
    patients.value = res.items || res || []
  } catch {}
  patientsLoading.value = false
}

async function searchPatients(query: string) {
  if (!query.trim()) { loadPatients(); return }
  patientsLoading.value = true
  try {
    const res = await api.get('/patients', { params: { search: query, page_size: 50 } }) as any
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
      body { font-family: 'SimSun', serif; margin: 40px; }
      h2 { text-align: center; margin-bottom: 20px; }
      .print-clinic { text-align: center; font-size: 16px; font-weight: bold; margin-bottom: 4px; }
      .print-info { display: flex; justify-content: space-between; margin-bottom: 10px; font-size: 14px; }
      .print-formula-name { font-size: 18px; font-weight: bold; margin: 10px 0; text-align: center; }
      table { width: 100%; border-collapse: collapse; margin: 10px 0; }
      th, td { border: 1px solid #333; padding: 6px 10px; text-align: center; font-size: 14px; }
      th { background: #f5f0eb; }
      .print-footer { margin-top: 16px; font-size: 14px; line-height: 1.8; }
      .print-doctor { text-align: right; margin-top: 12px; font-weight: bold; }
    </style></head><body>${content.innerHTML}</body></html>
  `)
  win.document.close()
  win.print()
}

onMounted(async () => {
  try {
    const res = await api.get('/config') as any
    clinicName.value = res.clinic_name || ''
    doctorName.value = res.doctor_name || ''
  } catch {}
  loadPatients()
  loadPrescriptions()
})
</script>

<style scoped lang="scss">
.prescription-list {
  .herb-tags {
    display: flex;
    flex-wrap: wrap;
    gap: 2px;
  }

  .acu-title {
    font-weight: 600;
    color: #2e7d32;
    margin-bottom: 2px;
  }

  .acu-tags {
    display: flex;
    flex-wrap: wrap;
    gap: 2px;
  }

  .acu-meta {
    font-size: 12px;
    color: #909399;
    margin-top: 2px;
  }
}

.prescription-print {
  font-family: 'SimSun', serif;
  padding: 20px;

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

  .print-formula-name {
    font-size: 18px;
    font-weight: bold;
    text-align: center;
    margin: 12px 0;
  }

  .print-acu-meta {
    font-size: 13px;
    text-align: center;
    color: #333;
    margin: 4px 0 8px;
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
</style>