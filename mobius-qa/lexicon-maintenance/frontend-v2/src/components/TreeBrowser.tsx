import { useState, useMemo } from 'react'
import type { TagEntry, TagKind } from '../types'

interface Props {
  tags: TagEntry[]
  loading: boolean
  filter: string
  selectedTag: { kind: TagKind; code: string } | null
  onSelect: (kind: TagKind, code: string) => void
}

interface TreeNode {
  tag: TagEntry
  children: TreeNode[]
}

function buildTree(tags: TagEntry[]): Record<TagKind, TreeNode[]> {
  const byKindCode = new Map<string, TagEntry>()
  for (const t of tags) byKindCode.set(`${t.kind}:${t.code}`, t)

  const roots: Record<TagKind, TreeNode[]> = { p: [], d: [], j: [] }

  // Build nodes
  const nodeMap = new Map<string, TreeNode>()
  for (const t of tags) {
    const key = `${t.kind}:${t.code}`
    nodeMap.set(key, { tag: t, children: [] })
  }

  // Attach children to parents
  for (const t of tags) {
    const key = `${t.kind}:${t.code}`
    const node = nodeMap.get(key)!
    if (t.parent_code) {
      const parentKey = `${t.kind}:${t.parent_code}`
      const parentNode = nodeMap.get(parentKey)
      if (parentNode) {
        parentNode.children.push(node)
        continue
      }
    }
    roots[t.kind].push(node)
  }

  // Sort
  for (const kind of ['p', 'd', 'j'] as TagKind[]) {
    sortNodes(roots[kind])
  }

  return roots
}

function sortNodes(nodes: TreeNode[]) {
  nodes.sort((a, b) => a.tag.code.localeCompare(b.tag.code))
  for (const n of nodes) sortNodes(n.children)
}

function filterTree(nodes: TreeNode[], q: string): TreeNode[] {
  if (!q) return nodes
  const lq = q.toLowerCase()
  return nodes.reduce<TreeNode[]>((acc, node) => {
    const matchesSelf = node.tag.code.toLowerCase().includes(lq) ||
      (node.tag.spec.description || '').toLowerCase().includes(lq) ||
      (node.tag.spec.strong_phrases || []).some(p => p.toLowerCase().includes(lq))
    const filteredChildren = filterTree(node.children, q)
    if (matchesSelf || filteredChildren.length > 0) {
      acc.push({ ...node, children: matchesSelf ? node.children : filteredChildren })
    }
    return acc
  }, [])
}

const KIND_LABELS: Record<TagKind, string> = { p: 'Procedural', d: 'Domain', j: 'Jurisdiction' }
const KIND_COLORS: Record<TagKind, string> = { p: 'var(--clr-p)', d: 'var(--clr-d)', j: 'var(--clr-j)' }

/** Collect all collapsible keys from the tree, grouped by depth. */
function collectKeys(tree: Record<TagKind, TreeNode[]>): { all: string[]; byDepth: Map<number, string[]> } {
  const all: string[] = []
  const byDepth = new Map<number, string[]>()

  const walk = (nodes: TreeNode[], depth: number) => {
    for (const n of nodes) {
      if (n.children.length > 0) {
        const key = `${n.tag.kind}:${n.tag.code}`
        all.push(key)
        const arr = byDepth.get(depth) || []
        arr.push(key)
        byDepth.set(depth, arr)
        walk(n.children, depth + 1)
      }
    }
  }

  // Kind-level keys
  for (const kind of ['p', 'd', 'j'] as TagKind[]) {
    const kindKey = `kind:${kind}`
    all.push(kindKey)
    const arr = byDepth.get(-1) || []
    arr.push(kindKey)
    byDepth.set(-1, arr)
    walk(tree[kind], 0)
  }

  return { all, byDepth }
}

