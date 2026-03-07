'use client';

import { useState, useEffect, useCallback, Suspense } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import Link from 'next/link';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import {
  FileText,
  FolderGit2,
  Target,
  Search,
  Send,
  Github,
  LogOut,
  Settings,
  Menu,
  User,
  Upload,
  X,
} from 'lucide-react';
import { ProjectsList } from '@/components/dashboard/projects-list';
import { JobsList } from '@/components/dashboard/jobs-list';
import { ResumesList } from '@/components/dashboard/resumes-list';
import { TemplatesList } from '@/components/dashboard/templates-list';
import { ProfileView } from '@/components/dashboard/profile-view';
import { SkillGapShell } from '@/components/dashboard/skill-gap-shell';
import { JobScoutShell } from '@/components/dashboard/job-scout-shell';
import { ApplyTrackShell } from '@/components/dashboard/apply-shell';
import { useToast } from '@/hooks/use-toast';
import { userApi, authApi, projectsApi, resumesApi, jobMatchApi, skillGapApi } from '@/lib/api';
import type { User as UserType } from '@/lib/api';

/* ─── Tab definitions ────────────────────────────────────────────────────── */
const TABS = [
  { key: 'resumes', label: 'Resumes', icon: FileText },
  { key: 'projects', label: 'Projects', icon: FolderGit2 },
  { key: 'skill-gap', label: 'Skill Gap', icon: Target },
  { key: 'job-scout', label: 'Job Scout', icon: Search },
  { key: 'apply', label: 'Apply & Track', icon: Send },
] as const;

// Hidden tabs — still routable via ?tab= but removed from sidebar
const HIDDEN_TABS = ['jobs', 'templates'] as const;

type TabKey = (typeof TABS)[number]['key'] | (typeof HIDDEN_TABS)[number] | 'profile';

