<template>
  <div class="dictionary-manage">
    <el-card shadow="hover">
      <template #header>
        <div style="display:flex;justify-content:space-between;align-items:center;">
          <span>🗂️ 数据字典</span>
          <el-button v-if="editable" type="primary" size="small" @click="openCreate">＋ 新增词条</el-button>
        </div>
      </template>

      <el-radio-group v-model="activeType" @change="loadTerms" style="margin-bottom:16px">
        <el-radio-button value="syndrome">证型</el-radio-button>
        <el-radio-button value="tongue">舌象</el-radio-button>
        <el-radio-button value="pulse">脉象</el-radio-button>
        <el-radio-button value="tag">患者标签</el-radio-button>
        <el-radio-button value="herb_tag">药材性味</el-radio-button>
      </el-radio-group>

      <el-table v-if="!isMobile" :data="terms" border stripe>
        <el-table-column prop="name" label="词项" min-width="140" />
        <el-table-column v-if="activeType === 'syndrome'" label="六经" width="150">
          <template #default="{ row }">
            <template v-if="(row.meridian || '').split(',').filter(Boolean).length">
              <el-tag v-for="m in (row.meridian || '').split(',').filter(Boolean)" :key="m" size="small" type="info" effect="plain" style="margin-right:4px">{{ m }}</el-tag>
            </template>
            <span v-else>—</span>
          </template>
        </el-table-column>
        <el-table-column v-if="activeType === 'syndrome'" prop="category" label="分类" width="100" />
        <el-table-column v-if="activeType === 'tongue'" prop="aspect" label="舌象维度" width="100" />
        <el-table-column v-if="activeType === 'pulse'" prop="pulse_type" label="脉类" width="110" />
        <el-table-column v-if="activeType === 'herb_tag'" prop="category" label="维度" width="100" />
        <el-table-column prop="description" label="释义" min-width="220" show-overflow-tooltip />
        <el-table-column label="颜色" width="120" align="center">
          <template #default="{ row }">
            <span class="xw-tag" :style="tagChipStyle(row)">{{ row.name }}</span>
          </template>
        </el-table-column>
        <el-table-column label="启用" width="80" align="center">
          <template #default="{ row }">
            <el-tag :type="row.is_active ? 'success' : 'info'" size="small">{{ row.is_active ? '启用' : '停用' }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column v-if="editable" label="操作" width="150" fixed="right">
          <template #default="{ row }">
            <el-button size="small" @click="openEdit(row)">编辑</el-button>
            <el-button size="small" type="danger" @click="remove(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>

      <!-- 移动端卡片视图 -->
      <div v-if="isMobile" class="dict-cards">
        <div v-for="row in terms" :key="row.id" class="dict-card">
          <div class="card-head">
            <span class="card-name">{{ row.name }}</span>
            <el-tag :type="row.is_active ? 'success' : 'info'" size="small">{{ row.is_active ? '启用' : '停用' }}</el-tag>
          </div>

          <template v-if="activeType === 'syndrome'">
            <div class="card-row" v-if="(row.meridian || '').split(',').filter(Boolean).length">
              <span class="label">六经</span>
              <div class="value">
                <el-tag v-for="m in (row.meridian || '').split(',').filter(Boolean)" :key="m" size="small" type="info" effect="plain" style="margin-right:4px">{{ m }}</el-tag>
              </div>
            </div>
            <div class="card-row" v-if="row.category">
              <span class="label">分类</span><span class="value">{{ row.category }}</span>
            </div>
          </template>

          <div class="card-row" v-if="activeType === 'tongue' && row.aspect">
            <span class="label">维度</span><span class="value">{{ row.aspect }}</span>
          </div>
          <div class="card-row" v-if="activeType === 'pulse' && row.pulse_type">
            <span class="label">脉类</span><span class="value">{{ row.pulse_type }}</span>
          </div>
          <div class="card-row" v-if="activeType === 'herb_tag' && row.category">
            <span class="label">维度</span><span class="value">{{ row.category }}</span>
          </div>

          <div class="card-row" v-if="row.description">
            <span class="label">释义</span><span class="value">{{ row.description }}</span>
          </div>
          <div class="card-row">
            <span class="label">颜色</span>
            <span class="value"><span class="xw-tag" :style="tagChipStyle(row)">{{ row.name }}</span></span>
          </div>

          <div class="card-actions" v-if="editable">
            <el-button size="small" @click="openEdit(row)">编辑</el-button>
            <el-button size="small" type="danger" @click="remove(row)">删除</el-button>
          </div>
        </div>
        <el-empty v-if="!terms.length" description="暂无词条" />
      </div>
    </el-card>

    <el-dialog v-model="dialogVisible" :title="editingId ? '编辑词条' : '新增词条'" width="520px">
      <el-form :model="form" label-width="90px" label-position="top">
        <el-form-item label="词项名称" required>
          <el-input v-model="form.name" placeholder="如：舌质淡红 / 肝气犯胃证 / 弦脉" />
        </el-form-item>

        <template v-if="activeType === 'tongue'">
          <el-form-item label="舌象维度">
            <el-radio-group v-model="form.aspect">
              <el-radio-button value="舌质">舌质</el-radio-button>
              <el-radio-button value="舌苔">舌苔</el-radio-button>
            </el-radio-group>
          </el-form-item>
          <el-form-item label="附属特征">
            <el-input v-model="attributesText" placeholder="逗号分隔，如：颜色淡红,形态胖大" />
          </el-form-item>
        </template>

        <template v-else-if="activeType === 'syndrome'">
          <el-form-item label="六经归属">
            <el-select v-model="form.meridian" multiple clearable placeholder="可多选(合病/并病)" style="width:100%">
              <el-option v-for="m in meridians" :key="m" :label="m" :value="m" />
            </el-select>
            <div style="font-size:12px;color:#999;margin-top:4px;">合病证候可同时选择多个经，如太阳+少阳</div>
          </el-form-item>
          <el-form-item label="分类">
            <el-input v-model="form.category" placeholder="如：表证/里证/寒证/热证" />
          </el-form-item>
        </template>

        <template v-else-if="activeType === 'pulse'">
          <el-form-item label="脉类">
            <el-select v-model="form.pulse_type" clearable placeholder="选择脉类" style="width:100%">
              <el-option v-for="p in pulseTypes" :key="p" :label="p" :value="p" />
            </el-select>
          </el-form-item>
          <el-form-item label="临床主病">
            <el-input v-model="form.clinical_meaning" type="textarea" :rows="2" />
          </el-form-item>
        </template>

        <template v-else-if="activeType === 'herb_tag'">
          <el-form-item label="所属维度" required>
            <el-select v-model="form.category" clearable placeholder="选择维度" style="width:100%">
              <el-option v-for="d in herbTagDimensions" :key="d" :label="d" :value="d" />
            </el-select>
          </el-form-item>
        </template>

        <el-form-item label="释义">
          <el-input v-model="form.description" type="textarea" :rows="2" />
        </el-form-item>
        <el-form-item label="颜色">
          <el-color-picker v-model="form.color" />
          <span style="font-size:12px;color:#999;margin-left:8px;">自定义颜色：证型按六经本色、脉象按脉类、舌象按色/苔、药材性味按五行本色，留空则用对应默认色</span>
          <div style="margin-top:10px;display:flex;align-items:center;gap:8px;">
            <span class="xw-tag" :style="{ color: readableInk(previewColor), backgroundColor: previewColor, borderColor: readableInk(previewColor) }">{{ form.name || '预览' }}</span>
            <span v-if="!form.color" style="font-size:12px;color:#999;">（当前为默认色，保存后按此色着色）</span>
          </div>
        </el-form-item>
        <el-form-item label="启用">
          <el-switch v-model="form.is_active" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="save" :loading="saving">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted, onBeforeUnmount } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import api from '@/utils/api'
