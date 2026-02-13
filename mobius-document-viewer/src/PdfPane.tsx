import { useState, useCallback, useRef, useEffect } from 'react'
import { Document, Page, pdfjs } from 'react-pdf'
import 'react-pdf/dist/Page/AnnotationLayer.css'
import 'react-pdf/dist/Page/TextLayer.css'
import type { Highlight } from './types'

// Configure PDF.js worker
pdfjs.GlobalWorkerOptions.workerSrc = `//unpkg.com/pdfjs-dist@${pdfjs.version}/build/pdf.worker.min.mjs`

interface PdfPaneProps {
  /** URL to fetch the original PDF file. */
  fileUrl: string
  /** Which page to render (1-based). */
  pageNumber: number
  zoom: number
  /** Highlights to overlay on the PDF text layer. */
  highlights?: Highlight[]
  /** Called once after the PDF document loads, with the total page count. */
  onDocumentLoaded?: (numPages: number) => void
  /** Called when the user hovers over a highlighted span. */
  onHighlightHover?: (r: Highlight, rect: DOMRect) => void
  /** Called when the user leaves a highlighted span. */
  onHighlightLeave?: () => void
}

/**
 * After the text layer renders, scan its spans for text that matches
 * any highlight's matchText, then apply CSS classes to those spans.
 */
function applyHighlightsToTextLayer(
  container: HTMLElement,
  highlights: Highlight[],
  onHover?: (r: Highlight, rect: DOMRect) => void,
  onLeave?: () => void,
) {
  const textLayer = container.querySelector('.textLayer')
  if (!textLayer) return

  const spans = Array.from(textLayer.querySelectorAll('span'))
  if (!spans.length || !highlights.length) return

  // Build full text from spans, tracking offsets
  let fullText = ''
  const spanMap: Array<{ span: HTMLElement; start: number; end: number }> = []
  for (const span of spans) {
    const text = span.textContent || ''
    spanMap.push({ span: span as HTMLElement, start: fullText.length, end: fullText.length + text.length })
    fullText += text
  }

  // Normalize whitespace for fuzzy matching
  const normFull = fullText.replace(/\s+/g, ' ')

  for (const hl of highlights) {
    const matchText = typeof hl.data?.matchText === 'string' ? (hl.data.matchText as string) : null
    if (!matchText || !matchText.trim()) continue

    // Find match in full text
    const normMatch = matchText.replace(/\s+/g, ' ')
    let idx = normFull.indexOf(normMatch)
    if (idx === -1) {
      // Case-insensitive fallback
      idx = normFull.toLowerCase().indexOf(normMatch.toLowerCase())
    }
    if (idx === -1) continue

    const matchEnd = idx + normMatch.length

    // Apply CSS to overlapping spans
    for (const { span, start, end } of spanMap) {
      if (end <= idx || start >= matchEnd) continue
      span.classList.add('dv-pdf-highlight')
      if (hl.className) {
        for (const cls of hl.className.split(' ')) {
          if (cls) span.classList.add(cls)
        }
      }
      span.setAttribute('data-highlight-id', hl.id)
      if (hl.label) span.title = hl.label

      // Attach hover listeners (once per span)
      if (!span.dataset.hlListenerAttached) {
        span.dataset.hlListenerAttached = '1'
        span.addEventListener('mouseenter', () => {
          onHover?.(hl, span.getBoundingClientRect())
        })
        span.addEventListener('mouseleave', () => {
          onLeave?.()
        })
      }
    }
  }
}

export function PdfPane({
  fileUrl,
  pageNumber,
  zoom,
  highlights = [],
  onDocumentLoaded,
  onHighlightHover,
  onHighlightLeave,
}: PdfPaneProps) {
  const [numPages, setNumPages] = useState<number | null>(null)
  const [error, setError] = useState<string | null>(null)
  const pageContainerRef = useRef<HTMLDivElement | null>(null)
  const [textLayerRendered, setTextLayerRendered] = useState(0)

  const onDocumentLoadSuccess = useCallback(
    ({ numPages: n }: { numPages: number }) => {
      setNumPages(n)
      setError(null)
      onDocumentLoaded?.(n)
    },
    [onDocumentLoaded],
  )

  const onDocumentLoadError = useCallback((err: Error) => {
    setError(err.message || 'Failed to load PDF')
  }, [])

  const onRenderTextLayerSuccess = useCallback(() => {
    // Trigger highlight application after text layer is ready
    setTextLayerRendered((k) => k + 1)
  }, [])

  // Apply highlights whenever text layer re-renders or highlights change
  useEffect(() => {
    if (!pageContainerRef.current || !highlights.length || textLayerRendered === 0) return
    // Small delay to ensure DOM is fully painted
    const timer = setTimeout(() => {
      if (pageContainerRef.current) {
        applyHighlightsToTextLayer(
          pageContainerRef.current,
          highlights,
          onHighlightHover,
          onHighlightLeave,
        )
      }
    }, 50)
    return () => clearTimeout(timer)
  }, [textLayerRendered, highlights, onHighlightHover, onHighlightLeave])

  if (!fileUrl) {
    return (
      <div className="dv-pdf-pane dv-pdf-empty">
        <p>No original file available for this document.</p>
      </div>
    )
  }

  // Clamp to valid range
  const safePage = numPages ? Math.max(1, Math.min(pageNumber, numPages)) : pageNumber

  return (
    <div className="dv-pdf-pane">
      {error && (
        <div className="dv-pdf-error">
          <p>Failed to load PDF: {error}</p>
        </div>
      )}
      <div ref={pageContainerRef}>
        <Document
          file={fileUrl}
          onLoadSuccess={onDocumentLoadSuccess}
          onLoadError={onDocumentLoadError}
          loading={<div className="dv-pdf-loading">Loading PDF...</div>}
          className="dv-pdf-document"
        >
          <Page
            pageNumber={safePage}
            scale={zoom}
            className="dv-pdf-page"
            renderTextLayer
            renderAnnotationLayer
            onRenderTextLayerSuccess={onRenderTextLayerSuccess}
          />
        </Document>
      </div>
      {numPages != null && (
        <div className="dv-pdf-page-indicator">
          Page {safePage} of {numPages}
        </div>
      )}
    </div>
  )
}
