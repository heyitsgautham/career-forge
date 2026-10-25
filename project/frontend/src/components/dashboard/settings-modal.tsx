'use client';

import { useQueryClient } from '@tanstack/react-query';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Github, Upload, X } from 'lucide-react';
import { useToast } from '@/hooks/use-toast';
import { userApi, authApi } from '@/lib/api';

/** Settings dialog: resume upload, GitHub connection and logout. */
export function SettingsModal({
  githubConnected,
  githubUsername,
  onClose,
  onResumeUploaded,
  onLogout,
}: {
  githubConnected: boolean;
  githubUsername: string;
  onClose: () => void;
  onResumeUploaded: () => void;
  onLogout: () => void;
}) {
  const { toast } = useToast();
  const queryClient = useQueryClient();

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm"
      onClick={() => onClose()}
      role="dialog"
      aria-modal="true"
      aria-label="Settings"
    >
      <Card className="w-full max-w-md shadow-xl" onClick={(e) => e.stopPropagation()}>
        <CardHeader className="flex flex-row items-start justify-between">
          <div>
            <CardTitle>Settings</CardTitle>
            <CardDescription>Manage integrations and upload your resume</CardDescription>
          </div>
          <Button variant="ghost" size="icon" onClick={() => onClose()} aria-label="Close settings">
            <X className="h-4 w-4" aria-hidden="true" />
          </Button>
        </CardHeader>
        <CardContent className="space-y-4">
          {/* Resume upload */}
          <div className="space-y-2">
            <p className="text-sm font-medium">Upload Resume</p>
            <p className="text-xs text-muted-foreground">
              Upload an existing resume to auto-fill profile fields
            </p>
            <input
              type="file"
              id="resume-upload"
              accept=".pdf,.docx,.doc,.txt"
              className="hidden"
              onChange={async (e) => {
                const file = e.target.files?.[0];
                if (!file) return;

                const formData = new FormData();
                formData.append('file', file);

                try {
                  const res = await userApi.uploadResume(formData);
                  toast({
                    title: 'Resume uploaded!',
                    description: `Extracted ${res.data.fields_updated} profile fields.`,
                  });
                  // Refresh user header + trigger ProfileView to re-fetch
                  queryClient.invalidateQueries({ queryKey: ['user-profile'] });
                  onResumeUploaded();
                  onClose();
                } catch {
                  toast({
                    title: 'Upload failed',
                    description: 'Could not process resume',
                    variant: 'destructive',
                  });
                }
                e.target.value = '';
              }}
            />
            <Button
              variant="outline"
              className="w-full gap-2"
              onClick={() => document.getElementById('resume-upload')?.click()}
            >
              <Upload className="h-4 w-4" aria-hidden="true" />
              Upload Resume (PDF / DOCX / TXT)
            </Button>
          </div>

          {/* GitHub */}
          <div className="space-y-2 border-t pt-4">
            <p className="text-sm font-medium">GitHub Integration</p>
            {githubConnected ? (
              <div className="flex items-center gap-2 rounded-lg border border-success/20 bg-success/5 p-3">
                <Github className="h-4 w-4 text-success" aria-hidden="true" />
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium">Connected</p>
                  <p className="text-xs text-muted-foreground truncate">@{githubUsername}</p>
                </div>
              </div>
            ) : (
              <Button
                variant="outline"
                className="w-full gap-2"
                onClick={() => authApi.githubInstall()}
              >
                <Github className="h-4 w-4" aria-hidden="true" />
                Connect GitHub
              </Button>
            )}
          </div>

          {/* Logout */}
          <div className="border-t pt-4">
            <Button variant="destructive" className="w-full" onClick={onLogout}>
              Logout
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
