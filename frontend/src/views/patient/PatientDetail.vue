<template>
  <div class="patient-detail" v-loading="loading">
    <el-page-header @back="$router.push('/patients')" :content="patient?.name || '加载中...'">
      <template #extra>
        <div class="header-actions">
          <el-button v-if="editable" @click="openEdit"><el-icon><Edit /></el-icon> 编辑</el-button>
          <el-button v-if="editable" @click="openVisitDrawer()">
            <el-icon><EditPen /></el-icon> 新增就诊
          </el-button>
        </div>
      </template>
    </el-page-header>

    <el-tabs v-model="activeTab" class="detail-tabs" style="margin-top: 16px;">
      <!-- 概览 -->
      <el-tab-pane label="概览" name="overview">
        <el-card v-if="patient" shadow="hover" class="health-overview">
          <template #header><span>🩺 健康速览</span></template>
          <el-row :gutter="12">
            <el-col :xs="12" :sm="6">
              <div class="ho-block">
                <div class="ho-label">体质类型</div>
                <div class="ho-value" :class="{ 'ho-muted': !patient.constitution_type }">
                  {{ patient.constitution_type || '未评估' }}
                </div>
              </div>
            </el-col>
            <el-col :xs="12" :sm="6">
              <div class="ho-block">
                <div class="ho-label">BMI / 身型</div>
                <div class="ho-value" v-if="patient.height != null && patient.weight != null">
                  {{ calcBmi(patient.height, patient.weight)?.toFixed(1) }}
                  <el-tag v-if="bodyTypeOf(patient)" size="small" :style="tagStyleOf(bodyTypeOf(patient)!.color)">{{ bodyTypeOf(patient)!.label }}</el-tag>
                </div>
                <div class="ho-value ho-muted" v-else>未填身高/体重</div>
              </div>
            </el-col>
            <el-col :xs="24" :sm="12">
              <div class="ho-block">
                <div class="ho-label">过敏史</div>
                <el-alert v-if="patient.allergy_history" type="error" :closable="false" show-icon :title="patient.allergy_history" />
                <el-tag v-else type="success" size="small">无过敏史</el-tag>
              </div>
            </el-col>
          </el-row>
          <div class="ho-tags" v-if="patient.tags && patient.tags.length">
            <span class="ho-label">标签</span>
            <el-tag v-for="t in patient.tags" :key="t" size="small" effect="plain" :style="tagStyleOf(t)">{{ t }}</el-tag>
          </div>
        </el-card>
        <el-card shadow="hover">
          <template #header><span>📋 基本信息</span></template>
          <el-descriptions :column="1" border size="small" v-if="patient">
            <el-descriptions-item label="姓名">{{ patient.name }}</el-descriptions-item>
            <el-descriptions-item label="性别">{{ patient.gender }}</el-descriptions-item>
            <el-descriptions-item label="出生日期">{{ patient.birth_date || '-' }}</el-descriptions-item>
            <el-descriptions-item label="年龄">
              {{ patient.birth_date ? (calcAge(patient.birth_date) ?? '-') + ' 岁' : '-' }}
            </el-descriptions-item>
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
            <el-descriptions-item label="身高/体重">
              {{ patient.height != null ? patient.height + 'cm' : '-' }} / {{ patient.weight != null ? patient.weight + 'kg' : '-' }}
            </el-descriptions-item>
            <el-descriptions-item label="身型" v-if="bodyTypeOf(patient)">
              <el-tag size="small" :style="tagStyleOf(bodyTypeOf(patient)!.color)">{{ bodyTypeOf(patient)!.label }}</el-tag>
            </el-descriptions-item>
            <el-descriptions-item label="备注">{{ patient.notes || '-' }}</el-descriptions-item>
            <el-descriptions-item label="标签">
              <template v-if="patient.tags && patient.tags.length">
                <div class="tag-list">
                  <el-tag
                    v-for="t in patient.tags"
                    :key="t"
                    size="small"
                    effect="plain"
                    :style="tagStyleOf(t)"
                  >{{ t }}</el-tag>
                </div>
              </template>
              <span v-else class="text-muted">无</span>
            </el-descriptions-item>
          </el-descriptions>
        </el-card>
      </el-tab-pane>

      <!-- 就诊记录 -->
      <el-tab-pane label="就诊记录" name="visits">
        <el-card shadow="hover">
          <template #header><span>🏥 就诊记录</span></template>
          <!-- 筛选条件：关键词 / 病种 / 日期范围 -->
          <div v-if="visits.length > 0" class="visit-filter">
            <el-input v-model="visitKeyword" clearable placeholder="搜索 病名/主诉/证型/症状" class="vf-key" />
            <el-select v-model="visitDisease" clearable placeholder="按病种筛选" class="vf-disease">
              <el-option v-for="t in visitDiseaseOptions" :key="t" :value="t" :label="t" />
            </el-select>
            <el-date-picker v-model="visitDateRange" type="daterange" value-format="YYYY-MM-DD"
              start-placeholder="开始日期" end-placeholder="结束日期" class="vf-date" />
            <el-button v-if="visitKeyword || visitDisease || visitDateRange" size="small" @click="resetVisitFilter">重置</el-button>
          </div>

          <!-- 按「初诊→复诊」父子关系组织：每条初诊为一个完整就诊，其下内嵌复诊 -->
          <div v-if="visitRoots.length" class="visit-tree">
            <div v-for="root in visitRoots" :key="root.id" class="visit-episode">
              <div class="episode-header" @click="toggleEpisode(root.id)">
                <span class="ep-arrow">{{ openEpisodes.has(root.id) ? '▾' : '▸' }}</span>
                <el-tag size="small" type="info" effect="plain">初诊</el-tag>
                <span class="ep-title">{{ root.chief_complaint }}</span>
                <span class="ep-meta">
                  {{ root.visit_date }}
                  <template v-if="root.tcm_disease || root.tcm_syndrome"> · {{ root.tcm_disease }}{{ root.tcm_syndrome ? ' / ' + root.tcm_syndrome : '' }}</template>
                  <template v-if="root.children && root.children.length"> · 复诊 {{ root.children.length }} 次</template>
                </span>
              </div>
              <div v-show="openEpisodes.has(root.id)">
                <VisitCard
                  :visit="root"
                  :inquiries="inquiriesByVisit[root.id] || []"
                  :prescriptions="rxByVisit[root.id] || []"
                  :followups="followupsByVisit[root.id] || []"
                  :editable="editable"
                  @view="openVisitDialog"
                  @edit="openVisitDrawer"
                  @add-followup="(v) => openFollowupDialog(undefined, v)"
                  @view-followup="openFollowupDialog"
                  @delete-followup="deleteFollowup"
                  @view-rx="openRxDialog"
                  @view-iq="openIqDialog"
                />
                <div v-if="rootTrend(root).length" class="visit-trend">
                  <span class="trend-label">📊 病情变化</span>
                  <span v-for="(t, ti) in rootTrend(root)" :key="'t' + t.visit_id + '-' + ti" class="trend-step">
                    <span class="trend-date">{{ t.date }}</span>
                    <el-tag size="small" :type="improvementTag(t.improvement)">{{ t.improvement }}</el-tag>
                    <span v-if="ti < rootTrend(root).length - 1" class="trend-arrow">→</span>
                  </span>
                </div>
                <div v-if="editable" class="visit-add-child">
                  <el-button link type="success" size="small" icon="Plus" @click="openVisitDrawerWithParent(root)">＋ 复诊</el-button>
                </div>
                <div v-if="root.children && root.children.length" class="visit-children">
                  <VisitCard
                    v-for="child in root.children" :key="child.id"
                    :visit="child"
                    :is-child="true"
                    :inquiries="inquiriesByVisit[child.id] || []"
                    :prescriptions="rxByVisit[child.id] || []"
                    :followups="followupsByVisit[child.id] || []"
                    :editable="editable"
                    @view="openVisitDialog"
                    @edit="openVisitDrawer"
                    @add-followup="(v) => openFollowupDialog(undefined, v)"
                    @view-followup="openFollowupDialog"
                    @delete-followup="deleteFollowup"
                    @view-rx="openRxDialog"
                    @view-iq="openIqDialog"
                  />
                </div>
              </div>
            </div>
          </div>
          <el-empty v-else-if="visits.length" description="无匹配的就诊记录，试试调整筛选条件" />
          <el-empty v-else description="暂无就诊记录" />
        </el-card>
      </el-tab-pane>

      <!-- 病情跟踪：该患者全病程随访/回访轨迹（按日期排序，标注归属初诊，给出整体趋势） -->
      <el-tab-pane label="病情跟踪" name="followup">
        <!-- 随访提醒：处方用药后自动生成；逾期/到期在工作台待办提醒 -->
        <el-card shadow="hover" class="reminder-card">
          <template #header>
            <span>⏰ 随访提醒</span>
            <span class="reminder-hint">处方用药后会自动生成；时间到了会在工作台待办提醒</span>
          </template>
          <div v-if="reminders.length" class="reminder-list">
            <div
              v-for="r in reminders"
              :key="r.id"
              class="reminder-item"
              :class="{ 'is-done': r.status === 'done', 'is-overdue': r.overdue && r.status === 'pending' }"
            >
              <el-tag size="small" :type="r.status === 'done' ? 'success' : r.overdue ? 'danger' : 'primary'">
                {{ r.status === 'done' ? '已完成' : r.overdue ? '已逾期' : '待回访' }}
              </el-tag>
              <span class="reminder-date">{{ r.due_date }}</span>
              <span v-if="r.note" class="reminder-note">{{ r.note }}</span>
              <span class="reminder-actions" v-if="editable">
                <el-button v-if="r.status === 'pending'" link type="success" size="small" @click="setReminderStatus(r, 'done')">完成</el-button>
                <el-button v-if="r.status === 'pending'" link type="warning" size="small" @click="setReminderStatus(r, 'cancelled')">取消</el-button>
                <el-button link type="danger" size="small" @click="deleteReminder(r)">删除</el-button>
              </span>
            </div>
          </div>
          <el-empty v-else description="暂无随访提醒" :image-size="50" />
          <el-form v-if="editable" :inline="true" class="reminder-add">
            <el-form-item label="应回访日期">
              <el-date-picker v-model="newReminderDate" type="date" value-format="YYYY-MM-DD" placeholder="选择日期" style="width: 160px;" />
            </el-form-item>
            <el-form-item label="备注">
              <el-input v-model="newReminderNote" placeholder="如：7 剂服完复诊" style="width: 200px;" />
            </el-form-item>
            <el-form-item>
              <el-button type="primary" size="small" :loading="savingReminder" @click="addReminder">添加提醒</el-button>
            </el-form-item>
          </el-form>
        </el-card>
        <el-card shadow="hover">
          <template #header>
            <span>📈 病情跟踪（全病程恢复轨迹）</span>
            <el-button v-if="editable" link type="primary" size="small" style="float:right;height:auto;" @click="openFollowupDialog()">+ 新增跟踪</el-button>
          </template>
          <div v-if="allFollowups.length" class="fu-summary">
            <span>共 {{ allFollowups.length }} 次随访</span>
            <el-tag size="small" :type="followupTrend.type">{{ followupTrend.label }}</el-tag>
            <span class="fu-latest">最近：{{ allFollowups[allFollowups.length - 1].followup_date }}</span>
          </div>
          <el-timeline v-if="allFollowups.length">
            <el-timeline-item v-for="fu in allFollowups" :key="fu.id" :timestamp="fu.followup_date" placement="top">
              <el-card shadow="never" class="visit-card">
                <div class="visit-header">
                  <el-tag size="small" :type="fu.treatment_type === '针灸' ? 'success' : 'primary'">{{ fu.treatment_type || '未填' }}</el-tag>
                  <el-tag v-if="fu.improvement" size="small" :type="improvementTag(fu.improvement)">{{ fu.improvement }}</el-tag>
                  <span
                    v-if="fu.episodeVisit"
                    class="fu-episode fu-episode--link"
                    @click="openVisitDialog(fu.episodeVisit)"
                  >归属：{{ fu.episodeLabel }} ↗</span>
                  <span v-else class="fu-episode fu-episode--orphan">{{ fu.episodeLabel }}</span>
                  <span v-if="editable" class="visit-actions" style="float:right;">
                    <el-button link type="primary" size="small" @click="openFollowupDialog(fu)">编辑</el-button>
                    <el-button link type="danger" size="small" @click="deleteFollowup(fu)">删除</el-button>
                  </span>
                </div>
                <div v-if="fu.feedback" class="fu-feedback">{{ fu.feedback }}</div>
                <div v-if="rxByVisit[fu.visit_id] && rxByVisit[fu.visit_id].length" class="fu-rx">
                  <div class="fu-rx-title">关联开方（本次反馈所对应的上次方案）</div>
                  <div v-for="rx in rxByVisit[fu.visit_id]" :key="rx.id" class="fu-rx-item">
                    <el-tag size="small" type="primary">{{ rx.formula_name || rx.prescription_type || '处方' }}</el-tag>
                    <span v-if="rx.treatment_days">疗程 {{ rx.treatment_days }} 天</span>
                    <span v-if="rx.doses">{{ rx.doses }} 剂</span>
                    <span v-if="rx.items && rx.items.length">· {{ rx.items.length }} 味</span>
                  </div>
                </div>
              </el-card>
            </el-timeline-item>
          </el-timeline>
          <el-empty v-else description="暂无随访/回访记录，可在『就诊记录』卡片或此处添加" />
        </el-card>
      </el-tab-pane>
    </el-tabs>

    <el-dialog v-model="editVisible" title="编辑患者信息" width="560px" class="patient-form-dialog">
      <el-form :model="editForm" label-width="80px" label-position="top">
        <el-row :gutter="12">
          <el-col :xs="24" :sm="12">
            <el-form-item label="姓名" required>
              <el-input v-model="editForm.name" />
            </el-form-item>
          </el-col>
          <el-col :xs="24" :sm="12">
            <el-form-item label="性别">
              <el-select v-model="editForm.gender" style="width:100%">
                <el-option label="男" value="男" /><el-option label="女" value="女" />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="12">
          <el-col :xs="24" :sm="12">
            <el-form-item label="出生日期">
              <el-date-picker v-model="editForm.birth_date" type="date" value-format="YYYY-MM-DD" style="width:100%" />
            </el-form-item>
          </el-col>
          <el-col :xs="24" :sm="12">
            <el-form-item label="年龄">
              <el-input :model-value="calcAge(editForm.birth_date) ?? ''" disabled placeholder="自动计算" style="width:100%">
                <template #append>岁</template>
              </el-input>
            </el-form-item>
          </el-col>
          <el-col :xs="24" :sm="6">
            <el-form-item label="身高(cm)">
              <el-input v-model.number="editForm.height" type="number" placeholder="如 170" />
            </el-form-item>
          </el-col>
          <el-col :xs="24" :sm="6">
            <el-form-item label="体重(kg)">
              <el-input v-model.number="editForm.weight" type="number" placeholder="如 65" />
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
        <el-form-item label="标签">
          <div class="tag-picker">
            <el-tag
              v-for="t in tagOptions"
              :key="t.id"
              class="tag-option"
              :class="{ 'tag-selected': (editForm.tags || []).includes(t.name) }"
              :style="tagChipStyle(t)"
              effect="plain"
              @click="toggleTag(t.name)"
            >{{ t.name }}</el-tag>
            <span v-if="!tagOptions.length" class="text-muted">暂无标签，请到『数据字典 → 患者标签』添加</span>
          </div>
          <div style="font-size:12px;color:#999;margin-top:4px;">点击标签切换选中（颜色由字典定义）；新增/停用请到字典页操作</div>
        </el-form-item>
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
      <div v-if="viewVisit.tongue_image || viewVisit.face_image || (viewVisit.lab_report_images && viewVisit.lab_report_images.length)" class="sub-block" style="margin-top: 14px;">
        <div class="sub-title">📷 影像资料</div>
        <div class="visit-imgs">
          <div v-if="viewVisit.tongue_image" class="visit-img-item">
            <span class="img-label">舌苔</span>
            <el-image :src="viewVisit.tongue_image" fit="cover" class="visit-thumb" :preview-src-list="[viewVisit.tongue_image]" />
          </div>
          <div v-if="viewVisit.face_image" class="visit-img-item">
            <span class="img-label">面色</span>
            <el-image :src="viewVisit.face_image" fit="cover" class="visit-thumb" :preview-src-list="[viewVisit.face_image]" />
          </div>
          <div v-for="(img, i) in (viewVisit.lab_report_images || [])" :key="i" class="visit-img-item">
            <span class="img-label">化验单{{ (viewVisit.lab_report_images || []).length > 1 ? i + 1 : '' }}</span>
            <el-image :src="img" fit="cover" class="visit-thumb" :preview-src-list="viewVisit.lab_report_images || []" :initial-index="i" />
          </div>
        </div>
      </div>
      <div v-if="viewVisit.ai_analysis" class="sub-block" style="margin-top: 14px;">
        <div class="sub-title">🤖 AI 诊断库（辨证论治）</div>
        <div class="view-ai-analysis" v-html="renderMarkdown(viewVisit.ai_analysis)"></div>
      </div>
      <template #footer>
        <el-button @click="showVisitDialog = false">关闭</el-button>
        <el-button type="primary" @click="showVisitDialog = false; openVisitDrawer(viewVisit?.id)">完善/编辑此就诊</el-button>
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
          <template v-for="(val, key) in viewIq.notes" :key="key">
            <div v-if="val && String(val).trim()" class="note-line">
              <b>{{ key }}</b>：{{ val }}
            </div>
          </template>
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

    <!-- 病情跟踪 新增/编辑 -->
    <el-dialog v-model="followupVisible" :title="followupForm.id ? '编辑病情跟踪' : '新增病情跟踪'" width="520px">
      <el-form :model="followupForm" label-width="90px" label-position="top">
        <el-form-item label="随访日期" required>
          <el-date-picker v-model="followupForm.followup_date" type="date" value-format="YYYY-MM-DD" style="width:100%" />
        </el-form-item>
        <el-form-item label="治疗类型">
          <el-select v-model="followupForm.treatment_type" style="width:100%" placeholder="选择治疗方式">
            <el-option label="中药" value="中药" />
            <el-option label="针灸" value="针灸" />
            <el-option label="其他" value="其他" />
          </el-select>
        </el-form-item>
        <el-form-item label="关联就诊">
          <el-select v-model="followupForm.visit_id" clearable filterable placeholder="选择对应的初诊/复诊（留空为独立随访）" style="width:100%">
            <el-option
              v-for="v in visits"
              :key="v.id"
              :value="v.id"
              :label="`${v.visit_date} · ${v.visit_type} · ${v.chief_complaint || v.tcm_disease || ''}`"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="改善程度">
          <el-select v-model="followupForm.improvement" style="width:100%" placeholder="选择改善程度">
            <el-option label="明显好转" value="明显好转" />
            <el-option label="好转" value="好转" />
            <el-option label="稳定" value="稳定" />
            <el-option label="反复" value="反复" />
            <el-option label="加重" value="加重" />
          </el-select>
        </el-form-item>
        <el-form-item label="效果反馈">
          <el-input v-model="followupForm.feedback" type="textarea" :rows="3" placeholder="症状变化、耐受情况、患者反馈等" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="followupVisible = false">取消</el-button>
        <el-button type="primary" @click="saveFollowup" :loading="savingFollowup">保存</el-button>
      </template>
    </el-dialog>

    <!-- 新增/编辑就诊：抽屉式，复用 VisitRecord（embedded），保留详情上下文 -->
    <el-drawer
      v-model="visitDrawer"
      :title="visitDrawerId ? '编辑就诊' : '新增就诊'"
      size="72%"
      :with-header="true"
      destroy-on-close
    >
      <VisitRecord
        :patient-id="patientId"
        :patient-name="patient?.name || ''"
        :patient-tags="patient?.tags || []"
        :visit-id="visitDrawerId"
        :parent-visit="visitDrawerParent"
        embedded
        @saved="onVisitSaved"
        @cancel="visitDrawer = false"
      />
    </el-drawer>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { Edit, EditPen, TrendCharts } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import api from '@/utils/api'
