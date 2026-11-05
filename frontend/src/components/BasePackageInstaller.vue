<template>
  <el-dialog v-model="visible" title="安装中医基础数据包" width="720px" destroy-on-close>
    <el-alert type="info" :closable="false" show-icon class="bundle-tip"
      title="开箱引导"
      description="数据包仅写入药材、穴位、方库、医籍等参考知识表，不会改动患者、处方、库存等业务数据；导入为幂等 upsert，重复安装不会重复。" />

    <el-form label-position="top" class="bundle-form">
      <el-form-item label="数据来源">
        <el-radio-group v-model="source" @change="resetPreview">
          <el-radio value="bundled" :disabled="!bundles.length">随应用附带的数据包</el-radio>
          <el-radio value="upload">上传 .zip 数据包</el-radio>
        </el-radio-group>
      </el-form-item>

      <el-form-item v-if="source === 'bundled'" label="数据包">
        <el-select v-model="selectedBundle" style="width: 100%" @change="onBundleChange">
          <el-option v-for="b in bundles" :key="b.name"
            :label="`${b.title} v${b.version}（${formatSize(b.size)}）`" :value="b.name" />
        </el-select>
        <div v-if="!bundles.length" class="bundle-hint">
          当前安装未附带数据包，请切换到「上传 .zip 数据包」，从项目 Releases 下载后安装。
        </div>
      </el-form-item>

      <el-form-item v-else label="数据包文件">
        <el-upload :auto-upload="false" :show-file-list="true" :limit="1" accept=".zip"
          :on-change="onFileChange" :on-remove="onFileRemove">
          <el-button><el-icon><Upload /></el-icon> 选择 .zip 文件</el-button>
        </el-upload>
      </el-form-item>

      <el-form-item v-if="layerOptions.length" label="安装内容（依赖层会自动补上）">
        <el-checkbox-group v-model="selectedLayers">
          <el-checkbox v-for="l in layerOptions" :key="l.name" :value="l.name">
            {{ l.label }}（{{ l.count }} 条）
          </el-checkbox>
        </el-checkbox-group>
      </el-form-item>
    </el-form>

    <div class="bundle-actions">
      <el-button @click="doPreview" :loading="previewing" :disabled="!canSubmit">
        预检（不写入）
      </el-button>
      <el-button type="primary" @click="doInstall" :loading="installing" :disabled="!canInstall">
        确认安装
      </el-button>
    </div>

    <template v-if="preview">
      <el-alert type="success" :closable="false" show-icon class="bundle-result"
        :title="`预检完成：将新增 ${preview.totals.added} 条、更新 ${preview.totals.updated} 条、跳过 ${preview.totals.skipped} 条`"
        :description="`执行顺序：${preview.order.join(' → ')}${preview.warnings.length ? '；注意：' + preview.warnings.join('；') : ''}`" />
      <el-table :data="preview.files" size="small" max-height="220" class="bundle-table">
        <el-table-column prop="layer" label="分层" width="100" />
        <el-table-column prop="file" label="文件" min-width="200" show-overflow-tooltip />
        <el-table-column prop="count" label="条目" width="80" />
        <el-table-column label="校验" width="90">
          <template #default="{ row }">
            <el-tag :type="row.sha256_verified ? 'success' : 'info'" size="small" effect="plain">
              {{ row.sha256_verified ? '通过' : '未声明' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="added" label="新增" width="70" />
        <el-table-column prop="updated" label="更新" width="70" />
        <el-table-column prop="skipped" label="跳过" width="70" />
      </el-table>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { ElMessage, ElMessageBox, type UploadFile } from 'element-plus'
import { Upload } from '@element-plus/icons-vue'
import api, { errMsg } from '@/utils/api'

interface LayerInfo { name: string; label: string; depends_on: string[]; types?: string[]; count: number }
interface BundleInfo {
  name: string; size: number; title: string; version: string; source: string;
  schema_version: number; layers: LayerInfo[]
}
interface BundleResult {
  dry_run: boolean
  manifest: { package: string; title: string; version: string; source: string; schema_version: number }
  order: string[]
  layers: LayerInfo[]
  warnings: string[]
  totals: { added: number; updated: number; skipped: number }
  files: Array<{
    layer: string; file: string; type: string; count: number; sha256_verified: boolean;
    added: number; updated: number; skipped: number
  }>
  errors: string[]
}

const props = defineProps<{ modelValue: boolean }>()
const emit = defineEmits<{
  'update:modelValue': [value: boolean]
  installed: []
}>()
const visible = computed({
  get: () => props.modelValue,
  set: (v: boolean) => emit('update:modelValue', v),
})

const bundles = ref<BundleInfo[]>([])
const selectedBundle = ref('')
const source = ref<'bundled' | 'upload'>('bundled')
const zipFile = ref<File | null>(null)
const selectedLayers = ref<string[]>([])
const uploadLayers = ref<LayerInfo[]>([])
const preview = ref<BundleResult | null>(null)
const previewLayersKey = ref('')
const previewing = ref(false)
const installing = ref(false)

const layerOptions = computed<LayerInfo[]>(() => {
  if (source.value === 'upload') return uploadLayers.value
  const b = bundles.value.find((x) => x.name === selectedBundle.value)
  return b?.layers || []
})
const canSubmit = computed(() => source.value === 'bundled' ? !!selectedBundle.value : !!zipFile.value)
const canInstall = computed(() =>
  !!preview.value && previewLayersKey.value === selectedLayers.value.join(',')
)

function formatSize(n: number): string {
  return n < 1024 * 1024 ? `${(n / 1024).toFixed(1)} KB` : `${(n / 1024 / 1024).toFixed(1)} MB`
}

function resetPreview() {
  preview.value = null
  previewLayersKey.value = ''
}

function onBundleChange() {
  resetPreview()
  selectedLayers.value = layerOptions.value.map((l) => l.name)
}

function onFileChange(file: UploadFile) {
  zipFile.value = file.raw || null
  resetPreview()
  uploadLayers.value = []
  selectedLayers.value = []
}

function onFileRemove() {
  zipFile.value = null
  resetPreview()
  uploadLayers.value = []
  selectedLayers.value = []
}

async function loadBundles() {
  resetPreview()
  try {
    const res = await api.get<{ packages: BundleInfo[] }>('/templates/bundles', { silent: true })
    bundles.value = res.packages || []
    source.value = bundles.value.length ? 'bundled' : 'upload'
    selectedBundle.value = bundles.value[0]?.name || ''
    selectedLayers.value = bundles.value[0]?.layers.map((l) => l.name) || []
  } catch {
    bundles.value = []
    source.value = 'upload'
  }
}

watch(visible, (open) => {
  if (open) void loadBundles()
})

function buildRequest(path: string): { url: string; data: FormData } {
  const params = new URLSearchParams()
  params.set('use_bundled', String(source.value === 'bundled'))
  if (source.value === 'bundled') params.set('name', selectedBundle.value)
  const layers = selectedLayers.value.join(',')
  if (layers) params.set('layers', layers)
  const data = new FormData()
  if (source.value === 'upload' && zipFile.value) data.append('file', zipFile.value)
  return { url: `${path}?${params.toString()}`, data }
}

async function doPreview() {
  previewing.value = true
  try {
    const { url, data } = buildRequest('/templates/bundle/preview')
    const res = await api.post<BundleResult>(url, data, { silent: true })
    if (source.value === 'upload' && !uploadLayers.value.length) {
      uploadLayers.value = res.layers.map((l) => ({ ...l, depends_on: l.depends_on || [] }))
    }
    if (!selectedLayers.value.length) selectedLayers.value = res.order.slice()
    preview.value = res
    previewLayersKey.value = selectedLayers.value.join(',')
  } catch (e) {
    resetPreview()
    ElMessage.error('预检失败：' + errMsg(e))
  } finally {
    previewing.value = false
  }
}

async function doInstall() {
  if (!preview.value) return
  const p = preview.value
  try {
    await ElMessageBox.confirm(
      `将新增 ${p.totals.added} 条、更新 ${p.totals.updated} 条、跳过 ${p.totals.skipped} 条。确认安装？`,
      '安装确认', { confirmButtonText: '确认安装', cancelButtonText: '取消', type: 'warning' },
    )
  } catch {
    return
  }
  installing.value = true
  try {
    const { url, data } = buildRequest('/templates/bundle/install')
    const res = await api.post<BundleResult>(url, data, { silent: true })
    ElMessage.success(
      `安装完成：新增 ${res.totals.added}，更新 ${res.totals.updated}，跳过 ${res.totals.skipped}`,
    )
    emit('installed')
    visible.value = false
  } catch (e) {
    ElMessage.error('安装失败：' + errMsg(e))
  } finally {
    installing.value = false
  }
}
</script>

<style scoped lang="scss">
.bundle-tip { margin-bottom: 16px; }
.bundle-form { :deep(.el-form-item) { margin-bottom: 14px; } }
.bundle-hint { font-size: 12px; color: #a39484; margin-top: 6px; line-height: 1.6; }
.bundle-actions { display: flex; justify-content: flex-end; gap: 10px; margin-top: 4px; }
.bundle-result { margin: 16px 0 10px; }
.bundle-table { width: 100%; }
</style>
