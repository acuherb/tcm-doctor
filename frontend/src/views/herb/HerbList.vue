<template>
  <div class="herb-list">
    <el-card shadow="hover">
      <template #header>
        <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:8px;">
          <span>💊 药材字典</span>
          <div>
            <el-button v-if="editable" size="small" @click="triggerImport">
              <el-icon><Upload /></el-icon> 导入JSON
            </el-button>
            <el-button v-if="editable" size="small" @click="exportHerbs">
              <el-icon><Download /></el-icon> 导出JSON
            </el-button>
            <el-button v-if="editable" type="primary" size="small" @click="openAdd">
              <el-icon><Plus /></el-icon> 新增药材
            </el-button>
            <input ref="fileInput" type="file" accept=".json,application/json" style="display:none" @change="onImportFile" />
          </div>
        </div>
      </template>

      <!-- 多维标签筛选 -->
      <el-form :inline="true" @submit.prevent="loadHerbs" class="filter-form">
        <el-form-item>
          <el-input v-model="searchText" placeholder="搜索药名/异名/功效" clearable @clear="loadHerbs" style="width:200px">
            <template #prefix><el-icon><Search /></el-icon></template>
          </el-input>
        </el-form-item>
        <el-form-item label="三品">
          <el-select v-model="gradeFilter" placeholder="全部" clearable @change="loadHerbs" style="width:110px">
            <el-option v-for="o in dimOptions('grade')" :key="o" :label="o" :value="o" />
          </el-select>
        </el-form-item>
        <el-form-item label="四气">
          <el-select v-model="natureFilter" placeholder="全部" clearable @change="loadHerbs" style="width:110px">
            <el-option v-for="o in dimOptions('nature')" :key="o" :label="o" :value="o" />
          </el-select>
        </el-form-item>
        <el-form-item label="五味">
          <el-select v-model="flavorFilters" multiple collapse-tags clearable placeholder="多选" @change="loadHerbs" style="width:150px">
            <el-option v-for="o in dimOptions('flavors')" :key="o" :label="o" :value="o" />
          </el-select>
        </el-form-item>
        <el-form-item label="归经">
          <el-select v-model="meridianFilters" multiple collapse-tags clearable placeholder="多选" @change="loadHerbs" style="width:170px">
            <el-option v-for="o in dimOptions('meridians')" :key="o" :label="o" :value="o" />
          </el-select>
        </el-form-item>
        <el-form-item label="升降浮沉">
          <el-select v-model="directionFilters" multiple collapse-tags clearable placeholder="多选" @change="loadHerbs" style="width:150px">
            <el-option v-for="o in dimOptions('directions')" :key="o" :label="o" :value="o" />
          </el-select>
        </el-form-item>
        <el-form-item label="功效分类/标签">
          <el-select v-model="tagFilters" multiple filterable allow-create default-first-option collapse-tags clearable placeholder="多选/自定义" @change="loadHerbs" style="width:200px">
            <el-option v-for="t in (meta.tag_suggestions || [])" :key="t" :label="t" :value="t" />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-checkbox v-model="pregOnly" @change="loadHerbs">仅看孕妇禁忌</el-checkbox>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="loadHerbs">查询</el-button>
          <el-button @click="resetFilters">重置</el-button>
        </el-form-item>
      </el-form>

      <el-table v-if="!isMobile" :data="herbs" stripe style="width:100%">
        <el-table-column prop="name" label="正名" width="100" />
        <el-table-column prop="aliases" label="异名" width="150">
          <template #default="{ row }">
            <span v-if="row.aliases && row.aliases.length">{{ row.aliases.join('、') }}</span>
            <span v-else class="text-muted">-</span>
          </template>
        </el-table-column>
        <el-table-column label="三品" width="72">
          <template #default="{ row }">
            <el-tag v-if="row.grade" :type="gradeTag(row.grade)" size="small">{{ row.grade }}</el-tag>
            <span v-else class="text-muted">-</span>
          </template>
        </el-table-column>
        <el-table-column prop="nature" label="性" width="50" />
        <el-table-column label="味" width="110">
          <template #default="{ row }">
            <el-tag v-for="f in (row.flavors || [])" :key="f" size="small" type="success" class="tag-cell">{{ f }}</el-tag>
            <span v-if="!(row.flavors && row.flavors.length)" class="text-muted">-</span>
          </template>
        </el-table-column>
        <el-table-column label="归经" width="160" show-overflow-tooltip>
          <template #default="{ row }">
            <el-tag v-for="m in (row.meridians || [])" :key="m" size="small" type="warning" class="tag-cell">{{ m }}</el-tag>
            <span v-if="!(row.meridians && row.meridians.length)" class="text-muted">-</span>
          </template>
        </el-table-column>
        <el-table-column label="升降浮沉" width="110">
          <template #default="{ row }">
            <el-tag v-for="d in (row.directions || [])" :key="d" size="small" type="info" class="tag-cell">{{ d }}</el-tag>
            <span v-if="!(row.directions && row.directions.length)" class="text-muted">-</span>
          </template>
        </el-table-column>
        <el-table-column label="功效分类/标签" min-width="180" show-overflow-tooltip>
          <template #default="{ row }">
            <el-tag v-for="t in (row.tags || [])" :key="t" size="small" class="tag-cell">{{ t }}</el-tag>
            <span v-if="!(row.tags && row.tags.length)" class="text-muted">-</span>
          </template>
        </el-table-column>
        <el-table-column prop="efficacy" label="功效" show-overflow-tooltip />
        <el-table-column label="剂量(g)" width="90">
          <template #default="{ row }">{{ row.dosage_min }}~{{ row.dosage_max }}<span class="unit">g</span></template>
        </el-table-column>
        <el-table-column prop="toxicity" label="毒性" width="70">
          <template #default="{ row }">
            <el-tag :type="toxicityTag(row.toxicity)" size="small">{{ row.toxicity }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="70">
          <template #default="{ row }">
            <el-tag :type="row.is_active === false ? 'info' : 'success'" size="small">{{ row.is_active === false ? '停用' : '启用' }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column v-if="editable" label="操作" width="120" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" size="small" @click="openEdit(row)">编辑</el-button>
            <el-button link type="danger" size="small" @click="removeHerb(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>

      <!-- 移动端卡片视图 -->
      <div v-if="isMobile" class="herb-cards">
        <div v-for="row in herbs" :key="row.id" class="herb-card">
          <div class="card-head">
            <span class="card-name">{{ row.name }}</span>
            <el-tag :type="row.is_active === false ? 'info' : 'success'" size="small">{{ row.is_active === false ? '停用' : '启用' }}</el-tag>
          </div>
          <div class="card-body">
            <div class="card-row" v-if="row.aliases && row.aliases.length">
              <span class="label">异名</span><span class="value">{{ row.aliases.join('、') }}</span>
            </div>
            <div class="card-row">
              <span class="label">三品</span>
              <span class="value"><el-tag v-if="row.grade" :type="gradeTag(row.grade)" size="small">{{ row.grade }}</el-tag><template v-else>-</template></span>
            </div>
            <div class="card-row">
              <span class="label">性味</span><span class="value">{{ row.nature || '-' }} / <template v-for="f in (row.flavors||[])">{{ f }} </template><template v-if="!(row.flavors&&row.flavors.length)">-</template></span>
            </div>
            <div class="card-row">
              <span class="label">归经</span><span class="value"><template v-for="m in (row.meridians||[])">{{ m }} </template><template v-if="!(row.meridians&&row.meridians.length)">-</template></span>
            </div>
            <div class="card-row" v-if="row.directions && row.directions.length">
              <span class="label">升降</span><span class="value"><template v-for="d in row.directions">{{ d }} </template></span>
            </div>
            <div class="card-row" v-if="row.tags && row.tags.length">
              <span class="label">标签</span><span class="value"><template v-for="t in row.tags">{{ t }} </template></span>
            </div>
            <div class="card-row">
              <span class="label">剂量</span><span class="value">{{ row.dosage_min }}~{{ row.dosage_max }} g</span>
            </div>
            <div class="card-row">
              <span class="label">毒性</span>
              <span class="value"><el-tag :type="toxicityTag(row.toxicity)" size="small">{{ row.toxicity || '无毒' }}</el-tag></span>
            </div>
            <div class="card-row" v-if="row.efficacy">
              <span class="label">功效</span><span class="value">{{ row.efficacy }}</span>
            </div>
          </div>
          <div v-if="editable" class="card-actions">
            <el-button link type="primary" size="small" @click="openEdit(row)">编辑</el-button>
            <el-button link type="danger" size="small" @click="removeHerb(row)">删除</el-button>
          </div>
        </div>
        <el-empty v-if="!herbs.length" description="暂无药材" />
      </div>
    </el-card>

    <el-dialog v-model="showDialog" :title="isEdit ? '编辑药材' : '新增药材'" width="680px" destroy-on-close>
      <el-form :model="form" label-width="96px">
        <el-form-item label="正名" required><el-input v-model="form.name" placeholder="请输入药名（如 桂枝）"/></el-form-item>
        <el-form-item label="异名"><el-input v-model="form.aliasesStr" placeholder="逗号分隔，如 官桂、桂心" /></el-form-item>
        <el-row :gutter="12">
          <el-col :span="8"><el-form-item label="三品">
            <el-select v-model="form.grade" clearable placeholder="选填" style="width:100%">
              <el-option v-for="o in dimOptions('grade')" :key="o" :label="o" :value="o" />
            </el-select>
          </el-form-item></el-col>
          <el-col :span="8"><el-form-item label="四气">
            <el-select v-model="form.nature" clearable placeholder="选填" style="width:100%">
              <el-option v-for="o in dimOptions('nature')" :key="o" :label="o" :value="o" />
            </el-select>
          </el-form-item></el-col>
        </el-row>
        <el-form-item label="五味">
          <el-select v-model="form.flavors" multiple clearable style="width:100%" placeholder="多选">
            <el-option v-for="o in dimOptions('flavors')" :key="o" :label="o" :value="o" />
          </el-select>
        </el-form-item>
        <el-form-item label="归经">
          <el-select v-model="form.meridians" multiple clearable style="width:100%" placeholder="多选">
            <el-option v-for="o in dimOptions('meridians')" :key="o" :label="o" :value="o" />
          </el-select>
        </el-form-item>
        <el-form-item label="升降浮沉">
          <el-select v-model="form.directions" multiple clearable style="width:100%" placeholder="多选">
            <el-option v-for="o in dimOptions('directions')" :key="o" :label="o" :value="o" />
          </el-select>
        </el-form-item>
        <el-form-item label="功效分类/标签">
          <el-select v-model="form.tags" multiple filterable allow-create default-first-option clearable style="width:100%" placeholder="选择或自定义">
            <el-option v-for="t in (meta.tag_suggestions || [])" :key="t" :label="t" :value="t" />
          </el-select>
        </el-form-item>
        <el-form-item label="功效"><el-input v-model="form.efficacy" type="textarea" :rows="2" /></el-form-item>
        <el-row :gutter="12">
          <el-col :span="12"><el-form-item label="最小剂量">
            <el-input-number v-model="form.dosage_min" :min="0" :max="1000" :precision="1" :step="1" controls-position="right" style="width:100%">
              <template #suffix><span class="unit">g</span></template>
            </el-input-number>
          </el-form-item></el-col>
          <el-col :span="12"><el-form-item label="最大剂量">
            <el-input-number v-model="form.dosage_max" :min="0" :max="1000" :precision="1" :step="1" controls-position="right" style="width:100%">
              <template #suffix><span class="unit">g</span></template>
            </el-input-number>
          </el-form-item></el-col>
        </el-row>
        <el-form-item label="毒性">
          <el-radio-group v-model="form.toxicity">
            <el-radio-button v-for="t in ['无毒','有小毒','有毒','有大毒']" :key="t" :label="t">{{ t }}</el-radio-button>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="储存条件"><el-input v-model="form.storage_condition" placeholder="如 置阴凉干燥处" /></el-form-item>
        <el-form-item label="孕妇禁忌">
          <el-switch v-model="form.pregnancy_contraindicated" active-text="是" inactive-text="否" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showDialog = false">取消</el-button>
        <el-button type="primary" @click="submitForm">确定</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onBeforeUnmount } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, Search, Upload, Download } from '@element-plus/icons-vue'
