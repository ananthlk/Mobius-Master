import { useState, useEffect, useCallback } from 'react'
import type { TagEntry, TagKind } from '../types'
import { fetchCandidates, bulkReview, runLlmTriage, purgeStale } from '../api'

interface Props {
  tags: TagEntry[]
  onRefresh: () => void
  onTagSelect: (kind: TagKind, code: string) => void
}

interface CandRow {
  normalized: string
  candidate_type: string
  total_occurrences: number
  doc_count: number
  avg_confidence: number
  llm_verdict?: string
  llm_confidence?: number
  llm_reason?: string
  llm_suggested_code?: string
  llm_suggested_parent?: string
  llm_suggested_kind?: string
}

export function CandidatesTab({ tags, onRefresh, onTagSelect }: Props) {
  const [rows, setRows] = useState<CandRow[]>([])
  const [loading, setLoading] = useState(true)
  const [selected, setSelected] = useState<Set<string>>(new Set())
  const [search, setSearch] = useState('')
  const [statusFilter, setStatusFilter] = useState<'proposed' | 'rejected'>('proposed')
  const [verdictFilter, setVerdictFilter] = useState<string>('')
  const [sortBy, setSortBy] = useState<string>('occurrences')
  const [triaging, setTriaging] = useState(false)
  const [purging, setPurging] = useState(false)
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState('')

  // -- Approve modal state --
  const [approveModal, setApproveModal] = useState<{
    phrases: string[]
    kind: TagKind
    tagCodeMap: Record<string, string>
  } | null>(null)
  const [approveKind, setApproveKind] = useState<TagKind>('d')
  const [approveTargetCode, setApproveTargetCode] = useState('')
  const [approveAsNew, setApproveAsNew] = useState(false)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const res = await fetchCandidates({ status: statusFilter, search, llm_verdict: verdictFilter, sort: sortBy, limit: 500 })
      setRows((res.rows || []).map(r => ({
        normalized: String(r.normalized || ''),
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
  const selectAll = () => setSelected(new Set(rows.map(r => r.normalized)))
  const selectFiltered = (pred: (r: CandRow) => boolean) => {
    setSelected(new Set(rows.filter(pred).map(r => r.normalized)))
  }
  const clearSelection = () => setSelected(new Set())

  // -- Restore rejected candidates back to proposed --
  const handleBulkRestore = async (phrases: string[]) => {
    if (phrases.length === 0) return
    setBusy(true)
    setMessage(`Restoring ${phrases.length} candidates to proposed…`)
    try {
      await bulkReview({
        normalized_list: phrases,
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

  // -- Bulk reject --
  const handleBulkReject = async (phrases: string[], note?: string) => {
    if (phrases.length === 0) return
    setBusy(true)
    setMessage(`Rejecting ${phrases.length} candidates…`)
    try {
      await bulkReview({
        normalized_list: phrases,
        state: 'rejected',
        reviewer: 'lexicon-ui',
        reviewer_notes: note,
      })
      setMessage(`${phrases.length} candidates rejected`)
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

  // -- Open approve modal --
  const openApproveModal = (phrases: string[]) => {
    if (phrases.length === 0) return
    // Pre-fill from LLM suggestions if available for the first phrase
    const firstRow = rows.find(r => phrases.includes(r.normalized))
    const sugKind = (firstRow?.llm_suggested_kind as TagKind) || 'd'
    const sugCode = firstRow?.llm_suggested_code || ''

    // Build tag_code_map from LLM suggestions where available
    const tagCodeMap: Record<string, string> = {}
    for (const p of phrases) {
      const r = rows.find(rr => rr.normalized === p)
      if (r?.llm_suggested_code) {
        tagCodeMap[p.toLowerCase()] = `${r.llm_suggested_kind || 'd'}:${r.llm_suggested_code}`
      }
    }

    setApproveKind(sugKind)
    setApproveTargetCode(sugCode)
    setApproveAsNew(firstRow?.llm_verdict === 'new_tag')
    setApproveModal({ phrases, kind: sugKind, tagCodeMap })
  }

  // -- Execute approve --
  const executeApprove = async () => {
    if (!approveModal) return
    const { phrases, tagCodeMap } = approveModal

    // Build final tag_code_map: use modal override for phrases without LLM suggestion
    const finalMap: Record<string, string> = { ...tagCodeMap }
    const targetWithKind = `${approveKind}:${approveTargetCode || approveModal.phrases[0].replace(/\s+/g, '_').toLowerCase()}`
    for (const p of phrases) {
      const key = p.toLowerCase()
      if (!finalMap[key]) {
        finalMap[key] = targetWithKind
      }
    }

    setBusy(true)
    setMessage(`Approving ${phrases.length} candidates…`)
    try {
      await bulkReview({
        normalized_list: phrases,
        state: 'approved',
        reviewer: 'lexicon-ui',
        candidate_type_override: approveKind,
        tag_code_map: finalMap,
      })
      setMessage(`${phrases.length} candidates approved`)
      setApproveModal(null)
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

  // -- Quick actions on LLM-scored groups --
  const handleAcceptLlmAliases = async () => {
    const aliases = rows.filter(r => r.llm_verdict === 'alias' && r.llm_suggested_code && r.llm_confidence != null && r.llm_confidence >= 0.6)
    if (aliases.length === 0) { setMessage('No high-confidence LLM aliases to approve'); return }
    // Build tag_code_map from LLM suggestions
    const tagCodeMap: Record<string, string> = {}
    for (const r of aliases) {
      tagCodeMap[r.normalized.toLowerCase()] = `${r.llm_suggested_kind || 'd'}:${r.llm_suggested_code!}`
    }
    setBusy(true)
    setMessage(`Approving ${aliases.length} LLM-suggested aliases…`)
    try {
      await bulkReview({
        normalized_list: aliases.map(r => r.normalized),
        state: 'approved',
        reviewer: 'llm-auto-approve',
        reviewer_notes: 'Auto-approved: LLM verdict=alias, confidence >= 0.6',
        candidate_type_override: 'd',
        tag_code_map: tagCodeMap,
      })
      setMessage(`${aliases.length} aliases approved`)
      load()
      onRefresh()
    } catch (e) {
      setMessage(`Error: ${e}`)
    } finally {
      setBusy(false)
    }
  }

  const handleRejectLlmRejects = async () => {
    const rejects = rows.filter(r => r.llm_verdict === 'reject')
    if (rejects.length === 0) { setMessage('No LLM-rejected candidates to reject'); return }
    await handleBulkReject(rejects.map(r => r.normalized), 'Auto-rejected: LLM verdict=reject')
  }

  // -- LLM triage --
  const handleLlmTriage = async () => {
    setTriaging(true)
    setMessage('Running LLM triage… this may take 30-60 seconds')
    try {
      const res = await runLlmTriage()
      setMessage(`LLM triaged ${res.triaged || 0} candidates`)
      load()
    } catch (e) {
      setMessage(`LLM triage failed: ${e}`)
    } finally {
      setTriaging(false)
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

  // -- Single row approve (quick: use LLM suggestion or create new) --
  const handleRowApprove = (r: CandRow) => {
    if (r.llm_suggested_code && r.llm_verdict === 'alias') {
      // Quick approve: LLM already knows the target
      const tagCodeMap: Record<string, string> = {
        [r.normalized.toLowerCase()]: `${r.llm_suggested_kind || 'd'}:${r.llm_suggested_code}`,
      }
      setBusy(true)
      setMessage(`Approving "${r.normalized}"…`)
      bulkReview({
        normalized_list: [r.normalized],
        state: 'approved',
        reviewer: 'lexicon-ui',
        candidate_type_override: (r.llm_suggested_kind as 'p' | 'd' | 'j') || 'd',
        tag_code_map: tagCodeMap,
      }).then(() => {
        setMessage(`"${r.normalized}" approved as alias of ${r.llm_suggested_code}`)
        load()
        onRefresh()
      }).catch(e => setMessage(`Error: ${e}`))
        .finally(() => setBusy(false))
    } else {
      // Open modal for manual mapping
      openApproveModal([r.normalized])
    }
  }

  // -- Render helpers --
  const verdictBadge = (v?: string) => {
    if (!v) return <span className="verdict-badge badge-unscored">?</span>
    const cls = v === 'new_tag' ? 'badge-new' : v === 'alias' ? 'badge-alias' : 'badge-reject'
    const label = v === 'new_tag' ? 'NEW' : v === 'alias' ? 'ALIAS' : 'REJ'
    return <span className={`verdict-badge ${cls}`}>{label}</span>
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

  // -- Counts --
  const unscored = rows.filter(r => !r.llm_verdict).length
  const llmAliasCount = rows.filter(r => r.llm_verdict === 'alias' && r.llm_suggested_code && (r.llm_confidence ?? 0) >= 0.6).length
  const llmRejectCount = rows.filter(r => r.llm_verdict === 'reject').length
  const llmNewCount = rows.filter(r => r.llm_verdict === 'new_tag').length

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
        {statusFilter === 'proposed' && llmRejectCount > 0 && <span className="stat-chip rej">{llmRejectCount} rejects</span>}
      </div>

      {/* Action bar row 1: LLM + maintenance (proposed view only) */}
      {statusFilter === 'proposed' && (
        <div className="action-bar">
          <button className="btn primary" onClick={handleLlmTriage} disabled={triaging || busy}>
            {triaging ? 'Triaging…' : `Run LLM Triage${unscored > 0 ? ` (${unscored})` : ''}`}
          </button>
          <button className="btn" onClick={handlePurgeStale} disabled={purging || busy}>
            {purging ? 'Purging…' : 'Purge Stale'}
          </button>
          <div className="action-bar-spacer" />
          <div className="filter-chips">
            {[
              { val: '', label: 'All', count: rows.length },
              { val: 'new_tag', label: 'New Tag', count: llmNewCount },
              { val: 'alias', label: 'Alias', count: llmAliasCount },
              { val: 'reject', label: 'Reject', count: llmRejectCount },
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

      {/* Action bar row 2: Quick bulk actions based on LLM results (proposed view only) */}
      {statusFilter === 'proposed' && (llmAliasCount > 0 || llmRejectCount > 0) && (
        <div className="action-bar quick-actions">
          {llmAliasCount > 0 && (
            <button className="btn success" onClick={handleAcceptLlmAliases} disabled={busy}>
              Accept All Aliases ({llmAliasCount})
            </button>
          )}
          {llmRejectCount > 0 && (
            <button className="btn danger" onClick={handleRejectLlmRejects} disabled={busy}>
              Reject All LLM Rejects ({llmRejectCount})
            </button>
          )}
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
      {/* Fallback sort/search when no LLM results (proposed) or always for rejected */}
      {(statusFilter === 'rejected' || (statusFilter === 'proposed' && llmAliasCount === 0 && llmRejectCount === 0)) && (
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
            <button className="btn sm success" onClick={() => handleBulkRestore(Array.from(selected))} disabled={busy}>
              Restore to Proposed
            </button>
          ) : (
            <>
              <button className="btn sm success" onClick={() => openApproveModal(Array.from(selected))} disabled={busy}>
                Approve Selected
              </button>
              <button className="btn sm danger" onClick={() => handleBulkReject(Array.from(selected))} disabled={busy}>
                Reject Selected
              </button>
              <span className="bulk-sep">|</span>
              <button className="btn sm" onClick={() => selectFiltered(r => r.llm_verdict === 'new_tag')}>
                Select New Tags
              </button>
              <button className="btn sm" onClick={() => selectFiltered(r => r.llm_verdict === 'alias')}>
                Select Aliases
              </button>
              <button className="btn sm" onClick={() => selectFiltered(r => r.llm_verdict === 'reject')}>
                Select Rejects
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
                <input type="checkbox" onChange={e => e.target.checked ? selectAll() : clearSelection()} checked={selected.size === rows.length && rows.length > 0} />
              </th>
              <th>Phrase</th>
              <th>LLM</th>
              <th>Conf</th>
              <th>Suggested Placement</th>
              <th className="col-num">Hits</th>
              <th className="col-num">Docs</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {loading && <tr><td colSpan={8} className="center-text">Loading…</td></tr>}
            {!loading && rows.length === 0 && <tr><td colSpan={8} className="center-text muted">No candidates</td></tr>}
            {rows.map(r => {
              const isDimmed = r.llm_verdict === 'reject'
              return (
                <tr key={r.normalized} className={`${isDimmed ? 'dimmed' : ''} ${selected.has(r.normalized) ? 'row-selected' : ''}`}>
                  <td>
                    <input type="checkbox" checked={selected.has(r.normalized)} onChange={() => toggleSelect(r.normalized)} />
                  </td>
                  <td className="phrase-cell" title={r.normalized}>{r.normalized}</td>
                  <td>{verdictBadge(r.llm_verdict)}</td>
                  <td>{confBar(r.llm_confidence)}</td>
                  <td className="suggested-cell">
                    {r.llm_suggested_code ? (
                      <span className="suggested-link" onClick={() => {
                        if (r.llm_suggested_kind && r.llm_suggested_code)
                          onTagSelect(r.llm_suggested_kind as TagKind, r.llm_suggested_code)
                      }}>
                        {r.llm_suggested_kind?.toUpperCase()} › {r.llm_suggested_code.replace(/_/g, ' ')}
                      </span>
                    ) : (
                      <span className="muted">—</span>
                    )}
                    {r.llm_reason && <span className="reason-tooltip" title={r.llm_reason}> ⓘ</span>}
                  </td>
                  <td className="col-num">{r.total_occurrences}</td>
                  <td className="col-num">{r.doc_count}</td>
                  <td className="actions-cell">
                    {statusFilter === 'rejected' ? (
                      <button className="btn xs success" onClick={() => handleBulkRestore([r.normalized])} disabled={busy} title="Restore to proposed">
                        ↺
                      </button>
                    ) : (
                      <>
                        <button className="btn xs success" onClick={() => handleRowApprove(r)} disabled={busy} title="Approve (add as alias or new tag)">
                          ✓
                        </button>
                        <button className="btn xs danger" onClick={() => {
                          handleBulkReject([r.normalized])
                        }} disabled={busy} title="Reject">
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

      {/* Approve Modal */}
      {approveModal && (
        <div className="modal-overlay" onClick={() => setApproveModal(null)}>
          <div className="modal" onClick={e => e.stopPropagation()}>
            <div className="modal-header">
              <h3>Approve {approveModal.phrases.length} candidate{approveModal.phrases.length > 1 ? 's' : ''}</h3>
              <button className="close-btn" onClick={() => setApproveModal(null)}>✕</button>
            </div>
            <div className="modal-body">
              {/* Phrases being approved */}
              <label className="field-label">Phrases</label>
              <div className="phrase-chips">
                {approveModal.phrases.slice(0, 20).map(p => (
                  <span key={p} className="alias-chip">{p}</span>
                ))}
                {approveModal.phrases.length > 20 && (
                  <span className="muted">…and {approveModal.phrases.length - 20} more</span>
                )}
              </div>

              {/* Tag kind */}
              <label className="field-label">Tag type</label>
              <div className="filter-chips">
                {(['d', 'p', 'j'] as TagKind[]).map(k => (
                  <button
                    key={k}
                    className={`chip ${approveKind === k ? 'active' : ''}`}
                    onClick={() => setApproveKind(k)}
                  >
                    {k === 'd' ? 'Domain (D)' : k === 'p' ? 'Procedural (P)' : 'Jurisdiction (J)'}
                  </button>
                ))}
              </div>

              {/* New tag vs existing */}
              <label className="field-label">
                <input type="checkbox" checked={approveAsNew} onChange={e => setApproveAsNew(e.target.checked)} />
                {' '}Create as new tag (otherwise add as alias to existing tag)
              </label>

              {!approveAsNew && (
                <>
                  <label className="field-label">Map to existing tag</label>
                  <select
                    className="modal-select"
                    value={approveTargetCode}
                    onChange={e => setApproveTargetCode(e.target.value)}
                  >
                    <option value="">— Select a tag —</option>
                    {tagOptions.filter(t => t.kind === approveKind).map(t => (
                      <option key={`${t.kind}:${t.code}`} value={t.code}>
                        {t.code.replace(/_/g, ' ')} {t.spec.description ? `— ${t.spec.description}` : ''}
                      </option>
                    ))}
                  </select>
                </>
              )}

              {approveAsNew && (
                <>
                  <label className="field-label">New tag code</label>
                  <input
                    className="modal-input"
                    type="text"
                    placeholder="e.g. health_care_services.chronic_pain"
                    value={approveTargetCode}
                    onChange={e => setApproveTargetCode(e.target.value)}
                  />
                </>
              )}
            </div>
            <div className="modal-footer">
              <button className="btn" onClick={() => setApproveModal(null)}>Cancel</button>
              <button
                className="btn success"
                onClick={executeApprove}
                disabled={busy || (!approveAsNew && !approveTargetCode)}
              >
                {busy ? 'Approving…' : `Approve ${approveModal.phrases.length}`}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
