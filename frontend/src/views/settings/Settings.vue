<template>
  <div class="settings-page">
    <el-row :gutter="20">
      <el-col :xs="24" :span="12">
        <el-card shadow="hover" class="clinic-card main-card">
          <template #header>
            <div class="card-head-bar">
              <div class="card-head-title">
                <span class="head-icon">🏥</span>
                <span class="head-text">诊所信息</span>
                <el-tag v-if="!editable" size="small" type="info" effect="plain" round class="head-count">只读</el-tag>
              </div>
            </div>
          </template>

          <div class="clinic-brand" :class="{ 'is-readonly': !editable }">
            <div class="clinic-logo-wrap">
              <img v-if="clinicLogo" :src="clinicLogo" class="clinic-logo" alt="诊所Logo" />
              <div v-else class="clinic-logo is-empty">
                <el-icon :size="26"><OfficeBuilding /></el-icon>
              </div>
            </div>
            <div class="clinic-brand-text">
              <div class="clinic-brand-name">{{ clinicName || '未命名诊所' }}</div>
              <div class="clinic-brand-sub">此名称与 Logo 将用于处方笺打印抬头</div>
              <div v-if="editable" class="clinic-logo-actions">
                <el-upload :auto-upload="false" :show-file-list="false" accept="image/*" :limit="1" @change="onLogoChange">
                  <el-button size="small" type="primary" plain>上传 Logo</el-button>
                </el-upload>
                <el-button v-if="clinicLogo" size="small" text type="danger" @click="clinicLogo = ''">移除</el-button>
              </div>
            </div>
          </div>

          <el-divider />

          <el-form label-width="100px">
            <el-form-item label="诊所名称">
              <el-input v-model="clinicName" placeholder="如 张氏中医馆" :disabled="!editable" />
            </el-form-item>
            <el-form-item label="医师署名" class="doctor-hint-item">
              <div class="doctor-hint">
                <el-icon><InfoFilled /></el-icon>
                <span>处方打印的医师署名取<i>开方账号</i>的显示名称，请到「账号管理」维护。</span>
              </div>
            </el-form-item>
            <el-form-item v-if="editable">
              <el-button type="primary" @click="saveClinic" :loading="savingClinic">保存诊所信息</el-button>
            </el-form-item>
            <el-form-item v-else>
              <div class="doctor-hint">
                <el-icon><Lock /></el-icon>
                <span>游客模式：诊所信息只读，如需修改请用管理员登录。</span>
              </div>
            </el-form-item>
          </el-form>
        </el-card>
      </el-col>

      <el-col :xs="24" :span="12">
        <el-card shadow="hover" class="main-card">
          <template #header>
            <div class="card-head-bar">
              <div class="card-head-title">
                <span class="head-icon">🤖</span>
                <span class="head-text">AI 配置</span>
                <el-tag v-if="hasKey" size="small" type="success" effect="plain" round class="head-count">已配置</el-tag>
                <el-tag v-else size="small" type="info" effect="plain" round class="head-count">未配置</el-tag>
              </div>
              <div class="card-actions">
                <span class="conn-pill" :class="`is-${connectionStatus.type}`">{{ connectionStatus.text }}</span>
              </div>
            </div>
          </template>

          <el-form label-width="100px" class="config-form">
            <div class="form-section-title">
              <span class="sec-dot is-chat"></span>对话模型
            </div>
            <el-form-item label="API Key">
              <el-input v-model="deepseekKey" type="password" show-password autocomplete="new-password" :placeholder="hasKey ? '已配置，输入新值可替换' : '输入 API Key'" />
            </el-form-item>
            <el-form-item label="对话模型">
              <el-select v-model="deepseekModel" class="full-width">
                <el-option label="deepseek-chat" value="deepseek-chat" />
                <el-option label="deepseek-reasoner" value="deepseek-reasoner" />
                <el-option label="deepseek-v4-pro" value="deepseek-v4-pro" />
                <el-option label="deepseek-v4-flash" value="deepseek-v4-flash" />
              </el-select>
            </el-form-item>
            <el-form-item label="Base URL">
              <el-input v-model="deepseekBaseUrl" placeholder="https://api.deepseek.com" />
            </el-form-item>

            <div class="form-section-title">
              <span class="sec-dot is-vision"></span>图片识别
              <el-tag v-if="visionConfigured" size="small" type="success" effect="plain" round>已启用</el-tag>
              <el-tag v-else size="small" type="warning" effect="plain" round>未启用</el-tag>
            </div>
            <div class="section-hint">
              <el-icon><InfoFilled /></el-icon>
              <span>DeepSeek 官方 API 不支持图片识别，需配置第三方 Vision 端点（如硅基流动）</span>
            </div>
            <el-form-item label="Vision 模型">
              <el-input v-model="visionModel" placeholder="如 Pro/deepseek-ai/DeepSeek-VL2" />
            </el-form-item>
            <el-form-item label="Vision URL">
              <el-input v-model="visionBaseUrl" placeholder="如 https://api.siliconflow.cn/v1" />
            </el-form-item>
            <el-form-item label="Vision Key">
              <el-input v-model="visionKey" type="password" show-password autocomplete="new-password" :placeholder="hasVisionKey ? '已配置，输入新值可替换' : '留空则复用上方 API Key'" />
            </el-form-item>

            <div class="config-footer">
              <div v-if="editable" class="footer-actions">
                <el-button type="primary" @click="saveConfig" :loading="savingConfig">保存配置</el-button>
                <el-button @click="testConnection" :loading="testing">测试连接</el-button>
              </div>
              <el-tag v-else type="info" size="small" effect="plain" round>游客模式：AI 配置只读</el-tag>
            </div>
          </el-form>
        </el-card>
      </el-col>
    </el-row>

    <el-row :gutter="20" class="settings-row">
      <el-col :xs="24" :span="12">
        <el-card shadow="hover" class="main-card">
          <template #header>
            <div class="card-head-bar">
              <div class="card-head-title">
                <span class="head-icon">💾</span>
                <span class="head-text">数据管理</span>
              </div>
            </div>
          </template>
          <el-form label-width="100px" class="config-form">
            <el-form-item label="数据备份">
              <div class="row-action">
                <el-button v-if="editable" type="primary" plain @click="exportData" :loading="exporting">
                  <el-icon><Download /></el-icon>导出备份
                </el-button>
                <span class="row-hint">导出为 SQLite 数据库文件</span>
              </div>
            </el-form-item>
            <el-form-item label="基础数据包">
              <div class="row-action">
                <el-button v-if="editable" plain @click="installerVisible = true">
                  <el-icon><Upload /></el-icon> 一键安装
                </el-button>
                <span class="row-hint">按清单导入药材 / 穴位 / 方库 / 医籍，先预检再写入</span>
              </div>
            </el-form-item>
            <el-form-item v-if="editable" label="数据恢复">
              <div class="row-action">
                <el-upload :auto-upload="false" :show-file-list="false" accept=".db,.json" @change="onImportFile">
                  <el-button type="warning" plain>
                    <el-icon><Upload /></el-icon>导入恢复
                  </el-button>
                </el-upload>
                <span class="row-hint">选择备份文件覆盖当前数据</span>
              </div>
            </el-form-item>
            <el-form-item v-if="editable" label="重置数据">
              <div class="row-action">
                <el-popconfirm title="确定要清空所有数据？此操作不可撤销！" @confirm="resetData">
                  <template #reference>
                    <el-button type="danger" plain>清空数据库</el-button>
                  </template>
                </el-popconfirm>
                <span class="row-hint">清空后不可恢复，请先备份</span>
              </div>
            </el-form-item>
          </el-form>
        </el-card>
      </el-col>

      <el-col :xs="24" :span="12">
        <el-card shadow="hover" class="main-card">
          <template #header>
            <div class="card-head-bar">
              <div class="card-head-title">
                <span class="head-icon">ℹ️</span>
                <span class="head-text">系统信息</span>
              </div>
            </div>
          </template>
          <el-descriptions :column="1" border class="sys-desc">
            <el-descriptions-item label="应用名称">中医诊所管理平台</el-descriptions-item>
            <el-descriptions-item label="版本">{{ appVersion ? 'v' + appVersion : '未获取' }}</el-descriptions-item>
            <el-descriptions-item label="技术栈">Electron + FastAPI + Vue3</el-descriptions-item>
            <el-descriptions-item label="数据库路径">
              <span class="mono">{{ dbPath || '未知' }}</span>
            </el-descriptions-item>
            <el-descriptions-item label="数据概览">
              <div class="count-chips">
                <span class="count-chip">患者 <b>{{ counts.patients || 0 }}</b></span>
                <span class="count-chip">就诊 <b>{{ counts.visits || 0 }}</b></span>
                <span class="count-chip">随访 <b>{{ counts.followups || 0 }}</b></span>
                <span class="count-chip">处方 <b>{{ counts.prescriptions || 0 }}</b></span>
                <span class="count-chip">问诊 <b>{{ counts.inquiries || 0 }}</b></span>
              </div>
            </el-descriptions-item>
            <el-descriptions-item label="AI 引擎">
              <span class="status-retest" @click="testConnection" title="点击重新测试 DeepSeek 连接">
                <el-tag :type="aiEngineStatus.type" size="small" effect="light" round>{{ aiEngineStatus.text }}</el-tag>
                <span class="retest-hint">重新测试</span>
              </span>
            </el-descriptions-item>
            <el-descriptions-item label="向量库">
              <el-tag :type="vectorAvailable ? 'success' : 'info'" size="small" effect="light" round>
                {{ vectorAvailable ? 'ChromaDB 已启用' : 'ChromaDB 未安装' }}
              </el-tag>
            </el-descriptions-item>
          </el-descriptions>
        </el-card>
      </el-col>
    </el-row>

    <el-row :gutter="20" class="settings-row">
      <el-col :xs="24" :span="24">
        <el-card shadow="hover" class="main-card">
          <template #header>
            <div class="card-head-bar">
              <div class="card-head-title">
                <span class="head-icon">🕒</span>
                <span class="head-text">自动备份</span>
              </div>
              <div class="card-actions">
                <el-button v-if="editable" size="small" @click="runAutoBackup" :loading="backupRunning">
                  <el-icon><Refresh /></el-icon> 立即备份
                </el-button>
                <el-button v-if="editable" type="primary" size="small" @click="saveAutoBackup" :loading="backupSaving">
                  保存设置
                </el-button>
              </div>
            </div>
          </template>

          <el-form label-width="100px" class="config-form">
            <el-form-item label="定时备份">
              <div class="row-action">
                <el-switch v-model="backupEnabled" :disabled="!editable" />
                <span class="row-hint">开启后每次启动先留一份快照，之后按间隔自动备份</span>
              </div>
            </el-form-item>
            <el-form-item label="备份间隔">
              <div class="row-action">
                <el-input-number v-model="backupInterval" :min="1" :max="720" :disabled="!editable" controls-position="right" />
                <span class="row-hint">小时（默认 24 小时）</span>
              </div>
            </el-form-item>
            <el-form-item label="保留份数">
              <div class="row-action">
                <el-input-number v-model="backupKeep" :min="1" :max="100" :disabled="!editable" controls-position="right" />
                <span class="row-hint">超出的旧快照自动删除，至少保留 1 份</span>
              </div>
            </el-form-item>
          </el-form>

          <el-alert type="info" :closable="false" show-icon
            :description="`备份目录：${backupDir || '—'}　最近备份：${backupLast || '暂无'}　共 ${backupItems.length} 份`" />

          <el-table v-if="backupItems.length" :data="backupItems" size="small" class="backup-table" max-height="260">
            <el-table-column prop="created_at" label="备份时间" width="180" />
            <el-table-column prop="name" label="文件名" min-width="220" show-overflow-tooltip />
            <el-table-column label="大小" width="110">
              <template #default="{ row }">{{ formatSize(row.size) }}</template>
            </el-table-column>
            <el-table-column label="操作" width="100">
              <template #default="{ row }">
                <el-button link type="primary" size="small" @click="downloadAutoBackup(row.name)">下载</el-button>
              </template>
            </el-table-column>
          </el-table>
          <el-empty v-else description="暂无自动备份快照" :image-size="60" />
        </el-card>
      </el-col>
    </el-row>

    <el-row :gutter="20" class="settings-row">
      <el-col :xs="24" :span="24">
        <el-card shadow="hover" class="main-card">
          <template #header>
            <div class="card-head-bar">
              <div class="card-head-title">
                <span class="head-icon">💰</span>
                <span class="head-text">AI 计费单价</span>
                <el-tag v-if="pricingConfigured" size="small" type="success" effect="plain" round class="head-count">已配置</el-tag>
                <el-tag v-else size="small" type="info" effect="plain" round class="head-count">未配置</el-tag>
              </div>
            </div>
          </template>

          <div class="section-hint">
            <el-icon><InfoFilled /></el-icon>
            <span>单位：元 / 百万 tokens。用于「AI 用量与成本」看板的<strong>估算</strong>费用，仅统计本功能启用后的调用，历史用量无法回溯；最终以服务商账单为准。</span>
          </div>
          <el-form label-width="150px" class="config-form">
            <div class="form-section-title"><span class="sec-dot is-chat"></span>对话模型</div>
            <el-row :gutter="12">
              <el-col :xs="24" :sm="8">
                <el-form-item label="输入（未缓存）">
                  <el-input-number v-model="priceInput" :min="0" :precision="2" :step="0.5" :disabled="!editable" controls-position="right" class="full-width" />
                </el-form-item>
              </el-col>
              <el-col :xs="24" :sm="8">
                <el-form-item label="输入（缓存命中）">
                  <el-input-number v-model="priceCacheHit" :min="0" :precision="2" :step="0.1" :disabled="!editable" controls-position="right" class="full-width" />
                </el-form-item>
              </el-col>
              <el-col :xs="24" :sm="8">
                <el-form-item label="输出">
                  <el-input-number v-model="priceOutput" :min="0" :precision="2" :step="0.5" :disabled="!editable" controls-position="right" class="full-width" />
                </el-form-item>
              </el-col>
            </el-row>

            <div class="form-section-title"><span class="sec-dot is-vision"></span>图片识别（Vision，第三方端点）</div>
            <el-row :gutter="12">
              <el-col :xs="24" :sm="8">
                <el-form-item label="输入">
                  <el-input-number v-model="priceVisionInput" :min="0" :precision="2" :step="0.5" :disabled="!editable" controls-position="right" class="full-width" />
                </el-form-item>
              </el-col>
              <el-col :xs="24" :sm="8">
                <el-form-item label="输出">
                  <el-input-number v-model="priceVisionOutput" :min="0" :precision="2" :step="0.5" :disabled="!editable" controls-position="right" class="full-width" />
                </el-form-item>
              </el-col>
            </el-row>
            <div class="section-hint">
              <el-icon><InfoFilled /></el-icon>
              <span>请按服务商<strong>当前实际单价</strong>填写（DeepSeek 对缓存命中的输入单独计价，价格会调整）；全部填 0 表示仅统计 token 用量、不估算费用。</span>
            </div>
            <div v-if="editable" class="config-footer">
              <div class="footer-actions">
                <el-button type="primary" :loading="savingPricing" @click="savePricing">保存单价</el-button>
              </div>
            </div>
          </el-form>
        </el-card>
      </el-col>
    </el-row>

    <BasePackageInstaller v-model="installerVisible" @installed="onInstalled" />
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { ElMessage, ElMessageBox, type UploadFile } from 'element-plus'
import { Download, Upload, Refresh, OfficeBuilding, InfoFilled, Lock } from '@element-plus/icons-vue'
import api, { errMsg } from '@/utils/api'
import { applyBranding } from '@/utils/branding'
import { refreshDictColors } from '@/utils/dictColors'
import { compressToDataUrl } from '@/utils/image'
import type { AppConfig } from '@/types'
import { useAuthStore } from '@/store/auth'
import BasePackageInstaller from '@/components/BasePackageInstaller.vue'