import { useAuthStore } from '@/store/auth'
import { renderMarkdown } from '@/utils/markdown'
import { calcAge, calcBmi, bodyType } from '@/utils/health'
import VisitRecord from '@/views/patient/VisitRecord.vue'
import VisitCard from '@/components/VisitCard.vue'

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

// —— 就诊记录筛选 + 按病种分组（方案A）——
const visitKeyword = ref('')
const visitDisease = ref('')
const visitDateRange = ref<[string, string] | null>(null)
function resetVisitFilter() {
  visitKeyword.value = ''
  visitDisease.value = ''
  visitDateRange.value = null
}
const visitDiseaseOptions = computed(() => {
  const set = new Set<string>()
  visits.value.forEach((v: any) => { if (v.tcm_disease && v.tcm_disease.trim()) set.add(v.tcm_disease.trim()) })
  return Array.from(set)
})
const filteredVisits = computed(() => {
  let list = visits.value.slice()
  const kw = visitKeyword.value.trim().toLowerCase()
  if (kw) {
    list = list.filter((v: any) =>
      [v.chief_complaint, v.tcm_disease, v.tcm_syndrome, v.treatment_method, v.observation, v.inquiry, v.palpation]
        .some((f: any) => f && String(f).toLowerCase().includes(kw)))
  }
  if (visitDisease.value) {
    const d = visitDisease.value
    list = list.filter((v: any) => (v.tcm_disease || '').trim() === d)
  }
  if (visitDateRange.value?.[0]) {
    const [s, e] = visitDateRange.value
    list = list.filter((v: any) => v.visit_date >= s && v.visit_date <= e)
  }
  return list
})
// 就诊记录：按「初诊→复诊」父子关系组织成一棵就诊树（初诊为根，复诊内嵌其下）
const visitRoots = computed<any[]>(() => {
  const all = visits.value
  const matched = new Set(filteredVisits.value.map((v: any) => v.id))
  const childrenOf: Record<number, any[]> = {}
  const roots: any[] = []
  for (const v of all) {
    const pid = v.parent_visit_id
    if (pid == null) roots.push(v)
    else (childrenOf[pid] ||= []).push(v)
  }
  roots.sort((a: any, b: any) => b.visit_date.localeCompare(a.visit_date))
  const out: any[] = []
  for (const r of roots) {
    const chAll = (childrenOf[r.id] || []).slice().sort((a: any, b: any) => a.visit_date.localeCompare(b.visit_date))
    const ch = chAll.filter((c: any) => matched.has(c.id))
    if (matched.has(r.id) || ch.length) out.push({ ...r, children: ch })
  }
  return out
})
// 初诊(根)及其复诊的随访改善趋势
function rootTrend(root: any): any[] {
  const items: any[] = []
  const collect = (v: any) => {
    for (const fu of followupsByVisit.value[v.id] || []) {
      if (fu && fu.improvement) items.push({ date: fu.followup_date, improvement: fu.improvement, visit_id: v.id })
    }
  }
  collect(root)
  for (const c of root.children || []) collect(c)
  items.sort((a: any, b: any) => String(a.date).localeCompare(String(b.date)))
  return items
}

