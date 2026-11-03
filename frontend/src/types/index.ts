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
  [key: string]: any
}

// 处方
export interface Prescription {
  id?: number
  visit_id?: number
  patient_id?: number
  formula_name?: string
  items?: PrescriptionItem[]
  [key: string]: any
}

export interface PrescriptionItem {
  id?: number
  herb_id?: number
  herb_name?: string
  dose?: string
  [key: string]: any
}

// 库存物品
export interface StockItem {
  id?: number
  name?: string
  item_type?: string
  unit?: string
  quantity?: number
  [key: string]: any
}

// 药材
export interface Herb {
  id?: number
  name?: string
  pinyin?: string
  [key: string]: any
}

// 供应商
export interface Supplier {
  id?: number
  name?: string
  contact?: string
  phone?: string
  [key: string]: any
}
