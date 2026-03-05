import Link from 'next/link';
import { Button } from '@/components/ui/button';
import { 
  FileText, 
  Github, 
  Briefcase, 
  Zap,
  CheckCircle2,
  ArrowRight
} from 'lucide-react';

export default function HomePage() {
  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 via-purple-50 to-pink-50 dark:from-gray-900 dark:via-blue-950 dark:to-purple-950">
      {/* Header */}
      <header className="border-b bg-white/50 dark:bg-gray-900/50 backdrop-blur-sm">
        <div className="container mx-auto px-4 py-4 flex justify-between items-center">
          <div className="flex items-center gap-2">
            <FileText className="h-8 w-8" />
            <span className="font-bold text-xl">LaTeX Resume Agent</span>
          </div>
          <div className="flex items-center gap-4">
            <Link href="/login">
              <Button variant="ghost">Sign In</Button>
            </Link>
            <Link href="/login">
              <Button>Get Started</Button>
            </Link>
          </div>
        </div>
      </header>

      {/* Hero Section */}
      <section className="container mx-auto px-4 py-20 text-center">
        <h1 className="text-5xl font-bold tracking-tight mb-6">
          JD-Aware, GitHub-Grounded
          <br />
          <span className="bg-gradient-to-r from-blue-600 via-purple-600 to-pink-600 bg-clip-text text-transparent">Resume Generation</span>
        </h1>
        <p className="text-xl text-muted-foreground max-w-2xl mx-auto mb-8">
          Generate ATS-friendly LaTeX resumes that highlight your real projects 
          and match them perfectly to job descriptions. No hallucinations, 
          just your actual work.
        </p>
        <div className="flex gap-4 justify-center">
          <Link href="/login">
            <Button size="lg" className="gap-2 bg-gradient-to-r from-blue-600 to-purple-600 hover:from-blue-700 hover:to-purple-700 shadow-lg shadow-blue-500/50">
              <Github className="h-5 w-5" />
              Connect GitHub
            </Button>
          </Link>
          <Link href="/dashboard">
            <Button size="lg" variant="outline" className="gap-2">
              View Demo
              <ArrowRight className="h-5 w-5" />
            </Button>
          </Link>
        </div>
      </section>

      {/* Features */}
      <section className="container mx-auto px-4 py-20">
        <h2 className="text-3xl font-bold text-center mb-12">How It Works</h2>
        <div className="grid md:grid-cols-3 gap-8">
          <FeatureCard
            icon={<Github className="h-10 w-10" />}
            title="Import Your Projects"
            description="Connect GitHub to automatically import your repositories, or manually add projects with descriptions and technologies."
          />
          <FeatureCard
            icon={<Briefcase className="h-10 w-10" />}
            title="Match to Job Descriptions"
            description="Paste any job description and our AI will semantically match your most relevant projects and skills."
          />
          <FeatureCard
            icon={<Zap className="h-10 w-10" />}
            title="Generate LaTeX Resume"
            description="Get a beautifully formatted LaTeX resume that passes ATS systems. Edit directly or download as PDF."
          />
        </div>
      </section>

      {/* Anti-Hallucination */}
      <section className="bg-muted py-20">
        <div className="container mx-auto px-4">
          <div className="max-w-3xl mx-auto text-center">
            <h2 className="text-3xl font-bold mb-6">
              Grounded in Reality, Not Imagination
            </h2>
            <p className="text-lg text-muted-foreground mb-8">
              Unlike generic AI resume builders, our agent NEVER invents projects, 
              skills, or experience. Every bullet point is grounded in your actual 
              stored data.
            </p>
            <div className="grid md:grid-cols-2 gap-6 text-left">
              <GuaranteeItem text="Projects sourced only from your GitHub or uploads" />
              <GuaranteeItem text="Skills extracted from your actual codebase" />
              <GuaranteeItem text="Descriptions reworded, never fabricated" />
              <GuaranteeItem text="Full traceability to source documents" />
            </div>
          </div>
        </div>
      </section>

      {/* CTA */}
      <section className="container mx-auto px-4 py-20 text-center">
        <h2 className="text-3xl font-bold mb-6">Ready to Build Your Resume?</h2>
        <p className="text-lg text-muted-foreground mb-8">
          Start by connecting your GitHub or uploading your projects.
        </p>
        <Link href="/login">
          <Button size="lg" className="gap-2">
            Get Started Free
            <ArrowRight className="h-5 w-5" />
          </Button>
        </Link>
      </section>

      {/* Footer */}
      <footer className="border-t py-8">
        <div className="container mx-auto px-4 text-center text-muted-foreground">
          <p>Built with Next.js, FastAPI, and Gemini AI</p>
        </div>
      </footer>
    </div>
  );
}

function FeatureCard({
  icon,
  title,
  description,
}: {
  icon: React.ReactNode;
  title: string;
  description: string;
}) {
  return (
    <div className="bg-card rounded-lg border p-6 text-center">
      <div className="inline-flex items-center justify-center rounded-lg bg-primary/10 p-3 mb-4">
        {icon}
      </div>
      <h3 className="text-xl font-semibold mb-2">{title}</h3>
      <p className="text-muted-foreground">{description}</p>
    </div>
  );
}

function GuaranteeItem({ text }: { text: string }) {
  return (
    <div className="flex items-start gap-3">
      <CheckCircle2 className="h-6 w-6 text-green-500 shrink-0 mt-0.5" />
      <span>{text}</span>
    </div>
  );
}