import api from '@/utils/api'
import { useAuthStore } from '@/store/auth'

// 游客只读：隐藏所有写操作
const auth = useAuthStore()
const editable = computed(() => !!auth.user?.is_admin)

const herbs = ref<any[]>([])
const searchText = ref('')
const gradeFilter = ref('')
const natureFilter = ref('')
const flavorFilters = ref<string[]>([])
const meridianFilters = ref<string[]>([])
const directionFilters = ref<string[]>([])
const tagFilters = ref<string[]>([])
const pregOnly = ref(false)

// 标签维度与受控词表（来自后端 /herbs/tags/meta）
const meta = ref<any>({ dimensions: {}, tag_suggestions: [] })
function dimOptions(dim: string): string[] {
  return meta.value?.dimensions?.[dim]?.options || []
}

const showDialog = ref(false)
const isEdit = ref(false)
const editingId = ref<number | null>(null)

// ---- 移动端适配：窄屏下用卡片视图替代表格 ----
const isMobile = ref(false)
function updateViewport() {
  isMobile.value = window.innerWidth < 768
}

function defaultForm() {
  return {
    name: '', aliasesStr: '', grade: '', nature: '平',
    flavors: [] as string[], meridians: [] as string[], directions: [] as string[], tags: [] as string[],
    efficacy: '', dosage_min: 3, dosage_max: 10, toxicity: '无毒',
    storage_condition: '', pregnancy_contraindicated: false,
  }
}
const form = ref(defaultForm())