// 游客（非管理员）隐藏所有写操作，只读浏览
const auth = useAuthStore()
const editable = computed(() => auth.can('system:write'))
const installerVisible = ref(false)

async function onInstalled() {
  // 基础数据包写入字典/物品后，共享缓存仍是安装前的旧数据，需主动失效并重取统计
  refreshDictColors()
  try {
    const res = await api.get<AppConfig>('/config')
    counts.value = res.counts || {}
  } catch { /* ignore */ }
}

const clinicName = ref('')
const clinicLogo = ref('')
const deepseekKey = ref('')
const hasKey = ref(false)
const deepseekModel = ref('deepseek-chat')
const deepseekBaseUrl = ref('https://api.deepseek.com')
const visionModel = ref('')
const visionBaseUrl = ref('')
const visionKey = ref('')
const hasVisionKey = ref(false)
const visionConfigured = ref(false)
const appVersion = ref('')
const testing = ref(false)
const savingConfig = ref(false)
const exporting = ref(false)
const vectorAvailable = ref(false)
const savingClinic = ref(false)
const dbPath = ref('')
const counts = ref<Record<string, any>>({})

// ── AI 计费单价（元 / 百万 tokens）──
const priceInput = ref(0)
const priceCacheHit = ref(0)
const priceOutput = ref(0)
const priceVisionInput = ref(0)
const priceVisionOutput = ref(0)
const savingPricing = ref(false)
const pricingConfigured = computed(() =>
  [priceInput.value, priceCacheHit.value, priceOutput.value,
    priceVisionInput.value, priceVisionOutput.value].some(v => Number(v) > 0),
)

