'use client';

import { useState, useEffect, useCallback, Suspense } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import Link from 'next/link';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Github, LogOut, Settings, Menu, User } from 'lucide-react';
import { ProjectsList } from '@/components/dashboard/projects-list';
import { JobsList } from '@/components/dashboard/jobs-list';
import { ResumesList } from '@/components/dashboard/resumes-list';
import { TemplatesList } from '@/components/dashboard/templates-list';
import { ProfileView } from '@/components/dashboard/profile-view';
import { SettingsModal } from '@/components/dashboard/settings-modal';
import { SkillGapShell } from '@/components/dashboard/skill-gap-shell';
import { JobScoutShell } from '@/components/dashboard/job-scout-shell';
import { ApplyTrackShell } from '@/components/dashboard/apply-shell';
import { ProjectRoadmapShell } from '@/components/dashboard/project-roadmap-shell';
import {
  TABS,
  TAB_DESCRIPTIONS,
  TAB_TITLES,
  parseTab,
  type TabKey,
} from '@/components/dashboard/dashboard-tabs';
import { SidebarItem } from '@/components/dashboard/sidebar-item';
import { useToast } from '@/hooks/use-toast';
import { clearCachedData } from '@/lib/query-cache';
import { userApi, authApi, projectsApi, resumesApi, jobMatchApi, skillGapApi } from '@/lib/api';
import type { User as UserType } from '@/lib/api';

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
    staleTime: 10 * 60 * 1000, // 10 min
    gcTime: 30 * 60 * 1000, // 30 min
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
  const switchTab = useCallback((tab: TabKey) => {
    setActiveTab(tab);
    const url = new URL(window.location.href);
    url.searchParams.set('tab', tab);
    window.history.replaceState(null, '', url.toString());
  }, []);

  /* Sync active tab from URL param on client mount */
  useEffect(() => {
    const tab = parseTab(searchParams.get('tab'));
    if (tab) {
      setActiveTab(tab);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []); // only on mount — switchTab() keeps URL in sync for all subsequent changes

  /* Handle OAuth callback query params */
  useEffect(() => {
    const github = searchParams.get('github');
    const google = searchParams.get('google');
    const token = new URLSearchParams(window.location.hash.slice(1)).get('token');
    const error = searchParams.get('error');

    if (github === 'connected' || google === 'connected') {
      if (token) {
        localStorage.setItem('token', token);
        void clearCachedData(queryClient);
      }
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
  }, [searchParams, router, toast, queryClient]);

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
      queryFn: () => resumesApi.list().then((r) => r.data),
      staleTime: 2 * 60 * 1000,
    });
    queryClient.prefetchQuery({
      queryKey: ['projects'],
      queryFn: () => projectsApi.list().then((r) => r.data),
      staleTime: 5 * 60 * 1000,
    });
    queryClient.prefetchQuery({
      queryKey: ['skill-gap-roles'],
      queryFn: () => skillGapApi.getRoles().then((r) => r.data.roles || []),
      staleTime: 60 * 60 * 1000,
    });
  }, [queryClient]);

  const handleLogout = () => {
    localStorage.removeItem('token');
    void clearCachedData(queryClient);
    toast({ title: 'Logged out successfully' });
    router.push('/login');
  };

  /* ── Hover-prefetch map: tab key → prefetch function ────────────────── */
  const prefetchTab = useCallback(
    (tab: string) => {
      switch (tab) {
        case 'resumes':
          queryClient.prefetchQuery({
            queryKey: ['resumes'],
            queryFn: () => resumesApi.list().then((r) => r.data),
            staleTime: 2 * 60 * 1000,
          });
          break;
        case 'projects':
          queryClient.prefetchQuery({
            queryKey: ['projects'],
            queryFn: () => projectsApi.list().then((r) => r.data),
            staleTime: 5 * 60 * 1000,
          });
          break;
        case 'skill-gap':
          queryClient.prefetchQuery({
            queryKey: ['skill-gap-roles'],
            queryFn: () => skillGapApi.getRoles().then((r) => r.data.roles || []),
            staleTime: 60 * 60 * 1000,
          });
          break;
        case 'job-scout':
          queryClient.prefetchQuery({
            queryKey: ['job-scout-matches'],
            queryFn: () => jobMatchApi.list().then((r) => r.data),
            staleTime: 30_000,
          });
          break;
      }
    },
    [queryClient]
  );

  return (
    <div className="flex h-screen overflow-hidden">
      {/* ─── Sidebar ─────────────────────────────────────────────────────── */}
      <aside
        className={`${
          sidebarOpen ? 'w-64' : 'w-16'
        } shrink-0 border-r border-border/60 bg-card backdrop-blur-sm transition-all duration-300 sticky top-0 h-screen flex flex-col overflow-hidden`}
      >
        {/* Brand */}
        <div className="flex h-14 items-center gap-2 border-b border-border/60 px-3">
          {sidebarOpen && (
            <Link
              href="/"
              className="group flex items-center gap-2 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring rounded-md"
            >
              <img
                src="/logo.svg"
                alt="CareerForge logo"
                className="h-10 w-10 rounded-full bg-white p-0.5 object-contain shadow-md shadow-primary/25 transition-all duration-300 group-hover:shadow-lg group-hover:shadow-primary/30 group-hover:scale-105"
              />
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
        <header className="sticky top-0 z-10 flex h-14 shrink-0 items-center justify-between gap-4 border-b border-border/60 bg-card/80 backdrop-blur-xl px-6">
          <div className="min-w-0">
            <h1 className="text-lg font-semibold capitalize truncate">{TAB_TITLES[activeTab]}</h1>
            <p className="text-xs text-muted-foreground truncate hidden sm:block">
              {TAB_DESCRIPTIONS[activeTab]}
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

            {mounted &&
              (githubConnected ? (
                <Badge
                  variant="outline"
                  className="gap-1.5 border-[hsl(var(--success))]/30 bg-[hsl(var(--success))]/5 text-[hsl(var(--success))] cursor-default"
                >
                  <Github className="h-3 w-3" aria-hidden="true" />@{githubUsername}
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
          {activeTab === 'roadmap' && <ProjectRoadmapShell />}
          {activeTab === 'skill-gap' && <SkillGapShell />}
          {activeTab === 'job-scout' && <JobScoutShell />}
          {activeTab === 'apply' && <ApplyTrackShell />}
          {activeTab === 'profile' && <ProfileView externalRefreshKey={profileRefreshKey} />}
        </div>
      </main>

      {/* ─── Settings Modal ──────────────────────────────────────────────── */}
      {showSettings && (
        <SettingsModal
          githubConnected={githubConnected}
          githubUsername={githubUsername}
          onClose={() => setShowSettings(false)}
          onResumeUploaded={() => setProfileRefreshKey((k) => k + 1)}
          onLogout={handleLogout}
        />
      )}
    </div>
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
