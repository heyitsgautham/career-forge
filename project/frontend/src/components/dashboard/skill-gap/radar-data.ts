import type { SkillGapReport } from '@/lib/api';
import type { RadarPoint } from './gap-results';

const MAX_LABEL = 18;

/** One radar spoke per skill domain, with long domain names cut to fit the chart. */
export function toRadarData(gaps: SkillGapReport['gaps']): RadarPoint[] {
  return gaps.map((g) => ({
    domain: g.domain.length > MAX_LABEL ? g.domain.slice(0, MAX_LABEL - 2) + '…' : g.domain,
    fullDomain: g.domain,
    user: g.userScore,
    benchmark: g.requiredScore,
  }));
}
