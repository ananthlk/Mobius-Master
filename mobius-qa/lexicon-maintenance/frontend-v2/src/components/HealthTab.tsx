import { useState, useMemo, useCallback, useRef, useEffect } from 'react'
import type { TagEntry, TagKind } from '../types'
import { runHealthAnalysis, deleteTag, mergeTags, patchTag, moveTag, previewHealthFix, applyHealthFix, dismissHealthIssue, listDismissedIssues, undismissHealthIssue } from '../api'
import type { FixOperation, DismissedIssue } from '../api'

interface Props {
  tags: TagEntry[]
  onRefresh: () => void
}

interface HealthIssue {
  id: string
  severity: 'critical' | 'warning' | 'info'
  type: string
  message: string
  tags: string[]
  fix: string
  action?: ActionType
  actionData?: ActionData
  operations?: FixOperation[]
}

type ActionType = 'delete' | 'merge' | 'reparent' | 'deactivate' | 'reclassify' | 'add_alias' | 'rename'
interface ActionData {
  kind?: TagKind
  sourceCode?: string
  targetCode?: string
  parentCode?: string | null
  newKind?: TagKind
}

interface LlmReport {
  score: number
  summary: string
  top_suggestions: string[]
  issues: LlmIssue[]
  tag_count: number
  llm_model: string
}

interface LlmIssue {
  type: string
  severity: string
  tags: string[]
  message: string
  fix: string
  operations?: FixOperation[]
}

function inferAction(type: string): ActionType | undefined {
  const map: Record<string, ActionType> = {
    orphan: 'reparent',
    missing_parent: 'reparent',
    duplicate: 'merge',
    alias_conflict: 'merge',
    unused: 'delete',
    deep: 'reparent',
    naming: 'rename',
    misclassified: 'reclassify',
    structural: 'reparent',
    coverage: 'add_alias',
  }
  return map[type]
}

// ── Client-side checks ──
function detectLocalIssues(tags: TagEntry[]): HealthIssue[] {
  const issues: HealthIssue[] = []
  const codeSet = new Set(tags.map(t => `${t.kind}:${t.code}`))

  // If almost all tags have 0 hits, extraction hasn't run yet -- skip unused checks
  const tagsWithHits = tags.filter(t => (t.hit_lines || 0) > 0).length
  const extractionHasRun = tagsWithHits > tags.length * 0.1 // at least 10% have hits

  for (const t of tags) {
    if (t.code.includes('.') && !t.parent_code) {
      const parent = t.code.split('.').slice(0, -1).join('.')
      issues.push({
        id: `orphan:${t.kind}:${t.code}`,
        severity: 'critical',
        type: 'orphan',
        message: `${t.kind.toUpperCase()}.${t.code} has dot-notation but no parent_code set`,
        tags: [t.code],
        fix: `Set parent_code to "${parent}"`,
        action: 'reparent',
        actionData: { kind: t.kind, sourceCode: t.code, parentCode: parent },
      })
    }
    if (t.parent_code && !codeSet.has(`${t.kind}:${t.parent_code}`)) {
      issues.push({
        id: `missing-parent:${t.kind}:${t.code}`,
        severity: 'critical',
        type: 'missing_parent',
        message: `${t.kind.toUpperCase()}.${t.code} references parent "${t.parent_code}" which does not exist`,
        tags: [t.code, t.parent_code],
        fix: `Create parent tag "${t.parent_code}" or re-parent to an existing tag`,
        action: 'reparent',
        actionData: { kind: t.kind, sourceCode: t.code, parentCode: null },
      })
    }
    // Only flag unused LEAF tags (with dot) if extraction has run.
    // Domain containers (no dot) are not matchable -- never flag them as unused.
    const isDomain = !t.code.includes('.')
    if (!isDomain && extractionHasRun && (t.hit_lines || 0) === 0 && !tags.some(c => c.parent_code === t.code && c.kind === t.kind)) {
      issues.push({
        id: `unused:${t.kind}:${t.code}`,
        severity: 'info',
        type: 'unused',
        message: `${t.kind.toUpperCase()}.${t.code} — 0 hits, no children`,
        tags: [t.code],
        fix: `Delete or add aliases/phrases so it matches content`,
        action: 'delete',
        actionData: { kind: t.kind, sourceCode: t.code },
      })
    }
    if (t.code.split('.').length > 3) {
      issues.push({
        id: `deep:${t.kind}:${t.code}`,
        severity: 'warning',
        type: 'deep',
        message: `${t.kind.toUpperCase()}.${t.code} — ${t.code.split('.').length} levels deep`,
        tags: [t.code],
        fix: `Flatten to 3 levels or fewer`,
        action: 'reparent',
        actionData: { kind: t.kind, sourceCode: t.code },
      })
    }
  }

  // Duplicate alias detection
  const aliasToCodes = new Map<string, { kind: TagKind; code: string }[]>()
  for (const t of tags) {
    for (const p of (t.spec.strong_phrases || [])) {
      const norm = p.toLowerCase().trim()
      if (!norm) continue
      if (!aliasToCodes.has(norm)) aliasToCodes.set(norm, [])
      aliasToCodes.get(norm)!.push({ kind: t.kind, code: t.code })
    }
  }
  for (const [alias, tagRefs] of aliasToCodes) {
    if (tagRefs.length > 1) {
      issues.push({
        id: `dup-alias:${alias}`,
        severity: 'warning',
        type: 'alias_conflict',
        message: `"${alias}" mapped to: ${tagRefs.map(r => `${r.kind}.${r.code}`).join(', ')}`,
        tags: tagRefs.map(r => r.code),
        fix: `Remove alias from one tag, or merge tags`,
        action: 'merge',
        actionData: { kind: tagRefs[0].kind, sourceCode: tagRefs[1].code, targetCode: tagRefs[0].code },
      })
    }
  }

  return issues
}

