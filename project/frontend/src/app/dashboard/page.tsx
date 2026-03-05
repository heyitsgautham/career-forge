'use client';

import { useState, useEffect } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import Link from 'next/link';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { 
  FileText, 
  FolderGit2, 
  Briefcase, 
  LayoutTemplate,
  Plus,
  Github,
  LogOut,
  Settings,
  Menu,
  User
} from 'lucide-react';
import { ProjectsList } from '@/components/dashboard/projects-list';
import { JobsList } from '@/components/dashboard/jobs-list';
import { ResumesList } from '@/components/dashboard/resumes-list';
import { TemplatesList } from '@/components/dashboard/templates-list';
import { ProfileView } from '@/components/dashboard/profile-view';
import { useToast } from '@/hooks/use-toast';

export default function DashboardPage() {
  const [activeTab, setActiveTab] = useState('resumes');
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [showSettings, setShowSettings] = useState(false);
  const [currentUser, setCurrentUser] = useState<any>(null);
  const [githubStatus, setGithubStatus] = useState<any>(null);
  const [linkedinStatus, setLinkedinStatus] = useState<any>(null);
  const router = useRouter();
  const searchParams = useSearchParams();
  const { toast } = useToast();

  // Handle OAuth callback params
  useEffect(() => {
    const github = searchParams.get('github');
    const linkedin = searchParams.get('linkedin');
    const token = searchParams.get('token');
    const error = searchParams.get('error');

    if (github === 'connected') {
      if (token) {
        localStorage.setItem('token', token);
        toast({ title: 'GitHub connected!', description: 'Your account is now linked.' });
      } else {
        toast({ title: 'GitHub connected!', description: 'Authorization successful.' });
      }
      router.replace('/dashboard');
    }

    if (linkedin === 'connected') {
      toast({ 
        title: 'LinkedIn connected!', 
        description: 'You can now import certifications from LinkedIn.' 
      });
      // Reload statuses
      window.location.reload();
    }

    if (error) {
      toast({ 
        title: 'Connection failed', 
        description: `Error: ${error.replace(/_/g, ' ')}`,
        variant: 'destructive'
      });
      router.replace('/dashboard');
    }
  }, [searchParams, router, toast]);

  // Load current user info
  useEffect(() => {
    const loadUser = async () => {
      try {
        const token = localStorage.getItem('token');
        if (!token) {
          router.push('/login');
          return;
        }

        const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
        
        const response = await fetch(`${apiUrl}/api/auth/profile`, {
          headers: { 'Authorization': `Bearer ${token}` }
        });
        
        if (response.ok) {
          const userData = await response.json();
          setCurrentUser(userData);
          
          // Load GitHub connection status
          const githubResponse = await fetch(`${apiUrl}/api/auth/github/status`, {
            headers: { 'Authorization': `Bearer ${token}` }
          });
          if (githubResponse.ok) {
            const githubData = await githubResponse.json();
            setGithubStatus(githubData);
          }
          
          // Load LinkedIn connection status
          const linkedinResponse = await fetch(`${apiUrl}/api/auth/linkedin/status`, {
            headers: { 'Authorization': `Bearer ${token}` }
          });
          if (linkedinResponse.ok) {
            const linkedinData = await linkedinResponse.json();
            setLinkedinStatus(linkedinData);
          }
        } else if (response.status === 401) {
          localStorage.removeItem('token');
          router.push('/login');
        }
      } catch (error) {
        console.error('Failed to load user:', error);
      }
    };
    
    loadUser();
  }, [router]);

  const handleLogout = () => {
    localStorage.removeItem('token');
    toast({ title: 'Logged out successfully' });
    router.push('/login');
  };

  const handleGithubConnect = () => {
    const clientId = 'Ov23li7PyDbHv0U1oqbZ';
    const appUrl = process.env.NEXT_PUBLIC_APP_URL || 'http://localhost:3000';
    const redirectUri = encodeURIComponent(`${appUrl}/api/auth/callback/github`);
    const scope = encodeURIComponent('read:user user:email repo');
    const authUrl = `https://github.com/login/oauth/authorize?client_id=${clientId}&redirect_uri=${redirectUri}&scope=${scope}`;
    console.log('Redirecting to GitHub OAuth:', authUrl);
    window.location.href = authUrl;
  };

  const handleLinkedInConnect = async () => {
    try {
      const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
      const response = await fetch(`${apiUrl}/api/auth/linkedin/authorize`, {
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('token')}`
        }
      });
      const data = await response.json();
      if (data.authorization_url) {
        window.location.href = data.authorization_url;
      } else {
        toast({
          title: 'Configuration Error',
          description: data.detail || 'LinkedIn OAuth not configured. Please set LINKEDIN_CLIENT_ID in backend/.env',
          variant: 'destructive'
        });
      }
    } catch (error) {
      toast({
        title: 'Error',
        description: 'Failed to initiate LinkedIn connection',
        variant: 'destructive'
      });
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 via-indigo-50 to-purple-50 dark:from-gray-900 dark:via-blue-950 dark:to-purple-950 flex">
      {/* Sidebar */}
      <aside className={`${sidebarOpen ? 'w-64' : 'w-16'} border-r bg-gradient-to-b from-white to-blue-50 dark:from-gray-900 dark:to-gray-800 transition-all duration-200 relative shadow-lg`}>
        <div className="p-4 border-b flex items-center justify-between">
          {sidebarOpen && (
            <div className="flex items-center gap-2">
              <FileText className="h-6 w-6" />
              <span className="font-bold">Resume Agent</span>
            </div>
          )}
          <Button 
            variant="ghost" 
            size="icon" 
            onClick={() => setSidebarOpen(!sidebarOpen)}
          >
            <Menu className="h-5 w-5" />
          </Button>
        </div>
        
        <nav className="p-2 space-y-1">
          <SidebarItem 
            icon={<FileText className="h-5 w-5" />} 
            label="Resumes" 
            active={activeTab === 'resumes'}
            onClick={() => setActiveTab('resumes')}
            collapsed={!sidebarOpen}
          />
          <SidebarItem 
            icon={<FolderGit2 className="h-5 w-5" />} 
            label="Projects" 
            active={activeTab === 'projects'}
            onClick={() => setActiveTab('projects')}
            collapsed={!sidebarOpen}
          />
          <SidebarItem 
            icon={<Briefcase className="h-5 w-5" />} 
            label="Job Descriptions" 
            active={activeTab === 'jobs'}
            onClick={() => setActiveTab('jobs')}
            collapsed={!sidebarOpen}
          />
          <SidebarItem 
            icon={<LayoutTemplate className="h-5 w-5" />} 
            label="Templates" 
            active={activeTab === 'templates'}
            onClick={() => setActiveTab('templates')}
            collapsed={!sidebarOpen}
          />
        </nav>

{/* <script src="https://platform.linkedin.com/badges/js/profile.js" async defer type="text/javascript"></script>
        <div class="badge-base LI-profile-badge" data-locale="en_US" data-size="medium" data-theme="dark" data-type="VERTICAL" data-vanity="hiruthik-sudhakar" data-version="v1"><a class="badge-base__link LI-simple-link" href="https://in.linkedin.com/in/hiruthik-sudhakar?trk=profile-badge">Hiruthik Sudhakar</a></div>
               */}
        
        <div className="absolute bottom-0 left-0 right-0 p-2 border-t bg-gradient-to-r from-blue-50 to-purple-50 dark:from-gray-800 dark:to-gray-700">
          <SidebarItem 
            icon={<User className="h-5 w-5" />} 
            label="Profile" 
            active={activeTab === 'profile'}
            onClick={() => setActiveTab('profile')}
            collapsed={!sidebarOpen}
          />
          <SidebarItem 
            icon={<Settings className="h-5 w-5" />} 
            label="Settings" 
            onClick={() => setShowSettings(true)}
            collapsed={!sidebarOpen}
          />
          <SidebarItem 
            icon={<LogOut className="h-5 w-5" />} 
            label="Logout" 
            onClick={handleLogout}
            collapsed={!sidebarOpen}
          />
        </div>
      </aside>

      {/* Main Content */}
      <main className="flex-1 overflow-auto bg-white/50 dark:bg-gray-900/50">
        {/* Header */}
        <header className="border-b bg-gradient-to-r from-white via-blue-50 to-purple-50 dark:from-gray-900 dark:via-blue-950 dark:to-purple-950 p-4 flex justify-between items-center shadow-sm">
          <div>
            <h1 className="text-2xl font-bold capitalize">{activeTab}</h1>
            <p className="text-muted-foreground">
              {activeTab === 'resumes' && 'Manage and generate your resumes'}
              {activeTab === 'projects' && 'Your imported projects and repositories'}
              {activeTab === 'jobs' && 'Job descriptions to tailor resumes to'}
              {activeTab === 'templates' && 'LaTeX templates for your resumes'}
              {activeTab === 'profile' && 'View and edit your profile information'}
            </p>
          </div>
          <div className="flex gap-3 items-center">
            {currentUser && (
              <div className="text-sm text-right mr-2">
                <p className="font-medium">{currentUser.name || currentUser.email}</p>
                <p className="text-xs text-muted-foreground">{currentUser.email}</p>
              </div>
            )}
            {githubStatus?.connected ? (
              <Button variant="outline" className="gap-2 border-green-300 dark:border-green-700 bg-gradient-to-r from-green-50 to-emerald-100 dark:from-green-950 dark:to-emerald-950 shadow-md" onClick={handleGithubConnect}>
                <Github className="h-4 w-4 text-green-600 dark:text-green-400" />
                <div className="flex flex-col items-start">
                  <span className="text-xs text-green-900 dark:text-green-100">GitHub Connected</span>
                  <span className="text-xs text-green-700 dark:text-green-300">@{githubStatus.username}</span>
                </div>
              </Button>
            ) : (
              <Button variant="outline" className="gap-2" onClick={handleGithubConnect}>
                <Github className="h-4 w-4" />
                Connect GitHub
              </Button>
            )}
          </div>
        </header>

        {/* Content */}
        <div className="p-6">
          {activeTab === 'resumes' && <ResumesList />}
          {activeTab === 'projects' && <ProjectsList />}
          {activeTab === 'jobs' && <JobsList />}
          {activeTab === 'templates' && <TemplatesList />}
          {activeTab === 'profile' && <ProfileView />}
        </div>
      </main>

      {/* Settings Modal */}
      {showSettings && (
        <div className="fixed inset-0 bg-black/50 backdrop-blur-sm flex items-center justify-center z-50" onClick={() => setShowSettings(false)}>
          <Card className="w-full max-w-md border-2 border-purple-200 dark:border-purple-800 shadow-2xl shadow-purple-500/20" onClick={(e) => e.stopPropagation()}>
            <CardHeader>
              <CardTitle>Profile Settings</CardTitle>
              <CardDescription>Manage your account settings and upload resume for auto-fill</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="space-y-2">
                <p className="text-sm font-medium">Upload Resume</p>
                <p className="text-xs text-muted-foreground">Upload your existing resume to auto-fill profile fields</p>
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
                      const token = localStorage.getItem('token');
                      const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
                      const response = await fetch(`${apiUrl}/api/auth/upload-resume`, {
                        method: 'POST',
                        headers: { 'Authorization': `Bearer ${token}` },
                        body: formData,
                      });

                      const data = await response.json();
                      if (response.ok) {
                        toast({ 
                          title: 'Resume uploaded!', 
                          description: `Successfully extracted ${data.fields_updated} profile fields. Check the Profile tab!` 
                        });
                        // Reload user data to show updated name
                        const userResponse = await fetch(`${apiUrl}/api/auth/profile`, {
                          headers: { 'Authorization': `Bearer ${token}` }
                        });
                        if (userResponse.ok) {
                          const userData = await userResponse.json();
                          setCurrentUser(userData);
                        }
                        setShowSettings(false);
                      } else {
                        toast({ 
                          title: 'Upload failed', 
                          description: data.detail || 'Could not process resume',
                          variant: 'destructive'
                        });
                      }
                    } catch (error) {
                      toast({ 
                        title: 'Upload error', 
                        description: 'Failed to upload resume',
                        variant: 'destructive'
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
                  <FileText className="h-4 w-4" />
                  Upload Resume (PDF/DOCX/TXT)
                </Button>
              </div>
              
              <div className="space-y-2 pt-2 border-t">
                <p className="text-sm font-medium">GitHub Integration</p>
                {githubStatus?.connected ? (
                  <div className="space-y-2">
                    <div className="flex items-center gap-2 p-3 bg-green-50 dark:bg-green-950 rounded-lg border border-green-200 dark:border-green-800">
                      <Github className="h-4 w-4 text-green-600 dark:text-green-400" />
                      <div className="flex-1">
                        <p className="text-sm font-medium text-green-900 dark:text-green-100">Connected</p>
                        <p className="text-xs text-green-700 dark:text-green-300">@{githubStatus.username}</p>
                      </div>
                    </div>
                    <Button variant="outline" className="w-full gap-2" onClick={handleGithubConnect}>
                      <Github className="h-4 w-4" />
                      Reconnect GitHub
                    </Button>
                  </div>
                ) : (
                  <Button variant="outline" className="w-full gap-2" onClick={handleGithubConnect}>
                    <Github className="h-4 w-4" />
                    Connect GitHub Account
                  </Button>
                )}
              </div>
              
              <div className="space-y-2 pt-2 border-t">
                <p className="text-sm font-medium">LinkedIn Certifications</p>
                <p className="text-xs text-muted-foreground">
                  Add your LinkedIn URL in the Profile tab to import certifications automatically.
                </p>
              </div>
              
              <div className="pt-4 border-t">
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

function SidebarItem({
  icon,
  label,
  active = false,
  onClick,
  collapsed = false,
}: {
  icon: React.ReactNode;
  label: string;
  active?: boolean;
  onClick: () => void;
  collapsed?: boolean;
}) {
  return (
    <button
      onClick={onClick}
      className={`w-full flex items-center gap-3 px-3 py-2 rounded-lg transition-all ${
        active 
          ? 'bg-gradient-to-r from-blue-500 to-purple-600 text-white shadow-lg shadow-blue-500/50' 
          : 'hover:bg-gradient-to-r hover:from-blue-50 hover:to-purple-50 dark:hover:from-blue-950 dark:hover:to-purple-950 text-muted-foreground hover:text-foreground'
      }`}
    >
      {icon}
      {!collapsed && <span>{label}</span>}
    </button>
  );
}
