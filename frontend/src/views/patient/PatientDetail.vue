<template>
  <div class="patient-detail" v-loading="loading">
    <el-page-header @back="$router.push('/patients')" :content="patient?.name || '加载中...'">
      <template #extra>
        <div class="header-actions">
          <el-button v-if="editable" @click="openEdit"><el-icon><Edit /></el-icon> 编辑</el-button>
          <el-button v-if="editable" @click="$router.push(`/patients/${patientId}/visit`)">
            <el-icon><EditPen /></el-icon> 新增就诊
          </el-button>
        </div>
      </template>
    </el-page-header>

    <el-row :gutter="20" style="margin-top: 20px;">
      <!-- 基本信息 -->
      <el-col :xs="24" :sm="10" :lg="8">
        <el-card shadow="hover">
          <template #header><span>📋 基本信息</span></template>
          <el-descriptions :column="1" border size="small" v-if="patient">
            <el-descriptions-item label="姓名">{{ patient.name }}</el-descriptions-item>
            <el-descriptions-item label="性别">{{ patient.gender }}</el-descriptions-item>
            <el-descriptions-item label="出生日期">{{ patient.birth_date || '-' }}</el-descriptions-item>
            <el-descriptions-item label="电话">{{ patient.phone || '-' }}</el-descriptions-item>
            <el-descriptions-item label="身份证号">{{ patient.id_card || '-' }}</el-descriptions-item>
            <el-descriptions-item label="地址">{{ patient.address || '-' }}</el-descriptions-item>
            <el-descriptions-item label="过敏史">
              <el-tag v-if="patient.allergy_history" type="danger" size="small">{{ patient.allergy_history }}</el-tag>
              <span v-else>无</span>
            </el-descriptions-item>
            <el-descriptions-item label="既往史">{{ patient.medical_history || '无' }}</el-descriptions-item>
            <el-descriptions-item label="体质">
              <el-tag v-if="patient.constitution_type" type="warning">{{ patient.constitution_type }}</el-tag>
              <span v-else class="text-muted">未评估</span>
            </el-descriptions-item>
            <el-descriptions-item label="备注">{{ patient.notes || '-' }}</el-descriptions-item>
          </el-descriptions>
        </el-card>
      </el-col>

      <!-- 就诊历史 -->
      <el-col :xs="24" :sm="14" :lg="16">
        <el-card shadow="hover">
          <template #header><span>🏥 就诊记录</span></template>
          <el-timeline v-if="visits.length > 0">
            <el-timeline-item
              v-for="visit in visits"
              :key="visit.id"
              :timestamp="visit.visit_date"
              placement="top"
            >
              <el-card shadow="never" class="visit-card">
                <div class="visit-header">
                  <strong>主诉：</strong>{{ visit.chief_complaint }}
                </div>
                <div v-if="visit.tcm_disease || visit.tcm_syndrome" class="visit-diagnosis">
                  <el-tag type="primary" size="small">{{ visit.tcm_disease }}</el-tag>
                  <el-tag type="warning" size="small">{{ visit.tcm_syndrome }}</el-tag>
                  <el-tag type="info" size="small">{{ visit.treatment_method }}</el-tag>
                </div>
                <div v-if="visit.tongue_body || visit.tongue_coat || visit.pulse" class="visit-sizhen">
                  <span v-if="visit.tongue_body">舌质: {{ visit.tongue_body }}</span>
                  <span v-if="visit.tongue_coat">舌苔: {{ visit.tongue_coat }}</span>
                  <span v-if="visit.pulse">脉象: {{ visit.pulse }}</span>
                </div>

                <!-- 本次问诊十问 -->
                <div v-if="inquiriesByVisit[visit.id] && inquiriesByVisit[visit.id].length" class="sub-block">
                  <div class="sub-title">🩺 本次问诊十问</div>
                  <div v-for="iq in inquiriesByVisit[visit.id]" :key="iq.id" class="sub-item">
                    <el-tag type="warning" size="small">{{ iq.primary_type || '未定型' }}</el-tag>
                    <span class="sub-note">偏性画像</span>
                    <ul v-if="iq.result && iq.result.findings && iq.result.findings.length" class="iq-findings">
                      <li v-for="(f, fi) in iq.result.findings" :key="fi">{{ f }}</li>
                    </ul>
                    <div v-if="iq.result && iq.result.suggestion" class="iq-suggestion">{{ iq.result.suggestion }}</div>
                    <div class="visit-actions">
                      <el-button link type="warning" size="small" @click="openIqDialog(iq)">查看完整评估</el-button>
                    </div>
                  </div>
                </div>

                <!-- 本次处方 -->
                <div v-if="rxByVisit[visit.id] && rxByVisit[visit.id].length" class="sub-block">
                  <div v-for="rx in rxByVisit[visit.id]" :key="rx.id" class="sub-item">
                    <div class="sub-title">💊 本次处方
                      <el-tag :type="statusTag(rx.status)" size="small" effect="plain">{{ rx.status }}</el-tag>
                    </div>

                    <template v-if="rx.items && rx.items.length">
                      <div class="rx-sub-title">🌿 中药方{{ rx.formula_name ? ' · ' + rx.formula_name : '' }}</div>
                      <div class="rx-herbs">
                        <span v-for="(it, ix) in rx.items" :key="'h'+ix" class="rx-herb">
                          {{ it.herb_name }}<em v-if="it.is_king_herb" class="king">君</em>
                          <b>{{ it.dose }}g</b>
                        </span>
                      </div>
                      <div class="rx-doses">{{ rx.doses }} 剂 · {{ rx.preparation_method }}</div>
                    </template>

                    <template v-if="rx.acupoints && rx.acupoints.length">
                      <div class="rx-sub-title">🪡 针灸方{{ rx.acupoint_formula_name ? ' · ' + rx.acupoint_formula_name : '' }}</div>
                      <div class="rx-herbs">
                        <span v-for="(a, ix) in rx.acupoints" :key="'a'+ix" class="rx-herb">
                          {{ a.acupoint_name }}<b v-if="a.technique">·{{ a.technique }}</b>
                        </span>
                      </div>
                      <div v-if="rx.acupoint_technique || rx.treatment_frequency || rx.treatment_days" class="rx-acu-meta">
                        <span v-if="rx.acupoint_technique">{{ rx.acupoint_technique }}</span>
                        <span v-if="rx.treatment_frequency">{{ rx.treatment_frequency }}</span>
                        <span v-if="rx.treatment_days">{{ rx.treatment_days }} 天</span>
                      </div>
                    </template>

                    <div class="visit-actions">
                      <el-button link type="danger" size="small" @click="openRxDialog(rx)">查看处方</el-button>
                    </div>
                  </div>
                </div>

                <div v-if="visit.ai_analysis" class="sub-block">
                  <div class="sub-title">🤖 AI 诊断库（辨证论治）</div>
                  <div class="view-ai-analysis" v-html="renderMarkdown(visit.ai_analysis)"></div>
                </div>

                <div class="visit-actions">
                  <el-button link type="primary" size="small" @click="openVisitDialog(visit)">查看就诊详情</el-button>
                  <el-button link type="warning" size="small" @click="$router.push(`/patients/${patientId}/visit?visit_id=${visit.id}`)">完善/编辑</el-button>
                </div>
              </el-card>
            </el-timeline-item>
          </el-timeline>
          <el-empty v-else description="暂无就诊记录" />
        </el-card>

        <el-card v-if="orphanInquiries.length > 0" shadow="hover" style="margin-top: 16px;">
          <template #header><span>🩺 问诊十问（未关联就诊）</span></template>
          <el-timeline>
            <el-timeline-item
              v-for="iq in orphanInquiries"
              :key="iq.id"
              :timestamp="fmtTime(iq.created_at)"
              placement="top"
              type="warning"
            >
              <el-card shadow="never" class="visit-card">
                <div class="iq-type">
                  <el-tag type="warning" size="small">{{ iq.primary_type || '未定型' }}</el-tag>
                  <span style="margin-left:6px;font-size:12px;color:#999;">偏性画像</span>
                </div>
                <ul v-if="iq.result && iq.result.findings && iq.result.findings.length" class="iq-findings">
                  <li v-for="(f, fi) in iq.result.findings" :key="fi">{{ f }}</li>
                </ul>
                <div v-if="iq.result && iq.result.suggestion" class="iq-suggestion">{{ iq.result.suggestion }}</div>
                <div class="visit-actions">
                  <el-button link type="warning" size="small" @click="openIqDialog(iq)">查看完整评估</el-button>
                </div>
              </el-card>
            </el-timeline-item>
          </el-timeline>
        </el-card>

      </el-col>
    </el-row>

    <el-dialog v-model="editVisible" title="编辑患者信息" width="560px">
      <el-form :model="editForm" label-width="80px" label-position="top">
        <el-form-item label="姓名" required>
          <el-input v-model="editForm.name" />
        </el-form-item>
        <el-row :gutter="12">
          <el-col :xs="24" :sm="12">
            <el-form-item label="性别">
              <el-select v-model="editForm.gender" style="width:100%">
                <el-option label="男" value="男" /><el-option label="女" value="女" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :xs="24" :sm="12">
            <el-form-item label="出生日期">
              <el-date-picker v-model="editForm.birth_date" type="date" value-format="YYYY-MM-DD" style="width:100%" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="12">
          <el-col :xs="24" :sm="12"><el-form-item label="电话"><el-input v-model="editForm.phone" /></el-form-item></el-col>
          <el-col :xs="24" :sm="12"><el-form-item label="身份证号"><el-input v-model="editForm.id_card" /></el-form-item></el-col>
        </el-row>
        <el-form-item label="地址"><el-input v-model="editForm.address" /></el-form-item>
        <el-form-item label="过敏史"><el-input v-model="editForm.allergy_history" /></el-form-item>
        <el-form-item label="既往史"><el-input v-model="editForm.medical_history" type="textarea" :rows="2" /></el-form-item>
        <el-form-item label="备注"><el-input v-model="editForm.notes" type="textarea" :rows="2" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="editVisible = false">取消</el-button>
        <el-button type="primary" @click="saveEdit" :loading="savingEdit">保存</el-button>
      </template>
    </el-dialog>

    <el-dialog :title="'就诊记录详情 · ' + (viewVisit?.visit_date || '')" :model-value="showVisitDialog" @update:model-value="showVisitDialog = $event" class="visit-detail-dialog" width="min(680px, 92vw)" destroy-on-close>
      <el-descriptions v-if="viewVisit" :column="1" border size="small">
        <el-descriptions-item label="就诊日期">{{ viewVisit.visit_date }}</el-descriptions-item>
        <el-descriptions-item label="主诉">{{ viewVisit.chief_complaint }}</el-descriptions-item>
        <el-descriptions-item v-if="viewVisit.present_illness" label="现病史">{{ viewVisit.present_illness }}</el-descriptions-item>
        <el-descriptions-item v-if="viewVisit.observation" label="望诊">{{ viewVisit.observation }}</el-descriptions-item>
        <el-descriptions-item v-if="viewVisit.auscultation" label="闻诊">{{ viewVisit.auscultation }}</el-descriptions-item>
        <el-descriptions-item v-if="viewVisit.inquiry" label="问诊">{{ viewVisit.inquiry }}</el-descriptions-item>
        <el-descriptions-item v-if="viewVisit.palpation" label="切诊">{{ viewVisit.palpation }}</el-descriptions-item>
        <el-descriptions-item v-if="viewVisit.tongue_body || viewVisit.tongue_coat" label="舌象">{{ viewVisit.tongue_body }}{{ viewVisit.tongue_coat ? ' / ' + viewVisit.tongue_coat : '' }}</el-descriptions-item>
        <el-descriptions-item v-if="viewVisit.pulse" label="脉象">{{ viewVisit.pulse }}</el-descriptions-item>
        <el-descriptions-item v-if="viewVisit.tcm_disease" label="中医病名">{{ viewVisit.tcm_disease }}</el-descriptions-item>
        <el-descriptions-item v-if="viewVisit.tcm_syndrome" label="证型">{{ viewVisit.tcm_syndrome }}</el-descriptions-item>
        <el-descriptions-item v-if="viewVisit.treatment_method" label="治法">{{ viewVisit.treatment_method }}</el-descriptions-item>
      </el-descriptions>
      <div v-if="viewVisit.ai_analysis" class="sub-block" style="margin-top: 14px;">
        <div class="sub-title">🤖 AI 诊断库（辨证论治）</div>
        <div class="view-ai-analysis" v-html="renderMarkdown(viewVisit.ai_analysis)"></div>
      </div>
      <template #footer>
        <el-button @click="showVisitDialog = false">关闭</el-button>
        <el-button type="primary" @click="$router.push(`/patients/${patientId}/visit?visit_id=${viewVisit?.id}`)">完善/编辑此就诊</el-button>
      </template>
    </el-dialog>

    <el-dialog :title="'问诊十问详情 · ' + fmtTime(viewIq?.created_at)" :model-value="showIqDialog" @update:model-value="showIqDialog = $event" class="iq-detail-dialog" width="min(680px, 92vw)" destroy-on-close>
      <template v-if="viewIq">
        <div class="view-iq-primary">主偏性&nbsp;:&nbsp;<el-tag type="warning">{{ viewIq.primary_type || '未定型' }}</el-tag></div>
        <div v-if="viewIq.result?.findings?.length" class="view-iq-sec">
          <h4>判据解析</h4>
          <ul class="iq-findings"><li v-for="(f, fi) in viewIq.result.findings" :key="fi">{{ f }}</li></ul>
        </div>
        <div v-if="viewIq.result?.suggestion" class="view-iq-sec">
          <h4>方域提示</h4>
          <p class="iq-suggestion">{{ viewIq.result.suggestion }}</p>
        </div>
        <div v-if="viewIq.result?.detail" class="view-iq-sec">
          <h4>维度分布</h4>
          <div class="view-iq-dims">
            <span v-for="(v, k) in viewIq.result.detail.dims" :key="k" class="dim-chip">
              {{ k }}: {{ v }}
            </span>
          </div>
        </div>
        <div v-if="viewIq.notes && Object.values(viewIq.notes).some(x => x && String(x).trim())" class="view-iq-sec">
          <h4>自填描述</h4>
          <div v-for="(val, key) in viewIq.notes" :key="key" v-if="val && String(val).trim()" class="note-line">
            <b>{{ key }}</b>：{{ val }}
          </div>
        </div>
      </template>
    </el-dialog>

    <el-dialog :title="'处方详情'" :model-value="showRxDialog" @update:model-value="showRxDialog = $event" class="rx-detail-dialog" width="min(680px, 92vw)" destroy-on-close>
      <template v-if="viewRx">
        <div class="view-iq-primary">
          💊 处方
          <el-tag :type="statusTag(viewRx.status)" size="small" effect="plain">{{ viewRx.status }}</el-tag>
          <span style="margin-left:8px;color:#999;font-size:12px;">{{ fmtTime(viewRx.created_at) }}</span>
        </div>

        <template v-if="viewRx.items && viewRx.items.length">
          <div class="rx-sub-title">🌿 中药方{{ viewRx.formula_name ? ' · ' + viewRx.formula_name : '' }}</div>
          <el-table :data="viewRx.items" size="small" border>
            <el-table-column prop="herb_name" label="药味" min-width="100" />
            <el-table-column prop="dose" label="剂量(g)" width="90" />
            <el-table-column prop="special_method" label="特殊煎法" min-width="110">
              <template #default="{ row }">{{ row.special_method || '—' }}</template>
            </el-table-column>
            <el-table-column prop="is_king_herb" label="地位" width="70">
              <template #default="{ row }">
                <el-tag v-if="row.is_king_herb" type="danger" size="small">君药</el-tag>
                <span v-else class="text-muted">臣佐</span>
              </template>
            </el-table-column>
          </el-table>
          <div class="rx-doses">{{ viewRx.doses }} 剂 · {{ viewRx.preparation_method }}<span v-if="viewRx.administration"> · {{ viewRx.administration }}</span></div>
        </template>

        <template v-if="viewRx.acupoints && viewRx.acupoints.length">
          <div class="rx-sub-title">🪡 针灸方{{ viewRx.acupoint_formula_name ? ' · ' + viewRx.acupoint_formula_name : '' }}</div>
          <el-table :data="viewRx.acupoints" size="small" border>
            <el-table-column prop="acupoint_name" label="穴位" min-width="100" />
            <el-table-column prop="technique" label="手法" min-width="90">
              <template #default="{ row }">{{ row.technique || '—' }}</template>
            </el-table-column>
            <el-table-column prop="retention" label="留针" min-width="90">
              <template #default="{ row }">{{ row.retention || '—' }}</template>
            </el-table-column>
            <el-table-column prop="note" label="备注" min-width="120">
              <template #default="{ row }">{{ row.note || '—' }}</template>
            </el-table-column>
          </el-table>
          <div v-if="viewRx.acupoint_technique || viewRx.treatment_frequency || viewRx.treatment_days" class="rx-acu-meta">
            <span v-if="viewRx.acupoint_technique">{{ viewRx.acupoint_technique }}</span>
            <span v-if="viewRx.treatment_frequency">{{ viewRx.treatment_frequency }}</span>
            <span v-if="viewRx.treatment_days">{{ viewRx.treatment_days }} 天</span>
          </div>
        </template>

        <div v-if="viewRx.total_price" class="rx-doses">总价：￥{{ viewRx.total_price }}</div>

        <div v-if="viewRx.doctor_notes" class="view-iq-sec">
          <h4>医嘱</h4>
          <p class="iq-suggestion">{{ viewRx.doctor_notes }}</p>
        </div>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { Edit, EditPen, TrendCharts } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import api from '@/utils/api'
