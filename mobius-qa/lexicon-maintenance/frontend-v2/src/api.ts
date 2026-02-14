/* Lexicon Maintenance — API client */

const API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost:8010'

async function _fetch<T>(path: string, opts?: RequestInit): Promise<T> {
  const url = `${API_BASE}${path}`
  const res = await fetch(url, {
    ...opts,
    headers: { 'Content-Type': 'application/json', ...opts?.headers },
  })
  if (!res.ok) {
    const body = await res.text().catch(() => '')
    throw new Error(`API ${res.status}: ${body.slice(0, 300)}`)
  }
  return res.json()
}

// ── Tags / Tree ──

export interface OverviewResponse {
  rows: Array<Record<string, unknown>>
  total: number
}

export async function fetchLexiconOverview(params: {
  kind?: string
  status?: string
  min_score?: number
  limit?: number
} = {}): Promise<OverviewResponse> {
  const qs = new URLSearchParams()
  if (params.kind) qs.set('kind', params.kind)
  if (params.status) qs.set('status', params.status ?? 'approved')
  if (params.min_score != null) qs.set('min_score', String(params.min_score))
  if (params.limit) qs.set('limit', String(params.limit))
  return _fetch(`/policy/lexicon/overview?${qs}`)
}

export async function fetchTagDetail(kind: string, code: string, min_score = 0.6) {
  const qs = new URLSearchParams({ kind, code, min_score: String(min_score) })
  return _fetch<Record<string, unknown>>(`/policy/lexicon/tag-details?${qs}`)
}

export async function patchTag(kind: string, code: string, body: Record<string, unknown>) {
  return _fetch<Record<string, unknown>>(`/policy/lexicon/tags/${kind}/${code}`, {
    method: 'PATCH',
    body: JSON.stringify(body),
  })
}

export async function moveTag(body: { kind: string; from_code: string; to_code: string; parent_code?: string | null }) {
  return _fetch<Record<string, unknown>>('/policy/lexicon/tags/move', {
    method: 'POST',
    body: JSON.stringify(body),
  })
}

export async function deleteTag(kind: string, code: string) {
  return _fetch<Record<string, unknown>>(`/policy/lexicon/tags/${kind}/${code}`, {
    method: 'DELETE',
  })
}

export async function mergeTags(body: { kind: string; source_code: string; target_code: string }) {
  return _fetch<Record<string, unknown>>('/policy/lexicon/tags/merge', {
    method: 'POST',
    body: JSON.stringify(body),
  })
}

// ── Candidates ──

export interface CandidateAggregateResponse {
  rows: Array<Record<string, unknown>>
  total: number
}

export async function fetchCandidates(params: {
  kind?: string
  status?: string
  search?: string
  sort?: string
  llm_verdict?: string
  limit?: number
} = {}): Promise<CandidateAggregateResponse> {
  // The overview endpoint returns both tags and candidates together.
  // We filter client-side for candidates only.
  const qs = new URLSearchParams()
  if (params.kind) qs.set('kind', params.kind)
  qs.set('status', params.status ?? 'proposed')
  if (params.search) qs.set('search', params.search)
  if (params.limit) qs.set('limit', String(params.limit ?? 500))
  qs.set('min_score', '0')
  const data = await _fetch<{ rows: Array<Record<string, unknown>> }>(`/policy/lexicon/overview?${qs}`)
  let rows = (data.rows || []).filter(r => r.row_type === 'candidate')

  // Client-side filters
  if (params.llm_verdict) {
    rows = rows.filter(r => r.llm_verdict === params.llm_verdict)
  }
  if (params.sort === 'llm_confidence') {
    rows.sort((a, b) => ((b.llm_confidence as number) || 0) - ((a.llm_confidence as number) || 0))
  } else if (params.sort === 'alphabetical') {
    rows.sort((a, b) => String(a.normalized || '').localeCompare(String(b.normalized || '')))
  }
  // Default sort (occurrences) is already from the API

  return { rows, total: rows.length }
}

