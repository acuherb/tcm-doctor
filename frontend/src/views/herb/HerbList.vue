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
        <el-form-item label="四气">
          <el-select v-model="natureFilter" placeholder="全部" clearable @change="loadHerbs" style="width:110px">
            <el-option v-for="o in dimOptions('nature')" :key="o" :label="o" :value="o">
              <span class="opt-dot" :style="{ backgroundColor: xwColor(o) }"></span>{{ o }}
            </el-option>
          </el-select>
        </el-form-item>
        <el-form-item label="五味">
          <el-select v-model="flavorFilters" multiple collapse-tags clearable placeholder="多选" @change="loadHerbs" style="width:150px">
            <el-option v-for="o in dimOptions('flavors')" :key="o" :label="o" :value="o">
              <span class="opt-dot" :style="{ backgroundColor: xwColor(o) }"></span>{{ o }}
            </el-option>
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
        <el-table-column label="性味" width="160">
          <template #default="{ row }">
            <span v-if="row.nature || (row.flavors && row.flavors.length) || (row.toxicity && row.toxicity !== '无毒')">
              <span v-if="row.nature" class="xw-tag" :style="xwTagStyle(row.nature)">{{ row.nature }}</span>
              <span v-for="f in (row.flavors || [])" :key="f" class="xw-tag" :style="xwTagStyle(f)">{{ f }}</span>
              <span v-if="row.toxicity && row.toxicity !== '无毒'" class="xw-tag" :style="xwTagStyle(row.toxicity)">{{ row.toxicity }}</span>
            </span>
            <span v-else class="text-muted">-</span>
          </template>
        </el-table-column>
        <el-table-column prop="efficacy" label="主治" min-width="220" show-overflow-tooltip />
        <el-table-column prop="contraindication" label="禁忌" min-width="180" show-overflow-tooltip />
        <el-table-column label="剂量(g)" width="90">
          <template #default="{ row }">{{ row.dosage_min }}~{{ row.dosage_max }}<span class="unit">g</span></template>
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
              <span class="label">性味</span>
              <span class="value xw-tags">
                <span v-if="row.nature" class="xw-tag" :style="xwTagStyle(row.nature)">{{ row.nature }}</span>
                <span v-for="f in (row.flavors || [])" :key="f" class="xw-tag" :style="xwTagStyle(f)">{{ f }}</span>
                <span v-if="row.toxicity && row.toxicity !== '无毒'" class="xw-tag" :style="xwTagStyle(row.toxicity)">{{ row.toxicity }}</span>
                <template v-if="!row.nature && !(row.flavors && row.flavors.length) && (!row.toxicity || row.toxicity === '无毒')">-</template>
              </span>
            </div>
            <div class="card-row" v-if="row.efficacy">
              <span class="label">主治</span><span class="value">{{ row.efficacy }}</span>
            </div>
            <div class="card-row" v-if="row.contraindication">
              <span class="label">禁忌</span><span class="value">{{ row.contraindication }}</span>
            </div>
            <div class="card-row">
              <span class="label">剂量</span><span class="value">{{ row.dosage_min }}~{{ row.dosage_max }} g</span>
            </div>
            <div class="card-row" v-if="row.storage_condition">
              <span class="label">储存</span><span class="value">{{ row.storage_condition }}</span>
            </div>
            <div class="card-row" v-if="row.pregnancy_contraindicated">
              <span class="label">孕妇</span><span class="value">慎用</span>
            </div>
            <div class="card-row">
              <span class="label">状态</span><span class="value">{{ row.is_active === false ? '停用' : '启用' }}</span>
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

    <el-dialog v-model="showDialog" width="680px" class="herb-dialog" destroy-on-close :close-on-click-modal="false" align-center>
      <template #header>
        <div class="dlg-title">
          <span class="dlg-dot"></span>
          {{ isEdit ? '编辑药材' : '新增药材' }}
        </div>
      </template>
      <el-form :model="form" label-position="top" class="herb-form">
        <el-form-item label="正名" required><el-input v-model="form.name" placeholder="请输入药名（如 桂枝）"/></el-form-item>
        <el-form-item label="异名"><el-input v-model="form.aliasesStr" placeholder="逗号分隔，如 官桂、桂心" /></el-form-item>
        <el-row :gutter="12">
          <el-col :span="12" :xs="24"><el-form-item label="四气">
            <el-select v-model="form.nature" clearable placeholder="选填" style="width:100%">
              <el-option v-for="o in dimOptions('nature')" :key="o" :label="o" :value="o">
                <span class="opt-dot" :style="{ backgroundColor: xwColor(o) }"></span>{{ o }}
              </el-option>
            </el-select>
          </el-form-item></el-col>
          <el-col :span="12" :xs="24"><el-form-item label="五味">
            <el-select v-model="form.flavors" multiple clearable style="width:100%" placeholder="多选">
              <el-option v-for="o in dimOptions('flavors')" :key="o" :label="o" :value="o">
                <span class="opt-dot" :style="{ backgroundColor: xwColor(o) }"></span>{{ o }}
              </el-option>
            </el-select>
          </el-form-item></el-col>
        </el-row>
        <el-form-item label="毒性">
          <el-radio-group v-model="form.toxicity">
            <el-radio-button v-for="t in ['无毒','有小毒','有毒','有大毒']" :key="t" :label="t">{{ t }}</el-radio-button>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="主治"><el-input v-model="form.efficacy" type="textarea" :rows="2" placeholder="如 发汗解肌，温通经脉，助阳化气" /></el-form-item>
        <el-form-item label="禁忌"><el-input v-model="form.contraindication" type="textarea" :rows="2" placeholder="如 阴虚火旺者忌用；孕妇慎用" /></el-form-item>
        <el-row :gutter="12">
          <el-col :span="12" :xs="24"><el-form-item label="最小剂量">
            <el-input-number v-model="form.dosage_min" :min="0" :max="1000" :precision="1" :step="1" controls-position="right" style="width:100%">
              <template #suffix><span class="unit">g</span></template>
            </el-input-number>
          </el-form-item></el-col>
          <el-col :span="12" :xs="24"><el-form-item label="最大剂量">
            <el-input-number v-model="form.dosage_max" :min="0" :max="1000" :precision="1" :step="1" controls-position="right" style="width:100%">
              <template #suffix><span class="unit">g</span></template>
            </el-input-number>
          </el-form-item></el-col>
        </el-row>
        <el-form-item label="储存条件"><el-input v-model="form.storage_condition" placeholder="如 置阴凉干燥处" /></el-form-item>
        <el-row :gutter="12">
          <el-col :span="12" :xs="12"><el-form-item label="孕妇禁忌">
            <el-switch v-model="form.pregnancy_contraindicated" active-text="是" inactive-text="否" />
          </el-form-item></el-col>
          <el-col :span="12" :xs="12"><el-form-item label="状态">
            <el-switch v-model="form.is_active" active-text="启用" inactive-text="停用" />
          </el-form-item></el-col>
        </el-row>
      </el-form>
      <template #footer>
        <div class="dlg-footer">
          <el-button @click="showDialog = false">取消</el-button>
          <el-button type="primary" @click="submitForm">确 定</el-button>
        </div>
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
const natureFilter = ref('')
const flavorFilters = ref<string[]>([])
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
    name: '', aliasesStr: '', nature: '平',
    flavors: [] as string[],
    efficacy: '', contraindication: '', dosage_min: 3, dosage_max: 10, toxicity: '无毒',
    storage_condition: '', pregnancy_contraindicated: false, is_active: true,
  }
}
const form = ref(defaultForm())

