/* Lexicon Maintenance — shared types */

export type TagKind = 'p' | 'd' | 'j'

export interface TagEntry {
  id?: string
  kind: TagKind
  code: string
  parent_code: string | null
  active: boolean
  spec: TagSpec
  // Computed from RAG
  hit_lines?: number
  hit_docs?: number
  max_score?: number
  // UI-only
  children?: TagEntry[]
  depth?: number
}

export interface TagSpec {
  description?: string
  category?: string
  strong_phrases?: string[]
  phrases?: string[]
  weak_keywords?: { any_of?: string[]; min_hits?: number }
  children?: Record<string, unknown>
}

export type LlmVerdict = 'new_tag' | 'alias' | 'reject' | ''

export interface CandidateRow {
  normalized: string
  candidate_type: string
  total_occurrences: number
  doc_count: number
  avg_confidence: number
  document_ids: string[]
  // LLM triage fields
  llm_verdict?: LlmVerdict
  llm_confidence?: number
  llm_reason?: string
  llm_suggested_kind?: string
  llm_suggested_code?: string
  llm_suggested_parent?: string
}

export interface HealthIssue {
  id: string
  severity: 'error' | 'warning' | 'info'
  type: string
  message: string
  tags: string[]
  fix_action?: string
}

export interface TagDetail {
  tag: TagEntry
  usage: { hit_lines: number; hit_docs: number; max_score: number }
  top_documents: Array<{ document_id: string; hit_lines: number; max_score: number }>
  sample_lines: Array<{ document_id: string; page_number: number; score: number; text: string; snippet: string }>
}

export type CenterTab = 'candidates' | 'overview' | 'health' | 'reader'
