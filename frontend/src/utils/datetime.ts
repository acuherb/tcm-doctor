/** 生成文件名友好的本地时间戳：YYYY-MM-DD_HH-MM-SS
 * 使用本地时间（非 UTC），并以短横线替代冒号，兼容 Windows 文件名限制。 */
export function fileTimestamp(d: Date = new Date()): string {
  const pad = (n: number) => String(n).padStart(2, '0')
  return (
    `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}` +
    `_${pad(d.getHours())}-${pad(d.getMinutes())}-${pad(d.getSeconds())}`
  )
}
