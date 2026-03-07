'use client';

import { ReactNode, useEffect, useState } from 'react';
import { Group as PanelGroup, Panel, Separator as PanelSeparator } from 'react-resizable-panels';
import { cn } from '@/lib/utils';

interface EditorLayoutProps {
  /** Left panel — Code view or PDF Preview (toggled by parent) */
  left: ReactNode;
  /** Right panel — AI chat, always visible */
  right: ReactNode;
  className?: string;
}

/**
 * Two-column resizable layout for the LaTeX editor page.
 *
 * Uses react-resizable-panels v4 (Group/Panel/Separator).
 *
 * ┌──────────────────────┬──────────────────────┐
 * │  Left (code/preview) │  Right (AI chat)     │
 * └──────────────────────┴──────────────────────┘
 */
export function EditorLayout({ left, right, className }: EditorLayoutProps) {
  const [mounted, setMounted] = useState(false);
  useEffect(() => setMounted(true), []);

  // react-resizable-panels reads DOM/window for sizing — render a stable
  // SSR-safe skeleton until the component is mounted on the client.
  if (!mounted) {
    return (
      <div className={cn('flex-1 overflow-hidden flex', className)}>
        <div className="h-full flex flex-col" style={{ flex: '0 0 42%' }}>{left}</div>
        <div className="w-1.5 shrink-0 bg-border" />
        <div className="h-full flex flex-col flex-1">{right}</div>
      </div>
    );
  }

  return (
    <PanelGroup
      orientation="horizontal"
      className={cn('flex-1 overflow-hidden', className)}
    >
      {/* Left: AI chat panel — always visible */}
      <Panel defaultSize={42} minSize={25}>
        <div className="h-full flex flex-col">{left}</div>
      </Panel>

      {/* Drag handle */}
      <PanelSeparator
        className="w-1.5 bg-border hover:bg-violet-400/60 transition-colors cursor-col-resize"
      />

      {/* Right: code editor OR pdf preview */}
      <Panel defaultSize={58} minSize={30}>
        <div className="h-full flex flex-col">{right}</div>
      </Panel>
    </PanelGroup>
  );
}
