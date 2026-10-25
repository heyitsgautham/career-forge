'use client';

import { useState, useEffect, useCallback, useRef } from 'react';
import { Button } from '@/components/ui/button';
import { useToast } from '@/hooks/use-toast';
import api, { githubApi } from '@/lib/api';

import type { IngestionSummary, ProfileData } from './profile/types';
import { ContactSections } from './profile/contact-sections';
import { ExperienceSection } from './profile/experience-section';
import { EducationSection } from './profile/education-section';
import { CertificationsSection } from './profile/certifications-section';
import { GithubProjectsSection } from './profile/github-projects-section';
import { SkillsAndAchievements } from './profile/skills-achievements';
import { apiErrorDetail } from '@/lib/api-error';

export function ProfileView({ externalRefreshKey = 0 }: { externalRefreshKey?: number }) {
  const [profile, setProfile] = useState<ProfileData | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const { toast } = useToast();

  // GitHub ingestion state
  const [ingesting, setIngesting] = useState(false);
  const [linkedInUrlPrompt, setLinkedInUrlPrompt] = useState(false);
  const [linkedInUrlInput, setLinkedInUrlInput] = useState('');
  const [ingestionStatus, setIngestionStatus] = useState<string>('none');
  const [ingestionSummary, setIngestionSummary] = useState<IngestionSummary | null>(null);
  const [projects, setProjects] = useState<Array<Record<string, unknown>>>([]);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    loadProfile();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [externalRefreshKey]);

  // Poll ingestion status and load projects on mount
  const stopPolling = useCallback(() => {
    if (pollRef.current) {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }
  }, []);

  const loadProjects = useCallback(async () => {
    try {
      const res = await githubApi.listProjects();
      setProjects(res.data as Array<Record<string, unknown>>);
    } catch {
      /* ignore */
    }
  }, []);

  const pollCountRef = useRef(0);
  const MAX_POLLS = 40; // 40 × 3s = 2 minutes max

  const pollIngestionStatus = useCallback(async () => {
    try {
      const res = await githubApi.getIngestStatus();
      const s = res.data.status;
      setIngestionStatus(s);
      setIngestionSummary(res.data.summary);

      if (s === 'done') {
        stopPolling();
        setIngesting(false);
        await loadProjects();
        // Reload profile so newly-added skills appear immediately
        try {
          const profileRes = await api.get('/api/auth/profile');
          setProfile(profileRes.data);
        } catch {}
        toast({
          title: 'Import Complete',
          description: `${res.data.summary?.processed ?? 0} projects imported.`,
        });
      } else if (s === 'failed' || s === 'stale') {
        stopPolling();
        setIngesting(false);
        if (s === 'stale') {
          toast({
            title: 'Import Timed Out',
            description: 'The previous import did not complete. Please try again.',
            variant: 'destructive',
          });
        } else {
          toast({
            title: 'Import Failed',
            description: 'Check your GitHub connection and try again.',
            variant: 'destructive',
          });
        }
      } else {
        // Safety cap: stop polling after MAX_POLLS attempts
        pollCountRef.current += 1;
        if (pollCountRef.current >= MAX_POLLS) {
          stopPolling();
          setIngesting(false);
          toast({
            title: 'Import Timed Out',
            description: 'The import is taking too long. Please try again.',
            variant: 'destructive',
          });
        }
      }
    } catch {
      stopPolling();
      setIngesting(false);
    }
  }, [stopPolling, loadProjects, toast]);

  const startPolling = useCallback(() => {
    stopPolling();
    pollCountRef.current = 0;
    setIngesting(true);
    pollRef.current = setInterval(pollIngestionStatus, 3000);
    // Also poll immediately
    pollIngestionStatus();
  }, [stopPolling, pollIngestionStatus]);

  useEffect(() => {
    // On mount: only resume polling if a sync is actively running.
    // Never auto-trigger a new sync — user must click the button.
    (async () => {
      try {
        const res = await githubApi.getIngestStatus();
        const s = res.data.status;
        setIngestionStatus(s);
        setIngestionSummary(res.data.summary);
        if (s === 'in_progress') {
          startPolling();
        }
      } catch {
        /* ignore */
      }
      await loadProjects();
    })();
    return () => stopPolling();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handleRefreshRepos = async () => {
    setIngesting(true);
    try {
      await githubApi.ingest(false);
      // Ingest is synchronous — skills are already updated in DynamoDB.
      // Reload profile immediately so the skills field reflects the new data.
      try {
        const profileRes = await api.get('/api/auth/profile');
        setProfile(profileRes.data);
      } catch {
        /* silent — UI still shows old skills */
      }
      await loadProjects();
      setIngesting(false);
      setIngestionStatus('done');
      toast({ title: 'Sync complete', description: 'Projects refreshed and skills updated.' });
    } catch {
      // Ingest may be running as a background job — fall back to polling.
      startPolling();
    }
  };

  const loadProfile = async () => {
    try {
      setLoading(true);
      const response = await api.get('/api/auth/profile');
      setProfile(response.data);
    } catch (error: unknown) {
      const msg = apiErrorDetail(error, 'Failed to load profile');
      toast({
        title: 'Error',
        description: msg,
        variant: 'destructive',
      });
    } finally {
      setLoading(false);
    }
  };

  const handleSave = async () => {
    if (!profile) return;

    try {
      setSaving(true);
      const response = await api.put('/api/auth/profile', {
        name: profile.name,
        headline: profile.headline,
        summary: profile.summary,
        location: profile.location,
        phone: profile.phone,
        website: profile.website,
        linkedin_url: profile.linkedin_url,
        address_line1: profile.address_line1,
        address_line2: profile.address_line2,
        city: profile.city,
        state: profile.state,
        zip_code: profile.zip_code,
        country: profile.country,
        institution: profile.institution,
        degree: profile.degree,
        field_of_study: profile.field_of_study,
        graduation_year: profile.graduation_year,
        experience: profile.experience,
        education: profile.education,
        skills: profile.skills,
        certifications: profile.certifications,
        achievements: profile.achievements,
      });
      setProfile(response.data);
      toast({
        title: 'Success',
        description: 'Profile updated successfully',
      });
    } catch (error: unknown) {
      const msg = apiErrorDetail(error, 'Failed to save profile');
      toast({
        title: 'Error',
        description: msg,
        variant: 'destructive',
      });
    } finally {
      setSaving(false);
    }
  };

  const handleChange = (field: keyof ProfileData, value: any) => {
    if (profile) {
      setProfile({ ...profile, [field]: value });
    }
  };

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
        const updatedProfile = await api.get('/api/auth/profile');
        setProfile(updatedProfile.data);

        const imp = response.data.imported;
        const parts: string[] = [];
        if (imp?.education_added) parts.push(`${imp.education_added} education`);
        if (imp?.certifications_added) parts.push(`${imp.certifications_added} certifications`);
        if (imp?.name) parts.push('name');
        if (imp?.headline) parts.push('headline');
        if (imp?.location) parts.push('location');
        if (imp?.email) parts.push('email');
        if (imp?.phone) parts.push('phone');
        if (imp?.website) parts.push('website');

        toast({
          title: 'Import Complete!',
          description:
            parts.length > 0
              ? `Imported: ${parts.join(', ')}`
              : 'Profile imported (no new data found).',
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
          <Button onClick={handleSave} disabled={saving}>
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

      <ContactSections profile={profile} onChange={handleChange} />
      <ExperienceSection profile={profile} onChange={handleChange} />
      <EducationSection profile={profile} onChange={handleChange} />
      <CertificationsSection profile={profile} onChange={handleChange} />
      <GithubProjectsSection
        projects={projects}
        ingesting={ingesting}
        ingestionStatus={ingestionStatus}
        ingestionSummary={ingestionSummary}
        onRefresh={handleRefreshRepos}
      />
      <SkillsAndAchievements profile={profile} onChange={handleChange} />

      {/* Save Button (bottom) */}
      <div className="flex justify-end">
        <Button onClick={handleSave} disabled={saving} size="lg">
          {saving ? 'Saving…' : 'Save Changes'}
        </Button>
      </div>
    </div>
  );
}
