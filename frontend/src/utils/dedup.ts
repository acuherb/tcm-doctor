// 患者查重：建档/挂号时调用，避免同名/同身份证/同电话造成重复档案
import api from '@/utils/api'

export interface DupPatient {
  id: number
  name: string
  gender?: string | null
  birth_date?: string | null
  phone?: string | null
  id_card?: string | null
  last_visit_date?: string | null
}

export async function findPatientDuplicates(params: {
  name: string
  phone?: string | null
  id_card?: string | null
}): Promise<DupPatient[]> {
  const name = (params.name || '').trim()
  if (!name) return []
  const q: Record<string, any> = { name }
  if (params.phone) q.phone = params.phone
  if (params.id_card) q.id_card = params.id_card
  try {
    const r = await api.get<DupPatient[]>('/patients/duplicates', { params: q })
    return r || []
  } catch {
    return []
  }
}
