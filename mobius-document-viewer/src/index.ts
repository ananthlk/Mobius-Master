/* @mobius/document-viewer – barrel export */

export { DocumentViewer } from './DocumentViewer'
export { MarkdownPane } from './MarkdownPane'
export { AnnotationLayer, getFirstSectionHeader, buildSegments, correctRangeToMatchText } from './AnnotationLayer'
export { PdfPane } from './PdfPane'
export { Toolbar } from './Toolbar'
export { PageNavigation, PageNavigationBar } from './PageNavigation'
export { ContextMenuShell } from './ContextMenu'

export type {
  ViewMode,
  PageData,
  DocumentMeta,
  Highlight,
  TextSelectionContext,
  InteractionConfig,
  NavigateTarget,
  DocumentViewerProps,
} from './types'

/* Import CSS side-effect for bundlers that support it */
import './styles/document-viewer.css'