// 初诊链折叠：表头常驻，点一下收起/展开该初诊及其随访复诊
const openEpisodes = reactive(new Set<number>())
function toggleEpisode(id: number) {
  openEpisodes.has(id) ? openEpisodes.delete(id) : openEpisodes.add(id)
}

// 病情跟踪
const followups = ref<any[]>([])
const reminders = ref<any[]>([])
const followupVisible = ref(false)
// 随访提醒：新增表单
const newReminderDate = ref('')
const newReminderNote = ref('')
const savingReminder = ref(false)
const savingFollowup = ref(false)
const followupForm = ref<any>({ id: null, followup_date: '', treatment_type: '', improvement: '', feedback: '', visit_id: null })
// 字典中的患者标签（供编辑表单选择）
const tagOptions = ref<any[]>([])

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
  // 优先按 visit_id 直接关联
  for (const iq of inquiries.value) {
    if (iq.visit_id != null) (m[iq.visit_id] ||= []).push(iq)
  }
  // 未关联 visit_id 的（旧数据/未回填），按就诊日期归并到当天就诊：问诊十问通常在就诊时进行
  const used = new Set<number>()
  for (const id in m) for (const iq of m[id]) used.add(iq.id)
  const visitsByDate: Record<string, number[]> = {}
  for (const v of visits.value) {
    const d = (v.visit_date || '').slice(0, 10)
    if (d) (visitsByDate[d] ||= []).push(v.id)
  }
  for (const iq of inquiries.value) {
    if (used.has(iq.id)) continue
    const d = (iq.created_at || '').slice(0, 10)
    const vids = d ? visitsByDate[d] : undefined
    if (vids && vids.length) {
      const vid = vids[0]
      ;(m[vid] ||= []).push(iq)
      used.add(iq.id)
    }
  }
  return m
})
// 按就诊聚合：随访/回访记录归到对应的 visit_id 下
const followupsByVisit = computed<Record<number, any[]>>(() => {
  const m: Record<number, any[]> = {}
  for (const fu of followups.value) {
    if (fu.visit_id != null) (m[fu.visit_id] ||= []).push(fu)
  }
  const orphans: any[] = []
  for (const fu of followups.value) if (fu.visit_id == null) orphans.push(fu)
  if (orphans.length) m[-1] = orphans
  return m
})
// 病情跟踪：汇总该患者全部随访（含已关联/未关联就诊），按日期排序，标注归属初诊，整体趋势
const allFollowups = computed<any[]>(() => {
  const byId = new Map(visits.value.map((v: any) => [v.id, v]))
  const rootOf = (vid: number | null): any => {
    let cur = vid != null ? byId.get(vid) : null
    while (cur && cur.parent_visit_id != null && byId.has(cur.parent_visit_id)) cur = byId.get(cur.parent_visit_id)
    return cur || null
  }
  return followups.value
    .map((fu: any) => {
      const root = rootOf(fu.visit_id)
      return {
        ...fu,
        episodeVisit: root,
        episodeLabel: root ? `${root.visit_date} · ${root.chief_complaint || root.tcm_disease || '初诊'}` : '未关联就诊',
      }
    })
    .sort((a: any, b: any) => String(a.followup_date).localeCompare(String(b.followup_date)))
})
// 整体改善趋势：按首末次评估推断（末次 - 首次）
const IMPROVE_SCORE: Record<string, number> = { 明显好转: 2, 好转: 1, 稳定: 0, 反复: -1, 加重: -2 }
const followupTrend = computed<{ label: string; type: string }>(() => {
  const scored = allFollowups.value
    .map((f: any) => IMPROVE_SCORE[f.improvement])
    .filter((s: number | undefined): s is number => s !== undefined)
  if (!scored.length) return { label: '暂无评估', type: 'info' }
  const delta = scored[scored.length - 1] - scored[0]
  if (delta > 0) return { label: '整体向好', type: 'success' }
  if (delta < 0) return { label: '整体变差', type: 'danger' }
  return { label: '总体平稳', type: 'warning' }
})

