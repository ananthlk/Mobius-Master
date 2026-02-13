import type { ReactNode } from 'react'

export interface ContextMenuShellProps {
  position: { x: number; y: number }
  children: ReactNode
}

/**
 * Generic positioned context-menu shell.
 *
 * The viewer manages show/hide lifecycle and positioning.
 * The calling module provides the menu items as `children`.
 */
export function ContextMenuShell({ position, children }: ContextMenuShellProps) {
  return (
    <div
      className="dv-context-menu"
      style={{ left: position.x, top: position.y }}
      onClick={(e) => e.stopPropagation()}
    >
      {children}
    </div>
  )
}
