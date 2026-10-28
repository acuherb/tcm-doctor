import MarkdownIt from 'markdown-it'
import DOMPurify from 'dompurify'

const md = new MarkdownIt({ html: false, linkify: true, breaks: true })

// AI 常把对比表输出成「制表符/多空格」分隔的纯文本，markdown-it 不识别；
// 此处把连续 >=2 列、列数一致的多行文本转换为 GFM 表格。同时跳过代码块。
function isTableRow(line: string): boolean {
  if (!line.trim()) return false
  const byTab = line.split('\t')
  if (byTab.length >= 2 && byTab.every((p) => p.trim() !== '')) return true
  const bySpace = line.split(/ {2,}/)
  if (bySpace.length >= 2 && bySpace.every((p) => p.trim() !== '')) return true
  return false
}

function splitRow(line: string): string[] {
  if (line.includes('\t')) return line.split('\t').map((c) => c.trim())
  return line.split(/ {2,}/).map((c) => c.trim())
}

function normalizeTables(src: string): string {
  const lines = src.split('\n')
  const out: string[] = []
  let i = 0
  let inFence = false
  while (i < lines.length) {
    const line = lines[i]
    if (line.trim().startsWith('```')) {
      inFence = !inFence
      out.push(line)
      i++
      continue
    }
    if (inFence) {
      out.push(line)
      i++
      continue
    }
    if (isTableRow(line)) {
      const orig: string[] = []
      const rows: string[][] = []
      while (i < lines.length && !lines[i].trim().startsWith('```')) {
        const r = splitRow(lines[i])
        if (r.length < 2) break
        orig.push(lines[i])
        rows.push(r)
        i++
      }
      const cols = rows[0]?.length ?? 0
      const ok = rows.length >= 2 && cols >= 2 && rows.every((r) => r.length === cols)
      if (ok) {
        // 表格前补一个空行，确保与前文段落正确分隔后能被 markdown-it 解析为表格
        const last = out[out.length - 1]
        if (last !== undefined && last.trim() !== '' && !last.startsWith('|')) out.push('')
        out.push('| ' + rows[0].join(' | ') + ' |')
        out.push('| ' + rows[0].map(() => '---').join(' | ') + ' |')
        for (let k = 1; k < rows.length; k++) out.push('| ' + rows[k].join(' | ') + ' |')
      } else {
        out.push(...orig)
      }
    } else {
      out.push(line)
      i++
    }
  }
  return out.join('\n')
}

// 去掉 AI 文末冗余的 ```json（recommended_formulas）代码块，避免把结构化 JSON 原样暴露
function stripJsonFence(src: string): string {
  return src.replace(/```json[\s\S]*?```/gi, '').replace(/^\s*\[\s*\{[\s\S]*\}\s*\]\s*$/g, '')
}

export function renderMarkdown(text: string): string {
  if (!text) return ''
  const normalized = normalizeTables(stripJsonFence(text))
  return DOMPurify.sanitize(md.render(normalized))
}