async function savePricing() {
  savingPricing.value = true
  try {
    await api.put('/config', {
      ai_price_input_per_m: Number(priceInput.value) || 0,
      ai_price_cache_hit_per_m: Number(priceCacheHit.value) || 0,
      ai_price_output_per_m: Number(priceOutput.value) || 0,
      ai_price_vision_input_per_m: Number(priceVisionInput.value) || 0,
      ai_price_vision_output_per_m: Number(priceVisionOutput.value) || 0,
    })
    ElMessage.success('AI 计费单价已保存')
  } catch {
    ElMessage.error('保存失败')
  } finally {
    savingPricing.value = false
  }
}

// ── 自动备份 ──
interface BackupItem { name: string; size: number; created_at: string }
interface AutoBackupStatus {
  config: { enabled: boolean; interval_hours: number; keep: number }
  dir: string
  last_backup: string | null
  items: BackupItem[]
}
const backupEnabled = ref(true)
const backupInterval = ref(24)
const backupKeep = ref(7)
const backupDir = ref('')
const backupLast = ref('')
const backupItems = ref<BackupItem[]>([])
const backupSaving = ref(false)
const backupRunning = ref(false)

function formatSize(n: number): string {
  if (!n) return '0 B'
  return n < 1024 * 1024 ? `${(n / 1024).toFixed(1)} KB` : `${(n / 1024 / 1024).toFixed(1)} MB`
}

