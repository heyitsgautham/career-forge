'use client';

import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Target, TrendingUp } from 'lucide-react';
import {
  Radar,
  RadarChart,
  PolarGrid,
  PolarAngleAxis,
  PolarRadiusAxis,
  ResponsiveContainer,
  Legend,
} from 'recharts';
import { type SkillGapReport } from '@/lib/api';
import { priorityColor } from './helpers';

/** One spoke of the skill radar: the user's score against the role benchmark. */
export interface RadarPoint {
  domain: string;
  fullDomain: string;
  user: number;
  benchmark: number;
}

export function GapResults({
  report,
  radarData,
}: {
  report: SkillGapReport;
  radarData: RadarPoint[];
}) {
  return (
    <>
      {/* Overall fit + Radar */}
      <div className="grid gap-6 lg:grid-cols-2">
        {/* Radar chart */}
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-base flex items-center gap-2">
              <Target className="h-4 w-4 text-primary" aria-hidden="true" />
              Skill Radar — {report.roleName}
            </CardTitle>
            <CardDescription>Your profile (indigo) vs. role benchmark (amber)</CardDescription>
          </CardHeader>
          <CardContent>
            <div aria-label="Skill gap radar chart" role="img">
              <ResponsiveContainer width="100%" height={320}>
                <RadarChart data={radarData} cx="50%" cy="50%" outerRadius="70%">
                  <PolarGrid strokeDasharray="3 3" />
                  <PolarAngleAxis
                    dataKey="domain"
                    tick={{ fontSize: 11, fill: 'hsl(var(--muted-foreground))' }}
                  />
                  <PolarRadiusAxis angle={90} domain={[0, 100]} tick={{ fontSize: 10 }} />
                  <Radar
                    name="Your Score"
                    dataKey="user"
                    stroke="hsl(var(--primary))"
                    fill="hsl(var(--primary))"
                    fillOpacity={0.25}
                    animationDuration={800}
                  />
                  <Radar
                    name="Benchmark"
                    dataKey="benchmark"
                    stroke="hsl(var(--accent))"
                    fill="hsl(var(--accent))"
                    fillOpacity={0.1}
                    strokeDasharray="5 5"
                    animationDuration={800}
                    animationBegin={200}
                  />
                  <Legend />
                </RadarChart>
              </ResponsiveContainer>
            </div>
          </CardContent>
        </Card>

        {/* Fit summary */}
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-base flex items-center gap-2">
              <TrendingUp className="h-4 w-4 text-primary" aria-hidden="true" />
              Overall Fit
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            {/* Big percentage */}
            <div className="flex items-baseline gap-2">
              <span
                className="text-5xl font-bold tracking-tight"
                style={{ fontVariantNumeric: 'tabular-nums' }}
              >
                {report.overallFitPercent}%
              </span>
              <span className="text-sm text-muted-foreground">match to {report.roleName}</span>
            </div>

            {/* Progress bar */}
            <div className="w-full h-3 rounded-full bg-muted overflow-hidden">
              <div
                className="h-full rounded-full bg-primary transition-all duration-1000"
                style={{ width: `${report.overallFitPercent}%` }}
              />
            </div>

            <p className="text-xs text-muted-foreground">
              Based on {report.projectCount} GitHub project
              {report.projectCount !== 1 ? 's' : ''} analysed by AI
            </p>

            {/* Missing skills badges */}
            <div>
              <p className="text-xs font-medium mb-2">Priority Gaps</p>
              <div className="flex flex-wrap gap-1.5">
                {report.gaps
                  .filter((g) => g.priority === 'high' || g.priority === 'medium')
                  .map((g) => (
                    <Badge
                      key={g.domain}
                      variant="outline"
                      className={`text-xs ${priorityColor(g.priority)}`}
                    >
                      {g.domain} (−{g.gap})
                    </Badge>
                  ))}
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Gap table */}
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-base">Gap Breakdown</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b text-left">
                  <th className="py-2 pr-4 font-medium text-muted-foreground">Domain</th>
                  <th className="py-2 pr-4 font-medium text-muted-foreground text-right">
                    Your Score
                  </th>
                  <th className="py-2 pr-4 font-medium text-muted-foreground text-right">
                    Required
                  </th>
                  <th className="py-2 pr-4 font-medium text-muted-foreground text-right">Gap</th>
                  <th className="py-2 font-medium text-muted-foreground">Priority</th>
                </tr>
              </thead>
              <tbody>
                {report.gaps.map((g) => (
                  <tr key={g.domain} className="border-b last:border-0">
                    <td className="py-2.5 pr-4 font-medium">{g.domain}</td>
                    <td
                      className="py-2.5 pr-4 text-right"
                      style={{ fontVariantNumeric: 'tabular-nums' }}
                    >
                      {g.userScore}
                    </td>
                    <td
                      className="py-2.5 pr-4 text-right"
                      style={{ fontVariantNumeric: 'tabular-nums' }}
                    >
                      {g.requiredScore}
                    </td>
                    <td
                      className="py-2.5 pr-4 text-right font-medium"
                      style={{ fontVariantNumeric: 'tabular-nums' }}
                    >
                      {g.gap > 0 ? `−${g.gap}` : '0'}
                    </td>
                    <td className="py-2.5">
                      <Badge variant="outline" className={`text-xs ${priorityColor(g.priority)}`}>
                        {g.priority}
                      </Badge>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </CardContent>
      </Card>
    </>
  );
}
