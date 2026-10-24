'use client';

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Button } from '@/components/ui/button';
import type { EducationEntry, ProfileChangeHandler, ProfileData } from './types';

/** Education entries plus the legacy single-education fields. */
export function EducationSection({
  profile,
  onChange,
}: {
  profile: ProfileData;
  onChange: ProfileChangeHandler;
}) {
  return (
    <>
      {/* Education (Multiple Entries) */}
      <Card>
        <CardHeader>
          <div className="flex justify-between items-center">
            <div>
              <CardTitle>Education</CardTitle>
              <CardDescription>Your educational background</CardDescription>
            </div>
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={() => {
                const newEdu: EducationEntry = {
                  school: '',
                  degree: '',
                  field: '',
                  dates: '',
                  location: '',
                  gpa: '',
                };
                onChange('education', [...(profile.education || []), newEdu]);
              }}
            >
              Add Education
            </Button>
          </div>
        </CardHeader>
        <CardContent className="space-y-6">
          {!profile.education || profile.education.length === 0 ? (
            <div className="space-y-4">
              <p className="text-sm text-muted-foreground text-center py-4">
                No education entries added yet. Click &quot;Add Education&quot; to get started.
              </p>

              {/* Legacy single education fields */}
              {(profile.institution || profile.degree || profile.field_of_study) && (
                <div className="border rounded-lg p-4 space-y-4 bg-muted/50">
                  <p className="text-sm font-medium">Legacy Education Entry</p>
                  <div className="space-y-2">
                    <Label htmlFor="institution">Institution</Label>
                    <Input
                      id="institution"
                      value={profile.institution || ''}
                      onChange={(e) => onChange('institution', e.target.value)}
                      placeholder="University or college name"
                    />
                  </div>
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div className="space-y-2">
                      <Label htmlFor="degree">Degree</Label>
                      <Input
                        id="degree"
                        value={profile.degree || ''}
                        onChange={(e) => onChange('degree', e.target.value)}
                        placeholder="Bachelor of Science"
                      />
                    </div>
                    <div className="space-y-2">
                      <Label htmlFor="field_of_study">Field of Study</Label>
                      <Input
                        id="field_of_study"
                        value={profile.field_of_study || ''}
                        onChange={(e) => onChange('field_of_study', e.target.value)}
                        placeholder="Computer Science"
                      />
                    </div>
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="graduation_year">Graduation Year</Label>
                    <Input
                      id="graduation_year"
                      value={profile.graduation_year || ''}
                      onChange={(e) => onChange('graduation_year', e.target.value)}
                      placeholder="2024"
                    />
                  </div>
                </div>
              )}
            </div>
          ) : (
            profile.education.map((edu, idx) => (
              <div key={idx} className="border rounded-lg p-4 space-y-4">
                <div className="flex justify-between items-start">
                  <h4 className="font-semibold">Education {idx + 1}</h4>
                  <Button
                    type="button"
                    variant="ghost"
                    size="sm"
                    onClick={() => {
                      const newEducation = profile.education!.filter((_, i) => i !== idx);
                      onChange('education', newEducation);
                    }}
                  >
                    Remove
                  </Button>
                </div>

                <div className="space-y-2">
                  <Label>Institution/School</Label>
                  <Input
                    value={edu.school}
                    onChange={(e) => {
                      const newEducation = [...profile.education!];
                      newEducation[idx].school = e.target.value;
                      onChange('education', newEducation);
                    }}
                    placeholder="University or college name"
                  />
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <Label>Degree</Label>
                    <Input
                      value={edu.degree}
                      onChange={(e) => {
                        const newEducation = [...profile.education!];
                        newEducation[idx].degree = e.target.value;
                        onChange('education', newEducation);
                      }}
                      placeholder="e.g., Bachelor of Science"
                    />
                  </div>
                  <div className="space-y-2">
                    <Label>Field of Study</Label>
                    <Input
                      value={edu.field}
                      onChange={(e) => {
                        const newEducation = [...profile.education!];
                        newEducation[idx].field = e.target.value;
                        onChange('education', newEducation);
                      }}
                      placeholder="e.g., Computer Science"
                    />
                  </div>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                  <div className="space-y-2">
                    <Label>Dates</Label>
                    <Input
                      value={edu.dates}
                      onChange={(e) => {
                        const newEducation = [...profile.education!];
                        newEducation[idx].dates = e.target.value;
                        onChange('education', newEducation);
                      }}
                      placeholder="e.g., 2018 - 2022"
                    />
                  </div>
                  <div className="space-y-2">
                    <Label>Location (optional)</Label>
                    <Input
                      value={edu.location || ''}
                      onChange={(e) => {
                        const newEducation = [...profile.education!];
                        newEducation[idx].location = e.target.value;
                        onChange('education', newEducation);
                      }}
                      placeholder="e.g., Boston, MA"
                    />
                  </div>
                  <div className="space-y-2">
                    <Label>GPA (optional)</Label>
                    <Input
                      value={edu.gpa || ''}
                      onChange={(e) => {
                        const newEducation = [...profile.education!];
                        newEducation[idx].gpa = e.target.value;
                        onChange('education', newEducation);
                      }}
                      placeholder="e.g., 3.8/4.0"
                    />
                  </div>
                </div>
              </div>
            ))
          )}
        </CardContent>
      </Card>
    </>
  );
}
