/* ─── @mobius/document-viewer – shared types ─── */

import type { ReactNode } from 'react'

/** View mode for the document viewer. */
export type ViewMode = 'mobius' | 'original'

/** A single page of a document (matches the RAG backend shape). */
export interface PageData {
  page_number: number
  text: string | null
  text_markdown?: string | null
  extraction_status?: string
  source_url?: string | null
}

/** A document stub (for the document selector). */
export interface DocumentMeta {
  id: string
  filename: string
  display_name?: string | null
  /** Does the original file exist in storage (GCS)? Drives the PDF toggle. */
  has_original_file?: boolean
}

/** Generic highlight range with caller-controlled metadata and styling. */
export interface Highlight {
  /** Unique identifier for this highlight. */
  id: string
  /** Character offset – start (inclusive). */
  start: number
  /** Character offset – end (exclusive). */
  end: number
  /** Fallback title attribute on the highlight span. */
  label?: string
  /** CSS class(es) for the highlight span. The caller controls appearance. */
  className?: string
  /**
   * Arbitrary metadata the caller attaches.
   * The viewer never reads this – it simply passes it back
   * via InteractionConfig render functions so the caller can
   * decide what to render.
   */
  data?: Record<string, unknown>
}

/** Context provided when the user selects text in the document. */
export interface TextSelectionContext {
  /** The selected text string. */
  text: string
  /** Page number where the selection was made. */
  pageNumber: number
  /** Character offset of the selection start within the page text. */
  startOffset: number
  /** Character offset of the selection end within the page text. */
  endOffset: number
}

/**
 * Caller-provided interaction configuration.
 *
 * This is the key abstraction that makes the viewer reusable across
 * modules (RAG, Lexicon, Chat). Each module provides its own tooltip
 * content, context menu items, and text-selection policy.
 */
export interface InteractionConfig {
  /**
   * Render tooltip content when the user hovers over a highlight.
   * The viewer handles positioning; the caller provides the inner JSX.
   * Return `null` for no tooltip.
   */
  renderTooltip?: (highlight: Highlight, anchorRect: DOMRect) => ReactNode | null

  /**
   * Render context-menu items when the user right-clicks a highlight.
   * The viewer provides a positioned container; the caller provides buttons.
   * Call `dismiss()` to close the menu after an action.
   * Return `null` for no menu.
   */
  renderHighlightMenu?: (highlight: Highlight, dismiss: () => void) => ReactNode | null

  /**
   * Whether users can select text and get a context menu.
   * Set to `false` to disable text-selection menus (e.g. Chat module).
   * @default true
   */
  textSelectionEnabled?: boolean

  /**
   * Render context-menu items for a user text selection.
   * Called on right-click when the user has selected text.
   * Call `dismiss()` to close the menu after an action.
   * Return `null` for no menu.
   */
  renderSelectionMenu?: (selection: TextSelectionContext, dismiss: () => void) => ReactNode | null
}

/** Navigation target (scroll to a specific page / highlight). */
export interface NavigateTarget {
  pageNumber?: number
  highlightId?: string
}

/** Props for the top-level DocumentViewer component. */
export interface DocumentViewerProps {
  /** Document ID currently being viewed. */
  documentId: string
  /** Pages to render (caller fetches from API). */
  pages: PageData[]
  /** Whether pages are still loading. */
  loading?: boolean
  /** Highlights keyed by page number. Caller controls styling via className. */
  highlights?: Record<number, Highlight[]>
  /** Initial page to show. */
  initialPage?: number
  /** Navigation target (scroll to page / highlight). */
  navigateTo?: NavigateTarget | null
  /** Called after navigateTo has been consumed. */
  onNavigateConsumed?: () => void
  /** Does the original file exist (show PDF toggle)? */
  hasOriginalFile?: boolean
  /** URL to fetch the original file (for PDF pane + download). */
  originalFileUrl?: string
  /** URL to download a markdown version (for scraped / text docs). */
  markdownDownloadUrl?: string
  /** Interaction configuration – tooltips, context menus, selection policy. */
  interaction?: InteractionConfig
  /** Called when page changes. */
  onPageChange?: (pageNumber: number) => void
  /** Optional className on the root element. */
  className?: string
}
