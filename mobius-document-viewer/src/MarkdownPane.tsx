import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import rehypeRaw from 'rehype-raw'
import type { Highlight, PageData } from './types'
import { AnnotationLayer } from './AnnotationLayer'

interface MarkdownPaneProps {
  page: PageData
  highlights: Highlight[]
  zoom: number
  onHighlightHover?: (r: Highlight, rect: DOMRect) => void
  onHighlightLeave?: () => void
  onContextMenu?: (e: React.MouseEvent) => void
}

export function MarkdownPane({
  page,
  highlights,
  zoom,
  onHighlightHover,
  onHighlightLeave,
  onContextMenu,
}: MarkdownPaneProps) {
  const text = page.text_markdown ?? page.text ?? ''
  const hasHighlights = highlights.length > 0
  const isMarkdown = !!page.text_markdown

  return (
    <div className="dv-markdown-pane" style={{ zoom }} onContextMenu={onContextMenu}>
      <div className="dv-book-page">
        <div className="dv-page-text-content">
          {hasHighlights ? (
            <AnnotationLayer
              text={text}
              ranges={highlights}
              isMarkdown={isMarkdown}
              onHighlightHover={onHighlightHover}
              onHighlightLeave={onHighlightLeave}
            />
          ) : isMarkdown ? (
            <div className="dv-markdown">
              <ReactMarkdown
                remarkPlugins={[remarkGfm]}
                rehypePlugins={[rehypeRaw]}
                components={{
                  h1: ({ children, ...props }) => (
                    <h1 className="dv-h1" {...props}>
                      {children}
                    </h1>
                  ),
                  h2: ({ children, ...props }) => (
                    <h2 className="dv-h2" {...props}>
                      {children}
                    </h2>
                  ),
                  h3: ({ children, ...props }) => (
                    <h3 className="dv-h3" {...props}>
                      {children}
                    </h3>
                  ),
                  table: ({ children, ...props }) => (
                    <div className="dv-table-wrapper">
                      <table className="dv-table" {...props}>
                        {children}
                      </table>
                    </div>
                  ),
                  ul: ({ children, ...props }) => (
                    <ul className="dv-list" {...props}>
                      {children}
                    </ul>
                  ),
                  ol: ({ children, ...props }) => (
                    <ol className="dv-list dv-list-ordered" {...props}>
                      {children}
                    </ol>
                  ),
                }}
              >
                {text}
              </ReactMarkdown>
            </div>
          ) : (
            <AnnotationLayer
              text={text}
              ranges={[]}
              isMarkdown={false}
              onHighlightHover={onHighlightHover}
              onHighlightLeave={onHighlightLeave}
            />
          )}
        </div>
      </div>
    </div>
  )
}