// 药材性味颜色：优先用字典自定义色，回退五行本色（酸木青/苦火赤/甘土黄/辛金白/咸水黑；四气寒→温 蓝→橙红）
const herbTagColor = ref<Record<string, string>>({})
const DEFAULT_XW_COLOR: Record<string, string> = {
  '酸': '#2e9e5b', '苦': '#d9434e', '甘': '#e0a82e', '辛': '#9fb3c8', '咸': '#2f3b47', '淡': '#b0a0c0',
  '寒': '#2f80b5', '微寒': '#5aa0cf', '平': '#7f9a6e', '微温': '#e08a3c', '温': '#d9642c',
  '有毒': '#c0392b', '有小毒': '#e67e22', '有大毒': '#8e1b1b',
}
function xwColor(name: string): string {
  return herbTagColor.value[name] || DEFAULT_XW_COLOR[name] || '#909399'
}
// 依据颜色亮度返回可读前景色：浅色背景用深字，深色背景用浅字（避免白色等浅色导致文字不可见）
function readableInk(hex: string): string {
  const c = (hex || '').replace('#', '')
  if (c.length < 6) return '#333333'
  const r = parseInt(c.slice(0, 2), 16)
  const g = parseInt(c.slice(2, 4), 16)
  const b = parseInt(c.slice(4, 6), 16)
  const L = (0.299 * r + 0.587 * g + 0.114 * b) / 255
  return L > 0.6 ? '#333333' : '#ffffff'
}
function xwTagStyle(name: string): Record<string, string> {
  const c = xwColor(name)
  const ink = readableInk(c)
  return { color: ink, backgroundColor: c, borderColor: ink }
}
async function loadHerbTagColors() {
  try {
    const list = (await api.get('/dictionaries', { params: { term_type: 'herb_tag' } })) as any[]
    const m: Record<string, string> = {}
    for (const t of (list || [])) if (t.name && t.color) m[t.name] = t.color
    herbTagColor.value = m
  } catch {}
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
    if (natureFilter.value) p.set('nature', natureFilter.value)
    if (pregOnly.value) p.set('pregnancy_contraindicated', 'true')
    flavorFilters.value.forEach((v) => p.append('flavors', v))
    const qs = p.toString()
    herbs.value = (await api.get('/herbs' + (qs ? '?' + qs : ''))) as any
  } catch {}
}

