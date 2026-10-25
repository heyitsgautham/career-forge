'use client';

import { Server, Monitor, Layers, Brain, BarChart3, Cloud, Smartphone, Shield } from 'lucide-react';

/* ─── Icon map for roles ─────────────────────────────────────────────────── */
export const ROLE_ICONS: Record<string, React.ReactNode> = {
  Server: <Server className="h-5 w-5" aria-hidden="true" />,
  Monitor: <Monitor className="h-5 w-5" aria-hidden="true" />,
  Layers: <Layers className="h-5 w-5" aria-hidden="true" />,
  Brain: <Brain className="h-5 w-5" aria-hidden="true" />,
  BarChart3: <BarChart3 className="h-5 w-5" aria-hidden="true" />,
  Cloud: <Cloud className="h-5 w-5" aria-hidden="true" />,
  Smartphone: <Smartphone className="h-5 w-5" aria-hidden="true" />,
  Shield: <Shield className="h-5 w-5" aria-hidden="true" />,
};

/* ─── Priority color helper ──────────────────────────────────────────────── */
export function priorityColor(p: string) {
  if (p === 'high') return 'bg-destructive/10 text-destructive border-destructive/20';
  if (p === 'medium')
    return 'bg-[hsl(var(--accent))]/10 text-[hsl(var(--accent))] border-[hsl(var(--accent))]/20';
  return 'bg-[hsl(var(--success))]/10 text-[hsl(var(--success))] border-[hsl(var(--success))]/20';
}
