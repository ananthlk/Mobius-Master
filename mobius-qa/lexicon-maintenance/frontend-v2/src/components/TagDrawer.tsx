import { useState, useEffect, useCallback } from 'react'
import type { TagKind } from '../types'
import { fetchTagDetail, patchTag } from '../api'

interface Props {
  kind: TagKind
  code: string
  onClose: () => void
  onSaved: () => void
}

interface TagDetailData {
  tag: {
    kind: string
    code: string
    parent_code: string | null
    active: boolean
    spec: Record<string, unknown>
  }
  usage: { hit_lines: number; hit_docs: number; max_score: number }
  top_documents: Array<{ document_id: string; hit_lines: number; max_score: number }>
  sample_lines: Array<{ document_id: string; page_number: number; score: number; text: string; snippet: string }>
}

export function TagDrawer({ kind, code, onClose, onSaved }: Props) {
  const [data, setData] = useState<TagDetailData | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  // Editable state
  const [description, setDescription] = useState('')
  const [strongPhrases, setStrongPhrases] = useState<string[]>([])
  const [newPhrase, setNewPhrase] = useState('')
  const [active, setActive] = useState(true)
  const [saving, setSaving] = useState(false)
  const [dirty, setDirty] = useState(false)

  const load = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const res = await fetchTagDetail(kind, code) as unknown as TagDetailData
      setData(res)
      const spec = (res.tag?.spec || {}) as Record<string, unknown>
      setDescription(String(spec.description || ''))
      setStrongPhrases((spec.strong_phrases as string[]) || (spec.phrases as string[]) || [])
      setActive(res.tag?.active !== false)
      setDirty(false)
    } catch (e) {
      setError(String(e))
    } finally {
      setLoading(false)
    }
  }, [kind, code])

  useEffect(() => { load() }, [load])

  const handleSave = async () => {
    setSaving(true)
    try {
      const spec = {
        ...(data?.tag?.spec || {}),
        description,
        strong_phrases: strongPhrases,
        phrases: strongPhrases, // Keep in sync
      }
      await patchTag(kind, code, { spec, active })
      setDirty(false)
      onSaved()
    } catch (e) {
      setError(String(e))
    } finally {
      setSaving(false)
    }
  }

  const addPhrase = () => {
    const p = newPhrase.trim()
    if (p && !strongPhrases.includes(p)) {
      setStrongPhrases([...strongPhrases, p])
      setNewPhrase('')
      setDirty(true)
    }
  }

  const removePhrase = (phrase: string) => {
    setStrongPhrases(strongPhrases.filter(p => p !== phrase))
    setDirty(true)
  }

  return (
    <aside className="tag-drawer">
      <div className="drawer-header">
        <div className="drawer-breadcrumb">
          <span className={`kind-badge kind-${kind}`}>{kind.toUpperCase()}</span>
          {data?.tag?.parent_code && (
            <><span className="breadcrumb-sep">›</span><span className="muted">{data.tag.parent_code}</span></>
          )}
          <span className="breadcrumb-sep">›</span>
          <strong>{code.replace(/_/g, ' ')}</strong>
        </div>
        <button className="close-btn" onClick={onClose}>✕</button>
      </div>

      {loading && <div className="drawer-body"><p className="muted">Loading…</p></div>}
      {error && <div className="drawer-body"><p className="error">{error}</p></div>}

      {data && !loading && (
        <div className="drawer-body">
          {/* Description */}
          <label className="field-label">Description</label>
          <textarea
            className="field-textarea"
            value={description}
            onChange={e => { setDescription(e.target.value); setDirty(true) }}
            rows={3}
          />

          {/* Strong phrases */}
          <label className="field-label">Strong phrases (aliases)</label>
          <div className="phrase-chips">
            {strongPhrases.map(p => (
              <span key={p} className="alias-chip editable">
                {p}
                <button className="chip-remove" onClick={() => removePhrase(p)}>×</button>
              </span>
            ))}
          </div>
          <div className="phrase-add-row">
            <input
              type="text"
              placeholder="Add phrase…"
              value={newPhrase}
              onChange={e => setNewPhrase(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && addPhrase()}
            />
            <button className="btn xs" onClick={addPhrase}>+</button>
          </div>

          {/* Active toggle */}
          <label className="field-label">
            <input
              type="checkbox"
              checked={active}
              onChange={e => { setActive(e.target.checked); setDirty(true) }}
            />
            {' '}Active
          </label>

          {/* Usage stats */}
          <div className="usage-stats">
            <div className="stat">
              <span className="stat-value">{data.usage.hit_lines}</span>
              <span className="stat-label">Lines</span>
            </div>
            <div className="stat">
              <span className="stat-value">{data.usage.hit_docs}</span>
              <span className="stat-label">Docs</span>
            </div>
            <div className="stat">
              <span className="stat-value">{data.usage.max_score.toFixed(1)}</span>
              <span className="stat-label">Max Score</span>
            </div>
          </div>

          {/* Sample lines */}
          {data.sample_lines.length > 0 && (
            <>
              <label className="field-label">Sample lines ({data.sample_lines.length})</label>
              <div className="sample-lines">
                {data.sample_lines.slice(0, 10).map((s, i) => (
                  <div key={i} className="sample-line">
                    <span className="sample-score">{s.score.toFixed(1)}</span>
                    <span className="sample-text">{s.snippet}</span>
                  </div>
                ))}
              </div>
            </>
          )}

          {/* Actions */}
          <div className="drawer-actions">
            <button className="btn primary" onClick={handleSave} disabled={saving || !dirty}>
              {saving ? 'Saving…' : dirty ? 'Save ●' : 'Save'}
            </button>
            <button className="btn" onClick={load} disabled={loading}>Revert</button>
          </div>
        </div>
      )}
    </aside>
  )
}
