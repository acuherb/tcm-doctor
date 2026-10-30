<template>
  <el-card shadow="never" class="visit-card" :class="{ 'visit-card--child': isChild }">
    <div class="visit-header">
      <el-tag size="small" :type="visit.visit_type === '复诊' ? 'success' : 'info'" effect="plain" style="margin-right:6px;">{{ visit.visit_type || '初诊' }}</el-tag>
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

    <!-- 影像资料（舌苔/面色/化验单，点击可放大） -->
    <div v-if="visit.tongue_image || visit.face_image || (visit.lab_report_images && visit.lab_report_images.length)" class="sub-block">
      <div class="sub-title">📷 影像资料</div>
      <div class="visit-imgs">
        <div v-if="visit.tongue_image" class="visit-img-item">
          <span class="img-label">舌苔</span>
          <el-image :src="visit.tongue_image" fit="cover" class="visit-thumb" :preview-src-list="[visit.tongue_image]" />
        </div>
        <div v-if="visit.face_image" class="visit-img-item">
          <span class="img-label">面色</span>
          <el-image :src="visit.face_image" fit="cover" class="visit-thumb" :preview-src-list="[visit.face_image]" />
        </div>
        <div v-for="(img, i) in (visit.lab_report_images || [])" :key="i" class="visit-img-item">
          <span class="img-label">化验单{{ (visit.lab_report_images || []).length > 1 ? i + 1 : '' }}</span>
          <el-image :src="img" fit="cover" class="visit-thumb" :preview-src-list="visit.lab_report_images || []" :initial-index="i" />
        </div>
      </div>
    </div>

    <!-- 本次问诊十问（按就诊日期关联，半折叠） -->
    <div v-if="inquiries.length" class="sub-block">
      <div class="sub-title">
        <span>🩺 本次问诊十问</span>
        <el-button link type="warning" size="small" style="margin-left:auto;padding:0;height:auto;" @click="iqExpanded = !iqExpanded">
          {{ iqExpanded ? '收起' : '查看全部' }}
        </el-button>
      </div>
      <div class="collapse-box" :class="{ collapsed: !iqExpanded }">
        <div v-for="iq in inquiries" :key="iq.id" class="sub-item">
          <el-tag type="warning" size="small">{{ iq.primary_type || '未定型' }}</el-tag>
          <span class="sub-note">偏性画像</span>
          <ul v-if="iq.result && iq.result.findings && iq.result.findings.length" class="iq-findings">
            <li v-for="(f, fi) in iq.result.findings" :key="fi">{{ f }}</li>
          </ul>
          <div v-if="iq.result && iq.result.suggestion" class="iq-suggestion">{{ iq.result.suggestion }}</div>
          <div class="visit-actions">
            <el-button link type="warning" size="small" @click="$emit('view-iq', iq)">查看完整评估</el-button>
          </div>
        </div>
      </div>
    </div>

    <!-- 本次处方 -->
    <div v-if="prescriptions.length" class="sub-block">
      <div v-for="rx in prescriptions" :key="rx.id" class="sub-item">
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
          <el-button link type="danger" size="small" @click="$emit('view-rx', rx)">查看处方</el-button>
        </div>
      </div>
    </div>

    <div v-if="visit.ai_analysis" class="sub-block">
      <div class="sub-title">
        <span>🤖 AI 诊断库（辨证论治）</span>
        <el-button link type="warning" size="small" style="margin-left:auto;padding:0;height:auto;" @click="aiExpanded = !aiExpanded">
          {{ aiExpanded ? '收起' : '查看全部' }}
        </el-button>
      </div>
      <div class="view-ai-analysis" :class="{ collapsed: !aiExpanded }" v-html="renderMarkdown(visit.ai_analysis)"></div>
    </div>

    <!-- 随访/回访记录（并入本次就诊） -->
    <div v-if="followups.length" class="sub-block">
      <div class="sub-title">📈 随访/回访记录</div>
      <div v-for="fu in followups" :key="fu.id" class="fu-item">
        <span class="fu-date">{{ fu.followup_date }}</span>
        <el-tag size="small" :type="improvementTag(fu.improvement)">{{ fu.improvement || '未评估' }}</el-tag>
        <span v-if="fu.feedback" class="fu-feedback">{{ fu.feedback }}</span>
        <span v-if="editable" class="visit-actions">
          <el-button link type="primary" size="small" @click="$emit('view-followup', fu)">编辑</el-button>
          <el-button link type="danger" size="small" @click="$emit('delete-followup', fu)">删除</el-button>
        </span>
      </div>
    </div>

    <div class="visit-actions">
      <el-button v-if="editable" link type="success" size="small" @click="$emit('add-followup', visit)">+ 随访</el-button>
      <el-button link type="primary" size="small" @click="$emit('view', visit)">查看就诊详情</el-button>
      <el-button link type="warning" size="small" @click="$emit('edit', visit.id)">完善/编辑</el-button>
    </div>
  </el-card>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { renderMarkdown } from '@/utils/markdown'

const props = withDefaults(
  defineProps<{
    visit: any
    inquiries?: any[]
    prescriptions?: any[]
    followups?: any[]
    editable?: boolean
    isChild?: boolean
  }>(),
  { inquiries: () => [], prescriptions: () => [], followups: () => [], editable: false, isChild: false },
)

