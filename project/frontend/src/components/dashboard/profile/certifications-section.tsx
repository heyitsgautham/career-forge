'use client';

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Button } from '@/components/ui/button';
import type { CertificationEntry, ProfileChangeHandler, ProfileData } from './types';

/** Certifications list, including LinkedIn-imported ones. */
export function CertificationsSection({
  profile,
  onChange,
}: {
  profile: ProfileData;
  onChange: ProfileChangeHandler;
}) {
  return (
    <>
      {/* Certifications */}
      <Card className="border-l-4 border-l-amber-400">
        <CardHeader>
          <div className="flex justify-between items-center">
            <div>
              <CardTitle className="flex items-center gap-2">
                <span className="text-2xl">🏆</span>
                Certifications
              </CardTitle>
              <CardDescription>Your professional certifications and credentials</CardDescription>
            </div>
            <div className="flex gap-2">
              <Button
                onClick={() => {
                  const newCert: CertificationEntry = {
                    name: '',
                    issuer: '',
                    date: '',
                    credential_id: '',
                    url: '',
                  };
                  onChange('certifications', [...(profile.certifications || []), newCert]);
                }}
                className="bg-amber-600 hover:bg-amber-700"
              >
                Add Manually
              </Button>
            </div>
          </div>
        </CardHeader>
        <CardContent className="space-y-4">
          {!profile.certifications || profile.certifications.length === 0 ? (
            <div className="text-center py-8 text-muted-foreground border-2 border-dashed rounded-lg">
              <p className="text-sm">
                No certifications added yet. Import from LinkedIn or add manually.
              </p>
            </div>
          ) : (
            profile.certifications.map((cert, idx) => (
              <div
                key={idx}
                className="p-4 border rounded-lg space-y-4 bg-amber-50 dark:bg-amber-950"
              >
                <div className="flex justify-between items-start">
                  <h4 className="font-semibold text-foreground">Certification {idx + 1}</h4>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => {
                      const newCertifications = profile.certifications!.filter((_, i) => i !== idx);
                      onChange('certifications', newCertifications);
                    }}
                    className="text-destructive hover:text-destructive/80 hover:bg-destructive/5"
                  >
                    Remove
                  </Button>
                </div>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <Label htmlFor={`cert-name-${idx}`}>Certification Name *</Label>
                    <Input
                      id={`cert-name-${idx}`}
                      value={cert.name}
                      onChange={(e) => {
                        const newCertifications = [...profile.certifications!];
                        newCertifications[idx] = {
                          ...newCertifications[idx],
                          name: e.target.value,
                        };
                        onChange('certifications', newCertifications);
                      }}
                      placeholder="AWS Certified Solutions Architect"
                    />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor={`cert-issuer-${idx}`}>Issuing Organization *</Label>
                    <Input
                      id={`cert-issuer-${idx}`}
                      value={cert.issuer}
                      onChange={(e) => {
                        const newCertifications = [...profile.certifications!];
                        newCertifications[idx] = {
                          ...newCertifications[idx],
                          issuer: e.target.value,
                        };
                        onChange('certifications', newCertifications);
                      }}
                      placeholder="Amazon Web Services"
                    />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor={`cert-date-${idx}`}>Issue Date *</Label>
                    <Input
                      id={`cert-date-${idx}`}
                      value={cert.date}
                      onChange={(e) => {
                        const newCertifications = [...profile.certifications!];
                        newCertifications[idx] = {
                          ...newCertifications[idx],
                          date: e.target.value,
                        };
                        onChange('certifications', newCertifications);
                      }}
                      placeholder="January 2024"
                    />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor={`cert-id-${idx}`}>Credential ID</Label>
                    <Input
                      id={`cert-id-${idx}`}
                      value={cert.credential_id || ''}
                      onChange={(e) => {
                        const newCertifications = [...profile.certifications!];
                        newCertifications[idx] = {
                          ...newCertifications[idx],
                          credential_id: e.target.value,
                        };
                        onChange('certifications', newCertifications);
                      }}
                      placeholder="ABC123XYZ"
                    />
                  </div>
                  <div className="space-y-2 md:col-span-2">
                    <Label htmlFor={`cert-url-${idx}`}>Credential URL</Label>
                    <Input
                      id={`cert-url-${idx}`}
                      value={cert.url || ''}
                      onChange={(e) => {
                        const newCertifications = [...profile.certifications!];
                        newCertifications[idx] = { ...newCertifications[idx], url: e.target.value };
                        onChange('certifications', newCertifications);
                      }}
                      placeholder="https://www.credly.com/badges/..."
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
