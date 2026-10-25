'use client';

import { useState } from 'react';
import { useMutation } from '@tanstack/react-query';
import { Card, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Loader2, X, Linkedin, CheckCircle2 } from 'lucide-react';
import { userApi } from '@/lib/api';
import { useToast } from '@/hooks/use-toast';
import { apiErrorDetail } from '@/lib/api-error';

/** Modal that imports the user's LinkedIn profile into their CareerForge profile. */
export function LinkedInImportModal({ onClose }: { onClose: () => void }) {
  const { toast } = useToast();
  const [linkedInUrlInput, setLinkedInUrlInput] = useState('');
  const [importResult, setImportResult] = useState<{
    name?: string;
    headline?: string;
    location?: string;
    summary: boolean;
    website?: string;
    phone?: string;
    email?: string;
    education_added: number;
    education?: Array<{ school: string; degree?: string; field?: string; dates?: string }>;
    certifications_added: number;
  } | null>(null);

  const importLinkedInMutation = useMutation({
    mutationFn: async (url: string) => {
      const res = await userApi.importLinkedInProfile(url || undefined);
      return res.data;
    },
    onSuccess: (data) => {
      setImportResult(data.imported);
      toast({
        title: 'LinkedIn profile imported!',
        description:
          [
            data.imported.name && `Name: ${data.imported.name}`,
            data.imported.headline && 'Headline',
            data.imported.summary && 'Summary',
            data.imported.website && 'Website',
            data.imported.phone && 'Phone',
            data.imported.education_added > 0 &&
              `${data.imported.education_added} education entries`,
            data.imported.certifications_added > 0 &&
              `${data.imported.certifications_added} certifications`,
          ]
            .filter(Boolean)
            .join(' · ') || 'Profile updated',
      });
    },
    onError: (err: unknown) => {
      toast({
        title: 'Import failed',
        description: apiErrorDetail(err, 'Could not import LinkedIn profile.'),
        variant: 'destructive',
      });
    },
  });

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
      <Card className="w-full max-w-md mx-4 shadow-2xl">
        <CardContent className="p-6 space-y-5">
          {/* Header */}
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Linkedin className="h-5 w-5 text-[#0A66C2]" />
              <h2 className="text-base font-semibold">Import from LinkedIn</h2>
            </div>
            <button
              onClick={() => {
                onClose();
                setImportResult(null);
              }}
              className="rounded-sm opacity-70 hover:opacity-100 transition-opacity"
            >
              <X className="h-4 w-4" />
            </button>
          </div>

          {importResult ? (
            /* ── Success state ── */
            <div className="space-y-4">
              <div className="rounded-lg border border-[hsl(var(--success))]/30 bg-[hsl(var(--success))]/5 p-4 space-y-2">
                <p className="text-sm font-medium text-[hsl(var(--success))]">Import complete!</p>
                <ul className="text-sm text-muted-foreground space-y-1">
                  {importResult.name && (
                    <li className="flex items-center gap-2">
                      <CheckCircle2 className="h-3.5 w-3.5 text-[hsl(var(--success))]" />
                      Name: {importResult.name}
                    </li>
                  )}
                  {importResult.headline && (
                    <li className="flex items-center gap-2">
                      <CheckCircle2 className="h-3.5 w-3.5 text-[hsl(var(--success))]" />
                      Headline: {importResult.headline}
                    </li>
                  )}
                  {importResult.location && (
                    <li className="flex items-center gap-2">
                      <CheckCircle2 className="h-3.5 w-3.5 text-[hsl(var(--success))]" />
                      Location: {importResult.location}
                    </li>
                  )}
                  {importResult.summary && (
                    <li className="flex items-center gap-2">
                      <CheckCircle2 className="h-3.5 w-3.5 text-[hsl(var(--success))]" />
                      Summary / About section
                    </li>
                  )}
                  {importResult.email && (
                    <li className="flex items-center gap-2">
                      <CheckCircle2 className="h-3.5 w-3.5 text-[hsl(var(--success))]" />
                      Email: {importResult.email}
                    </li>
                  )}
                  {importResult.phone && (
                    <li className="flex items-center gap-2">
                      <CheckCircle2 className="h-3.5 w-3.5 text-[hsl(var(--success))]" />
                      Phone: {importResult.phone}
                    </li>
                  )}
                  {importResult.website && (
                    <li className="flex items-center gap-2">
                      <CheckCircle2 className="h-3.5 w-3.5 text-[hsl(var(--success))]" />
                      Website: {importResult.website}
                    </li>
                  )}
                  {importResult.education_added > 0 && (
                    <li className="flex flex-col gap-0.5">
                      <span className="flex items-center gap-2">
                        <CheckCircle2 className="h-3.5 w-3.5 text-[hsl(var(--success))]" />
                        {importResult.education_added} education entr
                        {importResult.education_added === 1 ? 'y' : 'ies'} added
                      </span>
                      {importResult.education && importResult.education.length > 0 && (
                        <ul className="ml-6 mt-0.5 space-y-0.5">
                          {importResult.education.map((e, i) => (
                            <li key={i} className="text-xs">
                              <span className="font-medium">{e.school}</span>
                              {e.degree && (
                                <span className="text-muted-foreground/70"> · {e.degree}</span>
                              )}
                              {e.field && (
                                <span className="text-muted-foreground/70">, {e.field}</span>
                              )}
                              {e.dates && (
                                <span className="text-muted-foreground/50"> ({e.dates})</span>
                              )}
                            </li>
                          ))}
                        </ul>
                      )}
                    </li>
                  )}
                  {importResult.certifications_added > 0 && (
                    <li className="flex items-center gap-2">
                      <CheckCircle2 className="h-3.5 w-3.5 text-[hsl(var(--success))]" />
                      {importResult.certifications_added} certification
                      {importResult.certifications_added === 1 ? '' : 's'} added
                    </li>
                  )}
                </ul>
              </div>
              <Button
                className="w-full"
                onClick={() => {
                  onClose();
                  setImportResult(null);
                }}
              >
                Done
              </Button>
            </div>
          ) : (
            /* ── Input state ── */
            <div className="space-y-4">
              <p className="text-sm text-muted-foreground">
                Enter your LinkedIn profile URL to import your education, certifications, summary,
                contact info, and website.
              </p>
              <p className="text-xs text-muted-foreground bg-muted/50 rounded p-2">
                <strong>Note:</strong> A browser window may open on first use for a one-time
                LinkedIn login. Your session is saved for all future imports.
              </p>
              <div className="space-y-1.5">
                <label className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
                  LinkedIn Profile URL
                </label>
                <Input
                  placeholder="https://www.linkedin.com/in/your-username"
                  value={linkedInUrlInput}
                  onChange={(e) => setLinkedInUrlInput(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' && linkedInUrlInput.trim()) {
                      importLinkedInMutation.mutate(linkedInUrlInput.trim());
                    }
                  }}
                />
              </div>
              <div className="flex gap-2">
                <Button
                  variant="outline"
                  className="flex-1"
                  onClick={() => onClose()}
                  disabled={importLinkedInMutation.isPending}
                >
                  Cancel
                </Button>
                <Button
                  className="flex-1 gap-2 bg-[#0A66C2] hover:bg-[#0A66C2]/90"
                  onClick={() => importLinkedInMutation.mutate(linkedInUrlInput.trim())}
                  disabled={!linkedInUrlInput.trim() || importLinkedInMutation.isPending}
                >
                  {importLinkedInMutation.isPending ? (
                    <>
                      <Loader2 className="h-4 w-4 animate-spin" />
                      Importing…
                    </>
                  ) : (
                    <>
                      <Linkedin className="h-4 w-4" />
                      Import
                    </>
                  )}
                </Button>
              </div>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
