#!/usr/bin/env node
// 校验 el-table / el-table-column 作用域插槽的字段命名，避免再踩「{ r } 应为 { row }」这类坑。
//
// 背景：Element Plus 的 el-table-column 默认插槽作用域只暴露 { row, column, $index } 等字段，
// 若误写成 { r }，则 r 为 undefined，模板里访问 r.xxx 会每个单元格抛错，导致整页渲染崩溃
// （曾表现为「进报表后其他菜单不跳转、需刷新」，甚至 errorHandler 弹窗反馈回路卡死浏览器）。
//
// 用法：node scripts/check-table-slots.mjs   （仅扫描 src 下的 .vue 文件）
// 退出码：发现非法字段 -> 1；通过 -> 0。

import { readdirSync, readFileSync, statSync } from 'node:fs'
import { join, dirname } from 'node:path'
import { fileURLToPath } from 'node:url'

const __dirname = dirname(fileURLToPath(import.meta.url))
const SRC = join(__dirname, '..', 'src')

// el-table / el-table-column 作用域插槽合法字段（含常见的 EP 组件插槽字段，避免误报）
const ALLOWED = new Set([
  'row', 'column', '$index', 'index', 'store', '_self', 'data',
  // 常见嵌套组件插槽字段（单元格内可能用到），一并放行
  'node', 'item', 'value', 'label', 'scope', 'disabled', 'form',
  'tab', 'pane', 'command', 'file', 'fileList', 'group', 'submenu',
  'checked', 'percent', 'model', 'prop', 'children',
])

const violations = []

function walk(dir) {
  for (const name of readdirSync(dir)) {
    const p = join(dir, name)
    const st = statSync(p)
    if (st.isDirectory()) walk(p)
    else if (name.endsWith('.vue')) checkFile(p)
  }
}

// 判断位置是否落在某个 <el-table> 根区域内部（含嵌套表格）
function tableRegions(content) {
  const openRe = /<el-table(?!-)[^>]*>/g
  const closeRe = /<\/el-table>/g
  const marks = []
  let m
  while ((m = openRe.exec(content))) marks.push({ i: m.index, d: 1 })
  while ((m = closeRe.exec(content))) marks.push({ i: m.index, d: -1 })
  marks.sort((a, b) => a.i - b.i)
  const regions = []
  let depth = 0
  let start = -1
  for (const mk of marks) {
    depth += mk.d
    if (depth === 1 && mk.d === 1) start = mk.i
    else if (depth === 0 && mk.d === -1) { regions.push([start, mk.i]); start = -1 }
  }
  return regions
}

function inRegions(regions, idx) {
  return regions.some(([s, e]) => idx >= s && idx <= e)
}

function checkFile(file) {
  const content = readFileSync(file, 'utf8')
  const regions = tableRegions(content)
  if (!regions.length) return

  // 匹配任意插槽解构：#name="{ ... }"
  const slotRe = /#[\w-]+=(["'])\{([^}]*)\}\1/g
  let m
  while ((m = slotRe.exec(content))) {
    const idx = m.index
    if (!inRegions(regions, idx)) continue
    const inner = m[2]
    if (!inner.trim()) continue
    const line = content.slice(0, idx).split('\n').length
    for (let part of inner.split(',')) {
      // 处理重命名 { row: r } 与默认值 { row = x }，取绑定名
      part = part.split(':')[0].split('=')[0].trim()
      if (!part) continue
      const bad = part.length === 1 || !ALLOWED.has(part)
      if (bad) violations.push({ file, line, name: part })
    }
  }
}

walk(SRC)

if (violations.length) {
  console.error('❌ 发现 el-table 插槽字段命名问题（表格列插槽字段应为 row / column / $index 等）：')
  for (const v of violations) {
    console.error(`   ${v.file}:${v.line}  ->  "{ ${v.name} }"`)
  }
  console.error('\n请改为正确的作用域字段名（通常是 { row }）。')
  process.exit(1)
} else {
  console.log('✅ el-table 插槽字段命名校验通过')
}
