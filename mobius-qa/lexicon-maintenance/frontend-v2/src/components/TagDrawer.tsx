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

/* ── Reusable chip-list editor ── */
function ChipListEditor({
  label,
  sublabel,
  items,
  onChange,
  placeholder,
  chipClass,
}: {
  label: string
  sublabel?: string
  items: string[]
  onChange: (items: string[]) => void
  placeholder?: string
  chipClass?: string
}) {
  const [draft, setDraft] = useState('')

  const add = () => {
    const v = draft.trim()
    if (v && !items.includes(v)) {
      onChange([...items, v])
      setDraft('')
    }
  }
  const remove = (item: string) => onChange(items.filter(i => i !== item))

  return (
    <div className="chip-editor-section">
      <label className="field-label">
        {label}
        {sublabel && <span className="field-sublabel"> {sublabel}</span>}
        <span className="field-count">{items.length}</span>
      </label>
      {items.length > 0 && (
        <div className="phrase-chips">
          {items.map(p => (
            <span key={p} className={`alias-chip editable ${chipClass || ''}`}>
              {p}
              <button className="chip-remove" onClick={() => remove(p)}>×</button>
            </span>
          ))}
        </div>
      )}
      <div className="phrase-add-row">
        <input
          type="text"
          placeholder={placeholder || 'Add…'}
          value={draft}
          onChange={e => setDraft(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && add()}
        />
        <button className="btn xs" onClick={add}>+</button>
      </div>
    </div>
  )
}

export function TagDrawer({ kind, code, onClose, onSaved }: Props) {
  const [data, setData] = useState<TagDetailData | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  // Editable state
  const [description, setDescription] = useState('')
  const [strongPhrases, setStrongPhrases] = useState<string[]>([])
  const [aliases, setAliases] = useState<string[]>([])
  const [weakKeywords, setWeakKeywords] = useState<string[]>([])
  const [refutedWords, setRefutedWords] = useState<string[]>([])
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
      setAliases((spec.aliases as string[]) || [])
      const wk = spec.weak_keywords as { any_of?: string[] } | undefined
      setWeakKeywords(wk?.any_of || [])
      setRefutedWords((spec.refuted_words as string[]) || [])
      setActive(res.tag?.active !== false)
      setDirty(false)
    } catch (e) {
      setError(String(e))
    } finally {
      setLoading(false)
    }
  }, [kind, code])

  useEffect(() => { load() }, [load])

  const markDirty = <T,>(setter: React.Dispatch<React.SetStateAction<T>>) => {
    return (val: T) => { setter(val); setDirty(true) }
  }

  const handleSave = async () => {
    setSaving(true)
    try {
      const spec: Record<string, unknown> = {
        ...(data?.tag?.spec || {}),
        description,
        strong_phrases: strongPhrases,
        phrases: strongPhrases, // Keep in sync
        aliases,
        refuted_words: refutedWords,
      }
      // Build weak_keywords only if there are entries
      if (weakKeywords.length > 0) {
        spec.weak_keywords = { any_of: weakKeywords, min_hits: 1 }
      } else {
        spec.weak_keywords = undefined
      }
      await patchTag(kind, code, { spec, active })
      setDirty(false)
      onSaved()
      // Reload to get fresh data
      load()
    } catch (e) {
      setError(String(e))
    } finally {
      setSaving(false)
    }
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
            rows={2}
          />

          {/* Strong phrases */}
          <ChipListEditor
            label="Strong phrases"
            sublabel="(high-confidence matches)"
            items={strongPhrases}
            onChange={markDirty(setStrongPhrases)}
            placeholder="Add strong phrase…"
            chipClass="chip-strong"
          />

          {/* Aliases */}
          <ChipListEditor
            label="Aliases"
            sublabel="(short forms, abbreviations)"
            items={aliases}
            onChange={markDirty(setAliases)}
            placeholder="Add alias…"
            chipClass="chip-alias"
          />

          {/* Weak keywords */}
          <ChipListEditor
            label="Weak keywords"
            sublabel="(lower confidence, need multiple hits)"
            items={weakKeywords}
            onChange={markDirty(setWeakKeywords)}
            placeholder="Add weak keyword…"
            chipClass="chip-weak"
          />

          {/* Refuted words */}
          <ChipListEditor
            label="Refuted words"
            sublabel="(suppress match when present)"
            items={refutedWords}
            onChange={markDirty(setRefutedWords)}
            placeholder="Add refuted word…"
            chipClass="chip-refuted"
          />

          {/* Active toggle */}
          <label className="field-label active-toggle">
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
              {saving ? 'Saving…' : dirty ? 'Save changes' : 'Save'}
            </button>
            <button className="btn" onClick={load} disabled={loading}>Revert</button>
          </div>
        </div>
      )}
    </aside>
  )
}
