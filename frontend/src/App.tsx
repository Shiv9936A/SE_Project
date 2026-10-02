import { QueryClientProvider, useMutationState, useQuery } from "@tanstack/react-query";
import { BrowserRouter, Link, Route, Routes, useLocation } from "react-router-dom";
import { LoaderCircle } from "lucide-react";
import { ErrorBoundary } from "@/components/error-boundary";
import { ToastProvider } from "@/components/toast-provider";
import { queryClient } from "@/lib/query-client";
import { queryKeys } from "@/lib/query-keys";
import { api } from "@/services/api";
import ChatPage from "@/pages/ChatPage";
import DocumentsPage from "@/pages/DocumentsPage";
import ProjectDashboardPage from "@/pages/ProjectDashboardPage";
import HomePage from "@/pages/HomePage";
import ProjectFlowPage from "@/pages/ProjectFlowPage";
import RecommendationPage from "@/pages/RecommendationPage";
import MultiAgentAnalysisPage from "@/pages/MultiAgentAnalysisPage";

function BackgroundAnalysisMonitor() {
  const { pathname } = useLocation();
  const pathProjectId = pathname.match(/^\/projects\/([^/]+)/)?.[1] || "";
  const projectId = pathProjectId && pathProjectId !== "new" ? decodeURIComponent(pathProjectId) : "";
  const pendingRuns = useMutationState({
    filters: { mutationKey: ["orchestration", projectId], status: "pending" },
    select: (mutation) => mutation.state.status,
  });
  const pendingRecommendations = useMutationState({
    filters: { mutationKey: ["sdlc-recommendation", projectId], status: "pending" },
    select: (mutation) => mutation.state.status,
  });
  const historyQuery = useQuery({
    queryKey: queryKeys.analysisRuns(projectId),
    queryFn: ({ signal }) => api.listAnalysisRuns(projectId, 50, 0, signal),
    enabled: Boolean(projectId),
    staleTime: 0,
    refetchOnMount: "always",
    refetchInterval: (query) => pendingRuns.length || query.state.data?.some((run) => run.status === "running") ? 2000 : false,
    refetchIntervalInBackground: true,
  });
  const activeRun = historyQuery.data?.find((run) => run.status === "running");
  if (!projectId || (!activeRun && !pendingRuns.length && !pendingRecommendations.length)) return null;
  const analysisPending = Boolean(activeRun || pendingRuns.length);
  const destination = analysisPending ? `/projects/${projectId}/analysis` : `/projects/${projectId}/recommendation`;
  const label = analysisPending
    ? activeRun ? `AI analysis v${activeRun.version} is running in the background.` : "AI analysis is running in the background."
    : "SDLC recommendation is running in the background.";
  return <div role="status" className="fixed bottom-4 right-4 z-50 flex max-w-sm items-center gap-3 rounded-xl border border-blue-200 bg-white p-4 text-sm text-slate-800 shadow-lg">
    <LoaderCircle className="shrink-0 animate-spin text-blue-600" size={18} />
    <span>{label} <Link className="font-semibold text-blue-700 underline" to={destination}>View progress</Link></span>
  </div>;
}

export default function App() {
  return <ErrorBoundary><QueryClientProvider client={queryClient}><ToastProvider><BrowserRouter>
    <BackgroundAnalysisMonitor />
    <Routes>
      <Route path="/" element={<HomePage />} />
      <Route path="/projects/new" element={<ProjectFlowPage />} />
      <Route path="/projects/:projectId/questionnaire" element={<ProjectFlowPage />} />
      <Route path="/projects/:projectId" element={<ProjectDashboardPage />} />
      <Route path="/projects/:projectId/recommendation" element={<RecommendationPage />} />
      <Route path="/projects/:projectId/analysis" element={<MultiAgentAnalysisPage />} />
      <Route path="/projects/:projectId/chat" element={<ChatPage />} />
      <Route path="/projects/:projectId/documents" element={<DocumentsPage />} />
      <Route path="*" element={<HomePage />} />
    </Routes>
  </BrowserRouter></ToastProvider></QueryClientProvider></ErrorBoundary>;
}