const editVisible = ref(false)
const savingEdit = ref(false)
const editForm = ref<any>({})

const showVisitDialog = ref(false)
const viewVisit = ref<any>(null)
const showIqDialog = ref(false)
const viewIq = ref<any>(null)
const showRxDialog = ref(false)
const viewRx = ref<any>(null)

// 新增/编辑就诊：抽屉式，复用 VisitRecord（embedded），保留详情上下文
const activeTab = ref('overview')
const visitDrawer = ref(false)
const visitDrawerId = ref<number | null>(null)
const visitDrawerParent = ref<any>(null)
function openVisitDrawer(id?: number) {
  visitDrawerId.value = id ?? null
  visitDrawerParent.value = null
  visitDrawer.value = true
}
// 基于某次初诊发起复诊：抽屉内表单以该初诊为底稿并标记 parent 关系
function openVisitDrawerWithParent(root: any) {
  visitDrawerId.value = null
  visitDrawerParent.value = root
  visitDrawer.value = true
}
async function onVisitSaved() {
  visitDrawer.value = false
  try { await loadPatientData() } catch {}
}

function openVisitDialog(v: any) { viewVisit.value = v; showVisitDialog.value = true }
function openIqDialog(i: any) { viewIq.value = i; showIqDialog.value = true }
function openRxDialog(p: any) { viewRx.value = p; showRxDialog.value = true }

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

