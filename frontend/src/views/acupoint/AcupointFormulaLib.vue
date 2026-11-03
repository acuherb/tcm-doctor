<template>
  <div class="acupoint-formula-lib">
    <el-card shadow="hover" class="main-card">
      <template #header>
        <div class="card-head-bar">
          <div class="card-head-title">
            <span class="head-icon">🪡</span>
            <span class="head-text">针灸方库</span>
            <el-tag v-if="formulas.length > 0" size="small" type="info" effect="plain" round class="head-count">
              {{ formulas.length }} 首
            </el-tag>
          </div>
          <div v-if="editable" class="card-actions">
            <el-button type="primary" @click="openCreate">
              <el-icon><Plus /></el-icon>新增针方
            </el-button>
            <el-divider direction="vertical" />
            <el-button :loading="importing" @click="importFileRef?.click()">
              <el-icon><Upload /></el-icon>导入
            </el-button>
            <el-button @click="exportFormulas">
              <el-icon><Download /></el-icon>导出
            </el-button>
            <input ref="importFileRef" type="file" accept=".json,application/json"
              style="display:none" @change="onImportFile" />
          </div>
        </div>
      </template>

      <!-- 筛选栏 -->
      <div class="filter-bar">
        <el-input v-model="searchText" placeholder="搜索方名 / 功效" clearable class="search-input"
          @clear="loadFormulas" @keyup.enter="loadFormulas">
          <template #prefix><el-icon><Search /></el-icon></template>
        </el-input>
        <el-select v-model="sourceFilter" placeholder="全部出处" clearable class="source-select" @change="loadFormulas">
          <el-option v-for="s in sources" :key="s" :label="s" :value="s" />
        </el-select>
        <el-button type="primary" @click="loadFormulas">查询</el-button>
        <el-button v-if="searchText || sourceFilter" text class="reset-btn" @click="resetFilter">重置</el-button>
      </div>

      <div v-loading="loading" class="formula-grid-wrap">
        <el-row :gutter="14">
          <el-col :xs="24" :sm="12" :md="8" :lg="8" :xl="6" v-for="formula in formulas" :key="formula.id">
            <el-card shadow="never" class="formula-card" @click="viewFormula(formula)">
              <div class="formula-head">
                <div class="formula-name">{{ formula.name }}</div>
                <el-tag v-if="formula.source" size="small" type="info" effect="light" round class="formula-source">
                  {{ formula.source }}
                </el-tag>
              </div>

              <div class="formula-meta" v-if="formula.technique || formula.treatment_frequency || formula.treatment_days">
                <el-tag v-if="formula.technique" size="small" type="success" effect="light" round>
                  {{ formula.technique }}
                </el-tag>
                <el-tag v-if="formula.treatment_frequency" size="small" effect="plain" round>
                  {{ formula.treatment_frequency }}
                </el-tag>
                <el-tag v-if="formula.treatment_days" size="small" effect="plain" round>
                  {{ formula.treatment_days }} 天
                </el-tag>
              </div>

              <div class="formula-efficacy" v-if="formula.efficacy">{{ formula.efficacy }}</div>

              <div class="formula-composition" v-if="formula.composition?.acupoints?.length">
                <span class="acu-label">配穴</span>
                <span v-for="(a, idx) in formula.composition.acupoints" :key="idx" class="acu-chip">
                  {{ a.acupoint_name }}
                </span>
              </div>
              <div class="formula-composition is-empty" v-else>
                <span class="acu-label">配穴</span>
                <span class="acu-none">暂无配穴</span>
              </div>
            </el-card>
          </el-col>
        </el-row>

        <el-empty v-if="!formulas.length" :image-size="80">
          <template #description>
            <span>{{ searchText || sourceFilter ? '没有匹配的针灸方，试试调整筛选条件' : '针灸方库为空' }}</span>
          </template>
        </el-empty>
      </div>
    </el-card>

    <!-- 针灸方详情 -->
    <el-dialog v-model="detailVisible" :title="currentFormula?.name || '针灸方详情'" width="640px" destroy-on-close>
      <template v-if="currentFormula">
        <el-descriptions :column="2" border>
          <el-descriptions-item label="方名">{{ currentFormula.name }}</el-descriptions-item>
          <el-descriptions-item label="出处">{{ currentFormula.source || '-' }}</el-descriptions-item>
          <el-descriptions-item label="针法" v-if="currentFormula.technique">{{ currentFormula.technique }}</el-descriptions-item>
          <el-descriptions-item label="操作频次" v-if="currentFormula.treatment_frequency">{{ currentFormula.treatment_frequency }}</el-descriptions-item>
          <el-descriptions-item label="疗程天数" v-if="currentFormula.treatment_days">{{ currentFormula.treatment_days }} 天</el-descriptions-item>
          <el-descriptions-item label="功效" :span="2">{{ currentFormula.efficacy || '-' }}</el-descriptions-item>
          <el-descriptions-item label="主治" :span="2">{{ currentFormula.indications || '-' }}</el-descriptions-item>
          <el-descriptions-item label="操作要点" :span="2">{{ currentFormula.usage || '-' }}</el-descriptions-item>
        </el-descriptions>

        <el-divider content-position="left">配穴组成</el-divider>
        <el-table v-if="(currentFormula.composition?.acupoints || []).length" :data="currentFormula.composition.acupoints" class="tcm-table" size="small">
          <el-table-column type="index" label="#" width="50" />
          <el-table-column prop="acupoint_name" label="穴位" width="120" />
          <el-table-column prop="technique" label="针法" width="120">
            <template #default="{ row }">{{ row.technique || '-' }}</template>
          </el-table-column>
          <el-table-column prop="retention" label="留针" width="90">
            <template #default="{ row }">{{ row.retention ? row.retention : '-' }}</template>
          </el-table-column>
          <el-table-column prop="note" label="备注" show-overflow-tooltip>
            <template #default="{ row }">{{ row.note || '-' }}</template>
          </el-table-column>
        </el-table>
        <el-empty v-else description="暂无配穴明细" :image-size="50" />

        <div style="margin-top:16px;text-align:right;">
          <el-button v-if="editable" type="danger" plain @click="removeFormula(currentFormula)">🗑 删除</el-button>
          <el-button v-if="editable" @click="openEdit(currentFormula)">✏️ 编辑</el-button>
          <el-button type="primary" @click="useInPrescription(currentFormula)">
            引入到处方编辑器
          </el-button>
        </div>
      </template>
    </el-dialog>

    <!-- 新增/编辑针灸方 -->
    <el-dialog v-model="editVisible" :title="editId ? '编辑针灸方' : '新增针灸方'" width="760px" destroy-on-close>
      <el-form :model="editForm" label-width="90px">
        <el-form-item label="方名" required>
          <el-input v-model="editForm.name" placeholder="如：安神定志针方" />
        </el-form-item>
        <el-form-item label="出处">
          <el-input v-model="editForm.source" placeholder="如：倪海厦·针灸 / 通用" />
        </el-form-item>
        <el-row :gutter="12">
          <el-col :span="8">
            <el-form-item label="默认针法">
              <el-input v-model="editForm.technique" placeholder="如：平补平泻" />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="操作频次">
              <el-select v-model="editForm.treatment_frequency" placeholder="选择频次" clearable filterable allow-create style="width:100%">
                <el-option v-for="f in frequencies" :key="f" :label="f" :value="f" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="疗程天数">
              <el-input-number v-model="editForm.treatment_days" :min="1" :max="60" style="width:100%" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item label="功效">
          <el-input v-model="editForm.efficacy" placeholder="如：安神定志，交通心肾" />
        </el-form-item>
        <el-form-item label="主治">
          <el-input type="textarea" :rows="2" v-model="editForm.indications" />
        </el-form-item>
        <el-form-item label="操作要点">
          <el-input type="textarea" :rows="2" v-model="editForm.usage" placeholder="留针时长、灸法、注意事项等" />
        </el-form-item>

        <el-divider content-position="left">配穴组成</el-divider>
        <el-form-item label-width="0">
          <div style="width:100%">
            <div v-for="(a, idx) in editForm.acupoints" :key="idx" class="acu-row">
              <el-input v-model="a.acupoint_name" placeholder="穴名" style="width:150px" />
              <el-input v-model="a.technique" placeholder="针法" style="width:120px" />
              <el-input v-model="a.retention" placeholder="留针(分钟)" style="width:110px" />
              <el-input-number v-model="a.sequence" :min="1" :max="30" placeholder="顺序" style="width:90px" />
              <el-input v-model="a.note" placeholder="备注" style="width:140px" />
              <el-button type="danger" link @click="editForm.acupoints.splice(idx, 1)">—</el-button>
            </div>
            <el-button type="warning" plain size="small" @click="editForm.acupoints.push({ acupoint_name: '', technique: '', retention: '', sequence: editForm.acupoints.length + 1, note: '' })">＋ 加一个配穴</el-button>
          </div>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="editVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="saveFormula">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Search, Plus, Upload, Download } from '@element-plus/icons-vue'
