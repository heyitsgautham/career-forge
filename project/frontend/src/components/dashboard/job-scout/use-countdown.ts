import { useState, useEffect } from 'react';

// ── Countdown timer hook ─────────────────────────────────────────────────────

export function useCountdown(targetIso: string | null) {
  const [remaining, setRemaining] = useState('');

  useEffect(() => {
    if (!targetIso) {
      setRemaining('—');
      return;
    }
    const tick = () => {
      const diff = new Date(targetIso).getTime() - Date.now();
      if (diff <= 0) {
        setRemaining('Scraping now…');
        return;
      }
      const m = Math.floor(diff / 60000);
      const s = Math.floor((diff % 60000) / 1000);
      setRemaining(`${m}m ${s.toString().padStart(2, '0')}s`);
    };
    tick();
    const id = setInterval(tick, 1000);
    return () => clearInterval(id);
  }, [targetIso]);

  return remaining;
}
