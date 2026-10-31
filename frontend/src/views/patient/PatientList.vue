<template>
  <div class="patient-list">
    <el-card shadow="hover">
      <template #header>
        <div class="card-header">
          <span>👥 患者管理</span>
          <el-button v-if="editable" type="primary" @click="showAddDialog = true">
            <el-icon><Plus /></el-icon> 新增患者
          </el-button>
        </div>
      </template>

      <!-- 搜索/筛选栏 -->
      <el-form :inline="true" @submit.prevent="onSearch">
        <el-form-item label="搜索">
          <el-input v-model="searchText" placeholder="姓名/电话" clearable @clear="onSearch" style="width: 200px;">
            <template #prefix><el-icon><Search /></el-icon></template>
          </el-input>
        </el-form-item>
        <el-form-item label="体质">
          <el-select v-model="filterConstitution" placeholder="全部" clearable style="width: 140px;" @change="onFilterChange">
            <el-option v-for="c in constitutionOptions" :key="c" :label="c" :value="c" />
          </el-select>
        </el-form-item>
        <el-form-item label="标签">
          <el-select v-model="filterTag" placeholder="全部" clearable style="width: 150px;" @change="onFilterChange">
            <el-option v-for="t in tagOptions" :key="t.name" :label="t.name" :value="t.name" />
          </el-select>
        </el-form-item>
        <el-form-item label="过敏">
          <el-select v-model="filterAllergy" placeholder="全部" clearable style="width: 100px;" @change="onFilterChange">
            <el-option label="有" value="yes" /><el-option label="无" value="no" />
          </el-select>
        </el-form-item>
        <el-form-item label="最近改善">
          <el-select v-model="filterImprovement" placeholder="全部" clearable style="width: 130px;" @change="onFilterChange">
            <el-option v-for="s in IMPROVE_LIST" :key="s" :label="s" :value="s" />
          </el-select>
        </el-form-item>
        <el-form-item label="排序">
          <el-select v-model="sortOrder" placeholder="默认" clearable style="width: 130px;" @change="onFilterChange">
            <el-option label="最近就诊↓" value="desc" /><el-option label="最近就诊↑" value="asc" />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="onSearch">查询</el-button>
          <el-button @click="onReset">重置</el-button>
        </el-form-item>
      </el-form>

      <!-- 患者表格 -->
      <el-table v-if="!isMobile" :data="patients" stripe style="width: 100%" @row-click="goDetail">
        <el-table-column prop="id" label="ID" width="60" />
        <el-table-column prop="name" label="姓名" width="100" />
        <el-table-column prop="gender" label="性别" width="60" />
        <el-table-column label="年龄" width="60">
          <template #default="{ row }">{{ ageOf(row) }}</template>
        </el-table-column>
        <el-table-column prop="phone" label="电话" width="130" />
        <el-table-column prop="constitution_type" label="体质" width="100">
          <template #default="{ row }">
            <el-tag v-if="row.constitution_type" size="small" type="warning">{{ row.constitution_type }}</el-tag>
            <span v-else class="text-muted">未评估</span>
          </template>
        </el-table-column>
        <el-table-column prop="notes" label="备注" show-overflow-tooltip />
        <el-table-column label="最近就诊" width="150">
          <template #default="{ row }">
            <template v-if="row.last_visit_date">{{ row.last_visit_date }}
              <el-tag v-if="row.days_since_visit != null" size="small" :type="row.days_since_visit > 30 ? 'danger' : 'info'">{{ row.days_since_visit }}天前</el-tag>
            </template>
            <span v-else class="text-muted">—</span>
          </template>
        </el-table-column>
        <el-table-column label="最近改善" width="100">
          <template #default="{ row }">
            <el-tag v-if="row.last_improvement" size="small" :type="improveTag(row.last_improvement)">{{ row.last_improvement }}</el-tag>
            <span v-else class="text-muted">—</span>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="90" align="center">
          <template #default="{ row }">
            <el-tag size="small" :type="statusTag(row.active_status)">{{ row.active_status || '—' }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="风险" width="150">
          <template #default="{ row }">
            <el-tag v-if="row.allergy_history" type="danger" size="small" effect="dark">过敏</el-tag>
            <el-tag v-if="(row.tags || []).includes('不遵医嘱')" type="warning" size="small" effect="dark">不遵医嘱</el-tag>
            <span v-if="!row.allergy_history && !((row.tags || []).includes('不遵医嘱'))" class="text-muted">—</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="180" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" @click.stop="goDetail(row)">详情</el-button>
            <el-button v-if="editable" link type="danger" @click.stop="deletePatient(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>

      <!-- 移动端卡片视图 -->
      <div v-if="isMobile" class="pt-cards">
        <div v-for="row in patients" :key="row.id" class="pt-card" @click="goDetail(row)">
          <div class="card-head">
            <span class="card-name">{{ row.name }}</span>
            <div class="card-tags">
              <el-tag size="small">{{ row.gender || '-' }}</el-tag>
              <el-tag v-if="row.constitution_type" size="small" type="warning">{{ row.constitution_type }}</el-tag>
            </div>
          </div>
          <div class="card-row" v-if="row.phone">
            <span class="label">电话</span><span class="value">{{ row.phone }}</span>
          </div>
          <div class="card-row" v-if="row.birth_date">
            <span class="label">出生</span><span class="value">{{ row.birth_date }}（{{ ageOf(row) }}岁）</span>
          </div>
          <div class="card-row" v-if="row.height != null">
            <span class="label">身高</span><span class="value">{{ row.height }}cm</span>
          </div>
          <div class="card-row" v-if="row.weight != null">
            <span class="label">体重</span><span class="value">{{ row.weight }}kg</span>
          </div>
          <div class="card-row" v-if="bodyOf(row)">
            <span class="label">身型</span>
            <span class="value">
              <el-tag size="small" :style="tagStyle(bodyOf(row)!.color)">{{ bodyOf(row)!.label }}</el-tag>
            </span>
          </div>
          <div class="card-row">
            <span class="label">体质</span>
            <span class="value" v-if="row.constitution_type">{{ row.constitution_type }}</span>
            <span class="value text-muted" v-else>未评估</span>
          </div>
          <div class="card-row" v-if="row.notes">
            <span class="label">备注</span><span class="value">{{ row.notes }}</span>
          </div>
          <div class="card-row">
            <span class="label">最近就诊</span>
            <span class="value" v-if="row.last_visit_date">{{ row.last_visit_date }}<template v-if="row.days_since_visit != null">（{{ row.days_since_visit }}天前）</template></span>
            <span class="value text-muted" v-else>—</span>
          </div>
          <div class="card-row">
            <span class="label">状态</span>
            <span class="value">
              <el-tag size="small" :type="statusTag(row.active_status)">{{ row.active_status || '—' }}</el-tag>
              <el-tag v-if="row.allergy_history" type="danger" size="small" effect="dark" style="margin-left:4px;">过敏</el-tag>
            </span>
          </div>
          <div class="card-actions">
            <el-button link type="primary" size="small" @click.stop="goDetail(row)">详情</el-button>
            <el-button v-if="editable" link type="danger" size="small" @click.stop="deletePatient(row)">删除</el-button>
          </div>
        </div>
        <el-empty v-if="!patients.length" description="暂无患者" />
      </div>

      <!-- 分页 -->
      <div class="pagination-wrapper">
        <el-pagination
          v-model:current-page="page"
          :page-size="pageSize"
          :total="total"
          layout="total, prev, pager, next"
          @current-change="loadPatients"
        />
      </div>
    </el-card>

    <!-- 新增患者对话框 -->
    <el-dialog v-model="showAddDialog" title="新增患者" width="560px" destroy-on-close class="patient-form-dialog">
      <el-form :model="newPatient" label-position="top">
        <el-row :gutter="12">
          <el-col :xs="24" :sm="12">
            <el-form-item label="姓名" required>
              <el-input v-model="newPatient.name" placeholder="请输入姓名" />
            </el-form-item>
          </el-col>
          <el-col :xs="24" :sm="12">
            <el-form-item label="性别">
              <el-radio-group v-model="newPatient.gender">
                <el-radio value="男">男</el-radio>
                <el-radio value="女">女</el-radio>
              </el-radio-group>
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="12">
          <el-col :xs="24" :sm="12">
            <el-form-item label="出生日期">
              <el-date-picker v-model="newPatient.birth_date" type="date" value-format="YYYY-MM-DD" placeholder="选择日期" style="width:100%" />
            </el-form-item>
          </el-col>
          <el-col :xs="24" :sm="12">
            <el-form-item label="年龄">
              <el-input :model-value="calcAge(newPatient.birth_date) ?? ''" disabled placeholder="自动计算" style="width:100%">
                <template #append>岁</template>
              </el-input>
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="12">
          <el-col :xs="24" :sm="12">
            <el-form-item label="身高(cm)">
              <el-input v-model.number="newPatient.height" type="number" placeholder="如 170" />
            </el-form-item>
          </el-col>
          <el-col :xs="24" :sm="12">
            <el-form-item label="体重(kg)">
              <el-input v-model.number="newPatient.weight" type="number" placeholder="如 65" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="12">
          <el-col :xs="24" :sm="12"><el-form-item label="电话"><el-input v-model="newPatient.phone" placeholder="请输入电话" /></el-form-item></el-col>
          <el-col :xs="24" :sm="12"><el-form-item label="身份证号"><el-input v-model="newPatient.id_card" placeholder="请输入身份证号" /></el-form-item></el-col>
        </el-row>
        <el-form-item label="地址">
          <el-input v-model="newPatient.address" placeholder="请输入地址" />
        </el-form-item>
        <el-form-item label="过敏史">
          <el-input v-model="newPatient.allergy_history" type="textarea" :rows="2" placeholder="如：青霉素过敏" />
        </el-form-item>
        <el-form-item label="既往史">
          <el-input v-model="newPatient.medical_history" type="textarea" :rows="2" placeholder="重要疾病史" />
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="newPatient.notes" type="textarea" :rows="2" />
        </el-form-item>
        <el-form-item label="标签">
          <div class="tag-picker">
            <el-tag
              v-for="t in tagOptions"
              :key="t.id"
              class="tag-option"
              :class="{ 'tag-selected': (newPatient.tags || []).includes(t.name) }"
              :style="tagChipStyle(t)"
              effect="plain"
              @click="toggleTag(t.name)"
            >{{ t.name }}</el-tag>
            <span v-if="!tagOptions.length" class="text-muted">暂无标签，请到『数据字典 → 患者标签』添加</span>
          </div>
          <div style="font-size:12px;color:#999;margin-top:4px;">点击标签切换选中（颜色由字典定义）；新增/停用请到字典页操作</div>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showAddDialog = false">取消</el-button>
        <el-button type="primary" @click="addPatient" :loading="submitting">确定</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onBeforeUnmount } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, Search } from '@element-plus/icons-vue'
