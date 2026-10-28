<template>
  <div class="classic-formula-lib">
    <el-card shadow="hover">
      <template #header>
        <div style="display:flex;justify-content:space-between;align-items:center;">
          <span>📖 中药方库</span>
          <div>
            <el-button v-if="editable" type="primary" size="small" @click="openCreate">＋ 新增方剂</el-button>
            <el-button v-if="editable" size="small" @click="importFileRef?.click()">📥 导入JSON</el-button>
            <el-button v-if="editable" size="small" @click="exportFormulas">📤 导出JSON</el-button>
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
          <el-select v-model="sourceFilter" placeholder="出处筛选" clearable @change="loadFormulas" style="width:140px">
            <el-option v-for="s in sources" :key="s" :label="s" :value="s" />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="loadFormulas">查询</el-button>
        </el-form-item>
      </el-form>

      <el-row :gutter="16">
        <el-col :span="8" :xs="24" v-for="formula in formulas" :key="formula.id">
          <el-card shadow="hover" class="formula-card" @click="viewFormula(formula)">
            <div class="formula-name">{{ formula.name }}</div>
            <div class="formula-source" v-if="formula.source">
              <el-tag size="small" type="info">{{ formula.source }}</el-tag>
              <el-tag v-if="formula.composition?.meridian" size="small" type="success" style="margin-left:4px">{{ formula.composition.meridian }}</el-tag>
            </div>
            <div class="formula-efficacy" v-if="formula.efficacy">{{ formula.efficacy }}</div>
            <div class="formula-composition" v-if="formula.composition?.herbs">
              <span v-for="(h, idx) in formula.composition.herbs" :key="idx" class="herb-chip">
                {{ h.herb }}{{ h.dose ? h.dose + 'g' : '' }}
              </span>
            </div>
          </el-card>
        </el-col>
      </el-row>
    </el-card>

    <!-- 方剂详情 -->
    <el-dialog v-model="detailVisible" :title="currentFormula?.name || '方剂详情'" width="620px" destroy-on-close>
      <template v-if="currentFormula">
        <el-descriptions :column="2" border>
          <el-descriptions-item label="方名">{{ currentFormula.name }}</el-descriptions-item>
          <el-descriptions-item label="出处">{{ currentFormula.source || '-' }}</el-descriptions-item>
          <el-descriptions-item label="功效" :span="2">{{ currentFormula.efficacy || '-' }}</el-descriptions-item>
          <el-descriptions-item label="主治" :span="2">{{ currentFormula.indications || '-' }}</el-descriptions-item>
          <el-descriptions-item label="用法" :span="2">{{ currentFormula.usage || '-' }}</el-descriptions-item>
        </el-descriptions>

        <el-divider content-position="left">组成</el-divider>
        <div class="formula-herbs" v-if="currentFormula.composition?.herbs">
          <el-table :data="currentFormula.composition.herbs" stripe size="small">
            <el-table-column prop="herb" label="药味" width="100" />
            <el-table-column prop="dose" label="剂量" width="80">
              <template #default="{ row }">{{ row.dose ? row.dose + 'g' : '-' }}</template>
            </el-table-column>
            <el-table-column prop="special_method" label="煎法" width="80">
              <template #default="{ row }">{{ row.special_method || '-' }}</template>
            </el-table-column>
            <el-table-column prop="note" label="备注" show-overflow-tooltip>
              <template #default="{ row }">{{ row.note || '-' }}</template>
            </el-table-column>
          </el-table>
        </div>

        <!-- 加减变化 -->
        <template v-if="currentFormula.modifications?.changes?.length">
          <el-divider content-position="left">加减变化</el-divider>
          <div class="formula-modifications">
            <div v-for="(mod, idx) in currentFormula.modifications.changes" :key="idx" class="mod-item">
              <div class="mod-condition">
                <el-tag size="small" type="warning">{{ mod.condition || `变化${idx + 1}` }}</el-tag>
              </div>
              <div class="mod-detail">
                <span v-if="mod.add" class="mod-add">+ {{ mod.add }}</span>
                <span v-if="mod.remove" class="mod-remove">- {{ mod.remove }}</span>
              </div>
            </div>
          </div>
        </template>

        <div style="margin-top:16px;text-align:right;">
          <el-button v-if="editable" type="danger" plain @click="removeFormula(currentFormula)">🗑 删除</el-button>
          <el-button v-if="editable" @click="openEdit(currentFormula)">✏️ 编辑</el-button>
          <el-button type="primary" @click="useInPrescription(currentFormula)">
            引入到处方编辑器
          </el-button>
        </div>
      </template>
    </el-dialog>

    <!-- 新增/编辑方剂 -->
    <el-dialog v-model="editVisible" :title="editId ? '编辑方剂' : '新增方剂'" width="720px" destroy-on-close>
      <el-form :model="editForm" label-width="80px">
        <el-form-item label="方名" required>
          <el-input v-model="editForm.name" placeholder="如：桂枝汤" />
        </el-form-item>
        <el-form-item label="出处">
          <el-input v-model="editForm.source" placeholder="如：伤寒论" />
        </el-form-item>
        <el-form-item label="六经归属">
          <el-select v-model="editForm.meridian" clearable placeholder="选择六经（可选）" style="width:220px">
            <el-option v-for="m in meridians" :key="m" :label="m" :value="m" />
          </el-select>
        </el-form-item>
        <el-form-item label="功效">
          <el-input v-model="editForm.efficacy" placeholder="如：解肌发表，调和营卫" />
        </el-form-item>
        <el-form-item label="主治">
          <el-input type="textarea" :rows="2" v-model="editForm.indications" />
        </el-form-item>
        <el-form-item label="用法">
          <el-input type="textarea" :rows="2" v-model="editForm.usage" placeholder="如：上五味，以水七升，微火煮取三升，去滓，适寒温服一升" />
        </el-form-item>

        <el-divider content-position="left">组成</el-divider>
        <el-form-item label-width="0">
          <div style="width:100%">
            <div v-for="(herb, idx) in editForm.herbs" :key="idx" class="herb-row">
              <el-input v-model="herb.herb" placeholder="药名" style="width:140px" />
              <el-input v-model.number="herb.dose" placeholder="剂量(g)" style="width:90px" />
              <el-input v-model="herb.special_method" placeholder="特殊煎法" style="width:110px" />
              <el-checkbox v-model="herb.is_king_herb">君</el-checkbox>
              <el-button type="danger" link @click="editForm.herbs.splice(idx, 1)">—</el-button>
            </div>
            <el-button type="warning" plain size="small" @click="editForm.herbs.push({ herb: '', dose: null, special_method: '', is_king_herb: false, note: '' })">＋ 加一味药</el-button>
          </div>
        </el-form-item>

        <el-divider content-position="left">加减变化（可选）</el-divider>
        <el-form-item label-width="0">
          <div style="width:100%">
            <div v-for="(c, idx) in editForm.changes" :key="idx" class="herb-row">
              <el-input v-model="c.condition" placeholder="病证" style="width:150px" />
              <el-input v-model="c.add" placeholder="加" style="width:140px" />
              <el-input v-model="c.remove" placeholder="减" style="width:140px" />
              <el-button type="danger" link @click="editForm.changes.splice(idx, 1)">—</el-button>
            </div>
            <el-button type="info" plain size="small" @click="editForm.changes.push({ condition: '', add: '', remove: '' })">＋ 加一个变化</el-button>
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

