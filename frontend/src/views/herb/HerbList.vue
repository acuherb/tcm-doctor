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
      <el-form :inline="true" @submit.prevent="loadHerbs">
        <el-form-item>
          <el-input v-model="searchText" placeholder="搜索药名/异名" clearable @clear="loadHerbs" style="width:200px">
            <template #prefix><el-icon><Search /></el-icon></template>
          </el-input>
        </el-form-item>
        <el-form-item>
          <el-select v-model="categoryFilter" placeholder="分类筛选" clearable @change="loadHerbs" style="width:140px">
            <el-option v-for="c in categories" :key="c" :label="c" :value="c" />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="loadHerbs">查询</el-button>
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
        <el-table-column prop="category" label="分类" width="100" />
        <el-table-column prop="nature" label="性" width="50" />
        <el-table-column prop="flavor" label="味" width="80" />
        <el-table-column prop="meridian_tropism" label="归经" width="100" show-overflow-tooltip />
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
              <span class="label">分类</span><span class="value">{{ row.category || '-' }}</span>
            </div>
            <div class="card-row">
              <span class="label">性味</span><span class="value">{{ row.nature || '-' }} / {{ row.flavor || '-' }}</span>
            </div>
            <div class="card-row">
              <span class="label">归经</span><span class="value">{{ row.meridian_tropism || '-' }}</span>
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

    <el-dialog v-model="showDialog" :title="isEdit ? '编辑药材' : '新增药材'" width="620px" destroy-on-close>
      <el-form :model="form" label-width="90px">
        <el-form-item label="正名" required><el-input v-model="form.name" placeholder="请输入药名（如 桂枝）"/></el-form-item>
        <el-form-item label="异名"><el-input v-model="form.aliasesStr" placeholder="逗号分隔，如 官桂、桂心" /></el-form-item>
        <el-form-item label="分类">
          <el-select v-model="form.category" filterable allow-create default-first-option clearable style="width:100%" placeholder="选择或输入分类">
            <el-option v-for="c in categories" :key="c" :label="c" :value="c" />
          </el-select>
        </el-form-item>
        <el-row :gutter="12">
          <el-col :span="8"><el-form-item label="药性">
            <el-select v-model="form.nature" style="width:100%">
              <el-option v-for="n in ['寒','热','温','凉','平']" :key="n" :label="n" :value="n" />
            </el-select>
          </el-form-item></el-col>
          <el-col :span="16"><el-form-item label="药味"><el-input v-model="form.flavor" placeholder="如 辛、甘" /></el-form-item></el-col>
        </el-row>
        <el-form-item label="归经"><el-input v-model="form.meridian_tropism" placeholder="如 心、肺、膀胱" /></el-form-item>
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
const categoryFilter = ref('')
const categories = ['解表药', '清热药', '泻下药', '祛风湿药', '化湿药', '利水渗湿药', '温里药', '理气药', '消食药', '止血药', '活血化瘀药', '化痰止咳平喘药', '安神药', '平肝息风药', '开窍药', '补虚药', '收涩药', '涌吐药']

const showDialog = ref(false)
const isEdit = ref(false)
const editingId = ref<number | null>(null)

// ---- 移动端适配：窄屏下用卡片视图替代表格 ----
const isMobile = ref(false)
function updateViewport() {
  isMobile.value = window.innerWidth < 768
}
onMounted(() => {
  updateViewport()
  window.addEventListener('resize', updateViewport)
})
onBeforeUnmount(() => window.removeEventListener('resize', updateViewport))

function defaultForm() {
  return { name: '', aliasesStr: '', category: '', nature: '平', flavor: '', meridian_tropism: '', efficacy: '', dosage_min: 3, dosage_max: 10, toxicity: '无毒', storage_condition: '', pregnancy_contraindicated: false }
}
const form = ref(defaultForm())

function toxicityTag(t: string) {
  if (t === '有大毒') return 'danger'
  if (t === '有毒') return 'warning'
  if (t === '有小毒') return 'info'
  return 'success'
}

async function loadHerbs() {
  try {
    const params: any = {}
    if (searchText.value) params.search = searchText.value
    if (categoryFilter.value) params.category = categoryFilter.value
    herbs.value = (await api.get('/herbs', { params })) as any
  } catch {}
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
    category: row.category || '',
    nature: row.nature || '平',
    flavor: row.flavor || '',
    meridian_tropism: row.meridian_tropism || '',
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
    const payload: any = { ...form.value }
    payload.aliases = form.value.aliasesStr ? form.value.aliasesStr.split(/[,，、]/).map((s: string) => s.trim()).filter(Boolean) : null
    delete payload.aliasesStr
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

onMounted(loadHerbs)
</script>

<style scoped>
.text-muted { color: #c0c4cc; }
.unit { margin-left: 2px; color: #909399; font-size: 12px; }

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