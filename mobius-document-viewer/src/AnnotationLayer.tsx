import { type ReactNode } from 'react'
import type { Highlight } from './types'

/* ─── Text helpers ─── */

function normWs(s: string): string {
  return s.replace(/\s+/g, ' ').trim()
}

function tryFixFragmentHighlight(
  text: string,
  slice: string,
): { start: number; end: number } | null {
  const trimmed = slice.trim()
  if (!trimmed) return null
  const parts = trimmed.split(/\s+/)
  if (parts.length < 2) return null
  const first = parts[0]
  const rest = parts.slice(1).join(' ')
  if (first.length > 4 || !rest) return null
  const capitalized = rest.charAt(0).toUpperCase() + rest.slice(1)
  let idx = text.indexOf(capitalized)
  if (idx >= 0) return { start: idx, end: idx + capitalized.length }
  idx = text.indexOf(rest)
  if (idx > 0) {
    const charBefore = text[idx - 1]
    if (charBefore === 'F' || charBefore === 'f') {
      return { start: idx - 1, end: idx + rest.length }
    }
    return { start: idx, end: idx + rest.length }
  }
  return null
}

/**
 * If a highlight carries a `data.matchText` string and the stored offsets
 * don't match it, try to find the actual position by text search.
 */
export function correctRangeToMatchText(
  text: string,
  r: Highlight,
): { start: number; end: number } {
  const start = Math.max(0, Number(r.start))
  const end = Math.min(text.length, Math.max(start, Number(r.end)))
  const matchText = typeof r.data?.matchText === 'string' ? (r.data.matchText as string) : null
  const slice = text.slice(start, end)
  if (matchText && matchText.trim()) {
    if (normWs(slice) === normWs(matchText)) {
      const fixed = tryFixFragmentHighlight(text, slice)
      if (fixed) return fixed
      return { start, end }
    }
    const idx = text.indexOf(matchText)
    if (idx >= 0) return { start: idx, end: idx + matchText.length }
    try {
      const escaped = matchText.trim().replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
      const flexiblePattern = escaped.replace(/\s+/g, '\\s+')
      const match = text.match(new RegExp(flexiblePattern))
      if (match && match.index !== undefined)
        return { start: match.index, end: match.index + match[0].length }
    } catch {
      // regex invalid
    }
    const fixed = tryFixFragmentHighlight(text, slice)
    if (fixed) return fixed
  }
  return { start, end }
}

/* ─── Segment builder ─── */

function isSectionHeader(firstLine: string): boolean {
  if (!firstLine || firstLine.length > 120) return false
  const line = firstLine.trim()
  if (line.startsWith('## ')) return true
  if (line.endsWith(':')) return true
  if (/^[A-Z][A-Z\s]+:/.test(line)) return true
  if (/^\d+\.\s+[A-Z]/.test(line)) return true
  if (/^\d+\.\d+\s+/.test(line)) return true
  if (line.length <= 60 && !line.endsWith('.') && /^[A-Z]/.test(line)) {
    const wordCount = line.split(/\s+/).length
    if (wordCount >= 1 && wordCount <= 8) return true
  }
  return false
}

export function getFirstSectionHeader(text: string | null | undefined): string | null {
  if (!text?.trim()) return null
  const normalized = text
    .split('\n')
    .map((line) => line.replace(/\s+/g, ' ').trim())
    .join('\n')
    .replace(/\n{3,}/g, '\n\n')
    .trim()
  const blocks = normalized.split(/\n\n+/)
  for (const block of blocks) {
    const firstLine = block.split('\n')[0]?.trim() ?? ''
    if (isSectionHeader(firstLine)) {
      if (firstLine.startsWith('## ')) return firstLine.slice(3).trim()
      if (firstLine.endsWith(':')) return firstLine.slice(0, -1).trim()
      return firstLine
    }
  }
  return null
}

export interface Segment {
  start: number
  end: number
  text: string
  isHeader: boolean
  headerLabel?: string
}

