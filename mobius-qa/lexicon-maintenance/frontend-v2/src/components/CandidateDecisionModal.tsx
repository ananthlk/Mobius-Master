import { useState, useEffect } from 'react'
import type { TagEntry, TagKind } from '../types'
import { reviseCandidateOperation, getLlmSuggestion, type CandidateOperation } from '../api'

export interface CandidateDecisionModalProps {
  phrases: string[]
  initialOp: CandidateOperation | null
  initialManualKind?: TagKind
  initialManualCode?: string
  initialApproveAsNew?: boolean
  initialTagCodeMap?: Record<string, string>
  rows: Array<{ normalized: string; ids: string[] }>
  tags: TagEntry[]
  opWithIds: (op: CandidateOperation) => CandidateOperation
  onApply: (op: CandidateOperation) => Promise<void>
  onApprove: (params: { phrases: string[]; kind: TagKind; tagCodeMap: Record<string, string> }) => Promise<void>
  onReject: (phrases: string[]) => Promise<void>
  onClose: () => void
  onMessage: (msg: string) => void
  onReviseSuccess?: (op: CandidateOperation) => void
  onSuggestionSuccess?: (op: CandidateOperation) => void
}

function opBadge(op?: CandidateOperation | null) {
  if (!op) return null
  if (op.op === 'reject_candidate')
    return <span className="op-badge op-reject">LLM: Reject</span>
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

export function CandidateDecisionModal({
  phrases,
  initialOp,
  initialManualKind = 'd',
  initialManualCode = '',
  initialApproveAsNew = false,
  initialTagCodeMap = {},
  rows,
  tags,
  opWithIds,
  onApply,
  onApprove,
  onReject,
  onClose,
  onMessage,
  onReviseSuccess,
  onSuggestionSuccess,
}: CandidateDecisionModalProps) {
  const [mode, setMode] = useState<'llm' | 'manual'>(initialOp ? 'llm' : 'manual')
  const [op, setOp] = useState<CandidateOperation | null>(initialOp)
  const [reviseInstructions, setReviseInstructions] = useState('')
  const [revising, setRevising] = useState(false)
  const [suggesting, setSuggesting] = useState(false)
  const [busy, setBusy] = useState(false)

  const [approveKind, setApproveKind] = useState<TagKind>(initialManualKind)
  const [approveTargetCode, setApproveTargetCode] = useState(initialManualCode)
  const [approveAsNew, setApproveAsNew] = useState(initialApproveAsNew)
  const tagCodeMap: Record<string, string> = { ...initialTagCodeMap }

  const primaryPhrase = phrases[0] || ''
  const hasOp = !!op

  useEffect(() => {
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  }, [onClose])

  const handleGetLlmSuggestion = async () => {
    if (!primaryPhrase) return
    setSuggesting(true)
    try {
      const row = rows.find(r => phrases.includes(r.normalized))
      const ids = row?.ids
      const res = await getLlmSuggestion(primaryPhrase, ids)
      const suggestion = res.operation
      setOp(suggestion)
      setMode('llm')
      onSuggestionSuccess?.(suggestion)
      onMessage(`Got LLM suggestion for "${primaryPhrase}"`)
    } catch (e) {
      onMessage(`Get LLM suggestion failed: ${e}`)
    } finally {
      setSuggesting(false)
    }
  }

  const handleReviseSubmit = async () => {
    if (!op || !reviseInstructions.trim()) return
    setRevising(true)
    try {
      const res = await reviseCandidateOperation(primaryPhrase, op, reviseInstructions.trim())
      const revised = res.operation
      setOp(revised)
      setReviseInstructions('')
      onReviseSuccess?.(revised)
      onMessage(`Revised operation for "${primaryPhrase}"`)
    } catch (e) {
      onMessage(`Revise failed: ${e}`)
    } finally {
      setRevising(false)
    }
  }

  const handleApply = async () => {
    if (!op) return
    setBusy(true)
    try {
      await onApply(opWithIds(op))
      onClose()
    } finally {
      setBusy(false)
    }
  }

  const handleApprove = async () => {
    const finalMap: Record<string, string> = { ...tagCodeMap }
    const targetWithKind = `${approveKind}:${approveTargetCode || primaryPhrase.replace(/\s+/g, '_').toLowerCase()}`
    for (const p of phrases) {
      const key = p.toLowerCase()
      if (!finalMap[key]) finalMap[key] = targetWithKind
    }
    setBusy(true)
    try {
      await onApprove({ phrases, kind: approveKind, tagCodeMap: finalMap })
      onClose()
    } finally {
      setBusy(false)
    }
  }

  const handleReject = async () => {
    setBusy(true)
    try {
      await onReject(phrases)
      onClose()
    } finally {
      setBusy(false)
    }
  }

  const tagOptions = tags.filter(t => t.active !== false).sort((a, b) => a.code.localeCompare(b.code))
  const manualValid = approveAsNew ? !!approveTargetCode.trim() : !!approveTargetCode

  return (
    <div className="modal-overlay" onClick={onClose} aria-hidden>
      <div className="modal unified-decision-modal" onClick={e => e.stopPropagation()}>
        <div className="modal-header">
          <h3>Decide: {phrases.length === 1 ? phrases[0] : `${phrases.length} candidates`}</h3>
          <button type="button" className="close-btn" onClick={onClose} aria-label="Close">
            &times;
          </button>
        </div>

        <div className="modal-body">
        {phrases.length > 1 && (
          <div className="unified-phrases">
            {phrases.slice(0, 20).map(p => (
              <span key={p} className="alias-chip">
                {p}
              </span>
            ))}
            {phrases.length > 20 && <span className="muted">…and {phrases.length - 20} more</span>}
          </div>
        )}

        <div className="unified-mode-toggle">
          <button
            type="button"
            className={`chip ${mode === 'llm' ? 'active' : ''}`}
            onClick={() => setMode('llm')}
          >
            LLM
          </button>
          <button
            type="button"
            className={`chip ${mode === 'manual' ? 'active' : ''}`}
            onClick={() => setMode('manual')}
          >
            Manual
          </button>
        </div>

        {mode === 'llm' && (
          <div className="unified-llm-section">
            {hasOp ? (
              <>
                <label className="field-label">LLM Suggestion</label>
                <div className="revise-current-op">
                  {opBadge(op)}
                  <span className="revise-reason">{op?.reason || '—'}</span>
                </div>
                {op?.op === 'add_alias' && (
                  <div className="revise-detail">
                    Target: <strong>{op.target_kind}.{op.target_code}</strong>
                  </div>
                )}
                {op?.op === 'create_tag' && (
                  <div className="revise-detail">
                    New tag: <strong>{op.kind}.{op.code}</strong>
                    {op.parent_code && <span> (parent: {op.parent_code})</span>}
                    {op.description && <span> — {op.description}</span>}
                  </div>
                )}
                <label className="field-label">Revise with instructions (optional)</label>
                <textarea
                  className="revise-textarea"
                  rows={2}
                  placeholder="e.g. 'Reject this, it is noise' or 'Use emergency_services as target'"
                  value={reviseInstructions}
                  onChange={e => setReviseInstructions(e.target.value)}
                />
              </>
            ) : (
              <div className="unified-get-suggestion">
                <p className="muted">No LLM suggestion yet. Get one to apply or revise.</p>
                <button
                  type="button"
                  className="btn primary"
                  onClick={handleGetLlmSuggestion}
                  disabled={suggesting}
                >
                  {suggesting ? 'Getting suggestion…' : 'Get LLM Suggestion'}
                </button>
              </div>
            )}
          </div>
        )}

        {mode === 'manual' && (
          <div className="unified-manual-section">
            <label className="field-label">Tag type</label>
            <div className="filter-chips">
              {(['d', 'p', 'j'] as TagKind[]).map(k => (
                <button
                  key={k}
                  type="button"
                  className={`chip ${approveKind === k ? 'active' : ''}`}
                  onClick={() => setApproveKind(k)}
                >
                  {k === 'd' ? 'Domain (D)' : k === 'p' ? 'Procedural (P)' : 'Jurisdiction (J)'}
                </button>
              ))}
            </div>
            <label className="field-label">
              <input type="checkbox" checked={approveAsNew} onChange={e => setApproveAsNew(e.target.checked)} />
              {' '}Create as new tag (otherwise add as alias)
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
        )}
        </div>

        <div className="modal-footer unified-footer">
          <button type="button" className="btn danger" onClick={handleReject} disabled={busy}>
            Reject
          </button>
          <div className="footer-actions">
            <button type="button" className="btn" onClick={onClose}>
              Cancel
            </button>
            {mode === 'llm' && hasOp && (
              <>
                <button
                  type="button"
                  className="btn"
                  onClick={handleReviseSubmit}
                  disabled={revising || !reviseInstructions.trim()}
                >
                  {revising ? 'Revising…' : 'Revise with LLM'}
                </button>
                <button type="button" className="btn success" onClick={handleApply} disabled={busy}>
                  Apply
                </button>
              </>
            )}
            {mode === 'manual' && (
              <button
                type="button"
                className="btn success"
                onClick={handleApprove}
                disabled={busy || !manualValid}
              >
                {busy ? 'Approving…' : `Approve ${phrases.length}`}
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