import { useAuthStore } from '@/store/auth'

// 游客只读：隐藏所有写操作
const auth = useAuthStore()
const editable = computed(() => !!auth.user?.is_admin)

// ---- 移动端适配 ----
const isMobile = ref(false)
function updateViewport() {
  isMobile.value = window.innerWidth < 768
}
onMounted(() => {
  updateViewport()
  window.addEventListener('resize', updateViewport)
})
onBeforeUnmount(() => window.removeEventListener('resize', updateViewport))

interface DictTerm {
  id: number
  term_type: string
  name: string
  description?: string | null
  meridian?: string | null
  category?: string | null
  aspect?: string | null
  attributes?: string[] | null
  pulse_type?: string | null
  clinical_meaning?: string | null
  color?: string | null
  is_active: boolean
}

const activeType = ref<'syndrome' | 'tongue' | 'pulse' | 'tag' | 'herb_tag'>('syndrome')
const terms = ref<DictTerm[]>([])
const meridians = ['太阳', '阳明', '少阳', '太阴', '少阴', '厥阴']
const pulseTypes = ['浮脉类', '沉脉类', '迟脉类', '数脉类', '虚脉类', '实脉类']
const herbTagDimensions = ['四气', '五味']
// 药材性味固定显示顺序：先四气后五味，组内按本草经梯度
const HERB_TAG_ORDER: Record<string, string[]> = {
  '四气': ['寒', '微寒', '平', '微温', '温'],
  '五味': ['酸', '苦', '甘', '辛', '咸', '淡'],
}
function sortHerbTag(list: any[]): any[] {
  return [...list].sort((a, b) => {
    const ca = herbTagDimensions.indexOf(a.category)
    const cb = herbTagDimensions.indexOf(b.category)
    if (ca !== cb) return ca - cb
    const oa = HERB_TAG_ORDER[a.category]?.indexOf(a.name) ?? 999
    const ob = HERB_TAG_ORDER[b.category]?.indexOf(b.name) ?? 999
    return oa - ob
  })
}