async function loadAutoBackup() {
  try {
    const res = await api.get<AutoBackupStatus>('/backup/auto/status', { silent: true })
    backupEnabled.value = res.config?.enabled ?? true
    backupInterval.value = res.config?.interval_hours ?? 24
    backupKeep.value = res.config?.keep ?? 7
    backupDir.value = res.dir || ''
    backupLast.value = res.last_backup || ''
    backupItems.value = res.items || []
  } catch { /* 无 system:read 权限或后端不支持时静默留空 */ }
}

async function saveAutoBackup() {
  backupSaving.value = true
  try {
    await api.put('/backup/auto/config', {
      enabled: backupEnabled.value,
      interval_hours: backupInterval.value,
      keep: backupKeep.value,
    }, { silent: true })
    ElMessage.success('自动备份设置已保存')
    await loadAutoBackup()
  } catch (e) {
    ElMessage.error('保存失败：' + errMsg(e))
  } finally {
    backupSaving.value = false
  }
}

async function runAutoBackup() {
  backupRunning.value = true
  try {
    await api.post('/backup/auto/run', undefined, { silent: true })
    ElMessage.success('已生成备份快照')
    await loadAutoBackup()
  } catch (e) {
    ElMessage.error('备份失败：' + errMsg(e))
  } finally {
    backupRunning.value = false
  }
}

