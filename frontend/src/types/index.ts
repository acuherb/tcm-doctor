/**
 * 前端领域类型基础。
 *
 * 说明：此前 api 层运行时已解包为后端数据体（Promise<T>），但调用点多为 `any`。
 * 这里集中定义领域接口与分页/响应包裹类型，供各模块逐步替换 `any` 使用。
 * 接口字段默认可选并带 `[key: string]: any` 索引签名，便于逐步迁移而不引入大批量类型错误。
 */

// 后端列表接口统一返回 { items, total, page?, page_size? }
export interface Paginated<T> {
  items: T[]
  total: number
  page?: number
  page_size?: number
}

// 单条记录的响应即数据体本身（与 api 层解包后一致）
export type ApiResponse<T> = T

// 当前登录用户（与后端 auth.TokenOut/user 字段同源）
export interface TcmUser {
  id: number
  username: string
  display_name?: string | null
  department?: string | null
  is_admin?: boolean
  role?: string
  permissions?: string[]
  is_active?: boolean
  must_change_password?: boolean
  [key: string]: any
}

// 患者
export interface Patient {
  id?: number
  name?: string
  gender?: string
  birth_date?: string
  phone?: string
  constitution_type?: string
  tags?: string[]
  [key: string]: any
}

// 就诊记录
export interface Visit {
  id?: number
  patient_id?: number
  patient_name?: string | null
  visit_date?: string
  visit_type?: string | null
  chief_complaint?: string
  // 挂号（前台分诊登记）字段
  queue_no?: number | null
  registration_fee?: number | null
  registered_at?: string | null
  registrar_id?: number | null
  department?: string | null
  doctor_id?: number | null
  doctor_name?: string | null
  status?: string | null
  tongue_body_term_id?: number | null
  tongue_coat_term_id?: number | null
  pulse_term_id?: number | null
  syndrome_term_id?: number | null
  [key: string]: any
}

// 挂号登记（前台分诊）
export interface RegistrationCreate {
  patient_id?: number
  new_patient?: {
    name: string
    phone?: string | null
    gender?: string | null
    birth_date?: string | null
  }
  department?: string | null
  doctor_id?: number | null
  registration_fee?: number
  payment_method?: string | null
  paid?: number | null
  force?: boolean
}

export interface RegistrationUpdate {
  status?: string
  department?: string | null
}

export interface RegistrationQueueItem extends Visit {
  registration_charge?: Charge | null
  // 状态判定依据（后端按病历/处方/收费/发药等业务事实计算）
  evidence?: {
    has_record: boolean
    prescription_count: number
    unsettled_prescriptions: number
    dispensed: boolean
    paid_prescriptions: number
    can_complete: boolean
    completion_blockers: string[]
    completion_warnings: string[]
    can_revert: boolean
    revert_hint: string
  }
}

export interface RegistrationQueueResponse {
  items: RegistrationQueueItem[]
  date: string
}

// 处方
export interface Prescription {
  id?: number
  visit_id?: number
  patient_id?: number
  formula_name?: string
  total_price?: number | null
  patient_name?: string | null
  // 在账收费单状态（列表/详情批量回填，用于收敛「收费」按钮）
  charge_id?: number | null
  charge_no?: string | null
  charge_status?: string | null
  doctor_id?: number | null
  classic_formula_id?: number | null
  acupoint_formula_id?: number | null
  items?: PrescriptionItem[]
  injections?: PrescriptionInjection[]
  acupoints?: AcupointPrescription[]
  // 电子签名与防篡改
  content_hash?: string | null
  signed_by?: string | null
  signed_by_id?: number | null
  signed_at?: string | null
  signature?: string | null
  tampered?: boolean
  signed?: boolean
  signature_valid?: boolean
  [key: string]: any
}

export interface PrescriptionItem {
  id?: number
  herb_id?: number | null
  herb_name?: string
  dose?: string
  [key: string]: any
}

export interface PrescriptionInjection {
  id?: number
  drug_name?: string
  [key: string]: any
}

export interface AcupointPrescription {
  id?: number
  acupoint_id?: number | null
  acupoint_name?: string
  [key: string]: any
}