function toxicityTag(t: string) {
  if (t === '有大毒') return 'danger'
  if (t === '有毒') return 'warning'
  if (t === '有小毒') return 'info'
  return 'success'
}
function gradeTag(g: string) {
  if (g === '上品') return 'success'
  if (g === '中品') return 'warning'
  return 'danger' // 下品
}

async function loadMeta() {
  try {
    meta.value = await api.get('/herbs/tags/meta')
  } catch {}
}

async function loadHerbs() {
  try {
    const p = new URLSearchParams()
    if (searchText.value) p.set('search', searchText.value)
    if (gradeFilter.value) p.set('grade', gradeFilter.value)
    if (natureFilter.value) p.set('nature', natureFilter.value)
    if (pregOnly.value) p.set('pregnancy_contraindicated', 'true')
    flavorFilters.value.forEach((v) => p.append('flavors', v))
    meridianFilters.value.forEach((v) => p.append('meridians', v))
    directionFilters.value.forEach((v) => p.append('directions', v))
    tagFilters.value.forEach((v) => p.append('tags', v))
    const qs = p.toString()
    herbs.value = (await api.get('/herbs' + (qs ? '?' + qs : ''))) as any
  } catch {}
}

function resetFilters() {
  searchText.value = ''
  gradeFilter.value = ''
  natureFilter.value = ''
  flavorFilters.value = []
  meridianFilters.value = []
  directionFilters.value = []
  tagFilters.value = []
  pregOnly.value = false
  loadHerbs()
}