export function buildSegments(normalized: string): Segment[] {
  const segments: Segment[] = []
  const blocks = normalized.split(/\n\n+/)
  let offset = 0
  for (let i = 0; i < blocks.length; i++) {
    const block = blocks[i]
    const blockStart = offset
    offset += block.length + (i < blocks.length - 1 ? 2 : 0)
    const lines = block.split('\n')
    const firstLine = lines[0]?.trim() ?? ''
    if (lines.length > 0 && isSectionHeader(firstLine)) {
      const headerRaw = lines[0] ?? ''
      const headerLen = headerRaw.length
      const headerLabel = firstLine.startsWith('## ')
        ? firstLine.slice(3).trim()
        : firstLine.endsWith(':')
          ? firstLine.slice(0, -1)
          : firstLine
      segments.push({
        start: blockStart,
        end: blockStart + headerLen,
        text: normalized.slice(blockStart, blockStart + headerLen),
        isHeader: true,
        headerLabel,
      })
      if (lines.length > 1) {
        const bodyStart = blockStart + headerLen + 1
        segments.push({
          start: bodyStart,
          end: offset,
          text: normalized.slice(bodyStart, offset),
          isHeader: false,
        })
      }
    } else {
      segments.push({
        start: blockStart,
        end: offset,
        text: normalized.slice(blockStart, offset),
        isHeader: false,
      })
    }
  }
  return segments
}

/* ─── List / block rendering ─── */

const LIST_BULLET = /^[\s]*[•\-*]\s+/
const LIST_NUMBER = /^[\s]*\d+[.)]\s+/

function isListBlock(block: string): boolean {
  const lines = block.split('\n').filter((l) => l.trim())
  if (lines.length < 2) return false
  const listLike = lines.filter((l) => LIST_BULLET.test(l) || LIST_NUMBER.test(l)).length
  return listLike >= Math.min(2, lines.length) || listLike >= lines.length * 0.6
}

function renderBlock(block: string, keyPrefix: string): ReactNode {
  const trimmed = block.trim()
  if (!trimmed) return null
  if (isListBlock(trimmed)) {
    const lines = trimmed.split('\n').filter((l) => l.trim())
    return (
      <ul key={keyPrefix} className="dv-list">
        {lines.map((line, i) => {
          const bulletMatch = line.match(LIST_BULLET) || line.match(LIST_NUMBER)
          const content = bulletMatch ? line.slice(bulletMatch[0].length).trim() : line.trim()
          return <li key={`${keyPrefix}-${i}`}>{content}</li>
        })}
      </ul>
    )
  }
  return (
    <p key={keyPrefix} className="dv-raw-p">
      {trimmed.replace(/\n/g, ' ')}
    </p>
  )
}

/* ─── SegmentWithHighlights ─── */

function SegmentWithHighlights({
  segmentText,
  segStart,
  segEnd,
  ranges,
  onHighlightHover,
  onHighlightLeave,
}: {
  segmentText: string
  segStart: number
  segEnd: number
  ranges: Highlight[]
  onHighlightHover?: (r: Highlight, rect: DOMRect) => void
  onHighlightLeave?: () => void
}) {
  const nodes: ReactNode[] = []
  let pos = 0
  const segLen = segmentText.length
  for (const r of ranges) {
    const rStart = Math.max(segStart, r.start)
    const rEnd = Math.min(segEnd, r.end)
    if (rStart >= rEnd) continue
    const relStart = rStart - segStart
    const relEnd = rEnd - segStart
    if (relStart > pos) {
      nodes.push(<span key={`${pos}-pre`}>{segmentText.slice(pos, relStart)}</span>)
    }
    const hlClass = r.className ?? 'dv-highlight'
    nodes.push(
      <span
        key={`${r.id}-hl`}
        className={hlClass}
        title={r.label || undefined}
        data-highlight-id={r.id}
        onMouseEnter={(e) => {
          onHighlightHover?.(r, e.currentTarget.getBoundingClientRect())
        }}
        onMouseLeave={() => onHighlightLeave?.()}
      >
        {segmentText.slice(relStart, relEnd)}
      </span>,
    )
    pos = relEnd
  }
  if (pos < segLen) {
    nodes.push(<span key={`${pos}-post`}>{segmentText.slice(pos)}</span>)
  }
  return <>{nodes}</>
}

