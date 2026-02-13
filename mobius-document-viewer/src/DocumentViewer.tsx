import { useState, useEffect, useCallback, useRef, type ReactNode } from 'react'
import type {
  DocumentViewerProps,
  Highlight,
  ViewMode,
  TextSelectionContext,
} from './types'
import { MarkdownPane } from './MarkdownPane'
import { PdfPane } from './PdfPane'
import { Toolbar } from './Toolbar'
import { PageNavigation, PageNavigationBar } from './PageNavigation'
import { ContextMenuShell } from './ContextMenu'
import { getFirstSectionHeader } from './AnnotationLayer'

export function DocumentViewer({
  documentId,
  pages,
  loading = false,
  highlights = {},
  initialPage,
  navigateTo,
  onNavigateConsumed,
  hasOriginalFile = false,
  originalFileUrl,
  markdownDownloadUrl,
  interaction,
  onPageChange,
  className,
}: DocumentViewerProps) {
  /* ─── View state ─── */
  const [viewMode, setViewMode] = useState<ViewMode>('mobius')
  const [selectedPage, setSelectedPage] = useState<number | null>(initialPage ?? null)
  const [zoom, setZoom] = useState(1.0)
  const [sidebarOpen, setSidebarOpen] = useState(true)

  /* ─── Tooltip ─── */
  const [tooltipContent, setTooltipContent] = useState<ReactNode | null>(null)
  const [tooltipPosition, setTooltipPosition] = useState<{ left: number; top: number } | null>(null)
  const tooltipShowRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const tooltipHideRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const pageScrollRef = useRef<HTMLDivElement | null>(null)

  /* ─── Context menu ─── */
  const [contextMenuPos, setContextMenuPos] = useState<{ x: number; y: number } | null>(null)
  const [contextMenuContent, setContextMenuContent] = useState<ReactNode | null>(null)

  /* ─── Success toast ─── */
  const [successMessage, setSuccessMessage] = useState<string | null>(null)

  /* ─── Auto-select first page ─── */
  useEffect(() => {
    if (pages.length > 0 && selectedPage == null) {
      const first = initialPage ?? pages[0].page_number
      setSelectedPage(first)
    }
  }, [pages, selectedPage, initialPage])

  /* ─── Navigate to page / highlight ─── */
  useEffect(() => {
    if (navigateTo?.pageNumber != null && pages.length > 0) {
      setSelectedPage(navigateTo.pageNumber)
    }
  }, [navigateTo?.pageNumber, pages.length])

  useEffect(() => {
    if (!navigateTo?.highlightId || !selectedPage) return
    const highlightId = navigateTo.highlightId
    const timer = setTimeout(() => {
      const el = document.querySelector(`[data-highlight-id="${highlightId}"]`)
      if (el) el.scrollIntoView({ behavior: 'smooth', block: 'center' })
      onNavigateConsumed?.()
    }, 300)
    return () => clearTimeout(timer)
  }, [navigateTo?.highlightId, selectedPage, onNavigateConsumed])

  /* ─── Page nav ─── */
  const handlePageSelect = useCallback(
    (pageNumber: number) => {
      setSelectedPage(pageNumber)
      onPageChange?.(pageNumber)
    },
    [onPageChange],
  )

  const goToPreviousPage = useCallback(() => {
    if (selectedPage && selectedPage > 1) {
      handlePageSelect(selectedPage - 1)
    }
  }, [selectedPage, handlePageSelect])

  const goToNextPage = useCallback(() => {
    if (selectedPage && pages.length > 0) {
      const maxPage = Math.max(...pages.map((p) => p.page_number))
      if (selectedPage < maxPage) handlePageSelect(selectedPage + 1)
    }
  }, [selectedPage, pages, handlePageSelect])

  /* ─── Zoom ─── */
  const zoomIn = () => setZoom((prev) => Math.min(prev + 0.25, 3.0))
  const zoomOut = () => setZoom((prev) => Math.max(prev - 0.25, 0.5))
  const resetZoom = () => setZoom(1.0)

  useEffect(() => {
    const onKeyDown = (e: KeyboardEvent) => {
      if (!e.ctrlKey && !e.metaKey) return
      if (e.key === '=' || e.key === '+') {
        e.preventDefault()
        setZoom((prev) => Math.min(prev + 0.25, 3.0))
      } else if (e.key === '-') {
        e.preventDefault()
        setZoom((prev) => Math.max(prev - 0.25, 0.5))
      } else if (e.key === '0') {
        e.preventDefault()
        setZoom(1.0)
      }
    }
    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  }, [])

  /* ─── Tooltip handlers ─── */
  const handleHighlightHover = useCallback(
    (r: Highlight, rect: DOMRect) => {
      if (!interaction?.renderTooltip) return
      if (tooltipHideRef.current) {
        clearTimeout(tooltipHideRef.current)
        tooltipHideRef.current = null
      }
      const content = interaction.renderTooltip(r, rect)
      if (!content) {
        setTooltipContent(null)
        setTooltipPosition(null)
        return
      }
      tooltipShowRef.current = setTimeout(() => {
        setTooltipContent(content)
        setTooltipPosition({
          left: rect.left + rect.width / 2,
          top: rect.top - 8,
        })
        tooltipShowRef.current = null
      }, 120)
    },
    [interaction],
  )

  const handleHighlightLeave = useCallback(() => {
    if (tooltipShowRef.current) {
      clearTimeout(tooltipShowRef.current)
      tooltipShowRef.current = null
    }
    tooltipHideRef.current = setTimeout(() => {
      setTooltipContent(null)
      setTooltipPosition(null)
      tooltipHideRef.current = null
    }, 80)
  }, [])

  // Dismiss tooltip on scroll
  useEffect(() => {
    const el = pageScrollRef.current
    if (!el) return
    const onScroll = () => {
      if (tooltipShowRef.current) {
        clearTimeout(tooltipShowRef.current)
        tooltipShowRef.current = null
      }
      setTooltipContent(null)
      setTooltipPosition(null)
    }
    el.addEventListener('scroll', onScroll, { passive: true })
    return () => el.removeEventListener('scroll', onScroll)
  }, [selectedPage])

  /* ─── Context menu dismiss helper ─── */
  const dismissContextMenu = useCallback(() => {
    setContextMenuPos(null)
    setContextMenuContent(null)
  }, [])

  /* ─── Context menu handler ─── */
  const handleContextMenu = useCallback(
    (e: React.MouseEvent) => {
      if (!interaction) return

      // Check if right-clicked on a highlight
      const target = e.target as HTMLElement
      const span = target.closest?.('[data-highlight-id]')
      const highlightId = span?.getAttribute?.('data-highlight-id')

      if (highlightId && selectedPage != null && interaction.renderHighlightMenu) {
        const hl = (highlights[selectedPage] || []).find((r) => r.id === highlightId)
        if (hl) {
          e.preventDefault()
          const content = interaction.renderHighlightMenu(hl, dismissContextMenu)
          if (content) {
            setContextMenuContent(content)
            setContextMenuPos({ x: e.clientX, y: e.clientY })
          }
          return
        }
      }

      // Text selection menu
      const textSelectionEnabled = interaction.textSelectionEnabled !== false
      if (textSelectionEnabled && interaction.renderSelectionMenu && selectedPage != null) {
        const sel = window.getSelection()
        const text = (sel?.toString() ?? '').trim()
        if (text) {
          e.preventDefault()
          const currentPageData = pages.find((p) => p.page_number === selectedPage)
          const sourceText = currentPageData?.text_markdown ?? currentPageData?.text ?? ''
          const idx = sourceText.indexOf(text)
          const selection: TextSelectionContext = {
            text,
            pageNumber: selectedPage,
            startOffset: idx >= 0 ? idx : 0,
            endOffset: idx >= 0 ? idx + text.length : text.length,
          }
          const content = interaction.renderSelectionMenu(selection, dismissContextMenu)
          if (content) {
            setContextMenuContent(content)
            setContextMenuPos({ x: e.clientX, y: e.clientY })
          }
        }
      }
    },
    [interaction, selectedPage, highlights, pages, dismissContextMenu],
  )

  // Dismiss context menu on click anywhere
  useEffect(() => {
    const hide = () => dismissContextMenu()
    document.addEventListener('click', hide)
    return () => document.removeEventListener('click', hide)
  }, [dismissContextMenu])

  /* ─── Download ─── */
  const handleDownload = () => {
    if (hasOriginalFile && originalFileUrl) {
      window.open(originalFileUrl, '_blank')
    } else if (markdownDownloadUrl) {
      window.open(markdownDownloadUrl, '_blank')
    }
  }
  const canDownload = !!(originalFileUrl || markdownDownloadUrl)

  /* ─── Current page ─── */
  const currentPage = pages.find((p) => p.page_number === selectedPage)
  const highlightsForPage = selectedPage != null ? highlights[selectedPage] || [] : []

  return (
    <div className={`dv-root ${className ?? ''} ${sidebarOpen ? '' : 'dv-sidebar-hidden'}`}>
      {/* Toolbar */}
      <Toolbar
        viewMode={viewMode}
        hasOriginalFile={hasOriginalFile}
        zoom={zoom}
        onViewModeChange={setViewMode}
        onZoomIn={zoomIn}
        onZoomOut={zoomOut}
        onZoomReset={resetZoom}
        onDownload={canDownload ? handleDownload : undefined}
      />

      {/* Main layout */}
      <div className={`dv-layout ${sidebarOpen ? '' : 'dv-layout-sidebar-hidden'}`}>
        <PageNavigation
          pages={pages}
          selectedPage={selectedPage}
          loading={loading}
          sidebarOpen={sidebarOpen}
          onPageSelect={handlePageSelect}
          onToggleSidebar={() => setSidebarOpen((prev) => !prev)}
          onPreviousPage={goToPreviousPage}
          onNextPage={goToNextPage}
        />

        {/* Content area */}
        <div className="dv-content-area" ref={pageScrollRef}>
          {successMessage && <div className="dv-success-message">{successMessage}</div>}
          {currentPage ? (
            <>
              {/* Page header */}
              <div className="dv-page-header">
                <h4>
                  {(() => {
                    const firstHeader = getFirstSectionHeader(
                      currentPage.text_markdown ?? currentPage.text,
                    )
                    const headerLine = firstHeader
                      ? `${currentPage.page_number} \u2013 ${firstHeader}`
                      : `Page ${currentPage.page_number}`
                    return (
                      <>
                        {headerLine}
                        {viewMode === 'mobius' && (
                          <span className="dv-canonical-note" title="Mobius-enriched view with highlights and annotations">
                            {' '}
                            {'\u221E'} Mobius
                          </span>
                        )}
                      </>
                    )
                  })()}
                </h4>
              </div>

              {/* Content */}
              {viewMode === 'original' && hasOriginalFile && originalFileUrl ? (
                <PdfPane
                  fileUrl={originalFileUrl}
                  pageNumber={selectedPage ?? 1}
                  zoom={zoom}
                  highlights={highlightsForPage}
                  onHighlightHover={handleHighlightHover}
                  onHighlightLeave={handleHighlightLeave}
                />
              ) : (
                <MarkdownPane
                  page={currentPage}
                  highlights={highlightsForPage}
                  zoom={zoom}
                  onHighlightHover={handleHighlightHover}
                  onHighlightLeave={handleHighlightLeave}
                  onContextMenu={handleContextMenu}
                />
              )}

              {/* Bottom nav bar */}
              <PageNavigationBar
                selectedPage={selectedPage}
                totalPages={pages.length}
                onPreviousPage={goToPreviousPage}
                onNextPage={goToNextPage}
              />
            </>
          ) : (
            <div className="dv-no-page">
              {loading ? 'Loading...' : 'Select a section from the sidebar'}
            </div>
          )}
        </div>
      </div>

      {/* Tooltip (generic) */}
      {tooltipContent && tooltipPosition && (
        <div
          className="dv-tooltip"
          style={{ left: tooltipPosition.left, top: tooltipPosition.top }}
        >
          <div className="dv-tooltip-arrow" />
          <div className="dv-tooltip-inner">
            {tooltipContent}
          </div>
        </div>
      )}

      {/* Context menu (generic shell with caller-provided content) */}
      {contextMenuPos && contextMenuContent && (
        <ContextMenuShell position={contextMenuPos}>
          {contextMenuContent}
        </ContextMenuShell>
      )}
    </div>
  )
}
