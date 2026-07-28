import { Fragment, type ReactNode } from 'react'

type Props = {
  content: string
  className?: string
}

type Block =
  | { type: 'table'; headers: string[]; rows: string[][] }
  | { type: 'paragraph'; text: string }
  | { type: 'list'; ordered: boolean; items: string[] }
  | { type: 'heading'; level: 1 | 2 | 3; text: string }

function isTableSeparator(line: string): boolean {
  const cells = splitRow(line)
  return cells.length > 0 && cells.every((c) => /^:?-{3,}:?$/.test(c))
}

function splitRow(line: string): string[] {
  let s = line.trim()
  if (s.startsWith('|')) s = s.slice(1)
  if (s.endsWith('|')) s = s.slice(0, -1)
  return s.split('|').map((c) => c.trim())
}

function isTableRow(line: string): boolean {
  const t = line.trim()
  return t.includes('|') && !t.startsWith('```')
}

function parseBlocks(content: string): Block[] {
  const lines = content.replace(/\r\n/g, '\n').split('\n')
  const blocks: Block[] = []
  let i = 0

  while (i < lines.length) {
    const line = lines[i]

    if (!line.trim()) {
      i += 1
      continue
    }

    const heading = /^(#{1,3})\s+(.+)$/.exec(line)
    if (heading) {
      blocks.push({
        type: 'heading',
        level: heading[1].length as 1 | 2 | 3,
        text: heading[2].trim(),
      })
      i += 1
      continue
    }

    if (
      isTableRow(line) &&
      i + 1 < lines.length &&
      isTableSeparator(lines[i + 1])
    ) {
      const headers = splitRow(line)
      i += 2
      const rows: string[][] = []
      while (i < lines.length && isTableRow(lines[i]) && lines[i].trim()) {
        const cells = splitRow(lines[i])
        while (cells.length < headers.length) cells.push('')
        rows.push(cells.slice(0, headers.length))
        i += 1
      }
      blocks.push({ type: 'table', headers, rows })
      continue
    }

    const listMatch = /^(\d+\.\s+|[-*]\s+)(.+)$/.exec(line)
    if (listMatch) {
      const ordered = /^\d+\./.test(listMatch[1])
      const items: string[] = [listMatch[2]]
      i += 1
      while (i < lines.length) {
        const next = /^(\d+\.\s+|[-*]\s+)(.+)$/.exec(lines[i])
        if (!next) break
        if (ordered !== /^\d+\./.test(next[1])) break
        items.push(next[2])
        i += 1
      }
      blocks.push({ type: 'list', ordered, items })
      continue
    }

    const para: string[] = [line]
    i += 1
    while (
      i < lines.length &&
      lines[i].trim() &&
      !/^(#{1,3})\s+/.test(lines[i]) &&
      !/^(\d+\.\s+|[-*]\s+)/.test(lines[i]) &&
      !(
        isTableRow(lines[i]) &&
        i + 1 < lines.length &&
        isTableSeparator(lines[i + 1])
      )
    ) {
      para.push(lines[i])
      i += 1
    }
    blocks.push({ type: 'paragraph', text: para.join('\n') })
  }

  return blocks
}

function renderInline(text: string): ReactNode[] {
  const nodes: ReactNode[] = []
  // **bold**, *italic*, `code`, ***bold italic***
  const re = /(\*\*\*[^*]+\*\*\*|\*\*[^*]+\*\*|\*[^*]+\*|`[^`]+`)/g
  let last = 0
  let match: RegExpExecArray | null
  let key = 0

  while ((match = re.exec(text)) !== null) {
    if (match.index > last) {
      nodes.push(text.slice(last, match.index))
    }
    const token = match[0]
    if (token.startsWith('***') && token.endsWith('***')) {
      nodes.push(
        <strong key={key++}>
          <em>{token.slice(3, -3)}</em>
        </strong>,
      )
    } else if (token.startsWith('**') && token.endsWith('**')) {
      nodes.push(<strong key={key++}>{token.slice(2, -2)}</strong>)
    } else if (token.startsWith('*') && token.endsWith('*')) {
      nodes.push(<em key={key++}>{token.slice(1, -1)}</em>)
    } else if (token.startsWith('`') && token.endsWith('`')) {
      nodes.push(
        <code
          key={key++}
          className="rounded bg-black/10 px-1 py-0.5 text-[0.85em]"
        >
          {token.slice(1, -1)}
        </code>,
      )
    }
    last = match.index + token.length
  }

  if (last < text.length) {
    nodes.push(text.slice(last))
  }

  return nodes.length > 0 ? nodes : [text]
}

export function MarkdownMessage({ content, className = '' }: Props) {
  const blocks = parseBlocks(content)

  return (
    <div className={`markdown-msg space-y-2 ${className}`}>
      {blocks.map((block, idx) => {
        if (block.type === 'heading') {
          const Tag = (`h${block.level}` as 'h1' | 'h2' | 'h3')
          const sizes = {
            1: 'text-base font-semibold',
            2: 'text-sm font-semibold',
            3: 'text-sm font-medium',
          }
          return (
            <Tag key={idx} className={sizes[block.level]}>
              {renderInline(block.text)}
            </Tag>
          )
        }

        if (block.type === 'table') {
          return (
            <div key={idx} className="overflow-x-auto">
              <table className="w-full border-collapse text-left text-xs">
                <thead>
                  <tr className="border-b border-[var(--border)] bg-[var(--surface)]">
                    {block.headers.map((h, hi) => (
                      <th key={hi} className="px-2 py-1.5 font-semibold whitespace-nowrap">
                        {renderInline(h)}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {block.rows.map((row, ri) => (
                    <tr key={ri} className="border-b border-[var(--border)]/60">
                      {row.map((cell, ci) => (
                        <td key={ci} className="px-2 py-1.5 align-top">
                          {renderInline(cell)}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )
        }

        if (block.type === 'list') {
          const Tag = block.ordered ? 'ol' : 'ul'
          return (
            <Tag
              key={idx}
              className={`ml-4 space-y-0.5 ${block.ordered ? 'list-decimal' : 'list-disc'}`}
            >
              {block.items.map((item, ii) => (
                <li key={ii}>{renderInline(item)}</li>
              ))}
            </Tag>
          )
        }

        return (
          <p key={idx} className="whitespace-pre-wrap">
            {block.text.split('\n').map((line, li, arr) => (
              <Fragment key={li}>
                {renderInline(line)}
                {li < arr.length - 1 ? <br /> : null}
              </Fragment>
            ))}
          </p>
        )
      })}
    </div>
  )
}