import api from '@/utils/api'
import { useAuthStore } from '@/store/auth'
import { calcAge, calcBmi, bodyType } from '@/utils/health'

// 游客只读：隐藏所有写操作
const auth = useAuthStore()
const editable = computed(() => !!auth.user?.is_admin)

// ---- 移动端适配 ----
const isMobile = ref(false)
function updateViewport() {
  isMobile.value = window.innerWidth < 768
}
onMounted(updateViewport)
onBeforeUnmount(() => window.removeEventListener('resize', updateViewport))
onMounted(() => window.addEventListener('resize', updateViewport))

const router = useRouter()
const patients = ref<any[]>([])

function ageOf(row: any): string {
  const a = calcAge(row.birth_date)
  return a == null ? '-' : String(a)
}
function bodyOf(row: any): { label: string; color: string } | null {
  return bodyType(calcBmi(row.height, row.weight))
}
function tagStyle(color: string) {
  return { backgroundColor: color, borderColor: color, color: '#fff' }
}
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const searchText = ref('')
const showAddDialog = ref(false)
const submitting = ref(false)
// 字典中的患者标签（供新增表单选择 + 列表筛选）
const tagOptions = ref<any[]>([])

// 列表筛选条件
const filterConstitution = ref('')
const filterTag = ref('')
const filterAllergy = ref('') // '' / 'yes' / 'no'
const filterImprovement = ref('')
const sortOrder = ref('') // '' / 'desc' / 'asc'
const IMPROVE_LIST = ['明显好转', '好转', '稳定', '反复', '加重']
// 体质筛选选项：标准九种体质 + 数据集中实际出现的值
const BASE_CONSTITUTIONS = ['平和质', '气虚质', '阳虚质', '阴虚质', '痰湿质', '湿热质', '血瘀质', '气郁质', '特禀质']
const constitutionOptions = computed<string[]>(() => {
  const set = new Set(BASE_CONSTITUTIONS)
  for (const p of patients.value) if (p.constitution_type) set.add(p.constitution_type)
  return Array.from(set)
})
function improveTag(s: string): string {
  if (s === '明显好转' || s === '好转') return 'success'
  if (s === '稳定') return 'warning'
  return 'danger' // 反复 / 加重
}
function statusTag(s: string): string {
  if (s === '在治') return 'success'
  if (s === '停诊') return 'danger'
  if (s === '未复诊') return 'warning'
  return 'info' // 新诊
}