// 患者标签颜色：优先用字典词条自定义 color，否则回退危险/普通
const tagColorMap = computed<Record<string, string>>(() => {
  const m: Record<string, string> = {}
  for (const t of tagOptions.value) if (t.name) m[t.name] = t.color
  return m
})
function tagStyleOf(name: string): Record<string, string> {
  const c = tagColorMap.value[name]
  return c ? { backgroundColor: c, borderColor: c, color: '#fff' } : {}
}
function bodyTypeOf(p: any): { label: string; color: string } | null {
  return bodyType(calcBmi(p.height, p.weight))
}

// 标签彩色点选：选中用字典 color 实心，未选中用描边
function toggleTag(name: string) {
  const cur = editForm.value.tags || []
  editForm.value.tags = cur.includes(name) ? cur.filter((x: string) => x !== name) : [...cur, name]
}
function tagChipStyle(t: any): Record<string, string> {
  const selected = (editForm.value.tags || []).includes(t.name)
  const c = t.color || '#909399'
  return selected
    ? { backgroundColor: c, borderColor: c, color: '#fff' }
    : { color: c, borderColor: c, backgroundColor: '#fff' }
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
    height: p.height ?? null,
    weight: p.weight ?? null,
    allergy_history: p.allergy_history || '',
    medical_history: p.medical_history || '',
    notes: p.notes || '',
    tags: p.tags || [],
  }
  editVisible.value = true
}

