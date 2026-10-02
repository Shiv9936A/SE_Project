import { useMutation, useMutationState, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowRight, Award, LoaderCircle, RefreshCw, ShieldAlert, Sparkles } from "lucide-react";
import { Link, useParams } from "react-router-dom";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { PageError, PageLoading } from "@/components/page-states";
import { PageFrame } from "@/components/app-shell";
import { useToast } from "@/components/toast-provider";
import { queryKeys } from "@/lib/query-keys";
import { api, SUPPORTED_SDLC_MODELS } from "@/services/api";

export default function RecommendationPage() {
  const { projectId = "" } = useParams();
  const queryClient = useQueryClient();
  const toast = useToast();
  const projectQuery = useQuery({ queryKey: queryKeys.project(projectId), queryFn: () => api.getProject(projectId), enabled: Boolean(projectId) });
  const historyQuery = useQuery({ queryKey: queryKeys.recommendations(projectId), queryFn: () => api.recommendationHistory(projectId), enabled: Boolean(projectId) });
  const pendingGenerations = useMutationState({
    filters: { mutationKey: ["sdlc-recommendation", projectId], status: "pending" },
    select: (mutation) => mutation.state.status,
  });
  const generate = useMutation({
    mutationKey: ["sdlc-recommendation", projectId],
    mutationFn: () => api.generateRecommendation(projectId),
    onSuccess: async () => {
      toast("SDLC recommendation generated and saved.", "success");
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: queryKeys.recommendations(projectId) }),
        queryClient.invalidateQueries({ queryKey: queryKeys.project(projectId) }),
        queryClient.invalidateQueries({ queryKey: queryKeys.analytics }),
      ]);
    },
    onError: (error: Error) => toast(error.message, "error"),
  });

  if (projectQuery.isPending || historyQuery.isPending) return <PageFrame projectId={projectId}><PageLoading label="Loading recommendation data…" /></PageFrame>;
  if (projectQuery.isError || historyQuery.isError) return <PageFrame projectId={projectId}><PageError message={projectQuery.error?.message || historyQuery.error?.message || "Unable to load recommendation."} onRetry={() => { projectQuery.refetch(); historyQuery.refetch(); }} /></PageFrame>;

  const project = projectQuery.data;
  const generating = generate.isPending || pendingGenerations.length > 0;
  const supportedHistory = historyQuery.data.filter((item) => SUPPORTED_SDLC_MODELS.includes(item.recommended_model));
  const result = supportedHistory[0];
  const testingStrategy = project.questionnaire
    ? `${project.questionnaire.testing_requirement} testing rigor${project.questionnaire.formal_verification === "Yes" ? ", including formal verification evidence" : ""}; include security and compliance checks appropriate to the project.`
    : "Complete the project questionnaire to tailor a testing strategy.";
  const deliveryStrategy = project.questionnaire
    ? `${result?.recommended_model || "The selected SDLC model"} delivery with ${project.questionnaire.continuous_delivery === "Yes" ? "continuous delivery and automated release gates" : "planned, reviewable release checkpoints"}; account for ${project.questionnaire.expected_changes.toLowerCase()} requirement changes.`
    : "Complete the project questionnaire to tailor a delivery strategy.";

  return <PageFrame projectId={projectId}>
    <div className="flex flex-wrap items-end justify-between gap-4">
      <div><p className="text-xs font-semibold uppercase tracking-[.18em] text-blue-700">Decision support</p><h1 className="mt-2 text-3xl font-bold text-slate-950">SDLC recommendation</h1><p className="mt-2 text-sm text-slate-500">Evidence-based delivery guidance for {project.project_name}.</p></div>
      <Button onClick={() => generate.mutate()} disabled={generating || !project.questionnaire}>
        {generating ? <LoaderCircle className="animate-spin" size={16} /> : <RefreshCw size={16} />}
        {generating ? "Analyzing project…" : result ? "Regenerate recommendation" : "Generate recommendation"}
      </Button>
    </div>

    {!project.questionnaire && <div role="alert" className="mt-6 rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-900">Save the questionnaire before generating an SDLC recommendation. <Link to={`/projects/${projectId}/questionnaire`}>Open questionnaire <ArrowRight className="inline" size={14} /></Link></div>}
    {generate.isError && <div role="alert" className="mt-4 rounded-xl border border-rose-200 bg-rose-50 p-4 text-sm text-rose-800">{generate.error.message}</div>}

    {result ? <>
      <Card className="mt-7 overflow-hidden border-blue-100"><div className="h-1.5 bg-gradient-to-r from-blue-600 via-indigo-500 to-cyan-400" /><CardContent className="grid gap-6 p-6 md:grid-cols-[1fr_auto] md:items-center md:p-8">
        <div><div className="flex items-center gap-2 text-sm font-semibold text-blue-700"><Award size={17} />Recommended SDLC</div><h2 className="mt-2 text-3xl font-bold text-slate-950">{result.recommended_model}</h2><p className="mt-3 max-w-3xl text-sm leading-6 text-slate-600">{result.reasoning}</p></div>
        <div className="rounded-2xl bg-blue-50 px-6 py-5 text-center"><p className="text-xs font-semibold uppercase tracking-wide text-blue-700">Confidence</p><p className="mt-1 text-4xl font-bold text-blue-950">{Math.round(result.confidence)}<span className="text-xl">%</span></p><p className="mt-1 text-[11px] text-blue-700">Comparative fit estimate</p></div>
      </CardContent></Card>
      <p role="note" className="mt-3 rounded-xl border border-slate-200 bg-white px-4 py-3 text-xs leading-5 text-slate-600">
        {result.sources.length
          ? `Evidence used: questionnaire plus ${result.sources.length} retrieved document chunk${result.sources.length === 1 ? "" : "s"}.`
          : project.documents?.length
            ? "Evidence used: questionnaire only. No uploaded document chunks matched retrieval; check embedding status and document relevance."
            : "Evidence used: questionnaire only. No project documents were uploaded."}
      </p>

      <div className="mt-5 grid gap-5 lg:grid-cols-2">
        <Card><CardHeader><CardTitle className="flex items-center gap-2"><Sparkles className="text-blue-600" size={17} />Why it fits</CardTitle><CardDescription>Strengths identified from project inputs and retrieved evidence.</CardDescription></CardHeader><CardContent className="space-y-2">{result.strengths.map((item, index) => <p key={index} className="rounded-xl bg-emerald-50 p-3 text-sm leading-6 text-emerald-950">{item}</p>)}{result.sources.length > 0 && <div className="pt-2"><p className="mb-2 text-xs font-semibold text-slate-500">Evidence sources</p><div className="flex flex-wrap gap-2">{result.sources.map((source) => <Badge key={source.chunk_id} className="bg-blue-50 text-blue-800">{source.filename || source.document_id} · chunk {source.chunk_id}</Badge>)}</div></div>}</CardContent></Card>
        <Card><CardHeader><CardTitle className="flex items-center gap-2"><ShieldAlert className="text-amber-600" size={17} />Risks & mitigations</CardTitle><CardDescription>Risks to review and actions to manage them.</CardDescription></CardHeader><CardContent><div className="space-y-2">{result.risks.map((risk, index) => <p key={index} className="rounded-xl bg-amber-50 p-3 text-sm leading-6 text-amber-950">{risk}</p>)}</div><h3 className="mb-2 mt-5 text-xs font-bold uppercase tracking-wider text-slate-400">Mitigation and implementation notes</h3><div className="space-y-2">{result.implementation_notes.map((note, index) => <p key={index} className="rounded-xl bg-slate-50 p-3 text-sm leading-6 text-slate-700">{note}</p>)}</div></CardContent></Card>
        <Card><CardHeader><CardTitle>Testing strategy</CardTitle><CardDescription>Quality gates based on saved assurance requirements.</CardDescription></CardHeader><CardContent><p className="text-sm leading-6 text-slate-700">{testingStrategy}</p></CardContent></Card>
        <Card><CardHeader><CardTitle>Delivery strategy</CardTitle><CardDescription>Release rhythm aligned with project change and delivery needs.</CardDescription></CardHeader><CardContent><p className="text-sm leading-6 text-slate-700">{deliveryStrategy}</p></CardContent></Card>
      </div>

      <Card className="mt-5"><CardHeader><CardTitle>Model scorecard</CardTitle><CardDescription>Rule-based comparative fit scores; scores are not probabilities.</CardDescription></CardHeader><CardContent className="space-y-3">{result.model_scores.map((item) => <div key={item.model} className="grid grid-cols-[6.5rem_1fr_2.5rem] items-center gap-3"><span className="text-xs font-medium text-slate-600">{item.model}</span><div className="h-2 overflow-hidden rounded-full bg-slate-100"><div className={`h-full rounded-full ${item.model === result.recommended_model ? "bg-blue-600" : "bg-slate-300"}`} style={{ width: `${item.score}%` }} /></div><span className="text-right text-xs font-semibold text-slate-700">{item.score}</span></div>)}</CardContent></Card>
      <Card className="mt-5"><CardHeader><CardTitle>Alternatives</CardTitle><CardDescription>Other models that may fit, depending on project tradeoffs.</CardDescription></CardHeader><CardContent className="grid gap-3 md:grid-cols-3">{result.alternative_models.map((alternative) => <div key={alternative.model} className="rounded-xl border border-slate-100 p-4"><div className="flex justify-between gap-2"><span className="font-semibold text-slate-800">{alternative.model}</span><Badge>{alternative.score}</Badge></div><p className="mt-2 text-xs leading-5 text-slate-500">{alternative.rationale}</p></div>)}</CardContent></Card>
    </> : <Card className="mt-7"><CardContent className="py-12 text-center"><h2 className="text-lg font-bold text-slate-900">No current recommendation</h2><p className="mx-auto mt-2 max-w-lg text-sm text-slate-500">Generate an analysis to score the seven supported SDLC models against the questionnaire and any retrieved document evidence.</p></CardContent></Card>}

    {supportedHistory.length > 1 && <section className="mt-7"><h2 className="mb-3 text-lg font-bold text-slate-900">Previous recommendations</h2><div className="grid gap-3 md:grid-cols-2">{supportedHistory.slice(1).map((item) => <Card key={item.id} className="p-4"><div className="flex items-center justify-between"><span className="font-semibold text-slate-800">{item.recommended_model}</span><Badge>{Math.round(item.confidence)}%</Badge></div><p className="mt-2 line-clamp-2 text-xs leading-5 text-slate-500">{item.reasoning}</p><time className="mt-2 block text-[11px] text-slate-400">{new Date(item.created_at).toLocaleString()}</time></Card>)}</div></section>}
  </PageFrame>;
}
