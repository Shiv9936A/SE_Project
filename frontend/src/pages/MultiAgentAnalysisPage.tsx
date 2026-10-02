import { useMutation, useMutationState, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { AlertCircle, ArrowRight, Bot, CheckCircle2, Circle, FileCheck2, LoaderCircle, RefreshCw, ShieldAlert, Sparkles } from "lucide-react";
import { Link, useParams } from "react-router-dom";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { PageFrame } from "@/components/app-shell";
import { PageLoading } from "@/components/page-states";
import { queryKeys } from "@/lib/query-keys";
import { ApiError, api, type AgentRunStatus, type AnalysisRequirement, type GovernanceAnalysisResult, type OrchestrationResult, type RequirementCategory } from "@/services/api";

const categoryLabels: Record<RequirementCategory, string> = {
  functional: "Functional", non_functional: "Non-functional", business_rule: "Business rules",
  data: "Data", integration: "Integration", security_privacy_compliance: "Security, privacy & compliance",
  operational: "Operational",
};
const requirementOrder = Object.keys(categoryLabels) as RequirementCategory[];
const testingLabels: Record<string, string> = {
  unit_testing: "Unit testing", integration_testing: "Integration testing", system_testing: "System testing",
  acceptance_testing: "Acceptance testing", security_testing: "Security testing", performance_testing: "Performance testing",
};

function errorMessage(error: unknown) {
  if (error instanceof ApiError) {
    if (error.status === 404) return "This project could not be found. Return to the project list and open a current project.";
    if (error.status === 409 && error.message.toLowerCase().includes("already running")) return "An analysis is already running for this project. Its saved run will update here when it finishes.";
    if (error.status === 409) return "No completed interview was found. Complete the adaptive interview before running AI analysis.";
    if (error.status === 422) return "The project inputs could not be processed. Review the project and interview answers, then try again.";
    if (error.status === 429) return "The analysis service is temporarily busy. Please wait a moment and retry.";
    if (error.status === 408 || error.status === 504) return "The analysis took too long to finish. Retry the run when the service is ready.";
    if (error.status && error.status >= 500) return "AI analysis could not be completed right now. Please try again.";
    if (!error.status) return "Could not connect to the analysis service. Check that the backend is running, then retry.";
    return "The analysis request could not be accepted. Review the project inputs and retry.";
  }
  if (error instanceof DOMException && error.name === "AbortError") return "The analysis request timed out or was cancelled. Retry when ready.";
  return "AI analysis could not be completed. Please try again.";
}

function AgentStatus({ name, status, running }: { name: string; status: AgentRunStatus | "pending"; running: boolean }) {
  const labels: Record<string, string> = {
    pending: "Pending", skipped: "Skipped", completed: "Completed", partial: "Completed with fallback", failed: "Failed",
  };
  const icon = status === "completed" ? <CheckCircle2 size={18} aria-hidden="true" />
    : status === "partial" ? <ShieldAlert size={18} aria-hidden="true" />
      : status === "failed" ? <AlertCircle size={18} aria-hidden="true" />
        : running ? <LoaderCircle size={18} className="animate-spin" aria-hidden="true" />
          : <Circle size={18} aria-hidden="true" />;
  const statusLabel = running && status === "pending" ? "Waiting for the orchestration result" : labels[status];
  return <div className="flex min-w-0 items-start gap-3 rounded-xl border border-slate-200 bg-white p-4">
    <span className={status === "completed" ? "text-emerald-700" : status === "partial" ? "text-amber-700" : status === "failed" ? "text-rose-700" : "text-slate-400"}>{icon}</span>
    <div className="min-w-0"><p className="font-semibold text-slate-900">{name}</p><p className="mt-1 text-sm text-slate-600" role={running && status === "pending" ? "status" : undefined}>{statusLabel}</p></div>
  </div>;
}

function Evidence({ requirement }: { requirement: AnalysisRequirement }) {
  const sourceLabel = requirement.source_type === "inferred" ? "Inference (not directly sourced)" : requirement.source_type.replaceAll("_", " ");
  return <div className="mt-4 rounded-xl border border-blue-100 bg-blue-50/60 p-4">
    <p className="text-xs font-semibold uppercase tracking-wide text-blue-800">Traceability</p>
    <p className="mt-2 text-sm font-medium capitalize text-slate-800">Source: {sourceLabel}</p>
    {requirement.source_reference ? <p className="mt-1 break-words text-xs text-slate-600">Reference: <code className="break-all">{requirement.source_reference}</code></p> : <p className="mt-1 text-xs text-slate-600">No source reference was returned.</p>}
    {requirement.evidence.trim() ? <blockquote className="mt-3 border-l-2 border-blue-300 pl-3 text-sm leading-6 text-slate-700">{requirement.evidence}</blockquote> : <p className="mt-3 text-sm text-slate-500">No direct evidence was provided for this item.</p>}
  </div>;
}

function RequirementCard({ requirement }: { requirement: AnalysisRequirement }) {
  return <details className="group rounded-xl border border-slate-200 bg-white open:shadow-sm">
    <summary className="flex cursor-pointer list-none flex-wrap items-center justify-between gap-3 p-4 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500">
      <div className="min-w-0 flex-1"><p className="text-xs font-semibold text-blue-700">{requirement.requirement_id}</p><h4 className="mt-1 font-semibold text-slate-900">{requirement.title}</h4><p className="mt-1 line-clamp-2 text-sm leading-5 text-slate-600">{requirement.description}</p></div>
      <div className="flex items-center gap-2"><Badge className="capitalize">{requirement.priority} priority</Badge><span className="text-xs text-slate-500">{Math.round(requirement.confidence * 100)}% confidence</span></div>
    </summary>
    <div className="border-t border-slate-100 px-4 pb-4 pt-1">
      <div className="mt-3 flex flex-wrap gap-2"><Badge>Testability: {requirement.testability}</Badge>{requirement.tags.map((tag) => <Badge key={tag} className="bg-slate-100 text-slate-700">{tag}</Badge>)}</div>
      <Evidence requirement={requirement} />
      <DataList title="Acceptance criteria" items={requirement.acceptance_criteria} empty="No acceptance criteria were returned." />
      <DataList title="Dependencies" items={requirement.dependencies} empty="No dependencies were returned." />
      <DataList title="Missing information" items={requirement.missing_information} empty="No missing information was reported for this requirement." tone="amber" />
      <DataList title="Requirement ambiguities" items={requirement.ambiguities} empty="No requirement-level ambiguity was reported." tone="amber" />
    </div>
  </details>;
}

function DataList({ title, items, empty, tone = "slate" }: { title: string; items: string[]; empty: string; tone?: "slate" | "amber" }) {
  return <section className="mt-4"><h5 className="text-sm font-semibold text-slate-800">{title}</h5>{items.length ? <ul className={`mt-2 list-disc space-y-1 pl-5 text-sm leading-5 ${tone === "amber" ? "text-amber-900" : "text-slate-600"}`}>{items.map((item, index) => <li key={`${index}-${item}`}>{item}</li>)}</ul> : <p className="mt-1 text-sm text-slate-500">{empty}</p>}</section>;
}

function RequirementsView({ result }: { result: NonNullable<OrchestrationResult["requirements_analysis"]> }) {
  const grouped = requirementOrder.map((category) => ({ category, items: result.requirements.filter((item) => item.category === category) })).filter((group) => group.items.length);
  const categories = new Set(result.requirements.map((item) => item.category));
  const missing = result.requirements.flatMap((item) => item.missing_information.map((value) => `${item.requirement_id}: ${value}`));
  return <div className="space-y-5">
    <Card><CardHeader><CardTitle className="flex items-center justify-between gap-3"><span>Requirements Analysis</span><Badge>{result.requirements.length} requirements</Badge></CardTitle><CardDescription>{result.summary}</CardDescription></CardHeader><CardContent><div className="flex flex-wrap gap-2"><Badge>{categories.size} categories</Badge><Badge>{result.ambiguities.length} ambiguities</Badge><Badge>{result.conflicts.length} conflicts</Badge><Badge>{missing.length} missing information items</Badge></div></CardContent></Card>
    {grouped.length ? grouped.map(({ category, items }) => <section key={category} aria-label={`${categoryLabels[category]} requirements`}><div className="mb-3 flex items-center justify-between gap-3"><h3 className="font-semibold text-slate-900">{categoryLabels[category]}</h3><Badge>{items.length}</Badge></div><div className="space-y-3">{items.map((item) => <RequirementCard key={item.requirement_id} requirement={item} />)}</div></section>) : <Card><CardContent className="py-7 text-sm text-slate-600">No individual requirements were returned. Review the summary and clarification items below.</CardContent></Card>}
    <Card><CardHeader><CardTitle>Ambiguities</CardTitle><CardDescription>Unresolved wording that may need stakeholder clarification.</CardDescription></CardHeader><CardContent className="space-y-3">{result.ambiguities.length ? result.ambiguities.map((item, index) => <div key={`${item.related_requirement_id}-${index}`} className="rounded-xl border border-amber-200 bg-amber-50 p-4"><div className="flex flex-wrap items-center gap-2"><Badge className="bg-amber-100 text-amber-900">{item.severity}</Badge>{item.related_requirement_id && <span className="text-xs text-slate-600">{item.related_requirement_id}</span>}</div><p className="mt-2 text-sm font-medium text-amber-950">{item.description}</p><p className="mt-2 text-sm text-slate-700"><strong>Clarification:</strong> {item.clarification_question}</p>{item.source_reference && <p className="mt-2 break-all text-xs text-slate-600">Source: {item.source_reference}</p>}</div>) : <p className="text-sm text-slate-500">No ambiguities were returned.</p>}</CardContent></Card>
    <Card><CardHeader><CardTitle>Conflicts</CardTitle><CardDescription>Statements that the analysis identified as conflicting.</CardDescription></CardHeader><CardContent className="space-y-3">{result.conflicts.length ? result.conflicts.map((item, index) => <div key={index} className="rounded-xl border border-rose-200 bg-rose-50 p-4"><Badge className="bg-rose-100 text-rose-800">{item.severity}</Badge><p className="mt-2 text-sm font-medium text-rose-950">{item.description}</p><p className="mt-2 text-sm text-slate-700"><strong>Clarification:</strong> {item.clarification_question}</p><ul className="mt-3 space-y-2">{item.sources.map((source, sourceIndex) => <li key={sourceIndex} className="break-words rounded-lg bg-white/80 p-3 text-xs text-slate-700"><span className="font-semibold">{source.source_type.replaceAll("_", " ")}</span> · <code>{source.source_reference}</code><p className="mt-1">{source.evidence}</p></li>)}</ul></div>) : <p className="text-sm text-slate-500">No conflicts were returned.</p>}</CardContent></Card>
    <Card><CardHeader><CardTitle>Missing information</CardTitle><CardDescription>Open details to confirm with stakeholders.</CardDescription></CardHeader><CardContent><DataList title="Per requirement" items={missing} empty="No requirement-level missing information was reported." tone="amber" /><DataList title="Clarification questions" items={result.clarification_questions} empty="No clarification questions were returned." tone="amber" /><div className="mt-4 space-y-2">{result.completeness.filter((item) => item.status !== "covered").map((item) => <p key={item.area} className="rounded-lg bg-amber-50 p-3 text-sm text-amber-950"><strong>{item.area} · {item.status}:</strong> {item.note}</p>)}</div></CardContent></Card>
  </div>;
}

function GovernanceView({ result }: { result: GovernanceAnalysisResult }) {
  const assessment = [
    ["Complexity", result.project_assessment.complexity], ["Risk level", result.project_assessment.risk_level],
    ["Requirements stability", result.project_assessment.requirements_stability], ["Integration complexity", result.project_assessment.integration_complexity],
    ["Security sensitivity", result.project_assessment.security_sensitivity], ["Compliance impact", result.project_assessment.compliance_impact],
  ];
  const strategies = Object.entries(result.testing_strategy).filter(([, rows]) => rows.length);
  return <div className="space-y-5">
    <Card><CardHeader><CardTitle>Governance & SDLC</CardTitle><CardDescription>Methodology selected from the validated requirements analysis.</CardDescription></CardHeader><CardContent><div className="flex flex-wrap items-start justify-between gap-4"><div><h3 className="text-2xl font-bold text-slate-950">{result.methodology.name}</h3><p className="mt-1 text-sm text-slate-600">Methodology confidence: {Math.round(result.methodology.confidence * 100)}%</p></div><Badge>Evidence-linked rationale</Badge></div><div className="mt-4 space-y-3">{result.methodology.reasoning.map((item, index) => <div key={index} className="rounded-xl bg-slate-50 p-4"><p className="font-semibold text-slate-900">{item.factor}</p><p className="mt-1 text-sm leading-6 text-slate-700">{item.observation}</p><p className="mt-1 text-sm leading-6 text-slate-600"><strong>Impact:</strong> {item.impact}</p><p className="mt-2 break-all text-xs text-slate-500">References: {item.source_references.join(", ")}</p></div>)}</div></CardContent></Card>
    <Card><CardHeader><CardTitle>Project assessment</CardTitle></CardHeader><CardContent className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">{assessment.map(([label, value]) => <div key={label} className="rounded-xl bg-slate-50 p-3"><p className="text-xs text-slate-500">{label}</p><p className="mt-1 font-semibold capitalize text-slate-900">{value}</p></div>)}</CardContent></Card>
    <Card><CardHeader><CardTitle>Development lifecycle</CardTitle><CardDescription>Phases, outputs, and exit criteria returned by the governance analysis.</CardDescription></CardHeader><CardContent className="grid gap-3 md:grid-cols-2">{result.development_lifecycle.map((phase, index) => <div key={`${phase.phase}-${index}`} className="rounded-xl border border-slate-200 p-4"><h4 className="font-semibold text-slate-900">{phase.phase}</h4><DataList title="Activities" items={phase.activities} empty="No activities returned." /><DataList title="Deliverables" items={phase.deliverables} empty="No deliverables returned." /><DataList title="Exit criteria" items={phase.exit_criteria} empty="No exit criteria returned." /></div>)}</CardContent></Card>
    <Card><CardHeader><CardTitle>Testing strategy</CardTitle><CardDescription>Only populated strategy categories are shown.</CardDescription></CardHeader><CardContent className="grid gap-3 sm:grid-cols-2">{strategies.length ? strategies.map(([key, rows]) => <div key={key} className="rounded-xl bg-slate-50 p-4"><h4 className="font-semibold text-slate-900">{testingLabels[key] || key.replaceAll("_", " ")}</h4><ul className="mt-2 list-disc space-y-2 pl-5 text-sm leading-5 text-slate-700">{rows.map((row, index) => <li key={index}>{row.recommendation}{row.requirement_references.length > 0 && <span className="mt-1 block break-all text-xs text-slate-500">References: {row.requirement_references.join(", ")}</span>}</li>)}</ul></div>) : <p className="text-sm text-slate-500">No testing strategy categories were returned.</p>}</CardContent></Card>
    <Card><CardHeader><CardTitle>Project risks</CardTitle><CardDescription>Risks and mitigations to review with the project team.</CardDescription></CardHeader><CardContent className="grid gap-3 md:grid-cols-2">{result.risks.length ? result.risks.map((risk) => <div key={risk.risk_id} className="rounded-xl border border-slate-200 p-4"><div className="flex flex-wrap items-center justify-between gap-2"><h4 className="font-semibold text-slate-900">{risk.title}</h4><Badge className={risk.severity === "high" ? "bg-rose-100 text-rose-800" : risk.severity === "medium" ? "bg-amber-100 text-amber-900" : "bg-slate-100 text-slate-700"}>{risk.severity} severity</Badge></div><p className="mt-2 text-sm leading-6 text-slate-700">{risk.risk_id} · {risk.description}</p><p className="mt-2 text-sm leading-6 text-slate-700"><strong>Mitigation:</strong> {risk.mitigation}</p><p className="mt-2 break-all text-xs text-slate-500">Likelihood: {risk.likelihood} · References: {risk.source_references.join(", ")}</p></div>) : <p className="text-sm text-slate-500">No risks were returned.</p>}</CardContent></Card>
    <Card><CardHeader><CardTitle>Governance checkpoints</CardTitle><CardDescription>Review points provided by the analysis; no checkpoint is marked complete automatically.</CardDescription></CardHeader><CardContent className="grid gap-3 md:grid-cols-2">{result.governance_checkpoints.length ? result.governance_checkpoints.map((item, index) => <div key={`${item.checkpoint}-${index}`} className="rounded-xl border border-slate-200 p-4"><h4 className="font-semibold text-slate-900">{item.checkpoint}</h4><p className="mt-2 text-sm leading-5 text-slate-700">{item.purpose}</p><DataList title="Entry conditions" items={item.entry_conditions} empty="No entry conditions returned." /><DataList title="Exit conditions" items={item.exit_conditions} empty="No exit conditions returned." /><DataList title="Required artifacts" items={item.required_artifacts} empty="No artifacts returned." /></div>) : <p className="text-sm text-slate-500">No governance checkpoints were returned.</p>}</CardContent></Card>
    <Card><CardHeader><CardTitle>Quality gates</CardTitle><CardDescription>Review these checks with the team. The analysis does not report completion state for individual checks.</CardDescription></CardHeader><CardContent className="grid gap-3 md:grid-cols-2">{result.quality_gates.length ? result.quality_gates.map((gate, index) => <div key={`${gate.gate}-${index}`} className="rounded-xl bg-slate-50 p-4"><h4 className="font-semibold text-slate-900">{gate.gate}</h4><ul className="mt-2 list-disc space-y-1 pl-5 text-sm text-slate-700">{gate.checks.map((check, checkIndex) => <li key={checkIndex}>{check}</li>)}</ul>{gate.requirement_references.length > 0 && <p className="mt-2 break-all text-xs text-slate-500">References: {gate.requirement_references.join(", ")}</p>}</div>) : <p className="text-sm text-slate-500">No quality gates were returned.</p>}</CardContent></Card>
  </div>;
}

function Pipeline({ result, running, interviewState }: { result: OrchestrationResult | null; running: boolean; interviewState: "loading" | "completed" | "in_progress" | "unavailable" }) {
  const statusFor = (name: "requirements" | "governance"): AgentRunStatus | "pending" => result?.agents.find((agent) => agent.name === name)?.status || "pending";
  const interviewLabel = { loading: "Checking interview status", completed: "Completed", in_progress: "In progress", unavailable: "Not available" }[interviewState];
  const finalLabel = running ? "Waiting for final result" : result ? result.status[0].toUpperCase() + result.status.slice(1) : "Not run";
  return <Card><CardHeader><CardTitle className="flex items-center gap-2"><Bot size={18} className="text-blue-600" />Analysis pipeline</CardTitle><CardDescription>Project context and completed adaptive interview are passed to requirements analysis, then to governance and SDLC analysis.</CardDescription></CardHeader><CardContent><ol className="grid gap-3 md:grid-cols-5">
    <li className="rounded-xl bg-slate-50 p-4"><p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Project</p><p className="mt-2 font-semibold text-slate-900">Context loaded</p></li>
    <li className="rounded-xl bg-slate-50 p-4"><p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Adaptive interview</p><p className="mt-2 font-semibold text-slate-900">{interviewLabel}</p></li>
    <li><AgentStatus name="Requirements Agent" status={statusFor("requirements")} running={running} /></li>
    <li><AgentStatus name="Governance & SDLC Agent" status={statusFor("governance")} running={running} /></li>
    <li className="rounded-xl bg-slate-50 p-4"><p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Final project plan</p><p className="mt-2 font-semibold capitalize text-slate-900">{finalLabel}</p></li>
  </ol>{running && <p role="status" className="mt-4 flex items-center gap-2 text-sm text-blue-800"><LoaderCircle size={16} className="animate-spin" aria-hidden="true" />AI analysis is running. Agent statuses will be shown when the backend returns the completed result.</p>}</CardContent></Card>;
}

export default function MultiAgentAnalysisPage() {
  const { projectId = "" } = useParams();
  const queryClient = useQueryClient();
  const [selectedRunId, setSelectedRunId] = useState<string | null>(null);
  const projectQuery = useQuery({ queryKey: queryKeys.project(projectId), queryFn: ({ signal }) => api.getProject(projectId, signal), enabled: Boolean(projectId) });
  const interviewQuery = useQuery({ queryKey: ["interview", projectId], queryFn: ({ signal }) => api.getInterviewState(projectId, signal), enabled: Boolean(projectId), retry: false });
  const historyQuery = useQuery({
    queryKey: queryKeys.analysisRuns(projectId),
    queryFn: ({ signal }) => api.listAnalysisRuns(projectId, 50, 0, signal),
    enabled: Boolean(projectId), staleTime: 0, refetchOnMount: "always",
  });
  const pendingRuns = useMutationState({
    filters: { mutationKey: ["orchestration", projectId], status: "pending" },
    select: (mutation) => mutation.state.status,
  });
  const mutation = useMutation({
    mutationKey: ["orchestration", projectId],
    mutationFn: () => api.orchestrateProject(projectId),
    onError: (error) => {
      if (error instanceof ApiError && error.status === 409 && error.message.toLowerCase().includes("already running")) {
        void queryClient.invalidateQueries({ queryKey: queryKeys.analysisRuns(projectId) });
      }
    },
    onSuccess: (result) => {
      queryClient.setQueryData(["orchestration", projectId], result);
      setSelectedRunId(result.analysis_run_id);
      void queryClient.invalidateQueries({ queryKey: queryKeys.analysisRuns(projectId) });
      void queryClient.invalidateQueries({ queryKey: queryKeys.project(projectId) });
    },
  });
  const previousResult = queryClient.getQueryData<OrchestrationResult>(["orchestration", projectId]);
  const latestClientResult = mutation.data || previousResult || null;
  const latestHistoryRunId = historyQuery.data?.[0]?.id || latestClientResult?.analysis_run_id || null;
  const selectedViewRunId = selectedRunId || latestHistoryRunId;
  const historyDetailQuery = useQuery({
    queryKey: queryKeys.analysisRun(projectId, selectedViewRunId || ""),
    queryFn: ({ signal }) => api.getAnalysisRun(projectId, selectedViewRunId!, signal),
    enabled: Boolean(selectedViewRunId && latestClientResult?.analysis_run_id !== selectedViewRunId),
    staleTime: 0, refetchOnMount: "always",
    refetchInterval: (query) => query.state.data?.status === "running" ? 2000 : false,
    refetchIntervalInBackground: true,
  });
  const persistedDetail = historyDetailQuery.data;
  const result: OrchestrationResult | null = latestClientResult?.analysis_run_id === selectedViewRunId
    ? latestClientResult
    : persistedDetail ? {
      orchestration_id: `analysis-run-${persistedDetail.version}`,
      analysis_run_id: persistedDetail.id, analysis_run_version: persistedDetail.version,
      project_id: persistedDetail.project_id, status: persistedDetail.status,
      requirements_analysis_id: persistedDetail.requirements_analysis_id,
      governance_analysis_id: persistedDetail.governance_analysis_id,
      agents: persistedDetail.status === "running"
        ? persistedDetail.agents.map((agent) => ({ ...agent, status: agent.status === "skipped" ? "pending" as const : agent.status }))
        : persistedDetail.agents,
      requirements_analysis: persistedDetail.requirements_analysis,
      governance_analysis: persistedDetail.governance_analysis,
      warnings: persistedDetail.warnings, errors: persistedDetail.errors, created_at: persistedDetail.created_at,
    } : null;
  const isHistoricalView = Boolean(selectedRunId && latestHistoryRunId && selectedRunId !== latestHistoryRunId);
  const activeRun = historyQuery.data?.find((run) => run.status === "running");
  const running = mutation.isPending || pendingRuns.length > 0 || Boolean(activeRun);
  const interviewComplete = interviewQuery.data?.status === "completed";
  const topError = projectQuery.error;

  if (projectQuery.isPending) return <PageFrame projectId={projectId}><PageLoading label="Loading project for AI analysis…" /></PageFrame>;
  if (topError) return <PageFrame projectId={projectId}><Card><CardContent className="py-8"><h1 className="text-xl font-bold text-slate-950">Project unavailable</h1><p role="alert" className="mt-2 text-sm text-slate-600">{errorMessage(topError)}</p><Button className="mt-4" variant="outline" onClick={() => void projectQuery.refetch()}>Try again</Button></CardContent></Card></PageFrame>;

  const reqStatus = result?.agents.find((agent) => agent.name === "requirements")?.status;
  const govStatus = result?.agents.find((agent) => agent.name === "governance")?.status;
  const runError = mutation.error;
  return <PageFrame projectId={projectId}>
    <header className="flex flex-wrap items-end justify-between gap-4">
      <div><p className="text-xs font-semibold uppercase tracking-[.18em] text-blue-700">Multi-agent workflow</p><h1 className="mt-2 text-3xl font-bold tracking-tight text-slate-950">AI Analysis</h1><p className="mt-2 max-w-3xl text-sm leading-6 text-slate-600">Review evidence-grounded requirements and a governance plan for <strong>{projectQuery.data.project_name}</strong>.</p></div>
      <Button onClick={() => mutation.mutate()} disabled={!interviewComplete || running || historyQuery.isPending} aria-busy={running}>
        {running ? <><LoaderCircle size={16} className="animate-spin" aria-hidden="true" />Analysis running</> : result ? <><RefreshCw size={16} />Run again</> : <><Sparkles size={16} />Run AI Analysis</>}
      </Button>
    </header>

    <div className="mt-6"><Pipeline result={result} running={running} interviewState={interviewQuery.isPending ? "loading" : interviewComplete ? "completed" : interviewQuery.isError ? "unavailable" : "in_progress"} /></div>

    <Card className="mt-5">
      <CardHeader><div className="flex flex-wrap items-start justify-between gap-3"><div><CardTitle>Analysis history</CardTitle><CardDescription>Each run is saved as a version. Select one to review its original agent outputs.</CardDescription></div>{isHistoricalView && <Button variant="outline" onClick={() => setSelectedRunId(latestHistoryRunId)}>Return to latest</Button>}</div></CardHeader>
      <CardContent>
        {historyQuery.isPending ? <p role="status" className="text-sm text-slate-600">Loading saved analyses…</p>
          : historyQuery.isError ? <div className="flex flex-wrap items-center justify-between gap-3"><p role="alert" className="text-sm text-slate-700">Saved analysis history could not be loaded.</p><Button variant="outline" onClick={() => void historyQuery.refetch()}>Retry</Button></div>
            : historyQuery.data?.length ? <ol className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">{historyQuery.data.map((item) => {
              const selected = item.id === selectedViewRunId;
              return <li key={item.id}><button type="button" aria-pressed={selected} onClick={() => setSelectedRunId(item.id)} className={`w-full rounded-xl border p-4 text-left transition ${selected ? "border-blue-500 bg-blue-50 ring-1 ring-blue-200" : "border-slate-200 bg-white hover:border-blue-300"}`}>
                <span className="flex items-center justify-between gap-2"><strong className="text-sm text-slate-900">Analysis v{item.version}</strong><Badge className="capitalize">{item.status}</Badge></span>
                <span className="mt-2 block text-xs text-slate-600">{item.methodology || "Methodology pending"} · {new Date(item.created_at).toLocaleString()}</span>
                <span className="mt-1 block text-xs text-slate-500">{item.requirement_count} requirements · {item.risk_count} risks</span>
                {selected && <span className="mt-2 block text-xs font-semibold text-blue-800">{isHistoricalView ? "Viewing historical run" : "Selected run"}</span>}
              </button></li>;
            })}</ol>
              : <p className="text-sm text-slate-600">No saved analysis runs yet. Run AI analysis to create the first version.</p>}
        {historyDetailQuery.isPending && selectedViewRunId && latestClientResult?.analysis_run_id !== selectedViewRunId && <p role="status" className="mt-3 text-sm text-slate-600">Loading selected analysis…</p>}
        {historyDetailQuery.isError && <p role="alert" className="mt-3 text-sm text-rose-800">This saved analysis could not be opened. Select another run or retry later.</p>}
      </CardContent>
    </Card>

    {!interviewQuery.isPending && !interviewComplete && <Card className="mt-5 border-amber-200 bg-amber-50/70"><CardContent className="flex flex-wrap items-center justify-between gap-3 py-5"><div><h2 className="font-semibold text-amber-950">Complete the adaptive interview first</h2><p className="mt-1 text-sm text-amber-900">AI analysis requires stakeholder answers and will not invent missing interview responses.</p></div><Link to={`/projects/${projectId}/questionnaire`} className="inline-flex items-center gap-2 text-sm font-semibold text-blue-800 no-underline">Open interview <ArrowRight size={15} /></Link></CardContent></Card>}
    {interviewQuery.isError && !interviewComplete && <p className="mt-3 text-sm text-slate-600">Interview status is unavailable. Open the questionnaire to start or complete the interview.</p>}

    {runError && !(activeRun && runError instanceof ApiError && runError.status === 409) && <div role="alert" className="mt-5 rounded-xl border border-rose-200 bg-rose-50 p-4 text-sm text-rose-900"><div className="flex items-start gap-2"><AlertCircle size={17} className="mt-0.5 shrink-0" /><div><p className="font-semibold">Analysis could not be completed</p><p className="mt-1">{errorMessage(runError)}</p><Button className="mt-3" variant="outline" onClick={() => mutation.mutate()} disabled={!interviewComplete || running}>Retry analysis</Button></div></div></div>}

    {result?.status === "partial" && <div role="status" className="mt-5 rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-950"><p className="font-semibold">Analysis completed with fallback data.</p><p className="mt-1">One or more agents used deterministic fallback results. Review the findings with stakeholders before relying on them.</p>{result.warnings.map((warning, index) => <p key={index} className="mt-1 text-amber-900">{warning}</p>)}</div>}
    {result?.status === "failed" && <div role="alert" className="mt-5 rounded-xl border border-rose-200 bg-rose-50 p-4 text-sm text-rose-900"><p className="font-semibold">Requirements analysis could not be generated.</p><p className="mt-1">{result.errors[0]?.message || "Please try running the analysis again."}</p><Button className="mt-3" variant="outline" onClick={() => mutation.mutate()} disabled={!interviewComplete || running}>Retry analysis</Button></div>}
    {result?.status === "completed" && <div role="status" className="mt-5 flex items-center gap-2 rounded-xl border border-emerald-200 bg-emerald-50 p-4 text-sm text-emerald-900"><CheckCircle2 size={17} aria-hidden="true" />Both agents completed successfully. Review the draft before using it as a project baseline.</div>}

    {result && <div className="mt-6 grid gap-6">
      <p className="text-sm font-semibold text-slate-700">{isHistoricalView ? `Viewing historical analysis v${result.analysis_run_version}` : `Analysis version ${result.analysis_run_version}`}</p>
      <div className="grid gap-3 sm:grid-cols-2"><Card className="p-4"><p className="text-xs font-medium text-slate-500">Requirements analysis</p><p className="mt-1 break-all text-sm font-semibold text-slate-900">{result.requirements_analysis_id || "Not generated"}</p><Badge className="mt-2">{reqStatus || "not run"}</Badge></Card><Card className="p-4"><p className="text-xs font-medium text-slate-500">Governance analysis</p><p className="mt-1 break-all text-sm font-semibold text-slate-900">{result.governance_analysis_id || "Not generated"}</p><Badge className="mt-2">{govStatus || "not run"}</Badge></Card></div>
      {result.requirements_analysis && <RequirementsView result={result.requirements_analysis} />}
      {result.governance_analysis && <GovernanceView result={result.governance_analysis.result} />}
      {result.errors.length > 0 && result.status !== "failed" && <Card><CardHeader><CardTitle>Issues requiring review</CardTitle></CardHeader><CardContent className="space-y-2">{result.errors.map((item, index) => <p key={index} className="rounded-lg bg-amber-50 p-3 text-sm text-amber-950">{item.message}</p>)}</CardContent></Card>}
      <p className="flex items-center gap-2 text-xs text-slate-500"><FileCheck2 size={14} aria-hidden="true" />Draft analysis · execution {result.orchestration_id}</p>
    </div>}

    {!result && !running && !historyDetailQuery.isPending && <Card className="mt-5"><CardContent className="flex min-h-36 flex-col items-center justify-center gap-2 py-8 text-center"><Circle size={20} className="text-slate-300" aria-hidden="true" /><h2 className="font-semibold text-slate-900">No AI analysis yet</h2><p className="max-w-lg text-sm leading-6 text-slate-600">After the interview is complete, run the workflow to create reviewable requirements and a governance plan.</p></CardContent></Card>}
  </PageFrame>;
}