async function saveEdit() {
  if (!editForm.value.name.trim()) { ElMessage.warning('请填写姓名'); return }
  savingEdit.value = true
  try {
    patient.value = await api.put(`/patients/${patientId}`, editForm.value, { silent: true })
    ElMessage.success('已保存')
    editVisible.value = false
  } catch {
    ElMessage.error('保存失败')
  }
  savingEdit.value = false
}

// ── 病情跟踪 ──
async function loadFollowups() {
  followups.value = (await api.get(`/patients/${patientId}/followups`)) as any
}

function openFollowupDialog(fu?: any, visit?: any) {
  if (fu) {
    followupForm.value = { ...fu }
  } else {
    followupForm.value = {
      id: null,
      followup_date: new Date().toISOString().slice(0, 10),
      treatment_type: '',
      improvement: '',
      feedback: '',
      visit_id: visit?.id ?? null,
    }
  }
  followupVisible.value = true
}

async function saveFollowup() {
  if (!followupForm.value.followup_date) { ElMessage.warning('请选择随访日期'); return }
  savingFollowup.value = true
  try {
    if (followupForm.value.id) {
      await api.put(`/patients/${patientId}/followups/${followupForm.value.id}`, followupForm.value, { silent: true })
    } else {
      await api.post(`/patients/${patientId}/followups`, followupForm.value, { silent: true })
    }
    ElMessage.success('已保存')
    followupVisible.value = false
    await loadFollowups()
  } catch {}
  savingFollowup.value = false
}

