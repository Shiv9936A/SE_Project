export const queryKeys = {
  analytics: ["analytics"] as const,
  projects: ["projects"] as const,
  project: (projectId: string) => ["project", projectId] as const,
  documents: (projectId: string) => ["documents", projectId] as const,
  embeddingStatus: (projectId: string, documentId: string) => ["embedding-status", projectId, documentId] as const,
  recommendations: (projectId: string) => ["recommendations", projectId] as const,
  conversations: (projectId: string) => ["conversations", projectId] as const,
  conversation: (projectId: string, conversationId: string) => ["conversation", projectId, conversationId] as const,
  analysisRuns: (projectId: string) => ["analysis-runs", projectId] as const,
  analysisRun: (projectId: string, runId: string) => ["analysis-run", projectId, runId] as const,
};
