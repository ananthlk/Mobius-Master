import { useState } from 'react'
import { patchTag } from '../api'

const SEGMENT_REGEX = /^[a-z0-9_]+$/

export interface AddSubtagManualModalProps {
  kind: string
  parentCode: string
  onClose: () => void
  onSuccess: () => void
}

export function AddSubtagManualModal({
  kind,
  parentCode,
  onClose,
  onSuccess,
}: AddSubtagManualModalProps) {
  const [segment, setSegment] = useState('')
  const [description, setDescription] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  const handleSubmit = async () => {
    const seg = segment.trim().toLowerCase()
    if (!seg) {
      setError('Sub-tag code is required')
      return
    }
    if (!SEGMENT_REGEX.test(seg)) {
      setError('Use only lowercase letters, numbers, and underscores')
      return
    }
    setError(null)
    setBusy(true)
    try {
      const code = `${parentCode}.${seg}`
      await patchTag(kind, code, {
        spec: { parent_code: parentCode, description: description.trim() || undefined },
        active: true,
      })
      onSuccess()
      onClose()
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Failed to create sub-tag')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="modal-overlay" onClick={onClose} aria-hidden>
      <div className="modal" onClick={e => e.stopPropagation()}>
        <div className="modal-header">
          <h3>Add sub-tag under {parentCode}</h3>
          <button className="btn compact" onClick={onClose}>x</button>
        </div>
        <div className="modal-body">
          <div className="modal-field-group">
            <label className="modal-label">Sub-tag code (single segment)</label>
            <input
              className="modal-input"
              value={segment}
              onChange={e => setSegment(e.target.value.toLowerCase().replace(/[^a-z0-9_]/g, ''))}
              placeholder="e.g. transportation"
            />
            <span className="modal-hint">Lowercase letters, numbers, underscores. Full code will be {parentCode}.&lt;segment&gt;</span>
          </div>
          <div className="modal-field-group">
            <label className="modal-label">Description (optional)</label>
            <input
              className="modal-input"
              value={description}
              onChange={e => setDescription(e.target.value)}
              placeholder="Short description"
            />
          </div>
          {error && <p className="modal-hint" style={{ color: 'var(--error)' }}>{error}</p>}
        </div>
        <div className="modal-footer">
          <button className="btn" onClick={onClose}>Cancel</button>
          <button className="btn primary" onClick={handleSubmit} disabled={busy}>
            {busy ? 'Adding…' : 'Add sub-tag'}
          </button>
        </div>
      </div>
    </div>
  )
}
