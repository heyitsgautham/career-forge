'use client';

import { Clock, CheckCircle, XCircle, Loader2 } from 'lucide-react';

export const statusConfig = {
  draft: { icon: Clock, color: 'bg-muted text-muted-foreground', text: 'Draft' },
  generating: {
    icon: Loader2,
    color: 'bg-primary/10 text-primary',
    text: 'Generating\u2026',
    animate: true,
  },
  generated: {
    icon: CheckCircle,
    color: 'bg-[hsl(var(--accent))]/10 text-[hsl(var(--accent))]',
    text: 'Generated',
  },
  compiling: {
    icon: Loader2,
    color: 'bg-primary/10 text-primary',
    text: 'Compiling\u2026',
    animate: true,
  },
  compiled: {
    icon: CheckCircle,
    color: 'bg-[hsl(var(--success))]/10 text-[hsl(var(--success))]',
    text: 'Ready',
  },
  error: { icon: XCircle, color: 'bg-destructive/10 text-destructive', text: 'Error' },
};
