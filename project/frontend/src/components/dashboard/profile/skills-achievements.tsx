'use client';

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import type { ProfileChangeHandler, ProfileData } from './types';

/** Skills and achievements lists. */
export function SkillsAndAchievements({
  profile,
  onChange,
}: {
  profile: ProfileData;
  onChange: ProfileChangeHandler;
}) {
  return (
    <>
      {/* Skills */}
      <Card>
        <CardHeader>
          <CardTitle>Skills</CardTitle>
          <CardDescription>Your technical and professional skills</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="space-y-2">
            <Label htmlFor="skills">Skills (comma-separated)</Label>
            <Textarea
              id="skills"
              value={profile.skills?.join(', ') || ''}
              onChange={(e) =>
                onChange(
                  'skills',
                  e.target.value.split(',').map((s) => s.trim())
                )
              }
              placeholder="Python, JavaScript, React, etc."
              rows={4}
            />
          </div>
        </CardContent>
      </Card>

      {/* Achievements */}
      <Card className="border-l-4 border-l-purple-500">
        <CardHeader>
          <div className="flex justify-between items-center">
            <div>
              <CardTitle className="flex items-center gap-2">
                <span className="text-2xl">🌟</span>
                Achievements
              </CardTitle>
              <CardDescription>
                Awards, honors, and notable accomplishments — each line becomes a bullet on your
                resume
              </CardDescription>
            </div>
            <Button
              onClick={() => onChange('achievements', [...(profile.achievements || []), ''])}
              className="bg-gradient-to-r from-purple-600 to-violet-600 hover:from-purple-700 hover:to-violet-700"
            >
              Add Achievement
            </Button>
          </div>
        </CardHeader>
        <CardContent className="space-y-3">
          {!profile.achievements || profile.achievements.length === 0 ? (
            <div className="text-center py-8 text-muted-foreground border-2 border-dashed rounded-lg">
              <p className="text-sm font-medium mb-1">No achievements added yet.</p>
              <p className="text-xs">
                Each bullet should be self-contained, e.g.:
                <br />
                <span className="italic">
                  100% Merit Scholarship Recipient, Saveetha Engineering College (Full tuition
                  waiver, 4 years)
                </span>
              </p>
            </div>
          ) : (
            profile.achievements.map((bullet, idx) => (
              <div key={idx} className="flex items-center gap-2">
                <span className="text-muted-foreground text-lg leading-none mt-0.5">•</span>
                <Input
                  value={bullet}
                  onChange={(e) => {
                    const updated = [...profile.achievements!];
                    updated[idx] = e.target.value;
                    onChange('achievements', updated);
                  }}
                  placeholder="e.g. Smart India Hackathon 2025 Finalist – India's premier national innovation challenge"
                  className="flex-1"
                />
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() =>
                    onChange(
                      'achievements',
                      profile.achievements!.filter((_, i) => i !== idx)
                    )
                  }
                  className="text-destructive hover:text-destructive/80 hover:bg-destructive/5 shrink-0"
                >
                  ×
                </Button>
              </div>
            ))
          )}
        </CardContent>
      </Card>
    </>
  );
}
