import type { ReactNode } from 'react';
import { createPortal } from 'react-dom';

/**
 * Renders a modal overlay into document.body.
 *
 * Rendered in place, an overlay inherits layout from its parent. Inside a
 * Tailwind space-y-* list it picked up the list's top margin, so a strip at
 * the top of the screen stayed undimmed and clickable above the backdrop.
 */
export function Portal({ children }: { children: ReactNode }) {
  if (typeof document === 'undefined') return null;
  return createPortal(children, document.body);
}
