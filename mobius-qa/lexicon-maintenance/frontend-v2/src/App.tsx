import { useState, useEffect, useCallback } from 'react'
import type { TagEntry, CenterTab, TagKind } from './types'
import { fetchLexiconOverview, checkHealth, publishToRag } from './api'
import { TreeBrowser } from './components/TreeBrowser'
import { CandidatesTab } from './components/CandidatesTab'
import { TagOverviewTab } from './components/TagOverviewTab'
import { HealthTab } from './components/HealthTab'
import { TagDrawer } from './components/TagDrawer'
import './App.css'

function App() {
  const [activeTab, setActiveTab] = useState<CenterTab>('candidates')
  const [tags, setTags] = useState<TagEntry[]>([])
  const [loading, setLoading] = useState(true)
  const [apiOk, setApiOk] = useState<boolean | null>(null)
  const [selectedTag, setSelectedTag] = useState<{ kind: TagKind; code: string } | null>(null)
  const [drawerOpen, setDrawerOpen] = useState(false)
  const [treeFilter, setTreeFilter] = useState('')
  const [refreshKey, setRefreshKey] = useState(0)

  // Fetch all approved tags for the tree
  const loadTags = useCallback(async () => {
    setLoading(true)
    try {
      const [pRes, dRes, jRes] = await Promise.all([
        fetchLexiconOverview({ kind: 'p', status: 'approved', limit: 500 }),
        fetchLexiconOverview({ kind: 'd', status: 'approved', limit: 500 }),
        fetchLexiconOverview({ kind: 'j', status: 'approved', limit: 500 }),
      ])
      const all: TagEntry[] = [
        ...(pRes.rows || []).map(r => rowToTag(r, 'p')),
        ...(dRes.rows || []).map(r => rowToTag(r, 'd')),
        ...(jRes.rows || []).map(r => rowToTag(r, 'j')),
      ]
      setTags(all)
    } catch (e) {
      console.error('Failed to load tags:', e)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { loadTags() }, [loadTags, refreshKey])

  // API health check
  useEffect(() => {
    checkHealth().then(() => setApiOk(true)).catch(() => setApiOk(false))
    const iv = setInterval(() => {
      checkHealth().then(() => setApiOk(true)).catch(() => setApiOk(false))
    }, 30_000)
    return () => clearInterval(iv)
  }, [])

  const handleTagSelect = (kind: TagKind, code: string) => {
    setSelectedTag({ kind, code })
    setDrawerOpen(true)
  }

  const handleRefresh = () => setRefreshKey(k => k + 1)

  // Publish to RAG
  const [publishing, setPublishing] = useState(false)
  const [publishMsg, setPublishMsg] = useState('')

  const handlePublish = useCallback(async () => {
    // First dry run to show what would happen
    try {
      const preview = await publishToRag(true)
      const qaEntries = Number(preview.qa_entries || 0)
      const ragBefore = Number(preview.rag_entries_before || 0)
      const qaRev = Number(preview.qa_revision || 0)
      const ragRev = Number(preview.rag_revision_before || 0)
      if (!confirm(
        `Publish QA lexicon to RAG?\n\n` +
        `QA: ${qaEntries} entries (revision ${qaRev})\n` +
        `RAG: ${ragBefore} entries (revision ${ragRev})\n\n` +
        `This will replace all RAG lexicon entries with the current QA snapshot.`
      )) return
    } catch (e) {
      setPublishMsg(`Preview failed: ${e}`)
      return
    }
    setPublishing(true)
    setPublishMsg('')
    try {
      const result = await publishToRag(false)
      setPublishMsg(`Published: ${result.rag_entries_after} entries, revision ${result.rag_revision_after}`)
    } catch (e) {
      setPublishMsg(`Publish failed: ${e}`)
    } finally {
      setPublishing(false)
    }
  }, [])

  const tagCounts = {
    p: tags.filter(t => t.kind === 'p').length,
    d: tags.filter(t => t.kind === 'd').length,
    j: tags.filter(t => t.kind === 'j').length,
  }

  return (
    <div className="app">
      {/* Top bar */}
      <header className="topbar">
        <div className="topbar-left">
          <a className="back" href="/">← Module Hub</a>
          <h1>Lexicon Maintenance</h1>
        </div>
        <div className="topbar-right">
          {publishMsg && (
            <span className={`pill ${publishMsg.startsWith('Published') ? 'ok' : 'err'}`} style={{ marginRight: 8 }}>
              {publishMsg}
            </span>
          )}
          <button
            className="btn publish-btn"
            onClick={handlePublish}
            disabled={publishing}
            title="Copy QA lexicon to RAG DB so extraction jobs use the latest tags"
          >
            {publishing ? 'Publishing…' : 'Publish to RAG'}
          </button>
          <span className={`pill ${apiOk === true ? 'ok' : apiOk === false ? 'err' : ''}`}>
            API: {apiOk === true ? 'Connected' : apiOk === false ? 'Down' : '…'}
          </span>
        </div>
      </header>

      <div className="layout">
        {/* Left sidebar: tree browser */}
        <aside className="sidebar">
          <div className="sidebar-search">
            <input
              type="text"
              placeholder="Search tags…"
              value={treeFilter}
              onChange={e => setTreeFilter(e.target.value)}
            />
          </div>
          <TreeBrowser
            tags={tags}
            loading={loading}
            filter={treeFilter}
            selectedTag={selectedTag}
            onSelect={handleTagSelect}
          />
        </aside>

        {/* Center: tabs */}
        <main className="center">
          <nav className="tab-bar">
            {(['candidates', 'overview', 'health', 'reader'] as CenterTab[]).map(tab => (
              <button
                key={tab}
                className={`tab-btn ${activeTab === tab ? 'active' : ''}`}
                onClick={() => setActiveTab(tab)}
              >
                {tab === 'candidates' ? 'Candidates' :
                 tab === 'overview' ? 'Reporting' :
                 tab === 'health' ? 'Health' :
                 'Document Reader'}
              </button>
            ))}
          </nav>

          <div className="tab-content">
            {activeTab === 'candidates' && (
              <CandidatesTab
                tags={tags}
                onRefresh={handleRefresh}
                onTagSelect={handleTagSelect}
              />
            )}
            {activeTab === 'overview' && (
              <TagOverviewTab
                tags={tags}
                onTagSelect={handleTagSelect}
                onRefresh={handleRefresh}
              />
            )}
            {activeTab === 'health' && (
              <HealthTab tags={tags} onRefresh={handleRefresh} />
            )}
            {activeTab === 'reader' && (
              <div className="placeholder">Document Reader — coming soon</div>
            )}
          </div>
        </main>

        {/* Right drawer */}
        {drawerOpen && selectedTag && (
          <TagDrawer
            kind={selectedTag.kind}
            code={selectedTag.code}
            onClose={() => setDrawerOpen(false)}
            onSaved={handleRefresh}
          />
        )}
      </div>

      {/* Status bar */}
      <footer className="statusbar">
        <span>{tagCounts.d} D</span>
        <span>{tagCounts.p} P</span>
        <span>{tagCounts.j} J</span>
        <span className="sep">|</span>
        <span>{tags.length} total tags</span>
      </footer>
    </div>
  )
}

function rowToTag(r: Record<string, unknown>, fallbackKind: TagKind): TagEntry {
  const strongPhrases = Array.isArray(r.strong_phrases)
    ? (r.strong_phrases as string[]).filter(Boolean)
    : []
  return {
    kind: (r.kind as TagKind) || fallbackKind,
    code: String(r.code || ''),
    parent_code: r.parent_code ? String(r.parent_code) : null,
    active: r.active !== false,
    spec: {
      description: r.description ? String(r.description) : undefined,
      category: r.category ? String(r.category) : undefined,
      strong_phrases: strongPhrases,
    },
    hit_lines: Number(r.hit_lines || 0),
    hit_docs: Number(r.hit_docs || 0),
    max_score: Number(r.max_score || 0),
  }
}

export default App