import { useAuthStore } from '@/store/auth'
import { renderMarkdown } from '@/utils/markdown'

// 游客只读：隐藏所有写操作
const auth = useAuthStore()
const editable = computed(() => !!auth.user?.is_admin)

const route = useRoute()
const patientId = Number(route.params.id)
const patient = ref<any>(null)
const visits = ref<any[]>([])
const inquiries = ref<any[]>([])
const prescriptions = ref<any[]>([])
const loading = ref(false)

// 按就诊聚合：处方与十问分别归到对应的 visit_id 下
const rxByVisit = computed<Record<number, any[]>>(() => {
  const m: Record<number, any[]> = {}
  for (const rx of prescriptions.value) {
    if (rx.visit_id != null) (m[rx.visit_id] ||= []).push(rx)
  }
  return m
})
const inquiriesByVisit = computed<Record<number, any[]>>(() => {
  const m: Record<number, any[]> = {}
  for (const iq of inquiries.value) {
    if (iq.visit_id != null) (m[iq.visit_id] ||= []).push(iq)
  }
  return m
})
// 未关联就诊的十问（向后兼容旧数据）
const orphanInquiries = computed(() => inquiries.value.filter(iq => iq.visit_id == null))

const editVisible = ref(false)
const savingEdit = ref(false)
const editForm = ref<any>({})