const meridians = ['太阳', '阳明', '少阳', '太阴', '少阴', '厥阴']
const importFileRef = ref<HTMLInputElement | null>(null)
const editVisible = ref(false)
const editId = ref<number | null>(null)
const saving = ref(false)
const editForm = ref<any>({
  name: '', source: '', meridian: '', efficacy: '', indications: '', usage: '',
  herbs: [], changes: [],
})

function emptyForm() {
  return {
    name: '', source: '', meridian: '', efficacy: '', indications: '', usage: '',
    herbs: [], changes: [],
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
    meridian: f.composition?.meridian || '',
    efficacy: f.efficacy || '',
    indications: f.indications || '',
    usage: f.usage || '',
    herbs: (f.composition?.herbs || []).map((h: any) => ({ ...h })),
    changes: (f.modifications?.changes || []).map((c: any) => ({ ...c })),
  }
  editVisible.value = true
}

function buildPayload() {
  const herbs = editForm.value.herbs
    .filter((h: any) => h.herb && String(h.herb).trim())
    .map((h: any) => ({
      herb: h.herb.trim(),
      dose: h.dose || null,
      special_method: h.special_method || null,
      is_king_herb: !!h.is_king_herb,
      note: h.note || null,
    }))
  const composition: any = { herbs }
  if (editForm.value.meridian) composition.meridian = editForm.value.meridian
  const changes = editForm.value.changes.filter((c: any) => c.condition || c.add || c.remove)
  return {
    name: editForm.value.name.trim(),
    source: editForm.value.source?.trim() || null,
    composition,
    efficacy: editForm.value.efficacy?.trim() || null,
    indications: editForm.value.indications?.trim() || null,
    usage: editForm.value.usage?.trim() || null,
    modifications: changes.length ? { changes } : null,
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
      await api.put(`/prescriptions/classic-formulas/${editId.value}`, payload)
      ElMessage.success('方剂已更新')
    } else {
      await api.post('/prescriptions/classic-formulas', payload)
      ElMessage.success('方剂已新增')
    }
    editVisible.value = false
    await loadFormulas()
  } catch (e: any) {
    ElMessage.error('保存失败：' + (e?.response?.data?.detail || e?.message || ''))
  }
  saving.value = false
}