// 默认色（无自定义色时回退，让本色直接亮出来）：
// 证型=六经五色(太阳寒水黑蓝/阳明燥金白/少阳相火红/太阴湿土黄/少阴君火紫/厥阴风木青)
// 脉象=脉类(浮表青蓝/沉里黑/迟寒蓝/数热红/虚灰/实棕红/滑痰饮黄/涩血瘀紫/弦肝胆青绿/洪热盛橙/细血虚淡粉/缓湿黄褐/微浅灰/紧寒束深蓝)
// 舌象=色/苔关键词(绛深红/紫青紫/青木青/红赤/淡蓝灰/白/黄/灰/黑/少无花灰/滑浅蓝)
// 药材性味=五行本色(酸青苦赤甘黄辛白咸黑；四气寒蓝→温红)
const SYNDROME_MERIDIAN_COLOR: Record<string, string> = {
  '太阳': '#2c3e50', '阳明': '#cfd8dc', '少阳': '#d9434e',
  '太阴': '#e0a82e', '少阴': '#8e44ad', '厥阴': '#2e9e5b',
}
const PULSE_TYPE_COLOR: Record<string, string> = {
  '浮脉类': '#3498db', '沉脉类': '#2c3e50', '迟脉类': '#2980b9', '数脉类': '#d9434e',
  '虚脉类': '#95a5a6', '实脉类': '#a93226', '滑脉类': '#e0a82e', '涩脉类': '#8e44ad',
  '弦脉类': '#16a085', '洪脉类': '#e67e22', '细脉类': '#d988a0', '缓脉类': '#b9770e',
  '微脉类': '#bdc3c7', '紧脉类': '#1f618d',
}
const TONGUE_KEYWORD_COLOR: [string, string][] = [
  ['绛', '#a93226'], ['紫', '#8e44ad'], ['青', '#2e9e5b'], ['红', '#d9434e'],
  ['淡', '#aebfd0'], ['白', '#cfd8dc'], ['黄', '#e0a82e'], ['灰', '#7f8c8d'],
  ['黑', '#2c3e50'], ['少', '#95a5a6'], ['无', '#95a5a6'], ['花', '#95a5a6'], ['滑', '#aed6f1'],
]
const HERB_TAG_DEFAULT_COLOR: Record<string, string> = {
  '酸': '#2e9e5b', '苦': '#d9434e', '甘': '#e0a82e', '辛': '#9fb3c8', '咸': '#2f3b47', '淡': '#b0a0c0',
  '寒': '#2f80b5', '微寒': '#5aa0cf', '平': '#7f9a6e', '微温': '#e08a3c', '温': '#d9642c', '热': '#c0392b',
}
function tongueColor(name: string): string {
  for (const [kw, col] of TONGUE_KEYWORD_COLOR) if (name.includes(kw)) return col
  return '#909399'
}
// 依据颜色亮度返回可读前景色（浅色用深字/深边框，深色用浅字），避免白色等浅色导致标签不可见
function readableInk(hex: string): string {
  const c = (hex || '').replace('#', '')
  if (c.length < 6) return '#333333'
  const r = parseInt(c.slice(0, 2), 16)
  const g = parseInt(c.slice(2, 4), 16)
  const b = parseInt(c.slice(4, 6), 16)
  const L = (0.299 * r + 0.587 * g + 0.114 * b) / 255
  return L > 0.6 ? '#333333' : '#ffffff'
}
function defaultColorForTerm(term: any): string {
  const t = term?.term_type || activeType.value
  if (t === 'herb_tag') return HERB_TAG_DEFAULT_COLOR[term?.name] || '#909399'
  if (t === 'syndrome') {
    const m = (term?.meridian || '').split(',')[0]?.trim()
    return SYNDROME_MERIDIAN_COLOR[m] || '#7f8c8d'
  }
  if (t === 'pulse') return PULSE_TYPE_COLOR[term?.pulse_type] || '#7f8c8d'
  if (t === 'tongue') return tongueColor(term?.name || '')
  return '#909399'
}
function tagChipStyle(term: any): Record<string, string> {
  const c = term?.color || defaultColorForTerm(term)
  const ink = readableInk(c)
  return { color: ink, backgroundColor: c, borderColor: ink }
}
// 编辑弹窗实时预览色：自定义色优先，否则按类型回退默认色
const previewColor = computed(() => {
  if (form.color) return form.color
  if (activeType.value === 'herb_tag') return HERB_TAG_DEFAULT_COLOR[form.name] || '#909399'
  if (activeType.value === 'syndrome') return SYNDROME_MERIDIAN_COLOR[(form.meridian || [])[0]] || '#7f8c8d'
  if (activeType.value === 'pulse') return PULSE_TYPE_COLOR[form.pulse_type] || '#7f8c8d'
  if (activeType.value === 'tongue') return tongueColor(form.name)
  return '#909399'
})

