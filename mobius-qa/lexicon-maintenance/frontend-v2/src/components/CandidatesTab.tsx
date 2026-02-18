import { useState, useEffect, useCallback } from 'react'
import type { TagEntry, TagKind } from '../types'
import {
  fetchCandidates, bulkReview, runLlmTriage, purgeStale,
  applyCandidateOperations,
  type CandidateOperation, type CandidateApplyResult,
} from '../api'
import { CandidateDecisionModal } from './CandidateDecisionModal'

interface Props {
  tags: TagEntry[]
  onRefresh: () => void
  onTagSelect: (kind: TagKind, code: string) => void
}

interface CandRow {
  normalized: string
  ids: string[]
  candidate_type: string
  total_occurrences: number
  doc_count: number
  avg_confidence: number
  status?: string // 'proposed' | 'rejected' from API
  llm_verdict?: string
  llm_confidence?: number
  llm_reason?: string
  llm_suggested_code?: string
  llm_suggested_parent?: string
  llm_suggested_kind?: string
}

export function CandidatesTab({ tags, onRefresh, onTagSelect: _onTagSelect }: Props) {
  void _onTagSelect // retained for future use (navigate to tag on click)
  const [rows, setRows] = useState<CandRow[]>([])
  const [loading, setLoading] = useState(true)
  const [selected, setSelected] = useState<Set<string>>(new Set())
  const [search, setSearch] = useState('')
  const [statusFilter, setStatusFilter] = useState<'proposed' | 'rejected'>('proposed')
  const [verdictFilter, setVerdictFilter] = useState<string>('')
  const [minConfidence, setMinConfidence] = useState<number>(0)
  const [scoredOnly, setScoredOnly] = useState(false)
  const [unactedOnly, setUnactedOnly] = useState(false)
  const [sortBy, setSortBy] = useState<string>('occurrences')
  const [triaging, setTriaging] = useState(false)
  const [purging, setPurging] = useState(false)
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState('')

  // -- Operations from LLM triage --
  const [operations, setOperations] = useState<Map<string, CandidateOperation>>(new Map())
  const [appliedOps, setAppliedOps] = useState<Map<string, CandidateApplyResult>>(new Map())
  const [, setApplyResults] = useState<CandidateApplyResult[]>([])

  // -- Unified decision modal state --
  const [decisionModal, setDecisionModal] = useState<{
    phrases: string[]
    initialOp: CandidateOperation | null
    initialManualKind: TagKind
    initialManualCode: string
    initialApproveAsNew: boolean
    initialTagCodeMap: Record<string, string>
  } | null>(null)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const res = await fetchCandidates({ status: statusFilter, search, llm_verdict: verdictFilter, sort: sortBy, limit: 500 })
      setRows((res.rows || []).map(r => ({
        normalized: String(r.normalized || ''),
        ids: Array.isArray(r.ids) ? (r.ids as string[]).filter(Boolean) : [],
        status: r.status ? String(r.status) : (statusFilter === 'rejected' ? 'rejected' : 'proposed'),
        candidate_type: String(r.candidate_type || r.kind || 'd'),
        total_occurrences: Number(r.total_occurrences || r.occurrences || 0),
        doc_count: Number(r.doc_count || 0),
        avg_confidence: Number(r.avg_confidence || r.max_confidence || r.confidence || 0),
        llm_verdict: r.llm_verdict ? String(r.llm_verdict) : undefined,
        llm_confidence: r.llm_confidence != null ? Number(r.llm_confidence) : undefined,
        llm_reason: r.llm_reason ? String(r.llm_reason) : undefined,
        llm_suggested_code: r.llm_suggested_code ? String(r.llm_suggested_code) : undefined,
        llm_suggested_parent: r.llm_suggested_parent ? String(r.llm_suggested_parent) : undefined,
        llm_suggested_kind: r.llm_suggested_kind ? String(r.llm_suggested_kind) : undefined,
      })))
    } catch (e) {
      console.error('Failed to load candidates:', e)
      setMessage(`Failed to load: ${e}`)
    } finally {
      setLoading(false)
    }
  }, [statusFilter, search, verdictFilter, sortBy])

  useEffect(() => { load() }, [load])

  // -- Selection helpers --
  const toggleSelect = (norm: string) => {
    setSelected(prev => {
      const next = new Set(prev)
      next.has(norm) ? next.delete(norm) : next.add(norm)
      return next
    })
  }
  const selectFiltered = (pred: (r: CandRow) => boolean) => {
    setSelected(new Set(rows.filter(pred).map(r => r.normalized)))
  }
  const clearSelection = () => setSelected(new Set())

  // -- Restore rejected candidates back to proposed --
  const handleBulkRestore = async (phrases: string[]) => {
    const ids = rows.filter(r => phrases.includes(r.normalized)).flatMap(r => r.ids ?? [])
    if (ids.length === 0) {
      setMessage('No candidate IDs for selected rows. Try refreshing the list.')
      return
    }
    setBusy(true)
    setMessage(`Restoring ${phrases.length} candidates to proposed…`)
    try {
      await bulkReview({
        id_list: ids,
        state: 'proposed',
        reviewer: 'lexicon-ui',
        reviewer_notes: 'Restored from rejected',
      })
      setMessage(`${phrases.length} candidates restored to proposed`)
      setSelected(prev => {
        const next = new Set(prev)
        phrases.forEach(p => next.delete(p))
        return next
      })
      load()
      onRefresh()
    } catch (e) {
      setMessage(`Error: ${e}`)
    } finally {
      setBusy(false)
    }
  }

  // -- Bulk reject (manual, not via operations) --
  const handleBulkReject = async (phrases: string[], note?: string) => {
    const ids = rows.filter(r => phrases.includes(r.normalized)).flatMap(r => r.ids ?? [])
    if (ids.length === 0) {
      setMessage('No candidate IDs for selected rows. Try refreshing the list.')
      return
    }
    setBusy(true)
    setMessage(`Rejecting ${phrases.length} candidates…`)
    try {
      const res = await bulkReview({
        id_list: ids,
        state: 'rejected',
        reviewer: 'lexicon-ui',
        reviewer_notes: note,
      }) as { updated?: { normalized: string }[]; errors?: { normalized: string; error: string }[] }
      const okCount = (res.updated || []).length
      const errCount = (res.errors || []).length
      const errSample = (res.errors || []).slice(0, 3).map(e => `${e.normalized}: ${e.error}`).join('; ')
      setMessage(errCount > 0
        ? `Rejected ${okCount}, failed ${errCount}${errSample ? ` (e.g. ${errSample})` : ''}`
        : `${okCount} candidates rejected`)
      setSelected(prev => {
        const next = new Set(prev)
        ;(res.updated || []).forEach(u => next.delete(u.normalized))
        return next
      })
      load()
      onRefresh()
    } catch (e) {
      setMessage(`Error: ${e}`)
    } finally {
      setBusy(false)
    }
  }

  // -- LLM triage (now returns operations) --
  const handleLlmTriage = async () => {
    setTriaging(true)
    setMessage('Running LLM triage… this may take 30-60 seconds')
    setAppliedOps(new Map())
    setApplyResults([])
    try {
      const res = await runLlmTriage()
      // Build operations map keyed by normalized phrase
      const opsMap = new Map<string, CandidateOperation>()
      for (const op of (res.operations || [])) {
        if (op.normalized) {
          opsMap.set(op.normalized.toLowerCase(), op)
        }
      }
      setOperations(opsMap)
      setMessage(`LLM triaged ${res.triaged || 0} candidates with ${opsMap.size} operations`)
      load()
    } catch (e) {
      setMessage(`LLM triage failed: ${e}`)
    } finally {
      setTriaging(false)
    }
  }

  // Attach ids from loaded rows so backend uses UUIDs directly (no normalized resolution)
  const opWithIds = (op: CandidateOperation): CandidateOperation => {
    const row = rows.find(r => (r.normalized || '').toLowerCase() === (op.normalized || '').toLowerCase())
    if (row?.ids?.length) return { ...op, ids: row.ids }
    return op
  }

  // -- Apply selected operations --
  const handleApplySelected = async () => {
    const ops: CandidateOperation[] = []
    for (const norm of selected) {
      const op = operations.get(norm.toLowerCase())
      if (op && !appliedOps.has(norm.toLowerCase())) {
        ops.push(opWithIds(op))
      }
    }
    if (ops.length === 0) {
      setMessage('No pending operations for selected candidates')
      return
    }
    setBusy(true)
    setMessage(`Applying ${ops.length} operations…`)
    try {
      const res = await applyCandidateOperations(ops)
      setApplyResults(prev => [...prev, ...res.results])
      // Track applied status
      const newApplied = new Map(appliedOps)
      for (const r of res.results) {
        newApplied.set(r.normalized.toLowerCase(), r)
      }
      setAppliedOps(newApplied)
      const ok = res.applied_count
      const fail = res.failed_count
      setMessage(`Applied: ${ok} succeeded${fail > 0 ? `, ${fail} failed` : ''}${res.lexicon_revision ? ` (lexicon rev ${res.lexicon_revision})` : ''}`)
      setSelected(new Set())
      // Reload to reflect state changes
      await load()
      onRefresh()
    } catch (e) {
      setMessage(`Apply failed: ${e}`)
    } finally {
      setBusy(false)
    }
  }

  // -- Apply all operations at once --
  const handleApplyAll = async () => {
    const ops = Array.from(operations.values())
      .filter(op => !appliedOps.has(op.normalized.toLowerCase()))
      .map(opWithIds)
    if (ops.length === 0) {
      setMessage('No pending operations to apply')
      return
    }
    if (!confirm(`Apply all ${ops.length} LLM-suggested operations?\n\nThis will reject, add aliases, and create tags as recommended.`)) return
    setBusy(true)
    setMessage(`Applying all ${ops.length} operations…`)
    try {
      const res = await applyCandidateOperations(ops)
      setApplyResults(prev => [...prev, ...res.results])
      const newApplied = new Map(appliedOps)
      for (const r of res.results) {
        newApplied.set(r.normalized.toLowerCase(), r)
      }
      setAppliedOps(newApplied)
      const ok = res.applied_count
      const fail = res.failed_count
      setMessage(`Applied all: ${ok} succeeded${fail > 0 ? `, ${fail} failed` : ''}${res.lexicon_revision ? ` (lexicon rev ${res.lexicon_revision})` : ''}`)
      await load()
      onRefresh()
    } catch (e) {
      setMessage(`Apply failed: ${e}`)
    } finally {
      setBusy(false)
    }
  }

  // -- Apply single operation --
  const handleApplySingle = async (op: CandidateOperation) => {
    setBusy(true)
    setMessage(`Applying operation for "${op.normalized}"…`)
    try {
      const res = await applyCandidateOperations([opWithIds(op)])
      setApplyResults(prev => [...prev, ...res.results])
      const newApplied = new Map(appliedOps)
      for (const r of res.results) {
        newApplied.set(r.normalized.toLowerCase(), r)
      }
      setAppliedOps(newApplied)
      const r = res.results[0]
      setMessage(r?.status === 'ok'
        ? `Applied: ${op.op} for "${op.normalized}"`
        : `Failed: ${r?.detail || 'unknown error'}`)
      await load()
      onRefresh()
    } catch (e) {
      setMessage(`Apply failed: ${e}`)
    } finally {
      setBusy(false)
    }
  }

  // -- Purge stale --
  const handlePurgeStale = async () => {
    setPurging(true)
    setMessage('Purging stale candidates…')
    try {
      const preview = await purgeStale(true)
      const staleCount = Number(preview.stale_found || 0)
      if (staleCount === 0) {
        setMessage('No stale candidates found')
        setPurging(false)
        return
      }
      const res = await purgeStale(false)
      setMessage(`Purged ${res.purged || 0} stale candidates`)
      load()
      onRefresh()
    } catch (e) {
      setMessage(`Purge failed: ${e}`)
    } finally {
      setPurging(false)
    }
  }

  // -- Open unified decision modal (LLM or Manual path) --
  const openDecisionModal = (phrases: string[], mode: 'llm' | 'manual' = 'manual') => {
    if (phrases.length === 0) return
    const firstRow = rows.find(r => phrases.includes(r.normalized))
    const opOrLegacy = firstRow ? getOpOrLegacy(firstRow) : undefined
    const initialOp = mode === 'llm' && opOrLegacy ? opOrLegacy : opOrLegacy ?? null
    const sugKind = (firstRow?.llm_suggested_kind as TagKind) || 'd'
    const sugCode = firstRow?.llm_suggested_code || ''
    const sugAsNew = firstRow?.llm_verdict === 'new_tag'
    const tagCodeMap: Record<string, string> = {}
    for (const p of phrases) {
      const r = rows.find(rr => rr.normalized === p)
      if (r?.llm_suggested_code) {
        tagCodeMap[p.toLowerCase()] = `${r.llm_suggested_kind || 'd'}:${r.llm_suggested_code}`
      }
    }
    setDecisionModal({
      phrases,
      initialOp,
      initialManualKind: sugKind,
      initialManualCode: sugCode,
      initialApproveAsNew: sugAsNew,
      initialTagCodeMap: tagCodeMap,
    })
  }

  const executeApprove = async (params: {
    phrases: string[]
    kind: TagKind
    tagCodeMap: Record<string, string>
  }) => {
    const { phrases, kind, tagCodeMap } = params
    const ids = rows.filter(r => phrases.includes(r.normalized)).flatMap(r => r.ids ?? [])
    if (ids.length === 0) {
      setMessage('No candidate IDs for selected rows. Try refreshing the list.')
      return
    }
    setBusy(true)
    setMessage(`Approving ${phrases.length} candidates…`)
    try {
      await bulkReview({
        id_list: ids,
        state: 'approved',
        reviewer: 'lexicon-ui',
        candidate_type_override: kind,
        tag_code_map: tagCodeMap,
      })
      setMessage(`${phrases.length} candidates approved`)
      setDecisionModal(null)
      setSelected(prev => {
        const next = new Set(prev)
        phrases.forEach(p => next.delete(p))
        return next
      })
      load()
      onRefresh()
    } catch (e) {
      setMessage(`Approve failed: ${e}`)
    } finally {
      setBusy(false)
    }
  }

  // -- Render helpers --
  // LLM suggestion badges - prefixed to avoid confusion with user status (rejected)
  const opBadge = (op?: CandidateOperation) => {
    if (!op) return <span className="op-badge op-unscored">—</span>
    if (op.op === 'reject_candidate')
      return <span className="op-badge op-reject" title="LLM suggests reject">LLM: Reject</span>
    if (op.op === 'add_alias')
      return (
        <span className="op-badge op-alias" title={`LLM suggests alias to ${op.target_kind}.${op.target_code}`}>
          LLM: Alias → {op.target_code?.replace(/_/g, ' ')}
        </span>
      )
    if (op.op === 'create_tag')
      return (
        <span className="op-badge op-new" title={`LLM suggests new tag ${op.kind}.${op.code}`}>
          LLM: New → {op.code?.replace(/_/g, ' ')}
        </span>
      )
    return <span className="op-badge op-unscored">?</span>
  }

  const legacyVerdictBadge = (v?: string) => {
    if (!v) return <span className="op-badge op-unscored">—</span>
    const cls = v === 'new_tag' ? 'op-new' : v === 'alias' ? 'op-alias' : 'op-reject'
    const label = v === 'new_tag' ? 'LLM: New' : v === 'alias' ? 'LLM: Alias' : 'LLM: Reject'
    return <span className={`op-badge ${cls}`}>{label}</span>
  }

  const confBar = (conf?: number) => {
    if (conf == null) return null
    const pct = Math.round(conf * 100)
    const cls = conf >= 0.7 ? 'conf-high' : conf >= 0.4 ? 'conf-med' : 'conf-low'
    return (
      <div className="conf-bar-wrap" title={`${pct}%`}>
        <div className={`conf-bar ${cls}`} style={{ width: `${pct}%` }} />
        <span className="conf-label">{pct}%</span>
      </div>
    )
  }

  const getOp = (norm: string): CandidateOperation | undefined => operations.get(norm.toLowerCase())
  const getApplied = (norm: string): CandidateApplyResult | undefined => appliedOps.get(norm.toLowerCase())
  // Op from current triage or synthesized from stored llm_verdict (so Revise works for all scored rows)
  const getOpOrLegacy = (r: CandRow): CandidateOperation | undefined => {
    const op = getOp(r.normalized)
    if (op) return op
    const v = r.llm_verdict
    if (!v) return undefined
    const base = { normalized: r.normalized, reason: r.llm_reason }
    if (v === 'reject') return { ...base, op: 'reject_candidate' }
    if (v === 'alias') return { ...base, op: 'add_alias', target_kind: (r.llm_suggested_kind || 'd') as 'p' | 'd' | 'j', target_code: r.llm_suggested_code || '' }
    if (v === 'new_tag') return { ...base, op: 'create_tag', kind: (r.llm_suggested_kind || 'd') as 'p' | 'd' | 'j', code: r.llm_suggested_code || '', parent_code: r.llm_suggested_parent }
    return undefined
  }
  const hasOps = operations.size > 0
  const pendingOpsCount = Array.from(operations.values()).filter(op => !appliedOps.has(op.normalized.toLowerCase())).length

  // -- Counts --
  const unscored = rows.filter(r => !r.llm_verdict && !getOp(r.normalized)).length
  const opCounts = {
    reject: 0, alias: 0, new_tag: 0,
  }
  for (const op of operations.values()) {
    if (op.op === 'reject_candidate') opCounts.reject++
    else if (op.op === 'add_alias') opCounts.alias++
    else if (op.op === 'create_tag') opCounts.new_tag++
  }
  // Fallback to legacy verdict counts if no operations
  const llmRejectCount = hasOps ? opCounts.reject : rows.filter(r => r.llm_verdict === 'reject').length
  const llmAliasCount = hasOps ? opCounts.alias : rows.filter(r => r.llm_verdict === 'alias').length
  const llmNewCount = hasOps ? opCounts.new_tag : rows.filter(r => r.llm_verdict === 'new_tag').length

  // -- Client-side filtering (confidence slider, scored-only, verdict, unacted) --
  const filteredRows = rows.filter(r => {
    const op = getOp(r.normalized)
    const applied = getApplied(r.normalized)
    const conf = op?.confidence ?? r.llm_confidence
    const hasScore = !!(op || r.llm_verdict)
    const isUnacted = applied?.status !== 'ok'

    // Unacted only (Proposed tab): hide rows already applied this session
    if (statusFilter === 'proposed' && unactedOnly && !isUnacted) return false

    // Scored-only filter
    if (scoredOnly && !hasScore) return false

    // Confidence slider
    if (minConfidence > 0 && (conf == null || conf < minConfidence)) return false

    // Verdict / op type filter (applied client-side when we have operations)
    if (verdictFilter && hasOps) {
      if (!op) return false
      if (verdictFilter === 'reject' && op.op !== 'reject_candidate') return false
      if (verdictFilter === 'alias' && op.op !== 'add_alias') return false
      if (verdictFilter === 'new_tag' && op.op !== 'create_tag') return false
    }

    return true
  })

  // -- Tag list for approve modal --
  const tagOptions = tags.filter(t => t.active !== false).sort((a, b) => a.code.localeCompare(b.code))

  return (
    <div className="candidates-tab">
      {/* Top stats bar */}
      <div className="stats-bar">
        <div className="status-toggle">
          <button
            className={`chip ${statusFilter === 'proposed' ? 'active' : ''}`}
            onClick={() => { setStatusFilter('proposed'); setSelected(new Set()); setVerdictFilter('') }}
          >
            Proposed
          </button>
          <button
            className={`chip ${statusFilter === 'rejected' ? 'active' : ''}`}
            onClick={() => { setStatusFilter('rejected'); setSelected(new Set()); setVerdictFilter('') }}
          >
            Rejected
          </button>
        </div>
        <span className="stat-chip">{rows.length} candidates</span>
        {statusFilter === 'proposed' && unscored > 0 && <span className="stat-chip warn">{unscored} unscored</span>}
        {statusFilter === 'proposed' && llmNewCount > 0 && <span className="stat-chip new">{llmNewCount} new tags</span>}
        {statusFilter === 'proposed' && llmAliasCount > 0 && <span className="stat-chip alias">{llmAliasCount} aliases</span>}
        {statusFilter === 'proposed' && llmRejectCount > 0 && <span className="stat-chip rej">{llmRejectCount} LLM reject</span>}
      </div>

      {/* Action bar row 1: LLM + maintenance (proposed view only) */}
      {statusFilter === 'proposed' && (
        <div className="action-bar">
          <button className="btn primary" onClick={handleLlmTriage} disabled={triaging || busy}>
            {triaging ? 'Triaging…' : `Run LLM Triage${unscored > 0 ? ` (${unscored})` : ''}`}
          </button>
          {hasOps && pendingOpsCount > 0 && (
            <button className="btn success" onClick={handleApplyAll} disabled={busy}>
              Apply All ({pendingOpsCount})
            </button>
          )}
          <button className="btn" onClick={handlePurgeStale} disabled={purging || busy}>
            {purging ? 'Purging…' : 'Purge Stale'}
          </button>
          <div className="action-bar-spacer" />
          <div className="filter-chips">
            {[
              { val: '', label: 'All', count: rows.length },
              { val: 'new_tag', label: 'LLM New', count: llmNewCount },
              { val: 'alias', label: 'LLM Alias', count: llmAliasCount },
              { val: 'reject', label: 'LLM Reject', count: llmRejectCount },
            ].map(v => (
              <button
                key={v.val || 'all'}
                className={`chip ${verdictFilter === v.val ? 'active' : ''}`}
                onClick={() => setVerdictFilter(v.val)}
              >
                {v.label}{v.count > 0 ? ` (${v.count})` : ''}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Filter bar: scored-only toggle + confidence slider */}
      {statusFilter === 'proposed' && (
        <div className="action-bar filter-bar">
          <label className="scored-toggle">
            <input type="checkbox" checked={scoredOnly} onChange={e => setScoredOnly(e.target.checked)} />
            {' '}Scored only
          </label>
          <label className="scored-toggle">
            <input type="checkbox" checked={unactedOnly} onChange={e => setUnactedOnly(e.target.checked)} />
            {' '}Unacted only
          </label>
          <div className="confidence-slider">
            <span className="slider-label">Min confidence:</span>
            <input
              type="range"
              min={0}
              max={100}
              step={5}
              value={Math.round(minConfidence * 100)}
              onChange={e => setMinConfidence(Number(e.target.value) / 100)}
            />
            <span className="slider-value">{Math.round(minConfidence * 100)}%</span>
          </div>
          <div className="action-bar-spacer" />
          <span className="filter-count">{filteredRows.length} of {rows.length} shown</span>
          <select className="sort-select" value={sortBy} onChange={e => setSortBy(e.target.value)}>
            <option value="occurrences">Sort: Occurrences</option>
            <option value="llm_confidence">Sort: LLM Confidence</option>
            <option value="alphabetical">Sort: A-Z</option>
          </select>
          <input
            className="search-input"
            type="text"
            placeholder="Search…"
            value={search}
            onChange={e => setSearch(e.target.value)}
          />
        </div>
      )}
      {statusFilter === 'rejected' && (
        <div className="action-bar">
          <div className="action-bar-spacer" />
          <select className="sort-select" value={sortBy} onChange={e => setSortBy(e.target.value)}>
            <option value="occurrences">Sort: Occurrences</option>
            <option value="llm_confidence">Sort: LLM Confidence</option>
            <option value="alphabetical">Sort: A-Z</option>
          </select>
          <input
            className="search-input"
            type="text"
            placeholder="Search…"
            value={search}
            onChange={e => setSearch(e.target.value)}
          />
        </div>
      )}

      {message && <div className="message-bar">{message}</div>}

      {/* Selection bulk bar */}
      {selected.size > 0 && (
        <div className="bulk-bar">
          <span>{selected.size} selected</span>
          {statusFilter === 'rejected' ? (
            <button className="btn sm success" onClick={() => handleBulkRestore(Array.from(selected))} disabled={busy} title="Bring back to Proposed for re-review">
              Re-up (Bring back)
            </button>
          ) : (
            <>
              {hasOps && (
                <button className="btn sm success" onClick={handleApplySelected} disabled={busy}>
                  Apply Selected Ops
                </button>
              )}
              <button className="btn sm" onClick={() => openDecisionModal(Array.from(selected), 'manual')} disabled={busy}>
                Manual Approve
              </button>
              <button className="btn sm danger" onClick={() => handleBulkReject(Array.from(selected))} disabled={busy}>
                Reject Selected
              </button>
              <span className="bulk-sep">|</span>
              <button className="btn sm" onClick={() => selectFiltered(r => {
                const o = getOp(r.normalized)
                return o ? o.op === 'create_tag' : r.llm_verdict === 'new_tag'
              })}>
                Select LLM New
              </button>
              <button className="btn sm" onClick={() => selectFiltered(r => {
                const o = getOp(r.normalized)
                return o ? o.op === 'add_alias' : r.llm_verdict === 'alias'
              })}>
                Select LLM Alias
              </button>
              <button className="btn sm" onClick={() => selectFiltered(r => {
                const o = getOp(r.normalized)
                return o ? o.op === 'reject_candidate' : r.llm_verdict === 'reject'
              })}>
                Select LLM Reject
              </button>
            </>
          )}
          <div className="action-bar-spacer" />
          <button className="btn sm" onClick={clearSelection}>Clear</button>
        </div>
      )}

      {/* Table */}
      <div className="table-wrap">
        <table className="data-table">
          <thead>
            <tr>
              <th className="col-sel">
                <input type="checkbox" onChange={e => e.target.checked ? setSelected(new Set(filteredRows.map(r => r.normalized))) : clearSelection()} checked={selected.size > 0 && filteredRows.every(r => selected.has(r.normalized))} />
              </th>
              <th>Status</th>
              <th>Phrase</th>
              <th>LLM Suggestion</th>
              <th>Conf</th>
              <th>Reason</th>
              <th className="col-num">Hits</th>
              <th className="col-num">Docs</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {loading && <tr><td colSpan={9} className="center-text">Loading…</td></tr>}
            {!loading && filteredRows.length === 0 && <tr><td colSpan={9} className="center-text muted">{rows.length > 0 ? 'No candidates match filters' : 'No candidates'}</td></tr>}
            {filteredRows.map(r => {
              const op = getOp(r.normalized)
              const opOrLegacy = getOpOrLegacy(r)
              const applied = getApplied(r.normalized)
              const isDimmed = applied?.status === 'ok' || (!op && r.llm_verdict === 'reject')
              const conf = op?.confidence ?? r.llm_confidence
              const rowStatus = statusFilter === 'rejected' ? 'Rejected' : (applied?.status === 'ok' ? 'Applied' : 'Pending')

              return (
                <tr key={r.normalized} className={`${isDimmed ? 'dimmed' : ''} ${selected.has(r.normalized) ? 'row-selected' : ''} ${applied?.status === 'ok' ? 'row-applied' : ''}`}>
                  <td>
                    <input type="checkbox" checked={selected.has(r.normalized)} onChange={() => toggleSelect(r.normalized)} disabled={applied?.status === 'ok'} />
                  </td>
                  <td className="status-cell">
                    <span className={`status-badge status-${rowStatus.toLowerCase()}`} title={statusFilter === 'rejected' ? 'User rejected — click Re-up to bring back' : applied?.status === 'ok' ? 'Applied this session' : 'Awaiting your action'}>
                      {rowStatus}
                    </span>
                  </td>
                  <td className="phrase-cell" title={r.normalized}>{r.normalized}</td>
                  <td className="op-cell">
                    {applied?.status === 'ok' ? (
                      <span className="op-badge op-applied">✓ Applied</span>
                    ) : applied?.status === 'error' ? (
                      <span className="op-badge op-error" title={applied.detail}>✗ Failed</span>
                    ) : op ? (
                      opBadge(op)
                    ) : (
                      legacyVerdictBadge(r.llm_verdict)
                    )}
                  </td>
                  <td>{confBar(conf)}</td>
                  <td className="reason-cell">
                    <span className="reason-text" title={op?.reason || r.llm_reason || ''}>
                      {op?.reason || r.llm_reason || '—'}
                    </span>
                  </td>
                  <td className="col-num">{r.total_occurrences}</td>
                  <td className="col-num">{r.doc_count}</td>
                  <td className="actions-cell">
                    {statusFilter === 'rejected' ? (
                      <button className="btn xs success" onClick={() => handleBulkRestore([r.normalized])} disabled={busy} title="Re-up — bring back to Proposed">
                        ↺ Re-up
                      </button>
                    ) : applied?.status === 'ok' ? (
                      <span className="applied-check">✓</span>
                    ) : (
                      <>
                        <button className="btn xs" onClick={() => openDecisionModal([r.normalized], opOrLegacy ? 'llm' : 'manual')} disabled={busy} title="Review / Decide">
                          ✎
                        </button>
                        {op && (
                          <button className="btn xs success" onClick={() => handleApplySingle(op)} disabled={busy} title="Apply this operation">
                            ▶
                          </button>
                        )}
                        <button className="btn xs danger" onClick={() => handleBulkReject([r.normalized])} disabled={busy} title="Reject">
                          ✕
                        </button>
                      </>
                    )}
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>

      {/* Unified decision modal */}
      {decisionModal && (
        <CandidateDecisionModal
          phrases={decisionModal.phrases}
          initialOp={decisionModal.initialOp}
          initialManualKind={decisionModal.initialManualKind}
          initialManualCode={decisionModal.initialManualCode}
          initialApproveAsNew={decisionModal.initialApproveAsNew}
          initialTagCodeMap={decisionModal.initialTagCodeMap}
          rows={rows}
          tags={tagOptions}
          opWithIds={opWithIds}
          onApply={handleApplySingle}
          onApprove={executeApprove}
          onReject={handleBulkReject}
          onClose={() => setDecisionModal(null)}
          onMessage={setMessage}
          onReviseSuccess={(revised) => {
            const newOps = new Map(operations)
            newOps.set(revised.normalized.toLowerCase(), revised)
            setOperations(newOps)
          }}
          onSuggestionSuccess={(suggestion) => {
            const newOps = new Map(operations)
            newOps.set(suggestion.normalized.toLowerCase(), suggestion)
            setOperations(newOps)
          }}
        />
      )}
    </div>
  )
}