export async function bulkReview(body: {
  normalized_list: string[]
  state: string
  reviewer?: string
  reviewer_notes?: string
  candidate_type_override?: string
  tag_code_map?: Record<string, string>
}) {
  return _fetch<Record<string, unknown>>('/policy/candidates/aggregate/review-bulk', {
    method: 'POST',
    body: JSON.stringify(body),
  })
}

// ── LLM Triage ──

export async function runLlmTriage(force = false) {
  return _fetch<Record<string, unknown>>('/policy/candidates/llm-triage', {
    method: 'POST',
    body: JSON.stringify({ force }),
  })
}

// ── Purge Stale ──

export async function purgeStale(dryRun = false) {
  return _fetch<Record<string, unknown>>('/policy/candidates/purge-stale', {
    method: 'POST',
    body: JSON.stringify({ dry_run: dryRun }),
  })
}

// ── Publish ──

export async function publishToRag(dryRun = false) {
  return _fetch<Record<string, unknown>>('/policy/lexicon/publish', {
    method: 'POST',
    body: JSON.stringify({ dry_run: dryRun }),
  })
}

// ── Health ──

export async function runHealthAnalysis(model?: string) {
  return _fetch<Record<string, unknown>>('/policy/lexicon/health/analyze', {
    method: 'POST',
    body: JSON.stringify(model ? { model } : {}),
  })
}

export interface FixOperation {
  op: 'create_tag' | 'update_tag' | 'delete_tag' | 'merge_tags' | 'move_tag'
  kind?: string
  code?: string
  parent_code?: string | null
  spec?: Record<string, unknown>
  source_code?: string
  target_code?: string
  from_code?: string
  to_code?: string
}

export interface FixPreviewResponse {
  status: string
  explanation: string
  operations: FixOperation[]
  llm_model: string
}

export interface FixApplyResponse {
  status: string
  results: Array<{ index: number; op: string; code?: string; status: string; detail?: string; note?: string }>
  failed_count: number
  lexicon_revision: number
}

export async function previewHealthFix(
  issue: { type: string; severity: string; tags: string[]; message: string; fix: string },
  userInstructions?: string,
  model?: string,
): Promise<FixPreviewResponse> {
  return _fetch<FixPreviewResponse>('/policy/lexicon/health/fix/preview', {
    method: 'POST',
    body: JSON.stringify({
      issue,
      user_instructions: userInstructions || '',
      model: model || undefined,
    }),
  })
}

export async function applyHealthFix(operations: FixOperation[]): Promise<FixApplyResponse> {
  return _fetch<FixApplyResponse>('/policy/lexicon/health/fix/apply', {
    method: 'POST',
    body: JSON.stringify({ operations }),
  })
}

// ── Dismissed issues ──

export interface DismissedIssue {
  id: string
  issue_type: string
  issue_tags: string[]
  issue_message: string
  issue_fingerprint: string
  reason: string
  dismissed_by: string
  created_at: string
}

export async function dismissHealthIssue(body: {
  issue_type: string
  tags: string[]
  message: string
  reason?: string
}) {
  return _fetch<{ status: string; fingerprint: string }>('/policy/lexicon/health/dismiss', {
    method: 'POST',
    body: JSON.stringify(body),
  })
}

export async function listDismissedIssues() {
  return _fetch<{ status: string; dismissed: DismissedIssue[]; count: number }>('/policy/lexicon/health/dismissed')
}

export async function undismissHealthIssue(fingerprint: string) {
  return _fetch<{ status: string; fingerprint: string }>(`/policy/lexicon/health/dismiss/${encodeURIComponent(fingerprint)}`, {
    method: 'DELETE',
  })
}

// ── API status ──

export async function checkHealth() {
  return _fetch<{ status: string }>('/health')
}