function onSearch() {
  page.value = 1
  loadPatients()
}
function onReset() {
  searchText.value = ''
  filterConstitution.value = ''
  filterTag.value = ''
  filterAllergy.value = ''
  filterImprovement.value = ''
  sortOrder.value = ''
  page.value = 1
  loadPatients()
}
function onFilterChange() {
  page.value = 1
  loadPatients()
}

const newPatient = ref({
  name: '',
  gender: '男',
  birth_date: '',
  phone: '',
  id_card: '',
  address: '',
  height: null as number | null,
  weight: null as number | null,
  allergy_history: '',
  medical_history: '',
  notes: '',
  tags: [] as string[],
})

async function loadPatients() {
  try {
    const params: any = { page: page.value, page_size: pageSize.value }
    if (searchText.value) params.search = searchText.value
    if (filterConstitution.value) params.constitution_type = filterConstitution.value
    if (filterTag.value) params.tag = filterTag.value
    if (filterAllergy.value === 'yes') params.has_allergy = true
    if (filterAllergy.value === 'no') params.has_allergy = false
    if (filterImprovement.value) params.improvement = filterImprovement.value
    if (sortOrder.value) {
      params.sort_by = 'last_visit_date'
      params.order = sortOrder.value
    }
    const res = await api.get('/patients', { params }) as any
    patients.value = res.items || []
    total.value = res.total || 0
  } catch {}
}

