import { useQueries, useQuery, type QueryFunctionContext } from "@tanstack/react-query";
import { ArrowRight, Bot, FileText, MessageCircle, RefreshCw, ShieldCheck } from "lucide-react";
import { Link, useParams } from "react-router-dom";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { PageError, PageLoading } from "@/components/page-states";
import { PageFrame } from "@/components/app-shell";
import { api, SUPPORTED_SDLC_MODELS } from "@/services/api";
import { queryKeys } from "@/lib/query-keys";

function StatCard({ label, value, note }: { label: string; value: string | number; note: string }) {
  return <Card className="p-5"><p className="text-xs font-medium text-slate-500">{label}</p><p className="mt-2 text-2xl font-bold text-slate-950">{value}</p><p className="mt-1 text-xs text-slate-400">{note}</p></Card>;
}

export default function ProjectDashboardPage() {
  const { projectId = "" } = useParams();
  const projectQuery = useQuery({ queryKey: queryKeys.project(projectId), queryFn: ({ signal }) => api.getProject(projectId, signal), enabled: Boolean(projectId) });
  const documentsQuery = useQuery({ queryKey: queryKeys.documents(projectId), queryFn: ({ signal }) => api.listDocuments(projectId, signal), enabled: Boolean(projectId) });
  const recommendationsQuery = useQuery({ queryKey: queryKeys.recommendations(projectId), queryFn: () => api.recommendationHistory(projectId, 5), enabled: Boolean(projectId) });
  const conversationsQuery = useQuery({ queryKey: queryKeys.conversations(projectId), queryFn: () => api.listConversations(projectId, 5), enabled: Boolean(projectId) });
  const documents = documentsQuery.data || [];
  const statusQueries = useQueries({ queries: documents.map((document) => ({
    queryKey: queryKeys.embeddingStatus(projectId, document.id),
    queryFn: ({ signal }: QueryFunctionContext) => api.getEmbeddingStatus(projectId, document.id, signal),
  })) });

  if (projectQuery.isPending || documentsQuery.isPending) return <PageFrame projectId={projectId}><PageLoading /></PageFrame>;
  if (projectQuery.isError || documentsQuery.isError) return <PageFrame projectId={projectId}><PageError message={projectQuery.error?.message || documentsQuery.error?.message || "Unknown backend error"} onRetry={() => { projectQuery.refetch(); documentsQuery.refetch(); }} /></PageFrame>;

  const project = projectQuery.data;
  const embeddedCount = statusQueries.filter((query) => query.data?.status === "completed").length;
  const latestRecommendation = recommendationsQuery.data?.find((item) => SUPPORTED_SDLC_MODELS.includes(item.recommended_model));
  const recentConversations = conversationsQuery.data || [];
  const q = project.questionnaire;

  return <PageFrame projectId={projectId}>
    <div className="flex flex-wrap items-end justify-between gap-4">
      <div><p className="text-xs font-semibold uppercase tracking-[.18em] text-blue-700">Project overview</p><h1 className="mt-2 text-3xl font-bold tracking-tight text-slate-950">{project.project_name}</h1><p className="mt-2 max-w-3xl text-sm leading-6 text-slate-500">{project.description}</p></div>
      <Button variant="outline" onClick={() => { projectQuery.refetch(); documentsQuery.refetch(); recommendationsQuery.refetch(); conversationsQuery.refetch(); }}><RefreshCw size={15} />Refresh</Button>
    </div>

    <section aria-label="Project analytics" className="mt-7 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
      <StatCard label="Project" value={project.domain} note={`${project.organization_type} · team of ${project.team_size}`} />
      <StatCard label="Documents" value={documents.length} note="Uploaded reference files" />
      <StatCard label="Embedded documents" value={`${embeddedCount}/${documents.length}`} note="Ready for semantic retrieval" />
      <StatCard label="Recommendations" value={recommendationsQuery.data?.length ?? 0} note="Recent SDLC analyses" />
    </section>

    <div className="mt-6 grid gap-5 lg:grid-cols-2">
      <Card><CardHeader><CardTitle className="flex items-center gap-2"><ShieldCheck size={18} className="text-blue-600" />Questionnaire summary</CardTitle><CardDescription>Key delivery characteristics saved with this project.</CardDescription></CardHeader><CardContent>
        {q ? <div className="grid grid-cols-2 gap-3">{[
          ["Requirement change", q.requirement_stability], ["Risk", q.risk_level], ["Security", q.security_criticality], ["Compliance", q.compliance_criticality], ["Testing", q.testing_requirement], ["Stakeholders", q.stakeholder_availability], ["Delivery", q.continuous_delivery === "Yes" ? "Continuous delivery" : "Planned releases"], ["Complexity", q.complexity],
        ].map(([label, value]) => <div key={label} className="rounded-xl bg-slate-50 p-3"><p className="text-[11px] text-slate-500">{label}</p><p className="mt-1 text-sm font-semibold text-slate-800">{value}</p></div>)}</div> : <div className="rounded-xl bg-amber-50 p-4 text-sm text-amber-900">No questionnaire is saved yet. <Link to={`/projects/${projectId}/questionnaire`}>Complete it now <ArrowRight className="inline" size={14} /></Link></div>}
        {q && <Link className="mt-4 inline-flex text-xs font-semibold text-blue-700 no-underline" to={`/projects/${projectId}/questionnaire`}>Review or update questionnaire</Link>}
      </CardContent></Card>

      <Card><CardHeader><CardTitle className="flex items-center gap-2"><Bot size={18} className="text-blue-600" />SDLC recommendation</CardTitle><CardDescription>Latest recommendation generated from this project.</CardDescription></CardHeader><CardContent>
        {latestRecommendation ? <><div className="flex items-center justify-between gap-3"><span className="text-2xl font-bold text-slate-950">{latestRecommendation.recommended_model}</span><Badge>{Math.round(latestRecommendation.confidence)}% confidence</Badge></div><p className="mt-3 line-clamp-3 text-sm leading-6 text-slate-600">{latestRecommendation.reasoning}</p></> : <p className="text-sm text-slate-500">No current SDLC recommendation. Generate one using the supported model set.</p>}
        <Link className="mt-4 inline-flex items-center gap-2 text-sm font-semibold text-blue-700 no-underline hover:text-blue-900" to={`/projects/${projectId}/recommendation`}>View recommendation<ArrowRight size={15} /></Link>
      </CardContent></Card>

      <Card><CardHeader><div className="flex items-center justify-between"><div><CardTitle className="flex items-center gap-2"><FileText size={18} className="text-blue-600" />Uploaded documents</CardTitle><CardDescription>Embedding status and source metadata.</CardDescription></div><Link to={`/projects/${projectId}/documents`}><Button size="sm" variant="outline">Manage</Button></Link></div></CardHeader><CardContent className="space-y-3">
        {documents.length ? documents.slice(0, 5).map((document, index) => <div key={document.id} className="flex items-center justify-between gap-3 rounded-xl border border-slate-100 p-3"><span className="min-w-0 truncate text-sm font-medium text-slate-800">{document.original_filename}</span><Badge className={statusQueries[index]?.data?.status === "completed" ? "bg-emerald-50 text-emerald-700" : ""}>{statusQueries[index]?.data?.status || "Checking"}</Badge></div>) : <p className="text-sm text-slate-500">No reference documents uploaded.</p>}
      </CardContent></Card>

      <Card><CardHeader><CardTitle className="flex items-center gap-2"><MessageCircle size={18} className="text-blue-600" />Recent conversations</CardTitle><CardDescription>Continue a grounded project discussion.</CardDescription></CardHeader><CardContent className="space-y-3">
        {conversationsQuery.isError ? <p role="alert" className="text-sm text-rose-700">{conversationsQuery.error.message}</p> : recentConversations.length ? recentConversations.map((conversation) => {
          const lastQuestion = [...conversation.messages].reverse().find((message) => message.role === "user");
          return <Link key={conversation.id} to={`/projects/${projectId}/chat?conversation=${conversation.id}`} className="block rounded-xl border border-slate-100 p-3 text-sm text-slate-700 no-underline hover:border-blue-200 hover:bg-blue-50/40">{lastQuestion?.content || "New conversation"}<span className="mt-1 block text-xs text-slate-400">{new Date(conversation.created_at).toLocaleString()}</span></Link>;
        }) : <p className="text-sm text-slate-500">No conversations yet. Ask the project assistant a question.</p>}
        <Link className="inline-flex items-center gap-2 text-sm font-semibold text-blue-700 no-underline" to={`/projects/${projectId}/chat`}>Open assistant<ArrowRight size={15} /></Link>
      </CardContent></Card>
    </div>
  </PageFrame>;
}
