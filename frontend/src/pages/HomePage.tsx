import { useState } from "react";
import { ArrowRight, ArrowUpRight, Building2, CheckCircle2, Clock3, FilePlus2, FolderOpen, Shield, Sparkles } from "lucide-react";
import { useQuery } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { PageFrame } from "@/components/app-shell";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { api, type ApiProject } from "@/services/api";
import { queryKeys } from "@/lib/query-keys";

function dateLabel(value: string) {
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? "Recently" : date.toLocaleDateString(undefined, { month: "short", day: "numeric" });
}

export default function HomePage() {
  const navigate = useNavigate();
  const [showExisting, setShowExisting] = useState(false);
  const analytics = useQuery({ queryKey: queryKeys.analytics, queryFn: api.getDashboardAnalytics });
  const projectQuery = useQuery({ queryKey: queryKeys.projects, queryFn: api.listProjects, enabled: showExisting });
  const projects: ApiProject[] = projectQuery.data || [];

  return <PageFrame>
    <div className="grid items-center gap-12 lg:grid-cols-[1.08fr_.92fr]">
      <div className="py-5">
        <Badge className="mb-5 gap-1.5"><Sparkles size={13} />AI-assisted requirements discovery</Badge>
        <h1 className="max-w-2xl text-4xl font-bold leading-[1.12] tracking-tight text-slate-950 md:text-6xl">Start with the right questions.</h1>
        <p className="mt-6 max-w-xl text-lg leading-8 text-slate-600">Align stakeholders on what to build, uncover delivery risks, and find an SDLC approach that fits your financial project.</p>
        <div className="mt-8 flex flex-wrap gap-3">
          <Button size="lg" onClick={() => navigate("/projects/new")}><FilePlus2 size={18} />New project<ArrowRight size={17} /></Button>
          <Button size="lg" variant="outline" onClick={() => setShowExisting((value) => !value)}><FolderOpen size={18} />Existing project</Button>
        </div>
        <div className="mt-9 flex flex-wrap gap-x-6 gap-y-3 text-sm text-slate-500">
          <span className="inline-flex items-center gap-2"><CheckCircle2 size={16} className="text-emerald-600" />Guided stakeholder interview</span>
          <span className="inline-flex items-center gap-2"><Shield size={16} className="text-blue-600" />Human-reviewed by design</span>
        </div>
      </div>
      <Card className="overflow-hidden border-0 bg-white shadow-[0_26px_90px_-42px_rgba(30,64,175,.28)]">
        <div className="h-2 bg-gradient-to-r from-blue-600 via-indigo-500 to-cyan-400" />
        <CardHeader className="pb-3">
          <div className="mb-2 flex items-center justify-between"><Badge className="bg-emerald-50 text-emerald-700">A clearer path forward</Badge><span className="grid size-10 place-items-center rounded-xl bg-blue-50 text-blue-700"><Building2 size={18} /></span></div>
          <CardTitle className="text-2xl">From project idea to shared plan</CardTitle>
          <CardDescription>One short interview brings the key decisions into focus.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          {[
            ["01", "Describe the project", "Goals, stakeholders, scope and constraints"],
            ["02", "Explore delivery fit", "Change, risk, assurance and team readiness"],
            ["03", "Review the starting point", "A structured brief ready for your team"],
          ].map(([n, title, description]) => <div key={n} className="flex gap-4 rounded-xl border border-slate-100 bg-slate-50/70 p-4">
            <span className="grid size-9 shrink-0 place-items-center rounded-lg bg-white text-xs font-bold text-blue-700 shadow-sm">{n}</span>
            <span><span className="block text-sm font-semibold text-slate-800">{title}</span><span className="mt-1 block text-xs leading-5 text-slate-500">{description}</span></span>
          </div>)}
          <div className="flex items-center gap-2 pt-2 text-xs text-slate-500"><Clock3 size={14} />Submitted projects are saved to the backend and available later.</div>
        </CardContent>
      </Card>
    </div>

    <section aria-label="Dashboard analytics" className="mt-10 grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
      {[
        ["Projects", analytics.data?.project_count],
        ["Documents", analytics.data?.document_count],
        ["Embedded", analytics.data?.embedded_document_count],
        ["Recommendations", analytics.data?.recommendation_count],
        ["Conversations", analytics.data?.conversation_count],
      ].map(([label, count]) => <Card key={label as string} className="p-4"><p className="text-xs font-medium text-slate-500">{label}</p><p className="mt-2 text-2xl font-bold text-slate-900">{count ?? (analytics.isPending ? "…" : "—")}</p></Card>)}
      {analytics.isError && <p role="alert" className="text-xs text-rose-700">Dashboard counts are unavailable: {analytics.error.message}</p>}
    </section>

    {showExisting && <section className="mt-12">
      <div className="mb-4 flex items-end justify-between"><div><h2 className="text-xl font-bold text-slate-900">Continue a project</h2><p className="mt-1 text-sm text-slate-500">Projects loaded from the backend database.</p></div><Button variant="ghost" size="sm" onClick={() => setShowExisting(false)}>Close</Button></div>
      {projectQuery.isPending ? <div role="status" className="flex items-center gap-2 text-sm text-slate-500"><Clock3 size={15} className="animate-spin" />Loading projects from the server…</div> : projectQuery.isError ? <div role="alert" className="rounded-xl border border-rose-200 bg-rose-50 p-4 text-sm text-rose-700"><p>{projectQuery.error.message}</p><Button className="mt-3" size="sm" variant="outline" onClick={() => projectQuery.refetch()}>Try again</Button></div> : <div className="grid gap-3 md:grid-cols-2">
        {projects.map((project) => <button key={project.id} type="button" onClick={() => navigate(`/projects/${project.id}`)} className="group rounded-2xl border border-slate-200 bg-white p-5 text-left transition hover:border-blue-300 hover:shadow-md">
          <div className="flex items-start justify-between"><span className="grid size-10 place-items-center rounded-xl bg-blue-50 text-blue-700"><Building2 size={18} /></span><ArrowUpRight size={17} className="text-slate-300 transition group-hover:text-blue-600" /></div>
          <div className="mt-4 flex items-center justify-between gap-2"><h3 className="font-semibold text-slate-900">{project.project_name}</h3><Badge>Open project</Badge></div>
          <p className="mt-1 line-clamp-2 text-sm text-slate-500">{project.description || project.domain}</p>
          <div className="mt-4 flex items-center gap-2 text-xs text-slate-400"><Clock3 size={13} />Updated {dateLabel(project.updated_at)}</div>
        </button>)}
        {!projects.length && <p className="text-sm text-slate-500">No projects found yet. Create a new project to get started.</p>}
      </div>}
    </section>}
    <footer className="mt-14 border-t border-slate-200 pt-5 text-xs text-slate-400">Requirements Studio · A stakeholder discovery workspace for financial software projects</footer>
  </PageFrame>;
}
