import Link from 'next/link';
import { Button } from '@/components/ui/button';
import {
  FileText,
  Github,
  BarChart3,
  BookOpen,
  Briefcase,
  ArrowRight,
  Sparkles,
  Shield,
  Zap,
} from 'lucide-react';

export default function HomePage() {
  return (
    <div className="min-h-screen bg-background relative noise-bg">
      {/* Grid background */}
      <div
        className="absolute inset-0 opacity-[0.03] pointer-events-none"
        style={{
          backgroundImage:
            'linear-gradient(hsl(var(--foreground)) 1px, transparent 1px), linear-gradient(90deg, hsl(var(--foreground)) 1px, transparent 1px)',
          backgroundSize: '64px 64px',
        }}
      />

      {/* Header */}
      <header className="relative z-10 border-b border-border/50 bg-background/80 backdrop-blur-xl">
        <div className="container mx-auto px-6 py-4 flex justify-between items-center">
          <div className="flex items-center gap-2.5">
            <div className="h-8 w-8 rounded-md bg-primary flex items-center justify-center">
              <Sparkles className="h-4 w-4 text-primary-foreground" aria-hidden="true" />
            </div>
            <span className="font-bold text-lg tracking-tight">CareerForge</span>
          </div>
          <div className="flex items-center gap-3">
            <Link href="/login">
              <Button variant="ghost" size="sm">
                Sign In
              </Button>
            </Link>
            <Link href="/login">
              <Button size="sm" className="gap-2">
                <Github className="h-4 w-4" aria-hidden="true" />
                Get Started
              </Button>
            </Link>
          </div>
        </div>
      </header>

      {/* Hero */}
      <section className="relative z-10 container mx-auto px-6 pt-24 pb-20 text-center">
        {/* Badge */}
        <div className="inline-flex items-center gap-2 rounded-full border border-primary/30 bg-primary/5 px-4 py-1.5 text-sm text-primary mb-8">
          <Zap className="h-3.5 w-3.5" aria-hidden="true" />
          Powered by Amazon{'\u00A0'}Bedrock
        </div>

        <h1 className="text-5xl sm:text-6xl lg:text-7xl font-bold tracking-tight text-balance max-w-4xl mx-auto mb-6 leading-[1.1]">
          Turn Your GitHub
          <br />
          Into a{' '}
          <span className="text-primary">Job Engine</span>
        </h1>

        <p className="text-lg sm:text-xl text-muted-foreground max-w-2xl mx-auto mb-10 text-pretty">
          CareerForge extracts real skills from your code, generates ATS-ready resumes,
          maps your skill gaps, and matches you to jobs &mdash; all from your GitHub profile.
        </p>

        <div className="flex flex-col sm:flex-row gap-4 justify-center">
          <Link href="/login">
            <Button size="lg" className="gap-2 text-base px-8 h-12">
              <Github className="h-5 w-5" aria-hidden="true" />
              Connect GitHub
              <ArrowRight className="h-4 w-4" aria-hidden="true" />
            </Button>
          </Link>
        </div>
      </section>

      {/* Features */}
      <section className="relative z-10 container mx-auto px-6 py-24">
        <div className="text-center mb-16">
          <h2 className="text-3xl font-bold tracking-tight mb-4">
            Four tools. One profile.
          </h2>
          <p className="text-muted-foreground text-lg max-w-xl mx-auto">
            Everything you need to go from code to career, grounded in your real work.
          </p>
        </div>

        <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-6">
          <FeatureCard
            icon={<FileText className="h-5 w-5" />}
            title="Resume Generator"
            description="LaTeX resumes grounded in your actual projects. ATS-optimised, zero hallucination."
            accent="from-orange-500/20 to-amber-500/10"
          />
          <FeatureCard
            icon={<BarChart3 className="h-5 w-5" />}
            title="Skill Gap Analysis"
            description="Radar chart showing exactly where you stand vs. any role or job description."
            accent="from-blue-500/20 to-cyan-500/10"
          />
          <FeatureCard
            icon={<BookOpen className="h-5 w-5" />}
            title="LearnWeave"
            description="Personalised learning roadmap to close every gap with projects and resources."
            accent="from-emerald-500/20 to-green-500/10"
          />
          <FeatureCard
            icon={<Briefcase className="h-5 w-5" />}
            title="Job Scout"
            description="Curated job matches scored against your skill profile &mdash; not just keywords."
            accent="from-violet-500/20 to-purple-500/10"
          />
        </div>
      </section>

      {/* Trust section */}
      <section className="relative z-10 border-t border-border/50">
        <div className="container mx-auto px-6 py-24">
          <div className="max-w-3xl mx-auto">
            <div className="flex items-center gap-3 mb-6">
              <Shield className="h-6 w-6 text-primary" aria-hidden="true" />
              <h2 className="text-2xl font-bold tracking-tight">
                Grounded in Reality
              </h2>
            </div>
            <p className="text-muted-foreground text-lg mb-8">
              Unlike generic AI resume builders, CareerForge never invents projects, skills, or experience.
              Every data point traces back to your actual GitHub repos.
            </p>
            <div className="grid sm:grid-cols-2 gap-4">
              <TrustItem text="Projects sourced only from your GitHub" />
              <TrustItem text="Skills extracted from your actual codebase" />
              <TrustItem text="Descriptions reworded, never fabricated" />
              <TrustItem text="Full traceability to source repositories" />
            </div>
          </div>
        </div>
      </section>

      {/* CTA */}
      <section className="relative z-10 border-t border-border/50">
        <div className="container mx-auto px-6 py-24 text-center">
          <h2 className="text-3xl font-bold tracking-tight mb-4">
            Ready to forge your career?
          </h2>
          <p className="text-muted-foreground text-lg mb-8 max-w-lg mx-auto">
            Connect your GitHub and let CareerForge do the rest.
          </p>
          <Link href="/login">
            <Button size="lg" className="gap-2 text-base px-8 h-12">
              Get Started Free
              <ArrowRight className="h-4 w-4" aria-hidden="true" />
            </Button>
          </Link>
        </div>
      </section>

      {/* Footer */}
      <footer className="relative z-10 border-t border-border/50 py-8">
        <div className="container mx-auto px-6 text-center text-sm text-muted-foreground">
          <p>Built with Next.js, FastAPI, and Amazon{'\u00A0'}Bedrock</p>
        </div>
      </footer>
    </div>
  );
}

function FeatureCard({
  icon,
  title,
  description,
  accent,
}: {
  icon: React.ReactNode;
  title: string;
  description: string;
  accent: string;
}) {
  return (
    <div className="group relative rounded-xl border border-border/60 bg-card p-6 transition-colors duration-200 hover:border-primary/30 hover:bg-card/80">
      <div className={`absolute inset-0 rounded-xl bg-gradient-to-br ${accent} opacity-0 group-hover:opacity-100 transition-opacity duration-200`} />
      <div className="relative">
        <div className="inline-flex items-center justify-center rounded-lg bg-primary/10 p-2.5 mb-4 text-primary">
          {icon}
        </div>
        <h3 className="text-base font-semibold mb-2">{title}</h3>
        <p className="text-sm text-muted-foreground leading-relaxed">{description}</p>
      </div>
    </div>
  );
}

function TrustItem({ text }: { text: string }) {
  return (
    <div className="flex items-center gap-3 rounded-lg border border-border/50 bg-card/50 px-4 py-3">
      <div className="h-2 w-2 rounded-full bg-success shrink-0" />
      <span className="text-sm">{text}</span>
    </div>
  );
}