async function downloadAutoBackup(name: string) {
  try {
    const data = await api.get<Blob>(`/backup/auto/download/${encodeURIComponent(name)}`, { responseType: 'blob', silent: true })
    const link = document.createElement('a')
    link.href = URL.createObjectURL(new Blob([data]))
    link.download = name
    link.click()
    URL.revokeObjectURL(link.href)
  } catch (e) {
    ElMessage.error('下载失败：' + errMsg(e))
  }
}

const connectionStatus = ref({ type: 'info' as 'success' | 'danger' | 'info', text: '未测试' })

// 系统信息里的「AI 引擎」状态：与真实测试结果一致，而不只依据「是否存了 key」
const aiEngineStatus = computed(() => {
  const cs = connectionStatus.value
  if (cs.type === 'danger') return { type: 'danger' as const, text: 'DeepSeek 连接失败' }
  if (cs.text === '✅ 连接成功') return { type: 'success' as const, text: 'DeepSeek 已连接' }
  return hasKey.value
    ? { type: 'success' as const, text: 'DeepSeek 已配置' }
    : { type: 'info' as const, text: 'DeepSeek 未配置' }
})

onMounted(async () => {
  try {
    const res = await api.get<AppConfig>('/config')
    appVersion.value = res.version || ''
    dbPath.value = res.db_path || ''
    counts.value = res.counts || {}
    clinicName.value = res.clinic_name || ''
    clinicLogo.value = res.clinic_logo || ''
    deepseekModel.value = res.deepseek_model || 'deepseek-chat'
    deepseekBaseUrl.value = res.deepseek_base_url || 'https://api.deepseek.com'
    if (res.deepseek_configured) {
      hasKey.value = true
      connectionStatus.value = { type: 'success', text: '已配置' }
    }
    // 输入框不预填 key，仅作「已配置」占位用；杜绝浏览器自动填充的残留旧值被提交覆盖
    deepseekKey.value = ''
    visionKey.value = ''
    visionModel.value = res.deepseek_vision_model || ''
    visionBaseUrl.value = res.deepseek_vision_base_url || ''
    hasVisionKey.value = res.vision_key_configured || false
    visionConfigured.value = res.vision_configured || false
    priceInput.value = Number(res.ai_price_input_per_m) || 0
    priceCacheHit.value = Number(res.ai_price_cache_hit_per_m) || 0
    priceOutput.value = Number(res.ai_price_output_per_m) || 0
    priceVisionInput.value = Number(res.ai_price_vision_input_per_m) || 0
    priceVisionOutput.value = Number(res.ai_price_vision_output_per_m) || 0
  } catch {}

  try {
    const res = await api.get<Record<string, any>>('/diagnosis/status')
    vectorAvailable.value = res.vector_store_available || false
  } catch {}
  void loadAutoBackup()
})