const SEV_ORDER: Record<string, number> = { critical: 0, warning: 1, info: 2 }
const SEV_ICON: Record<string, string> = { critical: '●', warning: '▲', info: 'ⓘ' }
const ACTION_LABELS: Record<ActionType, string> = {
  delete: 'Delete Tag',
  merge: 'Merge Into…',
  reparent: 'Re-parent…',
  deactivate: 'Deactivate',
  reclassify: 'Reclassify (P/D/J)',
  add_alias: 'Add Alias…',
  rename: 'Rename…',
}

export function HealthTab({ tags, onRefresh }: Props) {
  const extractionHasRun = useMemo(() => {
    const withHits = tags.filter(t => (t.hit_lines || 0) > 0).length
    return withHits > tags.length * 0.1
  }, [tags])

  const localIssues = useMemo(() =>
    detectLocalIssues(tags).sort((a, b) => (SEV_ORDER[a.severity] ?? 9) - (SEV_ORDER[b.severity] ?? 9)),
    [tags]
  )

  const [llmReport, setLlmReport] = useState<LlmReport | null>(null)
  const [analyzing, setAnalyzing] = useState(false)
  const [error, setError] = useState('')
  const [successMsg, setSuccessMsg] = useState('')
  const [busy, setBusy] = useState<string | null>(null)
  const [openMenuId, setOpenMenuId] = useState<string | null>(null)
  const [filterSev, setFilterSev] = useState<string>('all')
  const [selectedModel, setSelectedModel] = useState('gemini-2.5-pro')
  const menuRef = useRef<HTMLDivElement>(null)

  // ── Modal state ──
  const [modalOpen, setModalOpen] = useState(false)
  const [modalAction, setModalAction] = useState<ActionType>('merge')
  const [modalIssue, setModalIssue] = useState<HealthIssue | null>(null)
  const [modalTarget, setModalTarget] = useState('')
  const [modalParent, setModalParent] = useState('')
  const [modalNewKind, setModalNewKind] = useState<TagKind>('d')

  // ── Inline operations state (per-issue) ──
  const [expandedOps, setExpandedOps] = useState<Set<string>>(new Set())
  const [inlineApplying, setInlineApplying] = useState<string | null>(null)
  const [inlineResults, setInlineResults] = useState<Record<string, Array<{ op: string; code?: string; status: string; detail?: string }>>>({})

  // ── Dismissed issues state ──
  const [dismissedIssues, setDismissedIssues] = useState<DismissedIssue[]>([])
  const [showDismissed, setShowDismissed] = useState(false)
  const [dismissingId, setDismissingId] = useState<string | null>(null)

  // Load dismissed issues on mount
  useEffect(() => {
    listDismissedIssues().then(res => setDismissedIssues(res.dismissed || [])).catch(() => {})
  }, [])

  // ── Fix modal state (for Revise flow) ──
  const [fixModalOpen, setFixModalOpen] = useState(false)
  const [fixIssue, setFixIssue] = useState<HealthIssue | null>(null)
  const [fixInstructions, setFixInstructions] = useState('')
  const [fixPreviewLoading, setFixPreviewLoading] = useState(false)
  const [fixOperations, setFixOperations] = useState<FixOperation[] | null>(null)
  const [fixExplanation, setFixExplanation] = useState('')
  const [fixApplying, setFixApplying] = useState(false)
  const [fixResults, setFixResults] = useState<Array<{ op: string; code?: string; status: string; detail?: string }> | null>(null)

  // Close dropdown when clicking outside
  useEffect(() => {
    if (!openMenuId) return
    const handler = (e: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setOpenMenuId(null)
      }
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [openMenuId])

  const runAnalysis = useCallback(async () => {
    setAnalyzing(true)
    setError('')
    setSuccessMsg('')
    try {
      const res = await runHealthAnalysis(selectedModel)
      setLlmReport({
        score: Number(res.score || 0),
        summary: String(res.summary || ''),
        top_suggestions: (res.top_suggestions as string[]) || [],
        issues: (res.issues as LlmIssue[]) || [],
        tag_count: Number(res.tag_count || 0),
        llm_model: String(res.llm_model || ''),
      })
    } catch (e) {
      setError(String(e))
    } finally {
      setAnalyzing(false)
    }
  }, [selectedModel])

  // ── Direct actions (no modal) ──
  const handleDelete = useCallback(async (issue: HealthIssue) => {
    const code = issue.actionData?.sourceCode || issue.tags[0]
    const kind = issue.actionData?.kind || 'p'
    if (!confirm(`Delete tag ${kind.toUpperCase()}.${code}? Children will be promoted to root.`)) return
    setBusy(issue.id)
    setOpenMenuId(null)
    try {
      await deleteTag(kind, code)
      setSuccessMsg(`Deleted ${kind.toUpperCase()}.${code}`)
      onRefresh()
    } catch (e) { setError(String(e)) }
    finally { setBusy(null) }
  }, [onRefresh])

  const handleDeactivate = useCallback(async (issue: HealthIssue) => {
    const code = issue.actionData?.sourceCode || issue.tags[0]
    const kind = issue.actionData?.kind || 'p'
    setBusy(issue.id)
    setOpenMenuId(null)
    try {
      await patchTag(kind, code, { active: false, spec: {} })
      setSuccessMsg(`Deactivated ${kind.toUpperCase()}.${code}`)
      onRefresh()
    } catch (e) { setError(String(e)) }
    finally { setBusy(null) }
  }, [onRefresh])

  // ── Open modal for complex actions ──
  const openActionModal = useCallback((action: ActionType, issue: HealthIssue) => {
    setModalAction(action)
    setModalIssue(issue)
    setModalTarget(issue.actionData?.targetCode || '')
    setModalParent(String(issue.actionData?.parentCode || ''))
    setModalNewKind(issue.actionData?.newKind || issue.actionData?.kind || 'd')
    setOpenMenuId(null)
    setModalOpen(true)
  }, [])

  const executeModal = useCallback(async () => {
    if (!modalIssue) return
    const kind = modalIssue.actionData?.kind || 'p'
    const code = modalIssue.actionData?.sourceCode || modalIssue.tags[0]
    setBusy(modalIssue.id)
    setError('')
    try {
      if (modalAction === 'merge') {
        if (!modalTarget.trim()) { setError('Target tag code is required'); setBusy(null); return }
        await mergeTags({ kind, source_code: code, target_code: modalTarget.trim() })
        setSuccessMsg(`Merged ${kind.toUpperCase()}.${code} into ${modalTarget.trim()}`)
      } else if (modalAction === 'reparent') {
        const newParent = modalParent.trim() || null
        await moveTag({ kind, from_code: code, to_code: code, parent_code: newParent })
        setSuccessMsg(`Re-parented ${kind.toUpperCase()}.${code} → ${newParent || '(root)'}`)
      } else if (modalAction === 'reclassify') {
        const tag = tags.find(t => t.kind === kind && t.code === code)
        const spec = tag?.spec || {}
        await patchTag(modalNewKind, code, { spec, active: true })
        await deleteTag(kind, code)
        setSuccessMsg(`Reclassified ${code}: ${kind.toUpperCase()} → ${modalNewKind.toUpperCase()}`)
      } else if (modalAction === 'rename') {
        if (!modalTarget.trim()) { setError('New code is required'); setBusy(null); return }
        await moveTag({ kind, from_code: code, to_code: modalTarget.trim(), parent_code: modalParent.trim() || undefined })
        setSuccessMsg(`Renamed ${kind.toUpperCase()}.${code} → ${modalTarget.trim()}`)
      } else if (modalAction === 'add_alias') {
        if (!modalTarget.trim()) { setError('Phrase is required'); setBusy(null); return }
        const tag = tags.find(t => t.kind === kind && t.code === code)
        const curPhrases = tag?.spec?.strong_phrases || []
        await patchTag(kind, code, { spec: { ...tag?.spec, strong_phrases: [...curPhrases, modalTarget.trim()] }, active: true })
        setSuccessMsg(`Added alias "${modalTarget.trim()}" to ${kind.toUpperCase()}.${code}`)
      }
      onRefresh()
      setModalOpen(false)
    } catch (e) {
      setError(String(e))
    } finally {
      setBusy(null)
    }
  }, [modalAction, modalIssue, modalTarget, modalParent, modalNewKind, tags, onRefresh])

  const scoreColor = (s: number) => s >= 80 ? 'var(--success)' : s >= 50 ? 'var(--warning)' : 'var(--error)'
  const scoreLabel = (s: number) => s >= 80 ? 'Healthy' : s >= 50 ? 'Needs Work' : 'Attention Required'

  // Combine local + LLM issues
  const allIssues = useMemo(() => {
    const combined: HealthIssue[] = [...localIssues]
    if (llmReport) {
      for (let i = 0; i < llmReport.issues.length; i++) {
        const li = llmReport.issues[i]
        const sev = (li.severity || 'info').toLowerCase() as 'critical' | 'warning' | 'info'
        const itype = (li.type || 'structural').replace(/\s+/g, '_').toLowerCase()
        let kind: TagKind = 'p'
        const firstTag = (li.tags || [])[0] || ''
        if (firstTag.startsWith('j.') || firstTag.startsWith('j_')) kind = 'j'
        else if (firstTag.startsWith('d.') || firstTag.startsWith('d_')) kind = 'd'
        else {
          const match = tags.find(t => li.tags?.includes(t.code))
          if (match) kind = match.kind
        }

        combined.push({
          id: `llm-${i}`,
          severity: sev,
          type: itype,
          message: li.message,
          tags: li.tags || [],
          fix: li.fix || '',
          action: inferAction(itype),
          actionData: {
            kind,
            sourceCode: (li.tags || [])[0] || '',
            targetCode: (li.tags || [])[1] || '',
          },
          operations: (li.operations || []) as FixOperation[],
        })
      }
    }
    return combined.sort((a, b) => (SEV_ORDER[a.severity] ?? 9) - (SEV_ORDER[b.severity] ?? 9))
  }, [localIssues, llmReport, tags])

  // Build fingerprints of dismissed issues for client-side filtering
  const dismissedFingerprints = useMemo(() => {
    const fps = new Set<string>()
    for (const d of dismissedIssues) {
      fps.add(d.issue_fingerprint)
    }
    return fps
  }, [dismissedIssues])

  const issueFingerprint = (type: string, issueTags: string[]) =>
    `${type}::${[...issueTags].map(t => t.trim().toLowerCase()).sort().join(',')}`

  const activeIssues = allIssues.filter(i => !dismissedFingerprints.has(issueFingerprint(i.type, i.tags)))
  const filtered = filterSev === 'all' ? activeIssues : activeIssues.filter(i => i.severity === filterSev)

  const critCount = activeIssues.filter(i => i.severity === 'critical').length
  const warnCount = activeIssues.filter(i => i.severity === 'warning').length
  const infoCount = activeIssues.filter(i => i.severity === 'info').length

  const menuActions: { key: ActionType; label: string; needsModal: boolean }[] = [
    { key: 'delete', label: 'Delete Tag', needsModal: false },
    { key: 'deactivate', label: 'Deactivate', needsModal: false },
    { key: 'merge', label: 'Merge Into…', needsModal: true },
    { key: 'reparent', label: 'Re-parent…', needsModal: true },
    { key: 'reclassify', label: 'Reclassify (P/D/J)', needsModal: true },
    { key: 'rename', label: 'Rename…', needsModal: true },
    { key: 'add_alias', label: 'Add Alias…', needsModal: true },
  ]

  const handleMenuClick = (action: ActionType, issue: HealthIssue) => {
    if (action === 'delete') handleDelete(issue)
    else if (action === 'deactivate') handleDeactivate(issue)
    else openActionModal(action, issue)
  }

  // ── Fix modal handlers ──
  const openFixModal = useCallback((issue: HealthIssue) => {
    setFixIssue(issue)
    setFixInstructions('')
    setFixOperations(null)
    setFixExplanation('')
    setFixResults(null)
    setFixModalOpen(true)
    setOpenMenuId(null)
  }, [])

  const handleFixPreview = useCallback(async () => {
    if (!fixIssue) return
    setFixPreviewLoading(true)
    setError('')
    setFixOperations(null)
    setFixExplanation('')
    setFixResults(null)
    try {
      const res = await previewHealthFix(
        { type: fixIssue.type, severity: fixIssue.severity, tags: fixIssue.tags, message: fixIssue.message, fix: fixIssue.fix },
        fixInstructions || undefined,
        selectedModel,
      )
      setFixOperations(res.operations)
      setFixExplanation(res.explanation)
    } catch (e) {
      setError(String(e))
    } finally {
      setFixPreviewLoading(false)
    }
  }, [fixIssue, fixInstructions, selectedModel])

  const handleFixApply = useCallback(async () => {
    if (!fixOperations || fixOperations.length === 0) return
    setFixApplying(true)
    setError('')
    try {
      const res = await applyHealthFix(fixOperations)
      setFixResults(res.results)
      if (res.failed_count === 0) {
        setSuccessMsg(`Fix applied successfully (${res.results.length} operation${res.results.length > 1 ? 's' : ''})`)
        onRefresh()
      } else {
        setError(`${res.failed_count} operation(s) failed. Check results below.`)
      }
    } catch (e) {
      setError(String(e))
    } finally {
      setFixApplying(false)
    }
  }, [fixOperations, onRefresh])

  const closeFixModal = useCallback(() => {
    setFixModalOpen(false)
    setFixIssue(null)
    setFixOperations(null)
    setFixExplanation('')
    setFixResults(null)
    setFixInstructions('')
  }, [])

  const OP_LABELS: Record<string, string> = {
    create_tag: 'CREATE',
    update_tag: 'UPDATE',
    delete_tag: 'DELETE',
    merge_tags: 'MERGE',
    move_tag: 'MOVE',
  }

  const handleDismiss = useCallback(async (issue: HealthIssue) => {
    setDismissingId(issue.id)
    setError('')
    try {
      await dismissHealthIssue({
        issue_type: issue.type,
        tags: issue.tags,
        message: issue.message,
        reason: 'User overruled',
      })
      // Reload dismissed list
      const res = await listDismissedIssues()
      setDismissedIssues(res.dismissed || [])
      setSuccessMsg(`Dismissed: ${issue.type} (${issue.tags.join(', ')})`)
    } catch (e) {
      setError(String(e))
    } finally {
      setDismissingId(null)
    }
  }, [])

  const handleUndismiss = useCallback(async (fingerprint: string) => {
    setError('')
    try {
      await undismissHealthIssue(fingerprint)
      const res = await listDismissedIssues()
      setDismissedIssues(res.dismissed || [])
      setSuccessMsg('Issue re-enabled — will appear in next analysis')
    } catch (e) {
      setError(String(e))
    }
  }, [])

  const toggleOps = useCallback((issueId: string) => {
    setExpandedOps(prev => {
      const next = new Set(prev)
      if (next.has(issueId)) next.delete(issueId)
      else next.add(issueId)
      return next
    })
  }, [])

  const handleInlineApply = useCallback(async (issue: HealthIssue) => {
    if (!issue.operations || issue.operations.length === 0) return
    setInlineApplying(issue.id)
    setError('')
    try {
      const res = await applyHealthFix(issue.operations)
      setInlineResults(prev => ({ ...prev, [issue.id]: res.results }))
      if (res.failed_count === 0) {
        setSuccessMsg(`Fix applied: ${res.results.length} operation${res.results.length > 1 ? 's' : ''} succeeded`)
        onRefresh()
      } else {
        setError(`${res.failed_count} operation(s) failed`)
      }
    } catch (e) {
      setError(String(e))
    } finally {
      setInlineApplying(null)
    }
  }, [onRefresh])

  return (
    <div className="health-tab">
      {/* Score card */}
      <div className="health-top">
        <div className="health-score-card">
          {llmReport ? (
            <>
              <div className="score-circle" style={{ borderColor: scoreColor(llmReport.score) }}>
                <span className="score-num" style={{ color: scoreColor(llmReport.score) }}>{llmReport.score}</span>
                <span className="score-max">/100</span>
              </div>
              <div className="score-details">
                <span className="score-verdict" style={{ color: scoreColor(llmReport.score) }}>{scoreLabel(llmReport.score)}</span>
                <p className="score-summary">{llmReport.summary}</p>
                {llmReport.llm_model && <span className="model-badge">{llmReport.llm_model}</span>}
              </div>
            </>
          ) : (
            <div className="score-details">
              <span className="score-verdict muted">Not analyzed yet</span>
              <p className="score-summary muted">Run the LLM analysis to get a health score, find duplicates, naming issues, and recommendations.</p>
            </div>
          )}
        </div>
        <div className="health-actions" style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
          <select
            className="model-select"
            value={selectedModel}
            onChange={e => setSelectedModel(e.target.value)}
            disabled={analyzing}
          >
            <option value="gemini-2.5-pro">Gemini 2.5 Pro</option>
            <option value="gemini-3-pro-preview">Gemini 3 Pro</option>
            <option value="gemini-2.0-flash">Gemini 2.0 Flash</option>
          </select>
          <button className="btn primary" onClick={runAnalysis} disabled={analyzing}>
            {analyzing ? 'Analyzing…' : llmReport ? 'Re-analyze' : 'Run LLM Health Check'}
          </button>
        </div>
      </div>

      {error && <div className="health-msg health-msg-error">{error}<button className="health-msg-close" onClick={() => setError('')}>x</button></div>}
      {successMsg && <div className="health-msg health-msg-success">{successMsg}<button className="health-msg-close" onClick={() => setSuccessMsg('')}>x</button></div>}

      {/* Extraction not-run notice */}
      {!extractionHasRun && (
        <div className="health-msg health-msg-info" style={{ marginBottom: 8 }}>
          Hit counts are empty — Publish to RAG and re-run extraction to populate. Unused-tag checks are suppressed until then.
        </div>
      )}

      {/* Filter bar */}
      <div className="stats-bar">
        <span className="stat-chip">{tags.length} tags</span>
        <span className="sep">|</span>
        <button className={`filter-chip ${filterSev === 'all' ? 'active' : ''}`} onClick={() => setFilterSev('all')}>All ({allIssues.length})</button>
        <button className={`filter-chip ${filterSev === 'critical' ? 'active' : ''}`} onClick={() => setFilterSev('critical')}>Critical ({critCount})</button>
        <button className={`filter-chip ${filterSev === 'warning' ? 'active' : ''}`} onClick={() => setFilterSev('warning')}>Warning ({warnCount})</button>
        <button className={`filter-chip ${filterSev === 'info' ? 'active' : ''}`} onClick={() => setFilterSev('info')}>Info ({infoCount})</button>
      </div>

      {/* LLM suggestions */}
      {llmReport && llmReport.top_suggestions.length > 0 && (
        <div className="health-suggestions">
          <h4>Top Recommendations</h4>
          <ol className="suggestion-list">
            {llmReport.top_suggestions.map((s, i) => (
              <li key={i}>{s}</li>
            ))}
          </ol>
        </div>
      )}

      {/* Issues list — card-based, not table, to avoid overflow clipping */}
      <div className="health-section">
        <h4>Issues ({filtered.length})</h4>
        <div className="health-issues-list">
          {filtered.map(issue => {
            const hasOps = issue.operations && issue.operations.length > 0
            const isExpanded = expandedOps.has(issue.id)
            const results = inlineResults[issue.id]
            const applying = inlineApplying === issue.id
            return (
            <div key={issue.id} className={`health-issue-card sev-${issue.severity}${results ? ' issue-resolved' : ''}`}>
              <div className="issue-left">
                <span className={`sev-dot severity-${issue.severity}`}>{SEV_ICON[issue.severity]}</span>
                <div className="issue-content">
                  <div className="issue-type">{issue.type.replace(/_/g, ' ')}</div>
                  <div className="issue-msg">{issue.message}</div>
                  <div className="issue-tags">
                    {issue.tags.slice(0, 4).map(t => <span key={t} className="alias-chip">{t}</span>)}
                    {issue.tags.length > 4 && <span className="muted">+{issue.tags.length - 4}</span>}
                  </div>
                  {issue.fix && <div className="issue-fix">{issue.fix}</div>}

                  {/* Inline operations preview */}
                  {hasOps && !results && (
                    <div className="inline-ops-section">
                      <button className="inline-ops-toggle" onClick={() => toggleOps(issue.id)}>
                        {isExpanded ? '▾' : '▸'} {issue.operations!.length} operation{issue.operations!.length > 1 ? 's' : ''} planned
                      </button>
                      {isExpanded && (
                        <div className="inline-ops-list">
                          {issue.operations!.map((op, i) => {
                            const opLabel = OP_LABELS[op.op] || op.op
                            const tagCode = op.code || op.source_code || op.from_code || ''
                            const kind = op.kind || ''
                            const targetInfo = op.target_code ? ` -> ${kind}.${op.target_code}` : op.to_code ? ` -> ${kind}.${op.to_code}` : ''
                            const specInfo = op.spec ? Object.entries(op.spec)
                              .filter(([, v]) => v !== undefined && v !== null)
                              .map(([k, v]) => {
                                if (Array.isArray(v)) return `${k}: [${(v as string[]).slice(0, 3).join(', ')}${(v as string[]).length > 3 ? '...' : ''}]`
                                if (typeof v === 'string' && v.length > 50) return `${k}: "${v.slice(0, 50)}..."`
                                return `${k}: ${JSON.stringify(v)}`
                              })
                              .slice(0, 4)
                              : []
                            return (
                              <div key={i} className="fix-op-card">
                                <span className={`fix-op-badge op-${op.op}`}>{opLabel}</span>
                                <div className="fix-op-detail">
                                  <span className="fix-op-code">{kind}.{tagCode}{targetInfo}</span>
                                  {op.parent_code && <span className="fix-op-meta">parent: {op.parent_code}</span>}
                                  {specInfo.length > 0 && (
                                    <div className="fix-op-spec">
                                      {specInfo.map((s, j) => <div key={j} className="fix-op-spec-line">{s}</div>)}
                                    </div>
                                  )}
                                </div>
                              </div>
                            )
                          })}
                        </div>
                      )}
                    </div>
                  )}

                  {/* Inline results after apply */}
                  {results && (
                    <div className="inline-results">
                      {results.map((r, i) => (
                        <span key={i} className={`inline-result-chip ${r.status === 'ok' ? 'result-ok' : 'result-fail'}`}>
                          {r.status === 'ok' ? '✓' : '✗'} {r.op}{r.code ? `: ${r.code}` : ''}
                        </span>
                      ))}
                    </div>
                  )}
                </div>
              </div>
              <div className="issue-actions" ref={openMenuId === issue.id ? menuRef : undefined}>
                {(busy === issue.id || applying) ? (
                  <span className="muted" style={{ fontSize: 12 }}>Working…</span>
                ) : results ? (
                  <span className="muted" style={{ fontSize: 12, color: 'var(--success)' }}>Applied</span>
                ) : (
                  <>
                    {/* Apply button if operations are available */}
                    {hasOps && (
                      <button
                        className="btn compact fix-btn"
                        onClick={() => handleInlineApply(issue)}
                        title={`Apply ${issue.operations!.length} operation(s)`}
                      >
                        Apply
                      </button>
                    )}
                    {/* Revise button — opens modal to refine with user input */}
                    <button
                      className="btn compact"
                      onClick={() => openFixModal(issue)}
                      title={hasOps ? 'Revise with additional instructions' : 'Ask LLM to generate a fix'}
                    >
                      {hasOps ? 'Revise' : 'Fix'}
                    </button>
                    {/* More manual actions */}
                    <button
                      className="btn compact"
                      onClick={() => setOpenMenuId(openMenuId === issue.id ? null : issue.id)}
                    >
                      More ▾
                    </button>
                    {openMenuId === issue.id && (
                      <div className="action-dropdown">
                        {menuActions.map(a => (
                          <button
                            key={a.key}
                            className={`dropdown-item ${a.key === issue.action ? 'primary-item' : ''}`}
                            onClick={(e) => {
                              e.stopPropagation()
                              handleMenuClick(a.key, issue)
                            }}
                          >
                            {a.label}{a.key === issue.action ? ' (recommended)' : ''}
                          </button>
                        ))}
                        <hr className="dropdown-divider" />
                        <button
                          className="dropdown-item dismiss-item"
                          onClick={(e) => {
                            e.stopPropagation()
                            setOpenMenuId(null)
                            handleDismiss(issue)
                          }}
                          disabled={dismissingId === issue.id}
                        >
                          {dismissingId === issue.id ? 'Dismissing...' : 'Dismiss (overrule)'}
                        </button>
                      </div>
                    )}
                  </>
                )}
              </div>
            </div>
            )
          })}
          {filtered.length === 0 && (
            <div className="center-text muted" style={{ padding: 32 }}>
              {allIssues.length === 0 && !llmReport ? 'No issues detected. Run LLM analysis for a deeper review.' : 'No issues match this filter.'}
            </div>
          )}
        </div>
      </div>

      {/* Dismissed issues section */}
      {dismissedIssues.length > 0 && (
        <div className="health-section dismissed-section">
          <button className="dismissed-toggle" onClick={() => setShowDismissed(!showDismissed)}>
            {showDismissed ? '▾' : '▸'} Dismissed Issues ({dismissedIssues.length})
          </button>
          {showDismissed && (
            <div className="dismissed-list">
              {dismissedIssues.map(d => (
                <div key={d.id} className="dismissed-card">
                  <div className="dismissed-info">
                    <span className="dismissed-type">{d.issue_type.replace(/_/g, ' ')}</span>
                    <span className="dismissed-msg">{d.issue_message || d.issue_tags.join(', ')}</span>
                    <span className="dismissed-meta">
                      {d.reason} — {d.dismissed_by}, {new Date(d.created_at).toLocaleDateString()}
                    </span>
                  </div>
                  <button
                    className="btn compact"
                    onClick={() => handleUndismiss(d.issue_fingerprint)}
                    title="Re-enable this issue in future analyses"
                  >
                    Restore
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Action modal (manual) */}
      {modalOpen && modalIssue && (
        <div className="modal-overlay" onClick={() => setModalOpen(false)}>
          <div className="modal" onClick={e => e.stopPropagation()}>
            <div className="modal-header">
              <h3>{ACTION_LABELS[modalAction]}</h3>
              <button className="btn compact" onClick={() => setModalOpen(false)}>x</button>
            </div>
            <div className="modal-body">
              <p style={{ fontSize: 12, color: 'var(--text-secondary)', margin: '0 0 12px' }}>
                Tag: <strong>{modalIssue.actionData?.kind?.toUpperCase()}.{modalIssue.actionData?.sourceCode || modalIssue.tags[0]}</strong>
              </p>

              {modalAction === 'merge' && (
                <div className="modal-field-group">
                  <label className="modal-label">Merge into (target tag code):</label>
                  <input
                    className="modal-input"
                    value={modalTarget}
                    onChange={e => setModalTarget(e.target.value)}
                    placeholder="e.g. claims.submission"
                    list="health-tag-list"
                    autoFocus
                  />
                  <span className="modal-hint">All aliases from source will be copied to target, then source is deleted.</span>
                </div>
              )}

              {modalAction === 'reparent' && (
                <div className="modal-field-group">
                  <label className="modal-label">New parent code (blank = root):</label>
                  <input
                    className="modal-input"
                    value={modalParent}
                    onChange={e => setModalParent(e.target.value)}
                    placeholder="e.g. claims"
                    list="health-tag-list"
                    autoFocus
                  />
                </div>
              )}

              {modalAction === 'reclassify' && (
                <div className="modal-field-group">
                  <label className="modal-label">New tag type:</label>
                  <div style={{ display: 'flex', gap: 16, marginTop: 6 }}>
                    {(['p', 'd', 'j'] as TagKind[]).map(k => (
                      <label key={k} style={{ display: 'flex', gap: 4, alignItems: 'center', cursor: 'pointer', fontSize: 13 }}>
                        <input type="radio" name="newKind" checked={modalNewKind === k} onChange={() => setModalNewKind(k)} />
                        {k === 'p' ? 'Procedural' : k === 'd' ? 'Domain' : 'Jurisdiction'}
                      </label>
                    ))}
                  </div>
                </div>
              )}

              {modalAction === 'rename' && (
                <>
                  <div className="modal-field-group">
                    <label className="modal-label">New tag code:</label>
                    <input
                      className="modal-input"
                      value={modalTarget}
                      onChange={e => setModalTarget(e.target.value)}
                      placeholder="e.g. claims.prior_auth"
                      autoFocus
                    />
                  </div>
                  <div className="modal-field-group">
                    <label className="modal-label">Parent code (optional):</label>
                    <input
                      className="modal-input"
                      value={modalParent}
                      onChange={e => setModalParent(e.target.value)}
                      placeholder="e.g. claims"
                      list="health-tag-list"
                    />
                  </div>
                </>
              )}

              {modalAction === 'add_alias' && (
                <div className="modal-field-group">
                  <label className="modal-label">Alias phrase to add:</label>
                  <input
                    className="modal-input"
                    value={modalTarget}
                    onChange={e => setModalTarget(e.target.value)}
                    placeholder="e.g. prior authorization"
                    autoFocus
                  />
                </div>
              )}

              {/* Autocomplete datalist */}
              <datalist id="health-tag-list">
                {tags.map(t => <option key={`${t.kind}:${t.code}`} value={t.code} />)}
              </datalist>
            </div>
            <div className="modal-footer">
              <button className="btn" onClick={() => setModalOpen(false)}>Cancel</button>
              <button className="btn primary" onClick={executeModal} disabled={busy != null}>
                {busy ? 'Working…' : ACTION_LABELS[modalAction]}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Fix modal (LLM-powered) */}
      {fixModalOpen && fixIssue && (
        <div className="modal-overlay" onClick={closeFixModal}>
          <div className="modal fix-modal" onClick={e => e.stopPropagation()}>
            <div className="modal-header">
              <h3>Fix Issue</h3>
              <button className="btn compact" onClick={closeFixModal}>x</button>
            </div>
            <div className="modal-body">
              {/* Issue summary */}
              <div className="fix-issue-summary">
                <div className="fix-issue-header">
                  <span className={`sev-dot severity-${fixIssue.severity}`}>{SEV_ICON[fixIssue.severity]}</span>
                  <span className="fix-issue-type">{fixIssue.type.replace(/_/g, ' ')}</span>
                </div>
                <p className="fix-issue-msg">{fixIssue.message}</p>
                <div className="fix-issue-tags">
                  {fixIssue.tags.map(t => <span key={t} className="alias-chip">{t}</span>)}
                </div>
                {fixIssue.fix && (
                  <div className="fix-suggestion-box">
                    <strong>Suggested fix:</strong> {fixIssue.fix}
                  </div>
                )}
              </div>

              {/* Instructions textarea */}
              {!fixResults && (
                <div className="modal-field-group">
                  <label className="modal-label">Additional instructions (optional):</label>
                  <textarea
                    className="modal-input fix-instructions"
                    value={fixInstructions}
                    onChange={e => setFixInstructions(e.target.value)}
                    placeholder="Accept the suggestion as-is, or provide additional guidance..."
                    rows={3}
                    disabled={fixPreviewLoading || fixApplying}
                  />
                </div>
              )}

              {/* Preview button */}
              {!fixOperations && !fixResults && (
                <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: 8 }}>
                  <button
                    className="btn primary"
                    onClick={handleFixPreview}
                    disabled={fixPreviewLoading}
                  >
                    {fixPreviewLoading ? 'Generating fix...' : 'Preview Fix'}
                  </button>
                </div>
              )}

              {/* Loading indicator */}
              {fixPreviewLoading && (
                <div className="fix-loading">
                  <div className="fix-spinner" />
                  <span>LLM is generating operations...</span>
                </div>
              )}

              {/* Operations preview */}
              {fixOperations && !fixResults && (
                <div className="fix-preview">
                  <h4>Planned Operations</h4>
                  {fixExplanation && <p className="fix-explanation">{fixExplanation}</p>}
                  <div className="fix-ops-list">
                    {fixOperations.map((op, i) => {
                      const opLabel = OP_LABELS[op.op] || op.op
                      const tagCode = op.code || op.source_code || op.from_code || ''
                      const kind = op.kind || ''
                      const targetInfo = op.target_code ? ` -> ${kind}.${op.target_code}` : op.to_code ? ` -> ${kind}.${op.to_code}` : ''
                      const specInfo = op.spec ? Object.entries(op.spec)
                        .filter(([, v]) => v !== undefined && v !== null)
                        .map(([k, v]) => {
                          if (Array.isArray(v)) return `${k}: [${(v as string[]).slice(0, 3).join(', ')}${(v as string[]).length > 3 ? '...' : ''}]`
                          if (typeof v === 'string' && v.length > 50) return `${k}: "${v.slice(0, 50)}..."`
                          return `${k}: ${JSON.stringify(v)}`
                        })
                        .slice(0, 4)
                        : []
                      return (
                        <div key={i} className="fix-op-card">
                          <span className={`fix-op-badge op-${op.op}`}>{opLabel}</span>
                          <div className="fix-op-detail">
                            <span className="fix-op-code">{kind}.{tagCode}{targetInfo}</span>
                            {op.parent_code && <span className="fix-op-meta">parent: {op.parent_code}</span>}
                            {specInfo.length > 0 && (
                              <div className="fix-op-spec">
                                {specInfo.map((s, j) => <div key={j} className="fix-op-spec-line">{s}</div>)}
                              </div>
                            )}
                          </div>
                        </div>
                      )
                    })}
                  </div>
                </div>
              )}

              {/* Apply results */}
              {fixResults && (
                <div className="fix-results">
                  <h4>Results</h4>
                  <div className="fix-ops-list">
                    {fixResults.map((r, i) => (
                      <div key={i} className={`fix-op-card ${r.status === 'ok' ? 'op-success' : 'op-error'}`}>
                        <span className={`fix-op-badge ${r.status === 'ok' ? 'op-ok' : 'op-fail'}`}>
                          {r.status === 'ok' ? 'OK' : 'FAIL'}
                        </span>
                        <div className="fix-op-detail">
                          <span className="fix-op-code">{r.op}: {r.code || ''}</span>
                          {r.detail && <span className="fix-op-meta error-text">{r.detail}</span>}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>

            <div className="modal-footer">
              <button className="btn" onClick={closeFixModal}>
                {fixResults ? 'Close' : 'Cancel'}
              </button>
              {fixOperations && !fixResults && (
                <button
                  className="btn primary"
                  onClick={handleFixApply}
                  disabled={fixApplying}
                >
                  {fixApplying ? 'Applying...' : `Apply ${fixOperations.length} Operation${fixOperations.length > 1 ? 's' : ''}`}
                </button>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