function resetFilters() {
  searchText.value = ''
  natureFilter.value = ''
  flavorFilters.value = []
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
    nature: row.nature || '平',
    flavors: row.flavors || [],
    efficacy: row.efficacy || '',
    contraindication: row.contraindication || '',
    dosage_min: row.dosage_min ?? 3,
    dosage_max: row.dosage_max ?? 10,
    toxicity: row.toxicity || '无毒',
    storage_condition: row.storage_condition || '',
    pregnancy_contraindicated: !!row.pregnancy_contraindicated,
    is_active: row.is_active ?? true,
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
      nature: f.nature || null,
      flavors: f.flavors.length ? f.flavors : null,
      efficacy: f.efficacy || null,
      contraindication: f.contraindication || null,
      dosage_min: f.dosage_min,
      dosage_max: f.dosage_max,
      toxicity: f.toxicity || '无毒',
      storage_condition: f.storage_condition || null,
      pregnancy_contraindicated: f.pregnancy_contraindicated,
      is_active: f.is_active,
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
    const r: any = await api.post('/herbs/import', arr, { silent: true })
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
  await loadHerbTagColors()
  await loadHerbs()
})
onBeforeUnmount(() => window.removeEventListener('resize', updateViewport))
</script>

<style scoped>
.text-muted { color: #c0c4cc; }
.unit { margin-left: 2px; color: #909399; font-size: 12px; }
.tag-cell { margin: 1px 2px; }

/* 药材性味五行本色标签 */
.xw-tag {
  display: inline-block;
  padding: 0 8px;
  margin: 1px 4px 1px 0;
  font-size: 12px;
  line-height: 20px;
  border: 1px solid;
  border-radius: 10px;
  white-space: nowrap;
}
.xw-tags { display: flex; flex-wrap: wrap; align-items: center; }
.opt-dot {
  display: inline-block;
  width: 8px;
  height: 8px;
  border-radius: 50%;
  margin-right: 6px;
  vertical-align: middle;
}

/* ---- 新增/编辑弹窗美化 ---- */
.dlg-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-weight: 600;
  font-size: 16px;
  color: #2C1810;
}
.dlg-dot {
  width: 6px;
  height: 16px;
  border-radius: 3px;
  background: linear-gradient(180deg, #c8a07a, #a9784f);
}
.dlg-footer { display: flex; gap: 10px; justify-content: flex-end; }
.dlg-footer .el-button { margin-left: 0; }
:deep(.herb-dialog) {
  border-radius: 14px;
  overflow: hidden;
  box-shadow: 0 12px 32px rgba(44, 24, 16, 0.18);
}
:deep(.herb-dialog .el-dialog__header) {
  margin: 0;
  padding: 18px 22px 12px;
  border-bottom: 1px solid #f0ebe5;
  background: #fbf8f4;
}
:deep(.herb-dialog .el-dialog__body) {
  padding: 20px 22px 6px;
}
:deep(.herb-dialog .el-dialog__footer) {
  padding: 14px 22px 18px;
  border-top: 1px solid #f0ebe5;
  background: #faf7f3;
}
:deep(.herb-form .el-form-item) { margin-bottom: 16px; }
:deep(.herb-form .el-form-item__label) {
  font-weight: 500;
  color: #5a4636;
}
:deep(.herb-form .el-switch) { display: flex; }
:deep(.herb-form .el-input-number) { width: 100% !important; }

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
  /* 新增/编辑弹窗：移动端限宽 + 标签上置，避免窄屏挤成一团 */
  :deep(.herb-dialog) {
    width: 94% !important;
    border-radius: 14px;
  }
  :deep(.herb-dialog .el-dialog__header) { padding: 16px 16px 10px; }
  :deep(.herb-dialog .el-dialog__body) { padding: 16px 16px 4px; }
  :deep(.herb-dialog .el-dialog__footer) { padding: 12px 16px 16px; }
  .dlg-footer {
    display: flex;
    gap: 10px;
    justify-content: flex-end;
  }
  .dlg-footer .el-button {
    flex: 1;
    margin-left: 0;
    height: 42px;
    border-radius: 8px;
    font-size: 15px;
  }
  :deep(.herb-dialog .el-form-item) { margin-bottom: 16px; }
  :deep(.herb-dialog .el-textarea__inner) { min-height: 76px; }
  :deep(.herb-dialog .el-switch__label) { white-space: nowrap; }
}
</style>