async function saveClinic() {
  savingClinic.value = true
  try {
    await api.put('/config', {
      clinic_name: clinicName.value,
      clinic_logo: clinicLogo.value,
    })
    ElMessage.success('诊所信息已保存')
    applyBranding(clinicName.value, clinicLogo.value)
  } catch {
    ElMessage.error('保存失败')
  } finally {
    savingClinic.value = false
  }
}

async function onLogoChange(uploadFile: UploadFile) {
  const raw = uploadFile?.raw
  if (!raw) return
  if (raw.size > 2 * 1024 * 1024) {
    ElMessage.warning('Logo 图片请小于 2MB')
    return
  }
  try {
    // 统一压缩为 webp：既与项目其它图片格式一致，也避免原图 base64 撑大配置文件
    clinicLogo.value = await compressToDataUrl(raw)
  } catch {
    ElMessage.error('Logo 处理失败，请换一张图片重试')
  }
}

async function saveConfig() {
  savingConfig.value = true
  try {
    const body: Record<string, any> = {
      deepseek_model: deepseekModel.value,
      deepseek_base_url: deepseekBaseUrl.value,
    }
    // 只有用户实际输入了新key才发送
    if (deepseekKey.value) {
      body.deepseek_api_key = deepseekKey.value
    }
    if (visionModel.value) {
      body.deepseek_vision_model = visionModel.value
    }
    if (visionBaseUrl.value) {
      body.deepseek_vision_base_url = visionBaseUrl.value
    }
    if (visionKey.value) {
      body.deepseek_vision_api_key = visionKey.value
    }
    await api.put('/config', body)
    visionConfigured.value = !!visionModel.value && !!(visionKey.value || hasVisionKey.value)
    hasVisionKey.value = !!visionKey.value || hasVisionKey.value
    // 保存成功后清空 key 输入框，避免残留值下次误提交
    if (deepseekKey.value) deepseekKey.value = ''
    if (visionKey.value) visionKey.value = ''
    ElMessage.success('配置已保存')
    connectionStatus.value = { type: 'success', text: '配置已保存' }
  } catch {
    ElMessage.error('保存失败，请检查配置')
  } finally {
    savingConfig.value = false
  }
}