defineEmits<{
  view: [any]
  edit: [number]
  'add-followup': [any]
  'view-followup': [any]
  'delete-followup': [any]
  'view-rx': [any]
  'view-iq': [any]
}>()

// 卡片内 问诊十问 / AI 诊断库 默认折叠
const iqExpanded = ref(false)
const aiExpanded = ref(false)

function statusTag(s?: string) {
  if (!s) return 'info'
  if (s.includes('审核')) return 'warning'
  if (s.includes('发药')) return 'success'
  return 'info'
}
function improvementTag(s?: string) {
  if (s === '明显好转' || s === '好转') return 'success'
  if (s === '稳定') return 'info'
  if (s === '反复' || s === '加重') return 'danger'
  return 'info'
}
</script>

<style scoped>
.visit-card { margin-bottom: 4px; }
.visit-card--child { margin-left: 28px; border-left: 3px solid #d9c9a3; }
.visit-header { font-size: 14px; }
.visit-diagnosis { margin-top: 8px; display: flex; gap: 6px; }
.visit-sizhen { margin-top: 8px; font-size: 13px; color: #666; display: flex; gap: 12px; }
.visit-imgs { display: flex; flex-wrap: wrap; gap: 12px; margin-top: 6px; }
.visit-img-item { text-align: center; }
.visit-img-item .img-label { display: block; font-size: 12px; color: #999; margin-bottom: 4px; }
.visit-thumb { width: 96px; height: 96px; border-radius: 6px; border: 1px solid #eee; cursor: zoom-in; }
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
  &.collapsed { max-height: 132px; overflow: hidden; position: relative; }
  &.collapsed::after {
    content: '';
    position: absolute;
    left: 0; right: 0; bottom: 0;
    height: 44px;
    background: linear-gradient(to bottom, rgba(255, 251, 240, 0), #fffbf0);
    pointer-events: none;
  }
  :deep(h1), :deep(h2), :deep(h3), :deep(h4) { margin: 8px 0 4px; color: #8B4513; line-height: 1.4; }
  :deep(h1) { font-size: 14px; }
  :deep(h2) { font-size: 13.5px; }
  :deep(h3) { font-size: 13px; }
  :deep(h4) { font-size: 12.5px; }
  :deep(p) { margin: 5px 0; overflow-wrap: anywhere; }
  :deep(ul), :deep(ol) { margin: 5px 0; padding-left: 20px; }
  :deep(li) { margin: 2px 0; overflow-wrap: anywhere; }
  :deep(table) { table-layout: fixed; width: 100%; border-collapse: collapse; margin: 6px 0; font-size: 12px; }
  :deep(th), :deep(td) { border: 1px solid #e8e0d8; padding: 3px 6px; text-align: left; word-break: break-word; overflow-wrap: anywhere; vertical-align: top; }
  :deep(th) { background: #faf7f4; }
  :deep(strong) { color: #8B4513; }
  :deep(code) { background: #f5f0eb; padding: 0 3px; border-radius: 3px; }
  :deep(pre) { background: #f5f0eb; padding: 8px; border-radius: 5px; overflow-x: auto; }
  :deep(pre code) { background: transparent; padding: 0; }
  :deep(blockquote) { border-left: 3px solid #d9c9a3; margin: 5px 0; padding-left: 8px; color: #999; }
}
.collapse-box { position: relative; }
.collapse-box.collapsed { max-height: 110px; overflow: hidden; }
.collapse-box.collapsed::after {
  content: '';
  position: absolute;
  left: 0; right: 0; bottom: 0;
  height: 38px;
  background: linear-gradient(to bottom, rgba(255, 255, 255, 0), #fff);
  pointer-events: none;
}
.visit-actions { margin-top: 8px; text-align: right; }
.fu-date { font-size:12px; color:#888; min-width:96px; }
.fu-item { display:flex; align-items:center; gap:8px; flex-wrap:wrap; padding:4px 0; border-bottom:1px dashed #f0f0f0; }
.fu-feedback { margin-top: 6px; font-size: 13px; color: #444; line-height: 1.7; white-space: pre-wrap; }
.rx-doses { font-size: 12px; color: #999; margin-top: 4px; }
.rx-herbs { margin-top: 8px; display: flex; flex-wrap: wrap; gap: 6px; }
.rx-sub-title { margin-top: 8px; font-size: 12.5px; font-weight: 600; color: #6b4f2a; }
.rx-acu-meta { margin-top: 4px; font-size: 12px; color: #999; display: flex; flex-wrap: wrap; gap: 8px; }
.rx-herb { font-size: 12px; background: #f5f7fa; border-radius: 4px; padding: 2px 8px; color: #333; }
.rx-herb b { color: #606266; margin-left: 2px; font-weight: normal; }
.rx-herb .king { color: #F56C6C; font-style: normal; margin-left: 2px; }
.sub-block { margin-top: 10px; border-top: 1px dashed #eee; padding-top: 8px; }
.sub-block + .sub-block { margin-top: 10px; }
.sub-title { font-size: 13px; font-weight: 600; color: #555; margin-bottom: 6px; display: flex; align-items: center; gap: 6px; }
.sub-item { margin-bottom: 8px; }
.sub-note { margin-left: 6px; font-size: 12px; color: #999; }
</style>
