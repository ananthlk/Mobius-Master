import { useState } from 'react'
import { patchTag, suggestSubtagsFromDocument, type SuggestFromDocumentItem } from '../api'

export interface AddSubtagDocumentModalProps {
  kind: string
  parentCode: string
  onClose: () => void
  onSuccess: () => void
}

export function AddSubtagDocumentModal({
  kind,
  parentCode,
  onClose,
  onSuccess,
}: AddSubtagDocumentModalProps) {
  const [text, setText] = useState('')
  const [file, setFile] = useState<File | null>(null)
  const [suggestions, setSuggestions] = useState<SuggestFromDocumentItem[]>([])
  const [selected, setSelected] = useState<Set<string>>(new Set())
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  const hasInput = text.trim().length > 0 || (file != null && file.size > 0)

  const handleExtract = async () => {
    if (!hasInput) {
      setError('Paste text or upload a file')
      return
    }
    setError(null)
    setLoading(true)
    setSuggestions([])
    setSelected(new Set())
    try {
      const res = await suggestSubtagsFromDocument(kind, parentCode, {
        text: text.trim() || undefined,
        file: file ?? undefined,
      })
      setSuggestions(res.suggestions ?? [])
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Failed to extract suggestions')
    } finally {
      setLoading(false)
    }
  }

  const toggle = (code: string) => {
    setSelected(prev => {
      const next = new Set(prev)
      if (next.has(code)) next.delete(code)
      else next.add(code)
      return next
    })
  }

  const handleAddSelected = async () => {
    if (selected.size === 0) return
    setError(null)
    setBusy(true)
    try {
      for (const code of selected) {
        const item = suggestions.find(s => s.code === code)
        const fullCode = `${parentCode}.${code}`
        await patchTag(kind, fullCode, {
          spec: {
            parent_code: parentCode,
            description: item?.description?.trim() || undefined,
          },
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
      <div className="modal add-subtag-document-modal" onClick={e => e.stopPropagation()}>
        <div className="modal-header">
          <h3>Extract sub-tags under {parentCode}</h3>
          <button className="btn compact" onClick={onClose}>x</button>
        </div>
        <div className="modal-body">
          <div className="modal-field-group">
            <label className="modal-label">Document text or file</label>
            <textarea
              className="modal-input"
              rows={4}
              placeholder="Paste document text here…"
              value={text}
              onChange={e => setText(e.target.value)}
            />
            <input
              type="file"
              accept=".txt,.pdf"
              onChange={e => setFile(e.target.files?.[0] ?? null)}
            />
          </div>
          <button
            className="btn primary"
            onClick={handleExtract}
            disabled={!hasInput || loading}
          >
            {loading ? 'Extracting…' : 'Extract'}
          </button>
          {suggestions.length > 0 && (
            <div className="modal-field-group" style={{ marginTop: 14 }}>
              <label className="modal-label">Suggested sub-tags (select to add)</label>
              <ul style={{ listStyle: 'none', padding: 0, margin: 0, maxHeight: 200, overflowY: 'auto' }}>
                {suggestions.map(({ code, description }) => (
                  <li key={code} style={{ marginBottom: 6 }}>
                    <label style={{ display: 'flex', alignItems: 'center', gap: 8, cursor: 'pointer' }}>
                      <input
                        type="checkbox"
                        checked={selected.has(code)}
                        onChange={() => toggle(code)}
                      />
                      <span>{code}</span>
                      {description && <span className="modal-hint">— {description}</span>}
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
