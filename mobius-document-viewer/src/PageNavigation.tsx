import type { PageData } from './types'
import { getFirstSectionHeader } from './AnnotationLayer'

interface PageNavigationProps {
  pages: PageData[]
  selectedPage: number | null
  loading?: boolean
  sidebarOpen: boolean
  onPageSelect: (pageNumber: number) => void
  onToggleSidebar: () => void
  onPreviousPage: () => void
  onNextPage: () => void
}

export function PageNavigation({
  pages,
  selectedPage,
  loading = false,
  sidebarOpen,
  onPageSelect,
  onToggleSidebar,
  onPreviousPage,
  onNextPage,
}: PageNavigationProps) {
  const totalPages = pages.length
  const maxPage = totalPages > 0 ? Math.max(...pages.map((p) => p.page_number)) : 0

  return (
    <>
      {/* Sidebar */}
      <div className="dv-pages-sidebar" aria-hidden={!sidebarOpen}>
        <h3 className="dv-sidebar-title">Sections</h3>
        {loading ? (
          <div className="dv-loading-pages">Loading sections...</div>
        ) : (
          <div className="dv-pages-list">
            {pages.map((page) => {
              const firstHeader = getFirstSectionHeader(page.text_markdown ?? page.text)
              const label = firstHeader
                ? `${page.page_number} \u2013 ${firstHeader}`
                : String(page.page_number)
              return (
                <button
                  key={page.page_number}
                  className={`dv-page-item ${selectedPage === page.page_number ? 'active' : ''}`}
                  onClick={() => onPageSelect(page.page_number)}
                  title={
                    firstHeader
                      ? `Page ${page.page_number}: ${firstHeader}`
                      : `Page ${page.page_number}`
                  }
                >
                  <span className="dv-page-item-label">{label}</span>
                  {page.extraction_status && page.extraction_status !== 'success' && (
                    <span className="dv-page-status-badge">{page.extraction_status}</span>
                  )}
                </button>
              )
            })}
          </div>
        )}
      </div>

      {/* Chevron to collapse/expand sidebar */}
      <button
        type="button"
        className="dv-sidebar-chevron"
        onClick={onToggleSidebar}
        title={sidebarOpen ? 'Collapse sections' : 'Expand sections'}
        aria-label={sidebarOpen ? 'Collapse sections' : 'Expand sections'}
      >
        {sidebarOpen ? '\u2039' : '\u203a'}
      </button>

      {/* Floating nav chevrons */}
      <button
        type="button"
        className="dv-nav-chevron dv-nav-chevron-left"
        onClick={onPreviousPage}
        disabled={!selectedPage || selectedPage === 1}
        title="Previous section"
        aria-label="Previous section"
      >
        {'\u2039'}
      </button>
      <button
        type="button"
        className="dv-nav-chevron dv-nav-chevron-right"
        onClick={onNextPage}
        disabled={!selectedPage || selectedPage >= maxPage}
        title="Next section"
        aria-label="Next section"
      >
        {'\u203a'}
      </button>
    </>
  )
}

/** Bottom navigation bar: Previous / Page X of Y / Next. */
export function PageNavigationBar({
  selectedPage,
  totalPages,
  onPreviousPage,
  onNextPage,
}: {
  selectedPage: number | null
  totalPages: number
  onPreviousPage: () => void
  onNextPage: () => void
}) {
  return (
    <div className="dv-page-navigation">
      <button
        onClick={onPreviousPage}
        disabled={!selectedPage || selectedPage === 1}
        className="dv-btn dv-btn-secondary"
      >
        {'\u2190'} Previous
      </button>
      <span className="dv-page-indicator">
        Page {selectedPage ?? '-'} of {totalPages}
      </span>
      <button
        onClick={onNextPage}
        disabled={!selectedPage || selectedPage === totalPages}
        className="dv-btn dv-btn-secondary"
      >
        Next {'\u2192'}
      </button>
    </div>
  )
}
