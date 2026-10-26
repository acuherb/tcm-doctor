<template>
  <div class="dictionary-manage">
    <el-card shadow="hover">
      <template #header>
        <div style="display:flex;justify-content:space-between;align-items:center;">
          <span>🗂️ 主数据字典</span>
          <el-button v-if="editable" type="primary" size="small" @click="openCreate">＋ 新增词条</el-button>
        </div>
      </template>

      <el-radio-group v-model="activeType" @change="loadTerms" style="margin-bottom:16px">
        <el-radio-button value="syndrome">证型</el-radio-button>
        <el-radio-button value="tongue">舌象</el-radio-button>
        <el-radio-button value="pulse">脉象</el-radio-button>
      </el-radio-group>

      <el-table :data="terms" border stripe>
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
        <el-table-column prop="description" label="释义" min-width="220" show-overflow-tooltip />
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

        <template v-else>
          <el-form-item label="脉类">
            <el-select v-model="form.pulse_type" clearable placeholder="选择脉类" style="width:100%">
              <el-option v-for="p in pulseTypes" :key="p" :label="p" :value="p" />
            </el-select>
          </el-form-item>
          <el-form-item label="临床主病">
            <el-input v-model="form.clinical_meaning" type="textarea" :rows="2" />
          </el-form-item>
        </template>

        <el-form-item label="释义">
          <el-input v-model="form.description" type="textarea" :rows="2" />
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
import { ref, reactive, computed, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import api from '@/utils/api'
import { useAuthStore } from '@/store/auth'

// 游客只读：隐藏所有写操作
const auth = useAuthStore()
const editable = computed(() => !!auth.user?.is_admin)

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
  is_active: boolean
}

const activeType = ref<'syndrome' | 'tongue' | 'pulse'>('syndrome')
const terms = ref<DictTerm[]>([])
const meridians = ['太阳', '阳明', '少阳', '太阴', '少阴', '厥阴']
const pulseTypes = ['浮脉类', '沉脉类', '迟脉类', '数脉类', '虚脉类', '实脉类']

const dialogVisible = ref(false)
const editingId = ref<number | null>(null)
const saving = ref(false)
const form = reactive<any>({
  term_type: 'syndrome', name: '', description: '',
  meridian: [], category: null, aspect: '舌质', attributes: null,
  pulse_type: null, clinical_meaning: null, is_active: true,
})
const attributesText = ref('')

async function loadTerms() {
  try {
    const res = await api.get('/dictionaries', { params: { term_type: activeType.value } }) as any
    terms.value = Array.isArray(res) ? res : []
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
    clinical_meaning: row.clinical_meaning, is_active: row.is_active,
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
    } else {
      payload.pulse_type = form.pulse_type || null
      payload.clinical_meaning = form.clinical_meaning || null
    }
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