/* ─── Dashboard inner (needs Suspense for useSearchParams) ───────────────── */
function DashboardInner() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { toast } = useToast();

  // Always start with 'resumes' on the server to avoid SSR ↔ client hydration
  // mismatch (server doesn't know the URL's ?tab= during pre-render).
  // Sync to the actual URL param in useEffect — runs only on the client.
  const [activeTab, setActiveTab] = useState<TabKey>('resumes');
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [showSettings, setShowSettings] = useState(false);
  const [profileRefreshKey, setProfileRefreshKey] = useState(0);
  // mounted guard: prevents server/client HTML mismatch for query-driven header content
  const [mounted, setMounted] = useState(false);
  useEffect(() => setMounted(true), []);
  const queryClient = useQueryClient();

  /* ── User profile via React Query (cached, persisted) ──────────────── */
  const { data: currentUser } = useQuery({
    queryKey: ['user-profile'],
    queryFn: async () => {
      const res = await userApi.getProfile();
      return res.data as UserType;
    },
    staleTime: 10 * 60 * 1000,   // 10 min
    gcTime: 30 * 60 * 1000,      // 30 min
    retry: false,
  });

  const { data: githubStatusData } = useQuery({
    queryKey: ['github-status'],
    queryFn: async () => {
      const res = await userApi.getGithubStatus();
      return res.data as { connected: boolean; username?: string };
    },
    staleTime: 10 * 60 * 1000,
    gcTime: 30 * 60 * 1000,
    retry: false,
  });

  const githubConnected = githubStatusData?.connected ?? false;
  const githubUsername = githubStatusData?.username ?? '';

  /* URL-sync: update ?tab= when activeTab changes */
  const switchTab = useCallback(
    (tab: TabKey) => {
      setActiveTab(tab);
      const url = new URL(window.location.href);
      url.searchParams.set('tab', tab);
      window.history.replaceState(null, '', url.toString());
    },
    []
  );

  /* Sync active tab from URL param on client mount */
  useEffect(() => {
    const tab = searchParams.get('tab') as TabKey;
    if (tab && TABS.some(t => t.key === (tab as string))) {
      setActiveTab(tab);
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []); // only on mount — switchTab() keeps URL in sync for all subsequent changes

  /* Handle OAuth callback query params */
  useEffect(() => {
    const github = searchParams.get('github');
    const google = searchParams.get('google');
    const token = searchParams.get('token');
    const error = searchParams.get('error');

    if (github === 'connected' || google === 'connected') {
      if (token) localStorage.setItem('token', token);
      const provider = github ? 'GitHub' : 'Google';
      toast({ title: `${provider} connected!`, description: 'Your account is now linked.' });
      router.replace('/dashboard');
    }
    if (error) {
      toast({
        title: 'Connection failed',
        description: `Error: ${error.replace(/_/g, ' ')}`,
        variant: 'destructive',
      });
      router.replace('/dashboard');
    }
  }, [searchParams, router, toast]);

  /* Load user + github status */
  useEffect(() => {
    const token = localStorage.getItem('token');
    if (!token) {
      router.push('/login');
    }
  }, [router]);

  /* ── Prefetch all tab data on mount ─────────────────────────────────── */
  useEffect(() => {
    queryClient.prefetchQuery({
      queryKey: ['resumes'],
      queryFn: () => resumesApi.list().then(r => r.data),
      staleTime: 2 * 60 * 1000,
    });
    queryClient.prefetchQuery({
      queryKey: ['projects'],
      queryFn: () => projectsApi.list().then(r => r.data),
      staleTime: 5 * 60 * 1000,
    });
    queryClient.prefetchQuery({
      queryKey: ['skill-gap-roles'],
      queryFn: () => skillGapApi.getRoles().then(r => r.data.roles || []),
      staleTime: 60 * 60 * 1000,
    });
  }, [queryClient]);

  const handleLogout = () => {
    localStorage.removeItem('token');
    toast({ title: 'Logged out successfully' });
    router.push('/login');
  };

  /* ── Hover-prefetch map: tab key → prefetch function ────────────────── */
  const prefetchTab = useCallback((tab: string) => {
    switch (tab) {
      case 'resumes':
        queryClient.prefetchQuery({ queryKey: ['resumes'], queryFn: () => resumesApi.list().then(r => r.data), staleTime: 2 * 60 * 1000 });
        break;
      case 'projects':
        queryClient.prefetchQuery({ queryKey: ['projects'], queryFn: () => projectsApi.list().then(r => r.data), staleTime: 5 * 60 * 1000 });
        break;
      case 'skill-gap':
        queryClient.prefetchQuery({ queryKey: ['skill-gap-roles'], queryFn: () => skillGapApi.getRoles().then(r => r.data.roles || []), staleTime: 60 * 60 * 1000 });
        break;
      case 'job-scout':
        queryClient.prefetchQuery({ queryKey: ['job-scout-matches'], queryFn: () => jobMatchApi.list().then(r => r.data), staleTime: 30_000 });
        break;
    }
  }, [queryClient]);

  /* Tab → Content mapping */
  const tabDescription: Record<TabKey, string> = {
    resumes: 'Generate and manage your LaTeX resumes',
    projects: 'Your imported projects and repositories',
    jobs: 'Job descriptions to tailor resumes to',
    templates: 'LaTeX templates for your resumes',
    'skill-gap': 'AI-powered gap analysis against target roles',
    'job-scout': 'Matched jobs ranked by fit',
    apply: 'Generate tailored resumes and track applications',
    profile: 'View and edit your profile information',
  };

  return (
    <div className="flex h-screen overflow-hidden">
      {/* ─── Sidebar ─────────────────────────────────────────────────────── */}
      <aside
        className={`${sidebarOpen ? 'w-64' : 'w-16'
          } shrink-0 border-r border-border/60 bg-card backdrop-blur-sm transition-all duration-300 sticky top-0 h-screen flex flex-col overflow-hidden`}
      >
        {/* Brand */}
        <div className="flex h-14 items-center gap-2 border-b border-border/60 px-3">
          {sidebarOpen && (
            <Link
              href="/"
              className="group flex items-center gap-2 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring rounded-md"
            >
              <img src="/logo.svg" alt="CareerForge logo" className="h-10 w-10 rounded-full bg-white p-0.5 object-contain shadow-md shadow-primary/25 transition-all duration-300 group-hover:shadow-lg group-hover:shadow-primary/30 group-hover:scale-105" />
              <span className="font-bold text-base tracking-tight">CareerForge</span>
            </Link>
          )}
          <Button
            variant="ghost"
            size="icon"
            className="ml-auto shrink-0"
            onClick={() => setSidebarOpen(!sidebarOpen)}
            aria-label={sidebarOpen ? 'Collapse sidebar' : 'Expand sidebar'}
          >
            <Menu className="h-4 w-4" aria-hidden="true" />
          </Button>
        </div>

        {/* Nav items */}
        <nav className="flex-1 overflow-y-auto p-2 space-y-0.5" aria-label="Dashboard navigation">
          {TABS.map(({ key, label, icon: Icon }) => (
            <SidebarItem
              key={key}
              icon={<Icon className="h-4 w-4" aria-hidden="true" />}
              label={label}
              active={activeTab === key}
              onClick={() => switchTab(key)}
              onMouseEnter={() => prefetchTab(key)}
              collapsed={!sidebarOpen}
            />
          ))}
        </nav>

        {/* Bottom actions */}
        <div className="border-t border-border/60 p-2 space-y-0.5">
          <SidebarItem
            icon={<User className="h-4 w-4" aria-hidden="true" />}
            label="Profile"
            active={activeTab === 'profile'}
            onClick={() => switchTab('profile')}
            collapsed={!sidebarOpen}
          />
          <SidebarItem
            icon={<Settings className="h-4 w-4" aria-hidden="true" />}
            label="Settings"
            onClick={() => setShowSettings(true)}
            collapsed={!sidebarOpen}
          />
          <SidebarItem
            icon={<LogOut className="h-4 w-4" aria-hidden="true" />}
            label="Logout"
            onClick={handleLogout}
            collapsed={!sidebarOpen}
          />
        </div>
      </aside>

      {/* ─── Main ────────────────────────────────────────────────────────── */}
      <main className="flex-1 min-w-0 flex flex-col overflow-y-auto" id="main-content">
        {/* Header bar */}
        <header className="sticky top-0 z-10 flex h-14 items-center justify-between gap-4 border-b border-border/60 bg-card/80 backdrop-blur-xl px-6">
          <div className="min-w-0">
            <h1 className="text-lg font-semibold capitalize truncate">
              {activeTab === 'skill-gap'
                ? 'Skill Gap'
                : activeTab === 'job-scout'
                  ? 'Job Scout'
                  : activeTab === 'apply'
                    ? 'Apply & Track'
                    : activeTab}
            </h1>
            <p className="text-xs text-muted-foreground truncate hidden sm:block">
              {tabDescription[activeTab]}
            </p>
          </div>

          <div className="flex items-center gap-3 shrink-0">
            {mounted && currentUser && (
              <div className="text-right hidden md:block">
                <p className="text-sm font-medium truncate max-w-[160px]">
                  {currentUser.name || currentUser.email}
                </p>
                {currentUser.email && (
                  <p className="text-xs text-muted-foreground truncate max-w-[160px]">
                    {currentUser.email}
                  </p>
                )}
              </div>
            )}

            {mounted && (githubConnected ? (
              <Badge
                variant="outline"
                className="gap-1.5 border-[hsl(var(--success))]/30 bg-[hsl(var(--success))]/5 text-[hsl(var(--success))] cursor-default"
              >
                <Github className="h-3 w-3" aria-hidden="true" />
                @{githubUsername}
              </Badge>
            ) : (
              <Button
                variant="outline"
                size="sm"
                className="gap-1.5"
                onClick={() => authApi.githubInstall()}
              >
                <Github className="h-3.5 w-3.5" aria-hidden="true" />
                Connect GitHub
              </Button>
            ))}
          </div>
        </header>

        {/* Content */}
        <div className="flex-1 p-6 animate-fade-in-up">
          {activeTab === 'resumes' && <ResumesList />}
          {/* Always keep ProjectsList mounted so import state survives tab switches */}
          <div className={activeTab !== 'projects' ? 'hidden' : ''}>
            <ProjectsList />
          </div>
          {activeTab === 'jobs' && <JobsList />}
          {activeTab === 'templates' && <TemplatesList />}
          {activeTab === 'skill-gap' && <SkillGapShell />}
          {activeTab === 'job-scout' && <JobScoutShell />}
          {activeTab === 'apply' && <ApplyTrackShell />}
          {activeTab === 'profile' && <ProfileView externalRefreshKey={profileRefreshKey} />}
        </div>
      </main>

      {/* ─── Settings Modal ──────────────────────────────────────────────── */}
      {showSettings && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm"
          onClick={() => setShowSettings(false)}
          role="dialog"
          aria-modal="true"
          aria-label="Settings"
        >
          <Card
            className="w-full max-w-md shadow-xl"
            onClick={(e) => e.stopPropagation()}
          >
            <CardHeader className="flex flex-row items-start justify-between">
              <div>
                <CardTitle>Settings</CardTitle>
                <CardDescription>
                  Manage integrations and upload your resume
                </CardDescription>
              </div>
              <Button
                variant="ghost"
                size="icon"
                onClick={() => setShowSettings(false)}
                aria-label="Close settings"
              >
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
                      setProfileRefreshKey(k => k + 1);
                      setShowSettings(false);
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
                <Button variant="destructive" className="w-full" onClick={handleLogout}>
                  Logout
                </Button>
              </div>
            </CardContent>
          </Card>
        </div>
      )}
    </div>
  );
}

