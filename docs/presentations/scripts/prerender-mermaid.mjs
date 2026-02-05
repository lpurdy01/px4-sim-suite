#!/usr/bin/env node
/**
 * Pre-render Mermaid diagrams to SVG for reliable PDF output.
 * 
 * Usage: node scripts/prerender-mermaid.mjs
 * 
 * For each .md file with mermaid blocks:
 *   1. Extracts mermaid code blocks
 *   2. Renders each to SVG via mmdc
 *   3. Creates a .processed.md with image references
 */
import { readFileSync, writeFileSync, mkdirSync, existsSync, readdirSync, statSync } from 'node:fs'
import { execSync } from 'node:child_process'
import { dirname, basename, join } from 'node:path'

const MERMAID_REGEX = /```mermaid\n([\s\S]*?)```/g

// Simple recursive file finder
function findMarkdownFiles(dir, files = []) {
  for (const entry of readdirSync(dir)) {
    if (entry === 'node_modules' || entry === 'dist' || entry === 'generated') continue
    const fullPath = join(dir, entry)
    const stat = statSync(fullPath)
    if (stat.isDirectory()) {
      findMarkdownFiles(fullPath, files)
    } else if (entry.endsWith('.md') && !entry.includes('.processed.') && entry !== 'README.md') {
      files.push(fullPath)
    }
  }
  return files
}

async function processFile(mdPath) {
  const content = readFileSync(mdPath, 'utf-8')
  const matches = [...content.matchAll(MERMAID_REGEX)]
  
  if (matches.length === 0) {
    return null // No mermaid blocks
  }

  const dir = dirname(mdPath)
  const base = basename(mdPath, '.md')
  const imgDir = join(dir, 'generated')
  
  if (!existsSync(imgDir)) {
    mkdirSync(imgDir, { recursive: true })
  }

  let processed = content
  let index = 0

  for (const match of matches) {
    const mermaidCode = match[1]
    const imgName = `${base}-mermaid-${index}.svg`
    const imgPath = join(imgDir, imgName)
    const mmdPath = join(imgDir, `${base}-mermaid-${index}.mmd`)
    
    // Write mermaid source
    writeFileSync(mmdPath, mermaidCode)
    
    // Render to SVG using mmdc (--no-sandbox needed in containers)
    try {
      execSync(`npx mmdc -i "${mmdPath}" -o "${imgPath}" -b transparent -p puppeteer-config.json`, {
        cwd: process.cwd(),
        stdio: 'pipe'
      })
      console.log(`  ✓ Rendered ${imgName}`)
    } catch (err) {
      console.error(`  ✗ Failed to render ${imgName}:`, err.message)
      index++
      continue
    }

    // Replace mermaid block with image reference
    const relativePath = `generated/${imgName}`
    processed = processed.replace(match[0], `![${base} diagram ${index}](${relativePath})`)
    index++
  }

  // Write processed file
  const processedPath = mdPath.replace('.md', '.processed.md')
  writeFileSync(processedPath, processed)
  console.log(`  → ${processedPath}`)
  
  return processedPath
}

function main() {
  console.log('Pre-rendering Mermaid diagrams...\n')
  
  // Find all markdown files (excluding processed ones)
  const files = findMarkdownFiles(process.cwd())

  for (const file of files) {
    console.log(`Processing ${file}...`)
    processFile(file)
  }

  console.log('\nDone! Use .processed.md files for PDF export.')
}

main()