/* ─── Main annotation-aware text renderer ─── */

export interface AnnotationLayerProps {
  /** Raw text (or markdown text) for the page. */
  text: string
  /** All highlights for this page (caller provides styling via className). */
  ranges: Highlight[]
  isMarkdown?: boolean
  onHighlightHover?: (r: Highlight, rect: DOMRect) => void
  onHighlightLeave?: () => void
}

export function AnnotationLayer({
  text,
  ranges,
  isMarkdown = false,
  onHighlightHover,
  onHighlightLeave,
}: AnnotationLayerProps) {
  const normalized = isMarkdown
    ? text
    : text
        .split('\n')
        .map((line) => line.replace(/\s+/g, ' ').trim())
        .join('\n')
        .replace(/\n{3,}/g, '\n\n')
        .trim()
  const len = normalized.length
  const segments = buildSegments(normalized)

  // Correct ranges so highlight span matches the text
  const correctedRanges = ranges.map((r) => {
    const { start, end } = correctRangeToMatchText(normalized, r)
    return { ...r, start, end }
  })

  if (!correctedRanges.length) {
    return (
      <div className="dv-markdown">
        {segments.map((seg, i) =>
          seg.isHeader ? (
            <h2 key={`h-${i}`} className="dv-h2">
              {seg.headerLabel ?? seg.text}
            </h2>
          ) : (
            <div key={`p-${i}`} className="dv-section-body">
              {seg.text.split(/\n\n+/).map((p, j) => renderBlock(p, `seg-${i}-${j}`))}
            </div>
          ),
        )}
      </div>
    )
  }

  const sorted = [...correctedRanges].sort((a, b) => a.start - b.start)
  const clamped: Highlight[] = []
  for (const r of sorted) {
    const start = Math.max(0, Number(r.start))
    const end = Math.min(len, Math.max(start, Number(r.end)))
    if (start >= end) continue
    clamped.push({ ...r, start, end })
  }
  // Merge overlapping highlights with the same id
  const merged: Highlight[] = []
  for (const r of clamped) {
    const last = merged[merged.length - 1]
    if (
      merged.length &&
      last.id === r.id &&
      r.start <= last.end
    ) {
      merged[merged.length - 1] = { ...last, end: Math.max(last.end, r.end) }
    } else {
      merged.push({ ...r })
    }
  }

  const segmentEls: ReactNode[] = []
  for (let i = 0; i < segments.length; i++) {
    const seg = segments[i]
    const rangesInSeg = merged.filter((r) => r.end > seg.start && r.start < seg.end)
    const rangesClipped = rangesInSeg.map((r) => ({
      ...r,
      start: Math.max(r.start, seg.start),
      end: Math.min(r.end, seg.end),
    }))
    if (seg.isHeader) {
      segmentEls.push(
        <h2 key={`h-${i}`} className="dv-h2">
          {seg.headerLabel ?? seg.text}
        </h2>,
      )
    } else {
      segmentEls.push(
        <div key={`p-${i}`} className="dv-section-body">
          <p
            className={`dv-raw-p ${rangesClipped.length > 0 ? 'dv-raw-p-with-highlights' : ''}`}
          >
            <SegmentWithHighlights
              segmentText={seg.text}
              segStart={seg.start}
              segEnd={seg.end}
              ranges={rangesClipped}
              onHighlightHover={onHighlightHover}
              onHighlightLeave={onHighlightLeave}
            />
          </p>
        </div>,
      )
    }
  }
  return <div className="dv-markdown">{segmentEls}</div>
}