import { useRouter } from 'vue-router'
import api from '@/utils/api'
import type { AcupointFormula } from '@/types'
import { useAuthStore } from '@/store/auth'

// 游客只读：隐藏所有写操作
const auth = useAuthStore()
const editable = computed(() => auth.canWrite('acupoint-formulas'))
const router = useRouter()
const formulas = ref<any[]>([])
const searchText = ref('')
const sourceFilter = ref('')
const detailVisible = ref(false)
const currentFormula = ref<any>(null)
const loading = ref(false)
const importing = ref(false)

const frequencies = ['每日', '隔日', '每周', '隔周', '每三日']
const importFileRef = ref<HTMLInputElement | null>(null)
const editVisible = ref(false)
const editId = ref<number | null>(null)
const saving = ref(false)
const editForm = ref<any>(emptyForm())

function emptyForm() {
  return {
    name: '', source: '', technique: '', treatment_frequency: '', treatment_days: null as number | null,
    efficacy: '', indications: '', usage: '',
    acupoints: [],
  }
}

function openCreate() {
  editId.value = null
  editForm.value = emptyForm()
  editVisible.value = true
}

function openEdit(f: any) {
  editId.value = f.id
  editForm.value = {
    name: f.name || '',
    source: f.source || '',
    technique: f.technique || '',
    treatment_frequency: f.treatment_frequency || '',
    treatment_days: f.treatment_days ?? null,
    efficacy: f.efficacy || '',
    indications: f.indications || '',
    usage: f.usage || '',
    acupoints: (f.composition?.acupoints || []).map((a: any) => ({ ...a })),
  }
  editVisible.value = true
}

