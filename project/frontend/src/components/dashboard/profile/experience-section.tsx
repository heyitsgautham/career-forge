'use client';

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Button } from '@/components/ui/button';
import type { ExperienceEntry, ProfileChangeHandler, ProfileData } from './types';

/** Work experience entries with add, edit and remove. */
export function ExperienceSection({
  profile,
  onChange,
}: {
  profile: ProfileData;
  onChange: ProfileChangeHandler;
}) {
  return (
    <>
      {/* Work Experience */}
      <Card>
        <CardHeader>
          <div className="flex justify-between items-center">
            <div>
              <CardTitle>Work Experience</CardTitle>
              <CardDescription>Your professional work history</CardDescription>
            </div>
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={() => {
                const newExp: ExperienceEntry = {
                  company: '',
                  title: '',
                  dates: '',
                  location: '',
                  highlights: [''],
                };
                onChange('experience', [...(profile.experience || []), newExp]);
              }}
            >
              Add Experience
            </Button>
          </div>
        </CardHeader>
        <CardContent className="space-y-6">
          {!profile.experience || profile.experience.length === 0 ? (
            <p className="text-sm text-muted-foreground text-center py-4">
              No work experience added yet. Click &quot;Add Experience&quot; to get started.
            </p>
          ) : (
            profile.experience.map((exp, idx) => (
              <div key={idx} className="border rounded-lg p-4 space-y-4">
                <div className="flex justify-between items-start">
                  <h4 className="font-semibold">Experience {idx + 1}</h4>
                  <Button
                    type="button"
                    variant="ghost"
                    size="sm"
                    onClick={() => {
                      const newExperience = profile.experience!.filter((_, i) => i !== idx);
                      onChange('experience', newExperience);
                    }}
                  >
                    Remove
                  </Button>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <Label>Company</Label>
                    <Input
                      value={exp.company}
                      onChange={(e) => {
                        const newExperience = [...profile.experience!];
                        newExperience[idx].company = e.target.value;
                        onChange('experience', newExperience);
                      }}
                      placeholder="Company name"
                    />
                  </div>
                  <div className="space-y-2">
                    <Label>Job Title</Label>
                    <Input
                      value={exp.title}
                      onChange={(e) => {
                        const newExperience = [...profile.experience!];
                        newExperience[idx].title = e.target.value;
                        onChange('experience', newExperience);
                      }}
                      placeholder="e.g., Senior Software Engineer"
                    />
                  </div>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <Label>Dates</Label>
                    <Input
                      value={exp.dates}
                      onChange={(e) => {
                        const newExperience = [...profile.experience!];
                        newExperience[idx].dates = e.target.value;
                        onChange('experience', newExperience);
                      }}
                      placeholder="e.g., Jan 2020 - Present"
                    />
                  </div>
                  <div className="space-y-2">
                    <Label>Location (optional)</Label>
                    <Input
                      value={exp.location || ''}
                      onChange={(e) => {
                        const newExperience = [...profile.experience!];
                        newExperience[idx].location = e.target.value;
                        onChange('experience', newExperience);
                      }}
                      placeholder="e.g., San Francisco, CA"
                    />
                  </div>
                </div>

                <div className="space-y-2">
                  <div className="flex justify-between items-center">
                    <Label>Key Achievements / Responsibilities</Label>
                    <Button
                      type="button"
                      variant="ghost"
                      size="sm"
                      onClick={() => {
                        const newExperience = [...profile.experience!];
                        newExperience[idx].highlights.push('');
                        onChange('experience', newExperience);
                      }}
                    >
                      Add Highlight
                    </Button>
                  </div>
                  {exp.highlights.map((highlight, hIdx) => (
                    <div key={hIdx} className="flex gap-2">
                      <Input
                        value={highlight}
                        onChange={(e) => {
                          const newExperience = [...profile.experience!];
                          newExperience[idx].highlights[hIdx] = e.target.value;
                          onChange('experience', newExperience);
                        }}
                        placeholder="Describe your achievement or responsibility"
                      />
                      <Button
                        type="button"
                        variant="ghost"
                        size="sm"
                        onClick={() => {
                          const newExperience = [...profile.experience!];
                          newExperience[idx].highlights = newExperience[idx].highlights.filter(
                            (_, i) => i !== hIdx
                          );
                          onChange('experience', newExperience);
                        }}
                      >
                        ×
                      </Button>
                    </div>
                  ))}
                </div>
              </div>
            ))
          )}
        </CardContent>
      </Card>
    </>
  );
}