const showVisitDialog = ref(false)
const viewVisit = ref<any>(null)
const showIqDialog = ref(false)
const viewIq = ref<any>(null)
const showRxDialog = ref(false)
const viewRx = ref<any>(null)

function openVisitDialog(v: any) { viewVisit.value = v; showVisitDialog.value = true }
function openIqDialog(i: any) { viewIq.value = i; showIqDialog.value = true }
function openRxDialog(p: any) { viewRx.value = p; showRxDialog.value = true }

function statusTag(s?: string) {
  if (!s) return 'info'
  if (s.includes('审核')) return 'warning'
  if (s.includes('发药')) return 'success'
  return 'info'
}

function openEdit() {
  const p = patient.value || {}
  editForm.value = {
    name: p.name || '',
    gender: p.gender || '',
    birth_date: p.birth_date || '',
    phone: p.phone || '',
    id_card: p.id_card || '',
    address: p.address || '',
    allergy_history: p.allergy_history || '',
    medical_history: p.medical_history || '',
    notes: p.notes || '',
  }
  editVisible.value = true
}

async function saveEdit() {
  if (!editForm.value.name.trim()) { ElMessage.warning('请填写姓名'); return }
  savingEdit.value = true
  try {
    patient.value = await api.put(`/patients/${patientId}`, editForm.value)
    ElMessage.success('已保存')
    editVisible.value = false
  } catch {
    ElMessage.error('保存失败')
  }
  savingEdit.value = false
}

