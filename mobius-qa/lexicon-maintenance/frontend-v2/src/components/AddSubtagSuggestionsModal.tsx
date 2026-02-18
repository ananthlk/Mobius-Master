import { useState } from 'react'
import { patchTag } from '../api'
import { SUGGESTIONS_BY_PARENT } from '../suggestionsByParent'

export interface AddSubtagSuggestionsModalProps {
  kind: string
  parentCode: string
  onClose: () => void
  onSuccess: () => void
}

export function AddSubtagSuggestionsModal({
  kind,
  parentCode,
  onClose,
  onSuccess,
}: AddSubtagSuggestionsModalProps) {
  const suggestions = SUGGESTIONS_BY_PARENT[parentCode] ?? []
  const [selected, setSelected] = useState<Set<string>>(new Set())
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  const toggle = (code: string) => {
    setSelected(prev => {
      const next = new Set(prev)
      if (next.has(code)) next.delete(code)
      else next.add(code)
      return next
    })
  }

  const handleAddSelected = async () => {
    if (selected.size === 0) {
      setError('Select at least one suggestion')
      return
    }
    setError(null)
    setBusy(true)
    try {
      for (const code of selected) {
        const fullCode = `${parentCode}.${code}`
        await patchTag(kind, fullCode, {
          spec: { parent_code: parentCode },
          active: true,
        })
      }
      onSuccess()
      onClose()
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Failed to add sub-tags')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="modal-overlay" onClick={onClose} aria-hidden>
      <div className="modal" onClick={e => e.stopPropagation()}>
        <div className="modal-header">
          <h3>Add from suggestions under {parentCode}</h3>
          <button className="btn compact" onClick={onClose}>x</button>
        </div>
        <div className="modal-body">
          {suggestions.length === 0 ? (
            <p className="modal-hint">No suggestions configured for this domain. Add sub-tags manually or extract from a document.</p>
          ) : (
            <div className="modal-field-group">
              <label className="modal-label">Select sub-tags to add</label>
              <ul style={{ listStyle: 'none', padding: 0, margin: 0 }}>
                {suggestions.map(({ code, label }) => (
                  <li key={code} style={{ marginBottom: 6 }}>
                    <label style={{ display: 'flex', alignItems: 'center', gap: 8, cursor: 'pointer' }}>
                      <input
                        type="checkbox"
                        checked={selected.has(code)}
                        onChange={() => toggle(code)}
                      />
                      <span>{label ?? code}</span>
                      <span className="modal-hint">({parentCode}.{code})</span>
                    </label>
                  </li>
                ))}
              </ul>
            </div>
          )}
          {error && <p className="modal-hint" style={{ color: 'var(--error)' }}>{error}</p>}
        </div>
        <div className="modal-footer">
          <button className="btn" onClick={onClose}>Cancel</button>
          <button
            className="btn primary"
            onClick={handleAddSelected}
            disabled={busy || suggestions.length === 0 || selected.size === 0}
          >
            {busy ? 'Adding…' : `Add selected (${selected.size})`}
          </button>
        </div>
      </div>
    </div>
  )
}