const dialogVisible = ref(false)
const editingId = ref<number | null>(null)
const saving = ref(false)
const form = reactive<any>({
  term_type: 'syndrome', name: '', description: '',
  meridian: [], category: null, aspect: '舌质', attributes: null,
  pulse_type: null, clinical_meaning: null, color: null, is_active: true,
})
const attributesText = ref('')

async function loadTerms() {
  try {
    const res = await api.get('/dictionaries', { params: { term_type: activeType.value } }) as any
    let data = Array.isArray(res) ? res : []
    if (activeType.value === 'herb_tag') data = sortHerbTag(data)
    terms.value = data
  } catch {
    ElMessage.error('加载字典失败')
  }
}

function resetForm() {
  form.term_type = activeType.value
  form.name = ''
  form.description = ''
  form.meridian = []
  form.category = null
  form.aspect = '舌质'
  form.attributes = null
  form.pulse_type = null
  form.clinical_meaning = null
  form.color = null
  form.is_active = true
  attributesText.value = ''
}

function openCreate() {
  resetForm()
  editingId.value = null
  dialogVisible.value = true
}

function openEdit(row: DictTerm) {
  resetForm()
  Object.assign(form, {
    term_type: row.term_type, name: row.name, description: row.description || '',
    meridian: (row.meridian || '').split(',').filter(Boolean), category: row.category, aspect: row.aspect || '舌质',
    attributes: row.attributes, pulse_type: row.pulse_type,
    clinical_meaning: row.clinical_meaning, color: row.color || null, is_active: row.is_active,
  })
  if (row.term_type === 'tongue' && Array.isArray(row.attributes)) {
    attributesText.value = row.attributes.join(',')
  }
  editingId.value = row.id
  dialogVisible.value = true
}

