import type { ViewMode } from './types'

interface ToolbarProps {
  viewMode: ViewMode
  hasOriginalFile: boolean
  zoom: number
  onViewModeChange: (mode: ViewMode) => void
  onZoomIn: () => void
  onZoomOut: () => void
  onZoomReset: () => void
  onDownload?: () => void
}

export function Toolbar({
  viewMode,
  hasOriginalFile,
  zoom,
  onViewModeChange,
  onZoomIn,
  onZoomOut,
  onZoomReset,
  onDownload,
}: ToolbarProps) {
  return (
    <div className="dv-toolbar">
      {/* View mode toggle */}
      {hasOriginalFile && (
        <div className="dv-toolbar-group dv-view-toggle">
          <button
            type="button"
            className={`dv-toolbar-btn ${viewMode === 'mobius' ? 'active' : ''}`}
            onClick={() => onViewModeChange('mobius')}
            title="Mobius-enriched view with highlights, tags, and annotations"
          >
            Mobius Renderer
          </button>
          <button
            type="button"
            className={`dv-toolbar-btn ${viewMode === 'original' ? 'active' : ''}`}
            onClick={() => onViewModeChange('original')}
            title="View original source document"
          >
            Original Document
          </button>
        </div>
      )}

      {/* Zoom controls */}
      <div className="dv-toolbar-group dv-zoom-controls">
        <button
          type="button"
          className="dv-toolbar-btn"
          onClick={onZoomOut}
          disabled={zoom <= 0.5}
          aria-label="Zoom out"
        >
          {'\u2212'}
        </button>
        <span className="dv-zoom-level">{Math.round(zoom * 100)}%</span>
        <button
          type="button"
          className="dv-toolbar-btn"
          onClick={onZoomIn}
          disabled={zoom >= 3.0}
          aria-label="Zoom in"
        >
          +
        </button>
        <button type="button" className="dv-toolbar-btn dv-zoom-reset" onClick={onZoomReset}>
          Reset
        </button>
      </div>

      {/* Download */}
      {onDownload && (
        <div className="dv-toolbar-group">
          <button
            type="button"
            className="dv-toolbar-btn dv-download-btn"
            onClick={onDownload}
            title="Download document"
            aria-label="Download document"
          >
            {'\u2193'} Download
          </button>
        </div>
      )}
    </div>
  )
}
