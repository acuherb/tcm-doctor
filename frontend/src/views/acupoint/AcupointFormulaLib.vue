<template>
  <div class="acupoint-formula-lib">
    <el-card shadow="hover">
      <template #header>
        <div style="display:flex;justify-content:space-between;align-items:center;">
          <span>🪡 针灸方库</span>
          <div>
            <el-button v-if="editable" type="primary" size="small" @click="openCreate">＋ 新增针方</el-button>
            <el-button v-if="editable" size="small" @click="importFileRef?.click()">📥 导入JSON</el-button>
            <el-button size="small" @click="exportFormulas">📤 导出JSON</el-button>
            <input ref="importFileRef" type="file" accept=".json,application/json"
              style="display:none" @change="onImportFile" />
          </div>
        </div>
      </template>

      <el-form :inline="true" @submit.prevent="loadFormulas">
        <el-form-item>
          <el-input v-model="searchText" placeholder="搜索方名/功效" clearable @clear="loadFormulas" style="width:220px">
            <template #prefix><el-icon><Search /></el-icon></template>
          </el-input>
        </el-form-item>
        <el-form-item>
          <el-select v-model="sourceFilter" placeholder="出处筛选" clearable @change="loadFormulas" style="width:160px">
            <el-option v-for="s in sources" :key="s" :label="s" :value="s" />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="loadFormulas">查询</el-button>
        </el-form-item>
      </el-form>

      <el-row :gutter="16">
        <el-col :span="8" v-for="formula in formulas" :key="formula.id">
          <el-card shadow="hover" class="formula-card" @click="viewFormula(formula)">
            <div class="formula-name">{{ formula.name }}</div>
            <div class="formula-source" v-if="formula.source">
              <el-tag size="small" type="info">{{ formula.source }}</el-tag>
            </div>
            <div class="formula-meta" v-if="formula.technique || formula.treatment_frequency || formula.treatment_days">
              <el-tag v-if="formula.technique" size="small" type="success">{{ formula.technique }}</el-tag>
              <el-tag v-if="formula.treatment_frequency" size="small">{{ formula.treatment_frequency }}</el-tag>
              <el-tag v-if="formula.treatment_days" size="small">{{ formula.treatment_days }}天</el-tag>
            </div>
            <div class="formula-efficacy" v-if="formula.efficacy">{{ formula.efficacy }}</div>
            <div class="formula-composition" v-if="formula.composition?.acupoints">
              <span v-for="(a, idx) in formula.composition.acupoints" :key="idx" class="acu-chip">
                {{ a.acupoint_name }}
              </span>
            </div>
          </el-card>
        </el-col>
      </el-row>
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
        <el-table v-if="(currentFormula.composition?.acupoints || []).length" :data="currentFormula.composition.acupoints" stripe size="small">
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
import { Search } from '@element-plus/icons-vue'
import { useRouter } from 'vue-router'
import api from '@/utils/api'
import { useAuthStore } from '@/store/auth'

// 游客只读：隐藏所有写操作
const auth = useAuthStore()
const editable = computed(() => !!auth.user?.is_admin)
const router = useRouter()
const formulas = ref<any[]>([])
const searchText = ref('')
const sourceFilter = ref('')
const detailVisible = ref(false)
const currentFormula = ref<any>(null)

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
    const data: any = await api.get('/acupoint-formulas/export')
    const list = Array.isArray(data) ? data : (data as any)?.data || []
    if (!list.length) {
      ElMessage.warning('当前针灸方库为空')
      return
    }
    const blob = new Blob([JSON.stringify(list, null, 2)], { type: 'application/json' })
    const a = document.createElement('a')
    a.href = URL.createObjectURL(blob)
    a.download = `针灸方库_${new Date().toISOString().slice(0, 10)}.json`
    a.click()
    URL.revokeObjectURL(a.href)
    ElMessage.success(`已导出 ${list.length} 首针灸方`)
  } catch (e: any) {
    ElMessage.error('导出失败')
  }
}

async function onImportFile(e: Event) {
  const input = e.target as HTMLInputElement
  const file = input.files?.[0]
  input.value = ''
  if (!file) return
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
    const res: any = await api.post('/acupoint-formulas/import', payload)
    ElMessage.success(`导入完成：新增 ${res.created}，更新 ${res.updated}`)
    await loadFormulas()
  } catch (e: any) {
    ElMessage.error('导入失败：' + (e?.message || '请检查JSON格式'))
  }
}

const sources = computed(() => {
  const set = new Set(formulas.value.map((f: any) => f.source).filter(Boolean))
  return Array.from(set)
})

async function loadFormulas() {
  try {
    const params: any = {}
    if (searchText.value) params.search = searchText.value
    if (sourceFilter.value) params.source = sourceFilter.value
    formulas.value = (await api.get('/acupoint-formulas', { params })) as any
  } catch {}
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
  .formula-card {
    margin-bottom: 16px;
    cursor: pointer;
    transition: all 0.2s;

    &:hover {
      transform: translateY(-2px);
      box-shadow: 0 4px 12px rgba(46, 125, 50, 0.18);
    }

    .formula-name {
      font-size: 16px;
      font-weight: 700;
      color: #2e7d32;
      margin-bottom: 6px;
    }

    .formula-source {
      margin-bottom: 6px;
    }

    .formula-meta {
      display: flex;
      flex-wrap: wrap;
      gap: 4px;
      margin-bottom: 6px;
    }

    .formula-efficacy {
      font-size: 13px;
      color: #666;
      margin-bottom: 8px;
    }

    .formula-composition {
      .acu-chip {
        display: inline-block;
        padding: 2px 6px;
        background: #eef7ee;
        border-radius: 4px;
        font-size: 12px;
        margin: 2px;
        color: #2e7d32;
      }
    }
  }
}

.acu-row {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}
</style>