function buildPayload() {
  const acupoints = editForm.value.acupoints
    .filter((a: any) => a.acupoint_name && String(a.acupoint_name).trim())
    .map((a: any) => ({
      acupoint_name: a.acupoint_name.trim(),
      technique: a.technique || null,
      retention: a.retention || null,
      sequence: a.sequence || 1,
      note: a.note || null,
    }))
  return {
    name: editForm.value.name.trim(),
    source: editForm.value.source?.trim() || null,
    efficacy: editForm.value.efficacy?.trim() || null,
    indications: editForm.value.indications?.trim() || null,
    usage: editForm.value.usage?.trim() || null,
    technique: editForm.value.technique?.trim() || null,
    treatment_frequency: editForm.value.treatment_frequency || null,
    treatment_days: editForm.value.treatment_days ?? null,
    composition: { acupoints },
  }
}

async function saveFormula() {
  if (!editForm.value.name.trim()) {
    ElMessage.warning('请填写方名')
    return
  }
  saving.value = true
  try {
    const payload = buildPayload()
    if (editId.value) {
      await api.put(`/acupoint-formulas/${editId.value}`, payload)
      ElMessage.success('针灸方已更新')
    } else {
      await api.post('/acupoint-formulas', payload)
      ElMessage.success('针灸方已新增')
    }
    editVisible.value = false
    await loadFormulas()
  } catch (e: any) {
    ElMessage.error('保存失败：' + (e?.response?.data?.detail || e?.message || ''))
  }
  saving.value = false
}

async function removeFormula(f: any) {
  ElMessageBox.confirm(`确定删除针灸方「${f.name}」吗？该操作不可恢复。`, '删除确认', {
    type: 'warning',
  }).then(async () => {
    try {
      await api.delete(`/acupoint-formulas/${f.id}`)
      ElMessage.success('已删除')
      detailVisible.value = false
      await loadFormulas()
    } catch (e: any) {
      ElMessage.error('删除失败：' + (e?.response?.data?.detail || e?.message || ''))
    }
  }).catch(() => {})
}

async function exportFormulas() {
  try {
    const data: Record<string, unknown> = await api.get('/acupoint-formulas/export')
    const nl = Array.isArray(data) ? data : (data as Paginated<AcupointFormula>)?.data || []
    if (!nl.length) {
      ElMessage.warning('当前针灸方库为空')
      return
    }
    const blob = new Blob([JSON.stringify(nl, null, 2)], { type: 'application/json' })
    const a = document.createElement('a')
    a.href = URL.createObjectURL(blob)
    a.download = `针灸方库_${new Date().toISOString().slice(0, 10)}.json`
    a.click()
    URL.revokeObjectURL(a.href)
    ElMessage.success(`已导出 ${nl.length} 首针灸方`)
  } catch (e: any) {
    ElMessage.error('导出失败')
  }
}