async function removeFormula(f: any) {
  ElMessageBox.confirm(`确定删除方剂「${f.name}」吗？该操作不可恢复。`, '删除确认', {
    type: 'warning',
  }).then(async () => {
    try {
      await api.delete(`/prescriptions/classic-formulas/${f.id}`)
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
    const data: any = await api.get('/prescriptions/classic-formulas/export')
    if (!Array.isArray(data)) {
      // 兼容某些 axios 包装：取 data
    }
    const list = Array.isArray(data) ? data : (data as any)?.data || []
    if (!list.length) {
      ElMessage.warning('当前方剂库为空')
      return
    }
    const blob = new Blob([JSON.stringify(list, null, 2)], { type: 'application/json' })
    const a = document.createElement('a')
    a.href = URL.createObjectURL(blob)
    a.download = `中药方库_${new Date().toISOString().slice(0, 10)}.json`
    a.click()
    URL.revokeObjectURL(a.href)
    ElMessage.success(`已导出 ${list.length} 首方剂`)
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
      composition: it.composition || { herbs: it.herbs || [] },
      efficacy: it.efficacy || null,
      indications: it.indications || null,
      usage: it.usage || null,
      modifications: it.modifications || (it.modification_changes ? { changes: it.modification_changes } : null),
    }))
    const res: any = await api.post('/prescriptions/classic-formulas/import', payload)
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
    formulas.value = (await api.get('/prescriptions/classic-formulas', { params })) as any
  } catch {}
}

function viewFormula(formula: any) {
  currentFormula.value = formula
  detailVisible.value = true
}

function useInPrescription(formula: any) {
  detailVisible.value = false
  // 跳转到处方编辑器，通过 router query 传递 formula_id
  router.push({ path: '/prescriptions/new', query: { formula_id: formula.id } })
}

onMounted(loadFormulas)
</script>

<style scoped lang="scss">
.classic-formula-lib {
  .formula-card {
    margin-bottom: 16px;
    cursor: pointer;
    transition: all 0.2s;

    &:hover {
      transform: translateY(-2px);
      box-shadow: 0 4px 12px rgba(139, 69, 19, 0.15);
    }

    .formula-name {
      font-size: 16px;
      font-weight: 700;
      color: #8B4513;
      margin-bottom: 6px;
    }

    .formula-source {
      margin-bottom: 6px;
    }

    .formula-efficacy {
      font-size: 13px;
      color: #666;
      margin-bottom: 8px;
    }

    .formula-composition {
      .herb-chip {
        display: inline-block;
        padding: 2px 6px;
        background: #f5f0eb;
        border-radius: 4px;
        font-size: 12px;
        margin: 2px;
        color: #8B4513;
      }
    }
  }
}

.formula-modifications {
  .mod-item {
    padding: 8px 0;
    border-bottom: 1px dashed #e8e0d8;

    .mod-detail {
      margin-top: 4px;
      font-size: 13px;

      .mod-add { color: #52c41a; margin-right: 12px; }
      .mod-remove { color: #f56c6c; }
    }
  }
}

.herb-row {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;

  .el-checkbox { white-space: nowrap; }
}

/* ---- 移动端适配 ---- */
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
  :deep(.el-form--inline .el-input),
  :deep(.el-form--inline .el-select) {
    width: 100% !important;
  }
  .formula-card {
    margin-bottom: 8px;
  }
}
</style>