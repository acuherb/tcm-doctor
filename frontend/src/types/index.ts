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
  visit_date?: string
  chief_complaint?: string
  tongue_body_term_id?: number | null
  tongue_coat_term_id?: number | null
  pulse_term_id?: number | null
  syndrome_term_id?: number | null
  [key: string]: any
}

// 处方
export interface Prescription {
  id?: number
  visit_id?: number
  patient_id?: number
  formula_name?: string
  doctor_id?: number | null
  classic_formula_id?: number | null
  acupoint_formula_id?: number | null
  items?: PrescriptionItem[]
  injections?: PrescriptionInjection[]
  acupoints?: AcupointPrescription[]
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
  [key: string]: any
}