onMounted(async () => {
  loading.value = true
  try {
    const [p, v, iq, rx] = await Promise.all([
      api.get(`/patients/${patientId}`),
      api.get(`/patients/${patientId}/visits`),
      api.get(`/patients/${patientId}/inquiries`),
      api.get(`/prescriptions?patient_id=${patientId}`),
    ])
    patient.value = p
    visits.value = v as any
    inquiries.value = iq as any
    prescriptions.value = rx as any
  } catch {}
  loading.value = false
})

function fmtTime(iso?: string): string {
  if (!iso) return ''
  return String(iso).replace('T', ' ').slice(0, 16)
}
</script>

<style scoped>
.text-muted { color: #c0c4cc; }
.visit-card { margin-bottom: 4px; }
.visit-header { font-size: 14px; }
.visit-diagnosis { margin-top: 8px; display: flex; gap: 6px; }
.visit-sizhen { margin-top: 8px; font-size: 13px; color: #666; display: flex; gap: 12px; }
.iq-type { margin-bottom: 6px; }
.iq-findings { margin: 4px 0; padding-left: 16px; font-size: 12.5px; color: #666; line-height: 1.8; }
.iq-suggestion { margin-top: 6px; font-size: 12.5px; color: #8B4513; }
.view-ai-analysis {
  white-space: normal;
  word-break: break-word;
  overflow-wrap: anywhere;
  font-size: 12.5px;
  line-height: 1.8;
  color: #333;
  background: #fffbf0;
  border: 1px dashed #d9c9a3;
  border-radius: 6px;
  padding: 8px 10px;
  :deep(h1), :deep(h2), :deep(h3), :deep(h4) { margin: 10px 0 5px; color: #8B4513; }
  :deep(h1) { font-size: 16px; }
  :deep(h2) { font-size: 15px; }
  :deep(h3) { font-size: 14px; }
  :deep(p) { margin: 5px 0; overflow-wrap: anywhere; }
  :deep(ul), :deep(ol) { margin: 5px 0; padding-left: 20px; }
  :deep(li) { margin: 2px 0; overflow-wrap: anywhere; }
  /* 表格固定布局 + 强制换行，避免宽表格把弹窗撑飞 */
  :deep(table) { table-layout: fixed; width: 100%; border-collapse: collapse; margin: 6px 0; font-size: 12px; }
  :deep(th), :deep(td) { border: 1px solid #e8e0d8; padding: 3px 6px; text-align: left; word-break: break-word; overflow-wrap: anywhere; vertical-align: top; }
  :deep(th) { background: #faf7f4; }
  :deep(strong) { color: #8B4513; }
  :deep(code) { background: #f5f0eb; padding: 0 3px; border-radius: 3px; }
  :deep(pre) { background: #f5f0eb; padding: 8px; border-radius: 5px; overflow-x: auto; }
  :deep(pre code) { background: transparent; padding: 0; }
  :deep(blockquote) { border-left: 3px solid #d9c9a3; margin: 5px 0; padding-left: 8px; color: #999; }
}
.visit-actions { margin-top: 8px; text-align: right; }
/* 弹窗内容超高时，仅 body 内部滚动，底部按钮始终可见（避免 AI 分析把弹窗顶飞） */
.visit-detail-dialog :deep(.el-dialog__body),
.iq-detail-dialog :deep(.el-dialog__body),
.rx-detail-dialog :deep(.el-dialog__body) {
  max-height: 72vh;
  overflow-y: auto;
}
@media (max-width: 767px) {
  .visit-detail-dialog, .iq-detail-dialog, .rx-detail-dialog { margin-top: 6vh !important; }
  .visit-detail-dialog :deep(.el-dialog__body),
  .iq-detail-dialog :deep(.el-dialog__body),
  .rx-detail-dialog :deep(.el-dialog__body) { max-height: 82vh; }
}
.view-iq-primary { font-size: 14px; margin-bottom: 10px; }
.view-iq-sec { margin-top: 12px; }
.view-iq-sec h4 { margin: 0 0 6px; font-size: 13px; color: #555; }
.view-iq-dims { display: flex; flex-wrap: wrap; gap: 6px; }
.dim-chip { font-size: 12px; background: #f4f4f5; border-radius: 4px; padding: 2px 8px; color: #606266; }
.note-line { font-size: 13px; color: #333; margin: 4px 0; }
.note-line b { color: #8B4513; margin-right: 4px; }
.rx-card { margin-top: 16px; }
.rx-row { display: flex; align-items: center; gap: 6px; }
.rx-doses { font-size: 12px; color: #999; margin-top: 4px; }
.rx-herbs { margin-top: 8px; display: flex; flex-wrap: wrap; gap: 6px; }
.rx-sub-title { margin-top: 8px; font-size: 12.5px; font-weight: 600; color: #6b4f2a; }
.rx-acu-meta { margin-top: 4px; font-size: 12px; color: #999; display: flex; flex-wrap: wrap; gap: 8px; }
.rx-herb { font-size: 12px; background: #f5f7fa; border-radius: 4px; padding: 2px 8px; color: #333; }
.rx-herb b { color: #606266; margin-left: 2px; font-weight: normal; }
.rx-herb .king { color: #F56C6C; font-style: normal; margin-left: 2px; }
.rx-more { font-size: 12px; color: #909399; }
.sub-block { margin-top: 10px; border-top: 1px dashed #eee; padding-top: 8px; }
.sub-block + .sub-block { margin-top: 10px; }
.sub-title { font-size: 13px; font-weight: 600; color: #555; margin-bottom: 6px; display: flex; align-items: center; gap: 6px; }.sub-item { margin-bottom: 8px; }
.sub-note { margin-left: 6px; font-size: 12px; color: #999; }

/* 移动端适配 */
@media (max-width: 767px) {
  .patient-detail :deep(.el-page-header__content) {
    font-size: 16px;
    margin-right: 4px;
  }
  .header-actions {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
    margin-top: 8px;
  }
  .visit-diagnosis,
  .visit-sizhen,
  .rx-row {
    flex-wrap: wrap;
  }
  .rx-doses {
    width: 100%;
    margin-left: 0;
  }
  .visit-actions {
    text-align: left;
    display: flex;
    flex-wrap: wrap;
    gap: 4px 12px;
  }
  .view-iq-dims {
    flex-direction: column;
    align-items: flex-start;
  }
  :deep(.el-dialog) {
    margin: 0 !important;
  }
  :deep(.el-descriptions) {
    font-size: 12.5px;
  }
}
</style>