export function TreeBrowser({ tags, loading, filter, selectedTag, onSelect }: Props) {
  const tree = useMemo(() => buildTree(tags), [tags])
  const [collapsed, setCollapsed] = useState<Set<string>>(new Set())
  const keys = useMemo(() => collectKeys(tree), [tree])

  const toggle = (key: string) => {
    setCollapsed(prev => {
      const next = new Set(prev)
      next.has(key) ? next.delete(key) : next.add(key)
      return next
    })
  }

  const collapseAll = () => setCollapsed(new Set(keys.all))
  const expandAll = () => setCollapsed(new Set())

  const toggleLevel = (depth: number) => {
    const levelKeys = keys.byDepth.get(depth) || []
    if (levelKeys.length === 0) return
    setCollapsed(prev => {
      const next = new Set(prev)
      // If most are already collapsed, expand them; otherwise collapse them
      const collapsedCount = levelKeys.filter(k => prev.has(k)).length
      const shouldExpand = collapsedCount > levelKeys.length / 2
      for (const k of levelKeys) {
        shouldExpand ? next.delete(k) : next.add(k)
      }
      return next
    })
  }

  // Determine max depth for level buttons
  const maxDepth = Math.max(...Array.from(keys.byDepth.keys()))
  const depthLabels: Record<number, string> = { [-1]: 'Kinds', 0: 'Groups', 1: 'Tags' }

  if (loading) return <div className="tree-loading">Loading tags…</div>

  return (
    <div className="tree-browser">
      <div className="tree-toolbar">
        <button className="tree-tb-btn" onClick={expandAll} title="Expand all">
          <span className="tree-tb-icon">⊞</span>
        </button>
        <button className="tree-tb-btn" onClick={collapseAll} title="Collapse all">
          <span className="tree-tb-icon">⊟</span>
        </button>
        <span className="tree-tb-sep" />
        {Array.from(keys.byDepth.keys()).sort((a, b) => a - b).filter(d => d <= maxDepth).map(depth => (
          <button
            key={depth}
            className="tree-tb-btn"
            onClick={() => toggleLevel(depth)}
            title={`Toggle ${depthLabels[depth] || `Level ${depth + 2}`}`}
          >
            {depthLabels[depth] || `L${depth + 2}`}
          </button>
        ))}
      </div>
      {(['p', 'd', 'j'] as TagKind[]).map(kind => {
        const roots = filter ? filterTree(tree[kind], filter) : tree[kind]
        const kindKey = `kind:${kind}`
        const isCollapsed = collapsed.has(kindKey)
        return (
          <div key={kind} className="tree-kind-group">
            <div
              className="tree-kind-header"
              onClick={() => toggle(kindKey)}
              style={{ borderLeftColor: KIND_COLORS[kind] }}
            >
              <span className="tree-chevron">{isCollapsed ? '▸' : '▾'}</span>
              <span className="tree-kind-badge" style={{ background: KIND_COLORS[kind] }}>
                {kind.toUpperCase()}
              </span>
              <span className="tree-kind-label">{KIND_LABELS[kind]}</span>
              <span className="tree-count">{roots.length}</span>
            </div>
            {!isCollapsed && (
              <div className="tree-kind-body">
                {roots.map(node => (
                  <TreeNodeView
                    key={node.tag.code}
                    node={node}
                    depth={0}
                    collapsed={collapsed}
                    toggle={toggle}
                    selectedTag={selectedTag}
                    onSelect={onSelect}
                  />
                ))}
              </div>
            )}
          </div>
        )
      })}
    </div>
  )
}

function TreeNodeView({ node, depth, collapsed, toggle, selectedTag, onSelect }: {
  node: TreeNode
  depth: number
  collapsed: Set<string>
  toggle: (key: string) => void
  selectedTag: { kind: TagKind; code: string } | null
  onSelect: (kind: TagKind, code: string) => void
}) {
  const { tag, children } = node
  const key = `${tag.kind}:${tag.code}`
  const isCollapsed = collapsed.has(key)
  const isSelected = selectedTag?.kind === tag.kind && selectedTag?.code === tag.code
  const hasChildren = children.length > 0
  // Display the last segment of the code for readability
  const label = tag.code.includes('.') ? tag.code.split('.').pop()! : tag.code

  return (
    <div className="tree-node">
      <div
        className={`tree-node-row ${isSelected ? 'selected' : ''}`}
        style={{ paddingLeft: `${12 + depth * 16}px` }}
        onClick={() => onSelect(tag.kind, tag.code)}
      >
        {hasChildren ? (
          <span className="tree-chevron" onClick={e => { e.stopPropagation(); toggle(key) }}>
            {isCollapsed ? '▸' : '▾'}
          </span>
        ) : (
          <span className="tree-chevron-space" />
        )}
        <span className="tree-node-label" title={tag.code}>
          {label.replace(/_/g, ' ')}
        </span>
        {hasChildren && <span className="tree-child-count">{children.length}</span>}
        {(tag.hit_lines || 0) > 0 && (
          <span className="tree-hit-badge" title={`${tag.hit_lines} lines, ${tag.hit_docs} docs`}>
            {tag.hit_lines}
          </span>
        )}
      </div>
      {hasChildren && !isCollapsed && (
        <div className="tree-children">
          {children.map(child => (
            <TreeNodeView
              key={child.tag.code}
              node={child}
              depth={depth + 1}
              collapsed={collapsed}
              toggle={toggle}
              selectedTag={selectedTag}
              onSelect={onSelect}
            />
          ))}
        </div>
      )}
    </div>
  )
}
