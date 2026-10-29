// 患者健康指标工具：年龄、BMI、身型分类

/** 由出生日期计算周岁年龄（无法解析返回 null） */
export function calcAge(birthDate?: string | null): number | null {
  if (!birthDate) return null
  const d = new Date(birthDate)
  if (isNaN(d.getTime())) return null
  const now = new Date()
  let age = now.getFullYear() - d.getFullYear()
  const m = now.getMonth() - d.getMonth()
  if (m < 0 || (m === 0 && now.getDate() < d.getDate())) age--
  return age >= 0 && age < 200 ? age : null
}

/** 由身高(cm)与体重(kg)计算 BMI（缺值返回 null） */
export function calcBmi(heightCm?: number | null, weightKg?: number | null): number | null {
  if (!heightCm || !weightKg) return null
  const h = heightCm / 100
  if (h <= 0) return null
  const bmi = weightKg / (h * h)
  return Math.round(bmi * 10) / 10
}

/** 中国成人 BMI 标准身型分类 */
export function bodyType(
  bmi?: number | null
): { label: string; color: string } | null {
  if (bmi == null) return null
  if (bmi < 18.5) return { label: '偏瘦', color: '#409EFF' }
  if (bmi < 24) return { label: '正常', color: '#67C23A' }
  if (bmi < 28) return { label: '偏胖', color: '#E6A23C' }
  return { label: '肥胖', color: '#F56C6C' }
}
