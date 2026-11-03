<template>
  <div class="classic-formula-lib">
    <el-card shadow="hover" class="main-card">
      <template #header>
        <div class="card-head-bar">
          <div class="card-head-title">
            <span class="head-icon">📖</span>
            <span class="head-text">中药方库</span>
            <el-tag v-if="formulas.length > 0" size="small" type="info" effect="plain" round class="head-count">
              {{ formulas.length }} 首
            </el-tag>
          </div>
          <div v-if="editable" class="card-actions">
            <el-button type="primary" @click="openCreate">
              <el-icon><Plus /></el-icon>新增方剂
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
          <el-col :xs="24" :sm="12" :md="8" :xl="6" v-for="formula in formulas" :key="formula.id">
            <el-card shadow="never" class="formula-card" @click="viewFormula(formula)">
              <div class="formula-head">
                <div class="formula-name">{{ formula.name }}</div>
                <el-tag v-if="formula.composition?.meridian" size="small" type="success" effect="light" round class="meridian-tag">
                  {{ formula.composition.meridian }}
                </el-tag>
              </div>

              <div class="formula-sub" v-if="formula.source">
                <el-icon class="sub-icon"><Collection /></el-icon>{{ formula.source }}
              </div>

              <div class="formula-efficacy" v-if="formula.efficacy">{{ formula.efficacy }}</div>

              <div class="formula-composition" v-if="formula.composition?.herbs?.length">
                <span class="herb-label">组成</span>
                <span v-for="(h, idx) in formula.composition.herbs" :key="idx" class="herb-chip"
                  :class="{ 'is-king': h.is_king_herb }">
                  {{ h.herb }}<em v-if="h.dose">{{ h.dose }}g</em>
                </span>
              </div>
              <div class="formula-composition is-empty" v-else>
                <span class="herb-label">组成</span>
                <span class="herb-none">暂无药味</span>
              </div>
            </el-card>
          </el-col>
        </el-row>

        <el-empty v-if="!formulas.length" :image-size="80">
          <template #description>
            <span>{{ searchText || sourceFilter ? '没有匹配的方剂，试试调整筛选条件' : '中药方库为空' }}</span>
          </template>
        </el-empty>
      </div>
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
          <el-table :data="currentFormula.composition.herbs" class="tcm-table" size="small">
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
                <el-tag size="small" type="warning">{{ mod.condition || `变化${Number(idx) + 1}` }}</el-tag>
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
import { Search, Plus, Upload, Download, Collection } from '@element-plus/icons-vue'
import { useRouter } from 'vue-router'
import api from '@/utils/api'
import { useAuthStore } from '@/store/auth'

// 游客只读：隐藏所有写操作
const auth = useAuthStore()
const editable = computed(() => auth.can('dict:write'))
const router = useRouter()
const formulas = ref<any[]>([])
const searchText = ref('')
const sourceFilter = ref('')
const detailVisible = ref(false)
const currentFormula = ref<any>(null)
const loading = ref(false)
const importing = ref(false)

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
    const nl = Array.isArray(data) ? data : (data as any)?.data || []
    if (!nl.length) {
      ElMessage.warning('当前方剂库为空')
      return
    }
    const blob = new Blob([JSON.stringify(nl, null, 2)], { type: 'application/json' })
    const a = document.createElement('a')
    a.href = URL.createObjectURL(blob)
    a.download = `中药方库_${new Date().toISOString().slice(0, 10)}.json`
    a.click()
    URL.revokeObjectURL(a.href)
    ElMessage.success(`已导出 ${nl.length} 首方剂`)
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
    const params: any = {}
    if (searchText.value) params.search = searchText.value
    if (sourceFilter.value) params.source = sourceFilter.value
    formulas.value = (await api.get('/prescriptions/classic-formulas', { params })) as any
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
  // 跳转到处方编辑器，通过 router query 传递 formula_id
  router.push({ path: '/prescriptions/new', query: { formula_id: formula.id } })
}

onMounted(loadFormulas)
</script>

<style scoped lang="scss">
.classic-formula-lib {
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
      border-color: #d4a574;
      box-shadow: 0 4px 14px rgba(139, 94, 52, .1);
      transform: translateY(-2px);
    }

    :deep(.el-card__body) { padding: 14px 16px; }

    .formula-head {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 8px;
      margin-bottom: 6px;
    }

    .formula-name {
      font-size: 16px;
      font-weight: 700;
      color: #8b4513;
      line-height: 1.4;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }

    .meridian-tag { flex: none; }

    .formula-sub {
      display: flex;
      align-items: center;
      gap: 4px;
      font-size: 12px;
      color: #a39484;
      margin-bottom: 8px;

      .sub-icon { font-size: 12px; }
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

      .herb-label { font-size: 12px; color: #a39484; margin-right: 2px; }

      .herb-chip {
        display: inline-block;
        padding: 1px 8px;
        background: #faf6f1;
        border: 1px solid #eddfd0;
        border-radius: 10px;
        font-size: 12px;
        line-height: 18px;
        color: #8b5e34;

        em {
          font-style: normal;
          font-size: 11px;
          color: #b08b62;
          margin-left: 1px;
        }

        &.is-king {
          background: #fdf3e7;
          border-color: #ebcfab;
          color: #a05c1f;
          font-weight: 600;

          em { color: #c08a4e; }
        }
      }

      &.is-empty .herb-none { font-size: 12px; color: #bdb0a2; }
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
  .classic-formula-lib {
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

  .herb-row { flex-wrap: wrap; }
  .herb-row :deep(.el-input) { width: 100% !important; }
}
</style>