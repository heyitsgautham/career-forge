'use client';

import { useState } from 'react';
import { Button } from '@/components/ui/button';
import { useToast } from '@/hooks/use-toast';
import api from '@/lib/api';
import { ContactSections } from './profile/contact-sections';
import { ExperienceSection } from './profile/experience-section';
import { EducationSection } from './profile/education-section';
import { CertificationsSection } from './profile/certifications-section';
import { GithubProjectsSection } from './profile/github-projects-section';
import { SkillsAndAchievements } from './profile/skills-achievements';
import { describeLinkedInImport } from './profile/linkedin-import';
import { useGithubIngestion } from './profile/use-github-ingestion';
import { useProfile } from './profile/use-profile';
import { apiErrorDetail } from '@/lib/api-error';

export function ProfileView({ externalRefreshKey = 0 }: { externalRefreshKey?: number }) {
  const { toast } = useToast();
  const { profile, loading, saving, save, change, reload } = useProfile(externalRefreshKey);
  const { projects, ingesting, ingestionStatus, ingestionSummary, refreshRepos } =
    useGithubIngestion(reload);
  const [linkedInUrlPrompt, setLinkedInUrlPrompt] = useState(false);
  const [linkedInUrlInput, setLinkedInUrlInput] = useState('');

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12">
        <p className="text-muted-foreground">Loading profile...</p>
      </div>
    );
  }

  if (!profile) {
    return (
      <div className="flex items-center justify-center py-12">
        <div className="text-center">
          <p className="text-muted-foreground mb-4">No profile data found</p>
          <p className="text-sm text-muted-foreground">
            Upload a resume in Settings to auto-fill your profile
          </p>
        </div>
      </div>
    );
  }

  const handleLinkedInImport = async (overrideUrl?: string) => {
    const urlToUse = overrideUrl || profile.linkedin_url;
    if (!urlToUse) {
      // No URL stored — show inline prompt
      setLinkedInUrlInput('');
      setLinkedInUrlPrompt(true);
      return;
    }
    setLinkedInUrlPrompt(false);
    try {
      toast({
        title: 'Opening LinkedIn…',
        description:
          'A browser will open. Please log in to LinkedIn if needed, then wait while we import your profile.',
      });

      const response = await api.post('/api/auth/linkedin/import-profile', {
        linkedin_url: urlToUse,
      });

      if (response.data.success) {
        await reload();
        toast({
          title: 'Import Complete!',
          description: describeLinkedInImport(response.data.imported),
        });
      }
    } catch (error: unknown) {
      console.error('Error importing LinkedIn profile:', error);
      toast({
        title: 'Import Failed',
        description: apiErrorDetail(
          error,
          'Failed to import from LinkedIn. Make sure you logged in when the browser opened.'
        ),
        variant: 'destructive',
      });
    }
  };

  return (
    <div className="space-y-6">
      <div className="space-y-2">
        <div className="flex justify-between items-center">
          <Button
            variant="outline"
            onClick={() => handleLinkedInImport()}
            className="border-[#0077B5]/40 text-[#0077B5] hover:bg-[#0077B5]/10"
          >
            <svg className="h-4 w-4 mr-2" fill="currentColor" viewBox="0 0 24 24">
              <path d="M20.447 20.452h-3.554v-5.569c0-1.328-.027-3.037-1.852-3.037-1.853 0-2.136 1.445-2.136 2.939v5.667H9.351V9h3.414v1.561h.046c.477-.9 1.637-1.85 3.37-1.85 3.601 0 4.267 2.37 4.267 5.455v6.286zM5.337 7.433c-1.144 0-2.063-.926-2.063-2.065 0-1.138.92-2.063 2.063-2.063 1.14 0 2.064.925 2.064 2.063 0 1.139-.925 2.065-2.064 2.065zm1.782 13.019H3.555V9h3.564v11.452zM22.225 0H1.771C.792 0 0 .774 0 1.729v20.542C0 23.227.792 24 1.771 24h20.451C23.2 24 24 23.227 24 22.271V1.729C24 .774 23.2 0 22.222 0h.003z" />
            </svg>
            Import from LinkedIn
          </Button>
          <Button onClick={save} disabled={saving}>
            {saving ? 'Saving…' : 'Save Changes'}
          </Button>
        </div>
        {linkedInUrlPrompt && (
          <div className="flex items-center gap-2 p-3 border rounded-lg bg-muted/30">
            <input
              autoFocus
              type="url"
              placeholder="https://linkedin.com/in/your-profile"
              value={linkedInUrlInput}
              onChange={(e) => setLinkedInUrlInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && linkedInUrlInput.trim())
                  handleLinkedInImport(linkedInUrlInput.trim());
                if (e.key === 'Escape') setLinkedInUrlPrompt(false);
              }}
              className="flex-1 px-3 py-1.5 text-sm border rounded-md bg-background focus:outline-none focus:ring-2 focus:ring-[#0077B5]/40"
            />
            <Button
              size="sm"
              className="bg-[#0077B5] hover:bg-[#006097] text-white"
              disabled={!linkedInUrlInput.trim()}
              onClick={() => handleLinkedInImport(linkedInUrlInput.trim())}
            >
              Import
            </Button>
            <Button size="sm" variant="ghost" onClick={() => setLinkedInUrlPrompt(false)}>
              Cancel
            </Button>
          </div>
        )}
      </div>

      <ContactSections profile={profile} onChange={change} />
      <ExperienceSection profile={profile} onChange={change} />
      <EducationSection profile={profile} onChange={change} />
      <CertificationsSection profile={profile} onChange={change} />
      <GithubProjectsSection
        projects={projects}
        ingesting={ingesting}
        ingestionStatus={ingestionStatus}
        ingestionSummary={ingestionSummary}
        onRefresh={refreshRepos}
      />
      <SkillsAndAchievements profile={profile} onChange={change} />

      {/* Save Button (bottom) */}
      <div className="flex justify-end">
        <Button onClick={save} disabled={saving} size="lg">
          {saving ? 'Saving…' : 'Save Changes'}
        </Button>
      </div>
    </div>
  );
}