/* ─── Sidebar Item ───────────────────────────────────────────────────────── */
function SidebarItem({
  icon,
  label,
  active = false,
  onClick,
  onMouseEnter,
  collapsed = false,
}: {
  icon: React.ReactNode;
  label: string;
  active?: boolean;
  onClick: () => void;
  onMouseEnter?: () => void;
  collapsed?: boolean;
}) {
  return (
    <button
      onClick={onClick}
      onMouseEnter={onMouseEnter}
      className={`w-full flex items-center gap-3 rounded-xl px-3 py-2 text-sm transition-all duration-200 ${active
          ? 'bg-primary/10 text-primary font-medium shadow-sm border-l-2 border-primary'
          : 'text-muted-foreground hover:bg-primary/5 hover:text-foreground'
        }`}
      aria-current={active ? 'page' : undefined}
    >
      {icon}
      {!collapsed && <span className="truncate">{label}</span>}
    </button>
  );
}

/* ─── Page wrapper with Suspense for searchParams ────────────────────────── */
export default function DashboardPage() {
  return (
    <Suspense
      fallback={
        <div className="flex min-h-screen items-center justify-center">
          <div className="h-6 w-6 animate-spin rounded-full border-2 border-primary border-t-transparent" />
        </div>
      }
    >
      <DashboardInner />
    </Suspense>
  );
}