async function deleteFollowup(fu: any) {
  try {
    await api.delete(`/patients/${patientId}/followups/${fu.id}`, { silent: true })
    ElMessage.success('已删除')
    await loadFollowups()
  } catch {}
}

async function loadPatientData() {
  const [p, v, iq, rx, fus, tags, rms] = await Promise.all([
    api.get(`/patients/${patientId}`),
    api.get(`/patients/${patientId}/visits`),
    api.get(`/patients/${patientId}/inquiries`),
    api.get(`/prescriptions?patient_id=${patientId}`),
    api.get(`/patients/${patientId}/followups`),
    api.get('/dictionaries', { params: { term_type: 'tag', is_active: true } }),
    api.get(`/followup-reminders?patient_id=${patientId}`),
  ])
  patient.value = p
  visits.value = v as any
  inquiries.value = iq as any
  prescriptions.value = rx as any
  followups.value = fus as any
  tagOptions.value = tags as any
  reminders.value = (rms || []) as any
}

async function loadReminders() {
  try {
    reminders.value = (await api.get(`/followup-reminders?patient_id=${patientId}`)) as any
  } catch {}
}
async function addReminder() {
  if (!newReminderDate.value) { ElMessage.warning('请选择应回访日期'); return }
  savingReminder.value = true
  try {
    await api.post('/followup-reminders', {
      patient_id: Number(patientId),
      due_date: newReminderDate.value,
      note: newReminderNote.value || null,
      source_type: 'manual',
    }, { silent: true })
    ElMessage.success('已添加随访提醒')
    newReminderDate.value = ''
    newReminderNote.value = ''
    await loadReminders()
  } catch {}
  savingReminder.value = false
}
async function setReminderStatus(r: any, status: string) {
  try {
    await api.patch(`/followup-reminders/${r.id}`, { status }, { silent: true })
    ElMessage.success(status === 'done' ? '已标记完成' : status === 'cancelled' ? '已取消' : '已更新')
    await loadReminders()
  } catch {}
}
async function deleteReminder(r: any) {
  try {
    await api.delete(`/followup-reminders/${r.id}`, { silent: true })
    ElMessage.success('已删除')
    await loadReminders()
  } catch {}
}