function goDetail(row: any) {
  router.push(`/patients/${row.id}`)
}

// 标签彩色点选：选中用字典 color 实心，未选中用描边
function toggleTag(name: string) {
  const cur = newPatient.value.tags || []
  newPatient.value.tags = cur.includes(name) ? cur.filter((x: string) => x !== name) : [...cur, name]
}
function tagChipStyle(t: any): Record<string, string> {
  const selected = (newPatient.value.tags || []).includes(t.name)
  const c = t.color || '#909399'
  return selected
    ? { backgroundColor: c, borderColor: c, color: '#fff' }
    : { color: c, borderColor: c, backgroundColor: '#fff' }
}

async function addPatient() {
  if (!newPatient.value.name.trim()) {
    ElMessage.warning('请输入患者姓名')
    return
  }
  submitting.value = true
  try {
    await api.post('/patients', newPatient.value)
    ElMessage.success('患者添加成功')
    showAddDialog.value = false
    newPatient.value = { name: '', gender: '男', birth_date: '', phone: '', id_card: '', address: '', height: null, weight: null, allergy_history: '', medical_history: '', notes: '', tags: [] }
    loadPatients()
  } catch {
    // 已被拦截器处理
  } finally {
    submitting.value = false
  }
}

async function deletePatient(row: any) {
  await ElMessageBox.confirm(`确定删除患者 "${row.name}" 吗？`, '确认删除', { type: 'warning' })
  try {
    await api.delete(`/patients/${row.id}`)
    ElMessage.success('删除成功')
    loadPatients()
  } catch {}
}

onMounted(async () => {
  loadPatients()
  try {
    tagOptions.value = (await api.get('/dictionaries', { params: { term_type: 'tag', is_active: true } })) as any
  } catch {}
})
</script>

<style scoped>
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.pagination-wrapper {
  display: flex;
  justify-content: flex-end;
  margin-top: 16px;
}
.text-muted {
  color: #c0c4cc;
  font-size: 13px;
}
.overdue { color: #f56c6c; font-weight: 600; }
.tag-picker { display: flex; flex-wrap: wrap; gap: 8px; }
.tag-option { cursor: pointer; user-select: none; transition: all .15s; }
.tag-option:hover { opacity: .85; }
.tag-selected { font-weight: 600; }

/* ---- 移动端卡片视图 ---- */
.pt-cards {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.pt-card {
  background: #fff;
  border: 1px solid #e8e0d8;
  border-radius: 10px;
  padding: 12px 14px;
  box-shadow: 0 1px 3px rgba(0,0,0,0.05);
  cursor: pointer;
}
.pt-card .card-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 8px;
}
.pt-card .card-name {
  font-size: 17px;
  font-weight: 600;
  color: #2C1810;
}
.pt-card .card-tags {
  display: flex;
  gap: 4px;
}
.pt-card .card-row {
  display: flex;
  align-items: flex-start;
  font-size: 14px;
  line-height: 1.5;
  margin-top: 4px;
}
.pt-card .card-row .label {
  flex-shrink: 0;
  width: 60px;
  color: #8a7563;
  white-space: nowrap;
}
.pt-card .card-row .value {
  flex: 1;
  color: #333;
  word-break: break-all;
}
.pt-card .card-actions {
  display: flex;
  justify-content: flex-end;
  gap: 4px;
  margin-top: 8px;
  padding-top: 8px;
  border-top: 1px dashed #eee;
}

/* ---- 移动端：搜索改为全宽 ---- */
@media (max-width: 767px) {
  :deep(.el-form--inline .el-form-item) {
    display: block;
    margin-right: 0;
    margin-bottom: 8px;
  }
  :deep(.el-form--inline .el-form-item__content) {
    display: block;
    max-width: 100%;
  }
  :deep(.el-form--inline .el-input) {
    width: 100% !important;
  }
  :deep(.el-form--inline .el-select) {
    width: 100% !important;
  }
  .pagination-wrapper {
    justify-content: center;
  }
  .patient-form-dialog {
    width: 94% !important;
    border-radius: 14px;
    margin-top: 6vh !important;
  }
}
/* 患者表单弹窗：顶部对齐，内容区内滚动，保证一屏内显示全 */
.patient-form-dialog { margin-top: 4vh !important; }
.patient-form-dialog :deep(.el-dialog__body) { max-height: 82vh; overflow-y: auto; }
</style>