async function testConnection() {
  if (!deepseekKey.value && !hasKey.value) {
    ElMessage.warning('请先输入 API Key')
    return
  }

  testing.value = true
  connectionStatus.value = { type: 'info', text: '测试中...' }

  try {
    // 先保存配置：仅当用户确实输入了新 key 才提交（否则易把残留旧值误写覆盖真实 key）
    const body: Record<string, any> = {
      deepseek_model: deepseekModel.value,
      deepseek_base_url: deepseekBaseUrl.value,
    }
    if (deepseekKey.value) {
      body.deepseek_api_key = deepseekKey.value
    }
    await api.put('/config', body)

    // 发送简单消息测试
    const res = await api.post<Record<string, any>>('/diagnosis/chat', { message: '你好' })
    if (res.reply && !res.reply.includes('未配置') && !res.reply.includes('失败')) {
      connectionStatus.value = { type: 'success', text: '✅ 连接成功' }
      ElMessage.success('DeepSeek API 连接成功')
      // 测试成功即代表 key 有效，清空输入框，避免残留旧值下次被误提交覆盖
      deepseekKey.value = ''
    } else {
      connectionStatus.value = { type: 'danger', text: '❌ 连接失败' }
    }
  } catch {
    connectionStatus.value = { type: 'danger', text: '❌ 连接失败' }
    ElMessage.error('连接测试失败，请检查 API Key')
  } finally {
    testing.value = false
  }
}

async function exportData() {
  exporting.value = true
  try {
    const res = await api.get<Blob>('/backup/export', { responseType: 'blob' })
    const url = window.URL.createObjectURL(new Blob([res]))
    const link = document.createElement('a')
    link.href = url
    link.download = `tcm_backup_${new Date().toLocaleDateString('sv-SE')}.db`
    link.click()
    window.URL.revokeObjectURL(url)
    ElMessage.success('数据备份已下载')
  } catch {
    // 降级方案：提示手动备份
    ElMessage.info('请手动备份数据库文件: backend/tcm_doctor.db')
  } finally {
    exporting.value = false
  }
}