onMounted(async () => {
  loading.value = true
  try {
    await loadPatientData()
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
.tag-picker { display: flex; flex-wrap: wrap; gap: 8px; }
.tag-option { cursor: pointer; user-select: none; transition: all .15s; }
.tag-option:hover { opacity: .85; }
.tag-selected { font-weight: 600; }
.patient-tags { margin: 12px 0 0 8px; }
.tag-list { display: flex; flex-wrap: wrap; gap: 4px; }
.visit-filter { display: flex; gap: 8px; flex-wrap: wrap; margin-bottom: 14px; }
.vf-key { width: 200px; }
.vf-disease { width: 150px; }
.vf-date { width: 240px; }
.visit-group { margin-bottom: 6px; }
.visit-tree { margin-top: 4px; }
.visit-episode { margin-bottom: 14px; border: 1px solid #eee; border-radius: 8px; overflow: hidden; }
.episode-header {
  display: flex; align-items: center; gap: 8px;
  padding: 9px 12px;
  background: #f7f3ee; cursor: pointer;
  font-size: 14px; user-select: none;
}
.episode-header:hover { background: #f0e9e0; }
.ep-arrow { color: #b07d33; font-size: 12px; width: 12px; text-align: center; }
.ep-title { font-weight: 600; color: #6b4f2a; }
.ep-meta { font-size: 12px; color: #999; margin-left: auto; text-align: right; }
.visit-children { padding-top: 4px; }
.visit-card { margin-bottom: 4px; }
.visit-header { font-size: 14px; }
.visit-diagnosis { margin-top: 8px; display: flex; gap: 6px; }
.visit-sizhen { margin-top: 8px; font-size: 13px; color: #666; display: flex; gap: 12px; }
.visit-imgs { display: flex; flex-wrap: wrap; gap: 12px; margin-top: 6px; }
.visit-img-item { text-align: center; }
.visit-img-item .img-label { display: block; font-size: 12px; color: #999; margin-bottom: 4px; }
.visit-thumb { width: 96px; height: 96px; border-radius: 6px; border: 1px solid #eee; cursor: zoom-in; }
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
  &.collapsed {
    max-height: 132px;
    overflow: hidden;
    position: relative;
  }
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
/* 通用半折叠：默认截断高度 + 底部渐隐，配合「查看全部/收起」切换（问诊十问复用） */
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
.visit-trend { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; margin: 2px 0 8px 14px; padding: 6px 10px; background: #faf8f5; border-radius: 6px; }
.visit-trend .trend-label { font-size: 12px; font-weight: 600; color: #8B4513; }
.trend-step { display: inline-flex; align-items: center; gap: 5px; }
.trend-date { font-size: 12px; color: #999; }
.fu-date { font-size:12px; color:#888; min-width:96px; }
.fu-item { display:flex; align-items:center; gap:8px; flex-wrap:wrap; padding:4px 0; border-bottom:1px dashed #f0f0f0; }
.fu-feedback { margin-top: 6px; font-size: 13px; color: #444; line-height: 1.7; white-space: pre-wrap; }
.fu-summary { display: flex; align-items: center; gap: 12px; margin-bottom: 12px; font-size: 13px; color: #666; }
.fu-summary .fu-latest { color: #999; }
.fu-episode { font-size: 12px; margin-left: 8px; padding: 1px 6px; border-radius: 4px; }
.fu-episode--link { color: #409eff; background: #ecf5ff; cursor: pointer; }
.fu-episode--link:hover { background: #d9ecff; }
.fu-episode--orphan { color: #999; background: #f5f5f5; }
/* 病情跟踪：关联开方对比 */
.fu-rx { margin-top: 8px; padding: 8px 10px; background: #f7faff; border-left: 3px solid #409eff; border-radius: 4px; }
.fu-rx-title { font-size: 12px; color: #409eff; margin-bottom: 4px; }
.fu-rx-item { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; font-size: 12px; color: #555; padding: 2px 0; }
/* 病情跟踪：随访提醒 */
.reminder-card .reminder-hint { font-size: 12px; color: #999; font-weight: 400; margin-left: 8px; }
.reminder-list { margin-bottom: 8px; }
.reminder-item { display: flex; align-items: center; gap: 10px; padding: 7px 0; border-bottom: 1px solid #f0f0f0; flex-wrap: wrap; }
.reminder-item.is-done { opacity: 0.55; }
.reminder-item.is-overdue .reminder-date { color: #f56c6c; font-weight: 600; }
.reminder-date { font-weight: 500; }
.reminder-note { font-size: 12px; color: #999; }
.reminder-actions { margin-left: auto; }
.reminder-add { margin-top: 8px; }
/* 概览：健康速览卡 */
.health-overview .ho-block { padding: 6px 4px; }
.health-overview .ho-label { font-size: 12px; color: #999; margin-bottom: 6px; }
.health-overview .ho-value { font-size: 16px; font-weight: 600; color: #6b4f2a; display: flex; align-items: center; gap: 6px; flex-wrap: wrap; }
.health-overview .ho-value.ho-muted { font-size: 13px; font-weight: 400; color: #c0c4cc; }
.health-overview .ho-tags { margin-top: 12px; display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.health-overview .ho-tags .ho-label { margin-bottom: 0; }
/* 弹窗内容超高时，仅 body 内部滚动，底部按钮始终可见（避免 AI 分析把弹窗顶飞） */
.visit-detail-dialog :deep(.el-dialog__body),
.iq-detail-dialog :deep(.el-dialog__body),
.rx-detail-dialog :deep(.el-dialog__body) {
  max-height: 72vh;
  overflow-y: auto;
}
/* 患者表单弹窗：顶部对齐，内容区内滚动，保证一屏内显示全 */
.patient-form-dialog { margin-top: 4vh !important; }
.patient-form-dialog :deep(.el-dialog__body) { max-height: 82vh; overflow-y: auto; }
@media (max-width: 767px) {
  .patient-form-dialog { margin-top: 4vh !important; }
  .patient-form-dialog :deep(.el-dialog__body) { max-height: 82vh; }
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