function openAdd() {
  isEdit.value = false
  editingId.value = null
  form.value = defaultForm()
  showDialog.value = true
}

function openEdit(row: any) {
  isEdit.value = true
  editingId.value = row.id
  form.value = {
    name: row.name || '',
    aliasesStr: row.aliases ? row.aliases.join('、') : '',
    grade: row.grade || '',
    nature: row.nature || '平',
    flavors: row.flavors || [],
    meridians: row.meridians || [],
    directions: row.directions || [],
    tags: row.tags || [],
    efficacy: row.efficacy || '',
    dosage_min: row.dosage_min ?? 3,
    dosage_max: row.dosage_max ?? 10,
    toxicity: row.toxicity || '无毒',
    storage_condition: row.storage_condition || '',
    pregnancy_contraindicated: !!row.pregnancy_contraindicated,
  }
  showDialog.value = true
}

async function submitForm() {
  if (!form.value.name.trim()) { ElMessage.warning('请输入药名'); return }
  try {
    const f = form.value
    const payload: any = {
      name: f.name,
      aliases: f.aliasesStr ? f.aliasesStr.split(/[,，、]/).map((s: string) => s.trim()).filter(Boolean) : null,
      grade: f.grade || null,
      nature: f.nature || null,
      flavors: f.flavors.length ? f.flavors : null,
      meridians: f.meridians.length ? f.meridians : null,
      directions: f.directions.length ? f.directions : null,
      tags: f.tags.length ? f.tags : null,
      efficacy: f.efficacy || null,
      dosage_min: f.dosage_min,
      dosage_max: f.dosage_max,
      toxicity: f.toxicity || '无毒',
      storage_condition: f.storage_condition || null,
      pregnancy_contraindicated: f.pregnancy_contraindicated,
    }
    if (isEdit.value) {
      await api.put(`/herbs/${editingId.value}`, payload)
      ElMessage.success('药材更新成功')
    } else {
      await api.post('/herbs', payload)
      ElMessage.success('药材添加成功')
    }
    showDialog.value = false
    loadHerbs()
  } catch {}
}