// 库存物品 / 批次 / 流水 / 供应商 / 采购
export interface StockItem {
  id?: number
  name?: string
  item_type?: string
  unit?: string
  quantity?: number
  herb_id?: number | null
  default_supplier_id?: number | null
  [key: string]: any
}

export interface StockBatch {
  id?: number
  item_id?: number
  batch_number?: string | null
  quantity?: number
  [key: string]: any
}

export interface StockTransaction {
  id?: number
  item_id?: number
  transaction_type?: string
  quantity?: number
  created_at?: string
  [key: string]: any
}

export interface Supplier {
  id?: number
  name?: string
  contact?: string
  phone?: string
  [key: string]: any
}

export interface PurchaseOrder {
  id?: number
  order_date?: string
  supplier_id?: number | null
  note?: string
  [key: string]: any
}

// 药材
export interface Herb {
  id?: number
  name?: string
  pinyin?: string
  [key: string]: any
}

// 字典词条
export interface DictionaryTerm {
  id?: number
  category?: string
  term?: string
  [key: string]: any
}

// 库存选项（类别/单位等自定义标签）
export interface StockOption {
  id?: number
  opt_type?: string
  name?: string
  color?: string
  [key: string]: any
}

// 知识库条目 / 医籍
export interface KnowledgeEntry {
  id?: number
  title?: string
  category?: string
  [key: string]: any
}

// 经典方 / 针灸方
export interface ClassicFormula {
  id?: number
  name?: string
  [key: string]: any
}

export interface AcupointFormula {
  id?: number
  name?: string
  [key: string]: any
}

// 穴位
export interface Acupoint {
  id?: number
  name?: string
  [key: string]: any
}

// 操作日志
export interface OperationLog {
  id?: number
  username?: string
  action?: string
  action_display?: string
  created_at?: string
  [key: string]: any
}

// 随访 / 问诊 / 会话
export interface FollowUp {
  id?: number
  patient_id?: number
  followup_date?: string
  [key: string]: any
}

export interface InquiryRecord {
  id?: number
  patient_id?: number
  [key: string]: any
}

export interface Conversation {
  id?: number
  patient_id?: number | null
  title?: string
  [key: string]: any
}

// 登录返回（与后端 auth.TokenOut 同源）
export interface AuthLoginResult {
  token: string
  user: TcmUser
  must_change_password?: boolean
  [key: string]: any
}

// 应用配置（与后端 config 端点返回同源，字段较多且向后兼容，故宽松）
export interface AppConfig {
  brand_name?: string
  brand_color?: string
  allow_guest_login?: boolean
  clinic_name?: string
  clinic_logo?: string
  ui_theme?: string
  [key: string]: any
}

// 消息
export interface Message {
  id?: number
  conversation_id?: string
  role?: string
  content?: string
  [key: string]: any
}

// 采购明细
export interface PurchaseItem {
  id?: number
  purchase_id?: number
  item_id?: number
  quantity?: number
  price?: number
  [key: string]: any
}

// 知识来源
export interface KnowledgeSource {
  id?: number
  title?: string
  [key: string]: any
}

// 收费单
export interface Charge {
  id?: number
  charge_no?: string
  prescription_id?: number
  patient_id?: number | null
  visit_id?: number | null
  patient_name?: string | null
  prescription_title?: string | null
  amount?: number
  discount?: number
  payable?: number
  paid?: number
  overpaid?: number
  refund_amount?: number
  net_paid?: number
  payment_method?: string | null
  status?: string
  cashier_name?: string | null
  paid_at?: string | null
  refunded_by?: string | null
  refunded_at?: string | null
  refund_reason?: string | null
  cancelled_by?: string | null
  cancelled_at?: string | null
  cancel_reason?: string | null
  note?: string | null
  created_at?: string | null
  prescription?: Prescription
  [key: string]: any
}

export interface ChargeStats {
  paid_amount: number
  refunded_amount: number
  pending_amount: number
  collected_amount: number
  net_amount: number
  overpaid_amount: number
  paid_count: number
  refunded_count: number
  pending_count: number
  cancelled_count: number
  total_count: number
}