import { useState, useMemo } from 'react'
import type { TagEntry, TagKind } from '../types'

interface Props {
  tags: TagEntry[]
  onTagSelect: (kind: TagKind, code: string) => void
  onRefresh: () => void
}

const KIND_COLORS: Record<string, string> = {
  d: '#3b82f6',  // blue
  p: '#22c55e',  // green
  j: '#f59e0b',  // amber
}

const KIND_LABELS: Record<string, string> = {
  d: 'Domain',
  p: 'Procedural',
  j: 'Jurisdiction',
}

export function TagOverviewTab({ tags, onTagSelect, onRefresh: _onRefresh }: Props) {
  void _onRefresh
  const [kindFilter, setKindFilter] = useState<string>('')

  // ── Derived data ──────────────────────────────────────────────────────

  const filtered = useMemo(() => {
    if (!kindFilter) return tags
    return tags.filter(t => t.kind === kindFilter)
  }, [tags, kindFilter])

  const leafTags = useMemo(() => filtered.filter(t => t.code.includes('.')), [filtered])
  const domains = useMemo(() => filtered.filter(t => !t.code.includes('.')), [filtered])
  const matched = useMemo(() => leafTags.filter(t => (t.hit_docs || 0) > 0), [leafTags])
  const unmatched = useMemo(() => leafTags.filter(t => (t.hit_docs || 0) === 0), [leafTags])

  // Kind distribution (always from all tags, ignoring filter, for donut)
  const kindCounts = useMemo(() => {
    const counts = { d: 0, p: 0, j: 0 }
    for (const t of tags) {
      if (t.kind in counts) counts[t.kind as keyof typeof counts]++
    }
    return counts
  }, [tags])
  const totalAllTags = kindCounts.d + kindCounts.p + kindCounts.j

  // Top tags by hit_docs
  const topByDocs = useMemo(() => {
    return [...leafTags]
      .filter(t => (t.hit_docs || 0) > 0)
      .sort((a, b) => (b.hit_docs || 0) - (a.hit_docs || 0))
      .slice(0, 15)
  }, [leafTags])
  const maxDocs = topByDocs.length > 0 ? (topByDocs[0].hit_docs || 1) : 1

  // Unmatched grouped by kind
  const unmatchedByKind = useMemo(() => {
    const groups: Record<string, TagEntry[]> = { d: [], p: [], j: [] }
    for (const t of unmatched) {
      if (t.kind in groups) groups[t.kind].push(t)
    }
    return groups
  }, [unmatched])

  // ── Donut chart helper ────────────────────────────────────────────────

  const donutGradient = useMemo(() => {
    if (totalAllTags === 0) return 'conic-gradient(var(--border) 0deg 360deg)'
    const dPct = (kindCounts.d / totalAllTags) * 100
    const pPct = (kindCounts.p / totalAllTags) * 100
    // j gets the rest
    return `conic-gradient(
      ${KIND_COLORS.d} 0% ${dPct}%,
      ${KIND_COLORS.p} ${dPct}% ${dPct + pPct}%,
      ${KIND_COLORS.j} ${dPct + pPct}% 100%
    )`
  }, [kindCounts, totalAllTags])

  // ── Render ────────────────────────────────────────────────────────────

  return (
    <div className="reporting-dashboard">
      {/* Kind filter */}
      <div className="rpt-filter-bar">
        {['', 'd', 'p', 'j'].map(k => (
          <button
            key={k || 'all'}
            className={`chip ${kindFilter === k ? 'active' : ''}`}
            onClick={() => setKindFilter(k)}
          >
            {k === '' ? 'All' : k.toUpperCase()}
          </button>
        ))}
      </div>

      {/* Summary cards */}
      <div className="rpt-stats-row">
        <div className="rpt-stat-card">
          <span className="rpt-stat-num">{leafTags.length}</span>
          <span className="rpt-stat-label">Tags</span>
        </div>
        <div className="rpt-stat-card">
          <span className="rpt-stat-num">{domains.length}</span>
          <span className="rpt-stat-label">Domains</span>
        </div>
        <div className="rpt-stat-card accent-green">
          <span className="rpt-stat-num">{matched.length}</span>
          <span className="rpt-stat-label">Matched</span>
        </div>
        <div className="rpt-stat-card accent-red">
          <span className="rpt-stat-num">{unmatched.length}</span>
          <span className="rpt-stat-label">Unmatched</span>
        </div>
      </div>

      {/* Row 2: Top hits + Kind distribution */}
      <div className="rpt-row rpt-row-2">
        {/* Top tags bar chart */}
        <div className="rpt-panel rpt-panel-wide">
          <h3 className="rpt-panel-title">Top Tags by Document Hits</h3>
          {topByDocs.length === 0 ? (
            <p className="rpt-empty">No tags with hits yet. Publish to RAG and run extraction.</p>
          ) : (
            <div className="rpt-bar-chart">
              {topByDocs.map(t => {
                const pct = Math.max(4, ((t.hit_docs || 0) / maxDocs) * 100)
                return (
                  <div
                    key={`${t.kind}:${t.code}`}
                    className="rpt-bar-row"
                    onClick={() => onTagSelect(t.kind, t.code)}
                  >
                    <span className="rpt-bar-label">
                      <span className={`kind-dot kind-dot-${t.kind}`} />
                      {t.code}
                    </span>
                    <div className="rpt-bar-track">
                      <div
                        className="rpt-bar-fill"
                        style={{
                          width: `${pct}%`,
                          backgroundColor: KIND_COLORS[t.kind] || '#666',
                        }}
                      />
                    </div>
                    <span className="rpt-bar-value">{t.hit_docs || 0}</span>
                  </div>
                )
              })}
            </div>
          )}
        </div>

        {/* Kind distribution donut */}
        <div className="rpt-panel rpt-panel-narrow">
          <h3 className="rpt-panel-title">Kind Distribution</h3>
          <div className="rpt-donut-wrap">
            <div className="rpt-donut" style={{ background: donutGradient }}>
              <div className="rpt-donut-center">
                <span className="rpt-donut-num">{totalAllTags}</span>
                <span className="rpt-donut-sub">total</span>
              </div>
            </div>
            <div className="rpt-donut-legend">
              {(['d', 'p', 'j'] as const).map(k => (
                <span key={k} className="rpt-legend-item">
                  <span className="rpt-legend-dot" style={{ backgroundColor: KIND_COLORS[k] }} />
                  {KIND_LABELS[k]}: {kindCounts[k]}
                </span>
              ))}
            </div>
          </div>
        </div>
      </div>

      {/* Row 3: Unmatched tags + Document coverage */}
      <div className="rpt-row rpt-row-3">
        {/* Unmatched tags list */}
        <div className="rpt-panel">
          <h3 className="rpt-panel-title">
            Unmatched Tags
            <span className="rpt-badge">{unmatched.length}</span>
          </h3>
          {unmatched.length === 0 ? (
            <p className="rpt-empty">All leaf tags have hits!</p>
          ) : (
            <div className="rpt-unmatched-list">
              {(['d', 'p', 'j'] as const).map(k => {
                const items = unmatchedByKind[k]
                if (!items || items.length === 0) return null
                return (
                  <div key={k} className="rpt-unmatched-group">
                    <div className="rpt-unmatched-kind-header">
                      <span className={`kind-badge kind-${k}`}>{k.toUpperCase()}</span>
                      <span className="muted">{items.length} tags</span>
                    </div>
                    {items.map(t => (
                      <div
                        key={`${t.kind}:${t.code}`}
                        className="rpt-unmatched-item"
                        onClick={() => onTagSelect(t.kind, t.code)}
                      >
                        {t.code}
                      </div>
                    ))}
                  </div>
                )
              })}
            </div>
          )}
        </div>

        {/* Document Coverage -- computed from tags that have hit_docs */}
        <div className="rpt-panel">
          <h3 className="rpt-panel-title">Tag Coverage Summary</h3>
          <div className="rpt-coverage-stats">
            <div className="rpt-coverage-row">
              <span className="rpt-coverage-label">Total leaf tags</span>
              <span className="rpt-coverage-val">{leafTags.length}</span>
            </div>
            <div className="rpt-coverage-row">
              <span className="rpt-coverage-label">With document hits</span>
              <span className="rpt-coverage-val accent-green">{matched.length}</span>
            </div>
            <div className="rpt-coverage-row">
              <span className="rpt-coverage-label">No hits (need extraction)</span>
              <span className="rpt-coverage-val accent-red">{unmatched.length}</span>
            </div>
            <div className="rpt-coverage-row">
              <span className="rpt-coverage-label">Coverage rate</span>
              <span className="rpt-coverage-val">
                {leafTags.length > 0 ? Math.round((matched.length / leafTags.length) * 100) : 0}%
              </span>
            </div>
            {/* Coverage bar */}
            <div className="rpt-coverage-bar-wrap">
              <div className="rpt-coverage-bar-track">
                <div
                  className="rpt-coverage-bar-fill"
                  style={{
                    width: leafTags.length > 0 ? `${(matched.length / leafTags.length) * 100}%` : '0%',
                  }}
                />
              </div>
              <div className="rpt-coverage-bar-labels">
                <span className="accent-green">{matched.length} matched</span>
                <span className="accent-red">{unmatched.length} unmatched</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Row 4: Coming Soon stubs */}
      <div className="rpt-row rpt-row-4">
        <div className="rpt-panel rpt-coming-soon">
          <h3 className="rpt-panel-title">Query Tag Usage</h3>
          <div className="rpt-coming-soon-body">
            <span className="rpt-coming-soon-label">Coming Soon</span>
            <span className="rpt-coming-soon-sub">Which tags are matched most frequently in chat queries</span>
            <span className="rpt-coming-soon-req">Requires query-level tag logging in chat</span>
          </div>
        </div>
        <div className="rpt-panel rpt-coming-soon">
          <h3 className="rpt-panel-title">Tag Performance</h3>
          <div className="rpt-coming-soon-body">
            <span className="rpt-coming-soon-label">Coming Soon</span>
            <span className="rpt-coming-soon-sub">Which tags lead to high-quality answers vs. poor ones</span>
            <span className="rpt-coming-soon-req">Requires feedback correlation with tag data</span>
          </div>
        </div>
        <div className="rpt-panel rpt-coming-soon">
          <h3 className="rpt-panel-title">Tag Trends</h3>
          <div className="rpt-coming-soon-body">
            <span className="rpt-coming-soon-label">Coming Soon</span>
            <span className="rpt-coming-soon-sub">Tag usage over time as new documents are processed</span>
            <span className="rpt-coming-soon-req">Requires time-series tag tracking</span>
          </div>
        </div>
      </div>
    </div>
  )
}