async function removeHerb(row: any) {
  try {
    await ElMessageBox.confirm(`确定删除药材「${row.name}」？`, '提示', { type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消' })
  } catch { return }
  try {
    const r: any = await api.delete(`/herbs/${row.id}`)
    ElMessage.success(r?.message || '操作成功')
    loadHerbs()
  } catch {}
}

// ── 导入/导出 ──
const fileInput = ref<HTMLInputElement | null>(null)
function triggerImport() {
  if (fileInput.value) { fileInput.value.value = ''; fileInput.value.click() }
}
async function onImportFile(e: any) {
  const f = e.target.files?.[0]
  if (!f) return
  try {
    const text = await f.text()
    const arr = JSON.parse(text)
    if (!Array.isArray(arr)) { ElMessage.error('文件须为药材数组 JSON'); return }
    const r: any = await api.post('/herbs/import', arr)
    ElMessage.success(`导入完成：新增 ${r.imported} 条，更新 ${r.updated} 条`)
    loadHerbs()
  } catch {
    ElMessage.error('JSON 解析或导入失败')
  } finally {
    if (fileInput.value) fileInput.value.value = ''
  }
}
async function exportHerbs() {
  try {
    const data: any = await api.get('/herbs/export')
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json;charset=utf-8' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `herbs_${new Date().toISOString().slice(0, 10)}.json`
    a.click()
    URL.revokeObjectURL(url)
  } catch {}
}

onMounted(async () => {
  updateViewport()
  window.addEventListener('resize', updateViewport)
  await loadMeta()
  await loadHerbs()
})
onBeforeUnmount(() => window.removeEventListener('resize', updateViewport))
</script>

<style scoped>
.text-muted { color: #c0c4cc; }
.unit { margin-left: 2px; color: #909399; font-size: 12px; }
.tag-cell { margin: 1px 2px; }

/* ---- 移动端卡片视图 ---- */
.herb-cards {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.herb-card {
  background: #fff;
  border: 1px solid #e8e0d8;
  border-radius: 10px;
  padding: 12px 14px;
  box-shadow: 0 1px 3px rgba(0,0,0,0.05);
}
.card-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 8px;
}
.card-name {
  font-size: 17px;
  font-weight: 600;
  color: #2C1810;
}
.card-body {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.card-row {
  display: flex;
  align-items: flex-start;
  font-size: 14px;
  line-height: 1.5;
}
.card-row .label {
  flex-shrink: 0;
  width: 48px;
  color: #8a7563;
}
.card-row .value {
  flex: 1;
  color: #333;
  word-break: break-all;
}
.card-actions {
  display: flex;
  justify-content: flex-end;
  gap: 4px;
  margin-top: 8px;
  padding-top: 8px;
  border-top: 1px dashed #eee;
}

/* ---- 移动端：搜索/筛选改为全宽纵向堆叠 ---- */
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
  :deep(.el-card__header) {
    padding: 12px;
  }
}
</style>