async function save() {
  if (!form.name.trim()) {
    ElMessage.warning('请填写词项名称')
    return
  }
  saving.value = true
  try {
    const payload: any = {
      term_type: form.term_type,
      name: form.name.trim(),
      description: form.description || null,
      is_active: form.is_active,
    }
    if (form.term_type === 'tongue') {
      payload.aspect = form.aspect || '舌质'
      payload.attributes = attributesText.value
        ? attributesText.value.split(/[,，]/).map((s: string) => s.trim()).filter(Boolean)
        : null
    } else if (form.term_type === 'syndrome') {
      payload.meridian = form.meridian.length ? form.meridian.join(',') : null
      payload.category = form.category || null
    } else if (form.term_type === 'herb_tag') {
      payload.category = form.category || null
    } else {
      payload.pulse_type = form.pulse_type || null
      payload.clinical_meaning = form.clinical_meaning || null
    }
    payload.color = form.color || null
    if (editingId.value) {
      await api.put(`/dictionaries/${editingId.value}`, payload)
    } else {
      await api.post('/dictionaries', payload)
    }
    ElMessage.success('已保存')
    dialogVisible.value = false
    await loadTerms()
  } catch {
    ElMessage.error('保存失败')
  }
  saving.value = false
}

async function remove(row: DictTerm) {
  try {
    await ElMessageBox.confirm(`确定删除词条「${row.name}」？`, '提示', { type: 'warning' })
  } catch { return }
  try {
    await api.delete(`/dictionaries/${row.id}`)
    ElMessage.success('已删除')
    await loadTerms()
  } catch {
    ElMessage.error('删除失败')
  }
}

onMounted(loadTerms)
</script>

<style scoped>
/* ---- 移动端卡片视图 ---- */
.dict-cards {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.dict-card {
  background: #fff;
  border: 1px solid #e8e0d8;
  border-radius: 10px;
  padding: 12px 14px;
  box-shadow: 0 1px 3px rgba(0,0,0,0.05);
}
.dict-card .card-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  margin-bottom: 8px;
}
.dict-card .card-name { font-size: 16px; font-weight: 600; color: #2C1810; }
.dict-card .card-row {
  display: flex;
  align-items: flex-start;
  font-size: 14px;
  line-height: 1.5;
  margin-top: 4px;
}
.dict-card .card-row .label { flex-shrink: 0; width: 40px; color: #8a7563; }
.dict-card .card-row .value { flex: 1; color: #333; word-break: break-all; }
.color-dot {
  display: inline-block;
  width: 16px;
  height: 16px;
  border-radius: 50%;
  border: 1px solid #dcdfe6;
  vertical-align: middle;
}
.xw-tag {
  display: inline-block;
  padding: 0 8px;
  font-size: 12px;
  line-height: 20px;
  border: 1px solid;
  border-radius: 10px;
  white-space: nowrap;
}
.dict-card .card-actions {
  display: flex;
  justify-content: flex-end;
  gap: 6px;
  margin-top: 8px;
  padding-top: 8px;
  border-top: 1px dashed #eee;
}

/* ---- 移动端：词典切换标签自适应滚动 ---- */
@media (max-width: 767px) {
  :deep(.el-radio-group) {
    display: flex;
    width: 100%;
  }
  :deep(.el-radio-group .el-radio-button) {
    flex: 1;
  }
  :deep(.el-radio-group .el-radio-button .el-radio-button__inner) {
    width: 100%;
    overflow: hidden;
    white-space: nowrap;
    text-overflow: ellipsis;
  }
}
</style>