async function onImportFile(e: Event) {
  const input = e.target as HTMLInputElement
  const file = input.files?.[0]
  input.value = ''
  if (!file) return
  importing.value = true
  try {
    const text = await file.text()
    let data = JSON.parse(text)
    if (!Array.isArray(data)) data = [data]
    const payload = data.map((it: any) => ({
      name: it.name,
      source: it.source || null,
      efficacy: it.efficacy || null,
      indications: it.indications || null,
      usage: it.usage || null,
      technique: it.technique || null,
      treatment_frequency: it.treatment_frequency || null,
      treatment_days: it.treatment_days ?? null,
      composition: it.composition || { acupoints: it.acupoints || [] },
    }))
    const res: { created?: number; updated?: number } = await api.post('/acupoint-formulas/import', payload)
    ElMessage.success(`导入完成：新增 ${res.created}，更新 ${res.updated}`)
    await loadFormulas()
  } catch (e: any) {
    ElMessage.error('导入失败：' + (e?.message || '请检查JSON格式'))
  } finally {
    importing.value = false
  }
}

const sources = computed(() => {
  const set = new Set(formulas.value.map((f: any) => f.source).filter(Boolean))
  return Array.from(set)
})

async function loadFormulas() {
  loading.value = true
  try {
    const params: Record<string, unknown> = {}
    if (searchText.value) params.search = searchText.value
    if (sourceFilter.value) params.source = sourceFilter.value
    formulas.value = (await api.get<Paginated<AcupointFormula>>('/acupoint-formulas', { params }))
  } catch {
    formulas.value = []
  } finally {
    loading.value = false
  }
}

function resetFilter() {
  searchText.value = ''
  sourceFilter.value = ''
  loadFormulas()
}

function viewFormula(formula: any) {
  currentFormula.value = formula
  detailVisible.value = true
}

function useInPrescription(formula: any) {
  detailVisible.value = false
  // 跳转到处方编辑器，通过 router query 传递 acupoint_formula_id
  router.push({ path: '/prescriptions/new', query: { acupoint_formula_id: formula.id } })
}

onMounted(loadFormulas)
</script>

<style scoped lang="scss">
.acupoint-formula-lib {
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
  .card-actions {
    display: flex;
    align-items: center;
    gap: 8px;
    flex-wrap: wrap;
    .el-divider--vertical { margin: 0 2px; }
  }
  .filter-bar {
    display: flex;
    gap: 10px;
    align-items: center;
    margin-bottom: 16px;
    flex-wrap: wrap;
    .search-input { width: 240px; }
    .source-select { width: 170px; }
    .reset-btn { margin-left: -2px; }
  }
  .formula-grid-wrap { min-height: 120px; }
  .formula-card {
    margin-bottom: 14px;
    border: 1px solid #eee3d6;
    border-radius: 10px;
    cursor: pointer;
    transition: all .2s ease;

    &:hover {
      border-color: var(--tcm-accent);
      box-shadow: 0 4px 14px rgba(139, 94, 52, .1);
      transform: translateY(-2px);
    }

    :deep(.el-card__body) { padding: 14px 16px; }

    .formula-head {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 8px;
      margin-bottom: 10px;
    }

    .formula-name {
      font-size: 16px;
      font-weight: 700;
      color: #2c1810;
      line-height: 1.4;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }

    .formula-source { flex: none; max-width: 50%; }

    .formula-meta {
      display: flex;
      flex-wrap: wrap;
      gap: 6px;
      margin-bottom: 8px;
    }

    .formula-efficacy {
      font-size: 13px;
      line-height: 1.7;
      color: #6b5644;
      margin-bottom: 10px;
      display: -webkit-box;
      -webkit-line-clamp: 2;
      -webkit-box-orient: vertical;
      overflow: hidden;
    }

    .formula-composition {
      display: flex;
      flex-wrap: wrap;
      align-items: center;
      gap: 5px;
      padding-top: 10px;
      border-top: 1px dashed #efe5d9;

      .acu-label { font-size: 12px; color: #a39484; margin-right: 2px; }

      .acu-chip {
        display: inline-block;
        padding: 1px 8px;
        background: #faf6f1;
        border: 1px solid #eddfd0;
        border-radius: 10px;
        font-size: 12px;
        line-height: 18px;
        color: #8b5e34;
      }

      &.is-empty .acu-none { font-size: 12px; color: #bdb0a2; }
    }
  }
}

.acu-row {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}

@media (max-width: 767px) {
  .acupoint-formula-lib {
    .card-head-bar { align-items: stretch; }
    .card-actions { justify-content: flex-start; }

    .filter-bar {
      flex-direction: column;
      align-items: stretch;
      gap: 8px;

      .search-input,
      .source-select { width: 100%; }
      .reset-btn { margin-left: 0; }
    }

    .formula-card { margin-bottom: 10px; }
  }

  :deep(.el-form-item__label) {
    float: none;
    display: block;
    text-align: left;
    width: auto !important;
  }
  .acu-row { flex-wrap: wrap; }
  .acu-row :deep(.el-input),
  .acu-row :deep(.el-input-number) { width: 100% !important; }
}
</style>