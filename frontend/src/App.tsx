import { QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Route, Routes } from "react-router-dom";
import { ErrorBoundary } from "@/components/error-boundary";
import { ToastProvider } from "@/components/toast-provider";
import { queryClient } from "@/lib/query-client";
import ChatPage from "@/pages/ChatPage";
import DocumentsPage from "@/pages/DocumentsPage";
import ProjectDashboardPage from "@/pages/ProjectDashboardPage";
import HomePage from "@/pages/HomePage";
import ProjectFlowPage from "@/pages/ProjectFlowPage";
import RecommendationPage from "@/pages/RecommendationPage";

export default function App() {
  return <ErrorBoundary><QueryClientProvider client={queryClient}><ToastProvider><BrowserRouter>
    <Routes>
      <Route path="/" element={<HomePage />} />
      <Route path="/projects/new" element={<ProjectFlowPage />} />
      <Route path="/projects/:projectId/questionnaire" element={<ProjectFlowPage />} />
      <Route path="/projects/:projectId" element={<ProjectDashboardPage />} />
      <Route path="/projects/:projectId/recommendation" element={<RecommendationPage />} />
      <Route path="/projects/:projectId/chat" element={<ChatPage />} />
      <Route path="/projects/:projectId/documents" element={<DocumentsPage />} />
      <Route path="*" element={<HomePage />} />
    </Routes>
  </BrowserRouter></ToastProvider></QueryClientProvider></ErrorBoundary>;
}