async function onImportFile(file: UploadFile) {
  try {
    await ElMessageBox.confirm('导入数据将覆盖当前数据，确定继续？', '数据恢复确认', {
      confirmButtonText: '确定导入',
      cancelButtonText: '取消',
      type: 'warning',
    })
    const formData = new FormData()
    if (file.raw) formData.append('file', file.raw)
    await api.post('/backup/import', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
    ElMessage.success('数据恢复成功，请重启应用')
  } catch {
    // 用户取消或接口未实现
  }
}

async function resetData() {
  try {
    await api.post('/backup/reset')
    ElMessage.success('数据已清空')
  } catch {}
}
</script>

<style scoped lang="scss">
.settings-page {
  // 每行左右卡片等高对齐，避免长短不齐
  :deep(.el-row) {
    align-items: stretch;
  }
  :deep(.el-col) {
    display: flex;
    flex-direction: column;
  }
  :deep(.el-card) {
    width: 100%;
    display: flex;
    flex-direction: column;
    flex: 1;
  }
  :deep(.el-card__header) {
    padding: 14px 18px;
    background: linear-gradient(135deg, #fdf8f3 0%, #f7efe6 100%);
    border-bottom: 1px solid #f0e4d6;
  }
  :deep(.el-card__body) {
    flex: 1;
    display: flex;
    flex-direction: column;
  }
  :deep(.el-card__body .el-form) {
    flex: 1;
    display: flex;
    flex-direction: column;
  }

  .settings-row { margin-top: 20px; }

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
  .card-actions { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }

  .conn-pill {
    display: inline-flex;
    align-items: center;
    padding: 2px 10px;
    border-radius: 999px;
    font-size: 12px;
    line-height: 1.7;
    border: 1px solid #e6d9c9;
    background: #fff;
    color: #907a63;

    &.is-success { border-color: #cfe0cb; background: #f4f8f2; color: #5f7f5c; }
    &.is-danger { border-color: #f0cdc6; background: #fdf4f2; color: #b5624f; }
  }

  .config-form {
    .el-form-item { margin-bottom: 16px; }
    .full-width { width: 100%; }
  }

  .form-section-title {
    display: flex;
    align-items: center;
    gap: 6px;
    font-size: 13px;
    font-weight: 600;
    color: #6b5644;
    padding-bottom: 8px;
    margin-bottom: 12px;
    border-bottom: 1px dashed #f0e4d6;

    .sec-dot {
      width: 6px;
      height: 6px;
      border-radius: 50%;
      background: #a97b4f;
      &.is-vision { background: #7fa07c; }
    }
  }

  .section-hint {
    display: flex;
    align-items: flex-start;
    gap: 6px;
    padding: 8px 12px;
    margin-bottom: 14px;
    border: 1px dashed #e6d9c9;
    border-radius: 8px;
    background: #fdfaf7;
    font-size: 12px;
    line-height: 1.7;
    color: #8a7a68;

    .el-icon { flex: none; margin-top: 2px; color: #b89a76; font-size: 13px; }
  }

  .config-footer {
    margin-top: auto;
    padding-top: 12px;

    .footer-actions { display: flex; gap: 8px; flex-wrap: wrap; }
  }

  .row-action {
    display: flex;
    align-items: center;
    gap: 10px;
    flex-wrap: wrap;

    .row-hint { font-size: 12px; color: #a39484; }
  }

  .backup-table { margin-top: 12px; width: 100%; }

  .sys-desc {
    :deep(.el-descriptions__label) {
      background: #faf6f1;
      color: #7a6553;
      font-weight: 600;
      width: 108px;
    }
    :deep(.el-descriptions__content) { color: #5c4a3a; }
  }

  .count-chips {
    display: flex;
    flex-wrap: wrap;
    gap: 6px;

    .count-chip {
      padding: 1px 8px;
      border-radius: 6px;
      background: #faf6f1;
      border: 1px solid #eddfd0;
      font-size: 12px;
      color: #8b7a68;

      b { color: var(--tcm-primary); font-variant-numeric: tabular-nums; }
    }
  }
}

.clinic-brand {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 14px 16px;
  border-radius: 10px;
  background: linear-gradient(135deg, #fdf8f3 0%, #f7efe6 100%);
  border: 1px solid #f0e4d6;
  &.is-readonly { opacity: .85; }
}
.clinic-logo-wrap { flex-shrink: 0; }
.clinic-logo {
  width: 72px;
  height: 72px;
  object-fit: contain;
  border-radius: 12px;
  background: #fff;
  border: 1px solid #e8e0d8;
  padding: 6px;
  box-shadow: 0 2px 8px rgba(139, 94, 52, .08);
  &.is-empty {
    display: flex;
    align-items: center;
    justify-content: center;
    color: #c9a882;
    border-style: dashed;
    box-shadow: none;
  }
}
.clinic-brand-text { min-width: 0; }
.clinic-brand-name {
  font-size: 17px;
  font-weight: 600;
  color: #2c1810;
  letter-spacing: .5px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.clinic-brand-sub { font-size: 12px; color: #9a8b7a; margin-top: 4px; }
.clinic-logo-actions { display: flex; align-items: center; gap: 10px; margin-top: 10px; }
.doctor-hint-item { margin-bottom: 12px; }
.doctor-hint {
  display: flex;
  align-items: flex-start;
  gap: 6px;
  font-size: 12.5px;
  line-height: 1.7;
  color: #8a7a68;
  padding: 8px 12px;
  border-radius: 8px;
  background: #faf6f1;
  border: 1px dashed #e6d9c9;
  .el-icon { margin-top: 3px; color: #b89a76; flex-shrink: 0; }
  i { font-style: normal; color: #8b5e34; font-weight: 600; }
}
.text-muted { color: #aaa; font-size: 13px; }
.status-retest { display: inline-flex; align-items: center; gap: 6px; cursor: pointer; }
.status-retest:hover .retest-hint { text-decoration: underline; }
.retest-hint { font-size: 12px; color: #b08753; }
.mono { font-family: ui-monospace, Menlo, Consolas, monospace; font-size: 12px; word-break: break-all; color: #555; }

// ---- 内容模板卡片 ----
@media (max-width: 767px) {
  .settings-page {
    .settings-row { margin-top: 16px; }
    .card-head-bar { align-items: stretch; }
    .card-actions { justify-content: flex-start; }
    .config-footer .footer-actions :deep(.el-button) { flex: 1; }
    .row-action { align-items: flex-start; flex-direction: column; gap: 6px; }
    .sys-desc :deep(.el-descriptions__label) { width: 92px; }
  }
}
</style>