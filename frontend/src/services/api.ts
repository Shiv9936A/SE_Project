import type { ProjectForm } from "@/types/project";

const configuredBaseUrl = import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000";
const API_BASE_URL = configuredBaseUrl.replace(/\/$/, "");

export type ApiQuestionnaire = {
  requirement_stability: string;
  risk_level: string;
  security_criticality: string;
  compliance_criticality: string;
  expected_changes: string;
  continuous_delivery: string;
  legacy_integration: string;
  formal_verification: string;
  stakeholder_availability: string;
  complexity: string;
  project_size: string;
  failure_impact: string;
  testing_requirement: string;
  budget_constraint: string;
  timeline_constraint: string;
  stakeholder_notes?: string | null;
};

export type ApiDocument = {
  id: string;
  project_id: string;
  original_filename: string;
  content_type: string;
  size_bytes: number;
  sha256: string;
  page_count: number | null;
  uploaded_at: string;
  chunk_count: number;
};

export type EmbeddingStatus = {
  total_chunks: number;
  completed_chunks: number;
  failed_chunks: number;
  status: "pending" | "processing" | "completed" | "failed" | string;
};

export const SUPPORTED_SDLC_MODELS = [
  "Waterfall", "V-Model", "Incremental", "Iterative", "Spiral", "Agile Scrum", "RAD",
] as const;
export type SupportedSDLCModel = typeof SUPPORTED_SDLC_MODELS[number];
export type ModelScore = { model: SupportedSDLCModel; score: number };
export type SDLCAlternative = ModelScore & { rationale: string };
export type RecommendationSource = { chunk_id: string; document_id: string; score: number; filename?: string | null };

export type ApiRecommendation = {
  id: string;
  project_id: string;
  recommended_model: SupportedSDLCModel;
  confidence: number;
  reasoning: string;
  alternative_models: SDLCAlternative[];
  strengths: string[];
  risks: string[];
  implementation_notes: string[];
  model_scores: ModelScore[];
  sources: RecommendationSource[];
  created_at: string;
};

export type ApiConversationMessage = {
  id: number;
  conversation_id: string;
  role: "user" | "assistant";
  content: string;
  created_at: string;
};

export type ApiConversation = {
  id: string;
  project_id: string;
  created_at: string;
  messages: ApiConversationMessage[];
};

export type ApiRAGAnswer = {
  answer: string;
  sources: RecommendationSource[];
  conversation_id: string;
  degraded?: boolean;
};

export type ApiSearchResult = {
  chunk_id: string;
  document_id: string;
  score: number;
  text: string;
};

export type DashboardAnalytics = {
  project_count: number;
  document_count: number;
  embedded_document_count: number;
  recommendation_count: number;
  conversation_count: number;
};

export type ApiProject = {
  id: string;
  project_name: string;
  description: string;
  domain: string;
  organization_type: string;
  team_size: number;
  stakeholders: string;
  initial_requirements: string | null;
  created_at: string;
  updated_at: string;
  questionnaire?: ApiQuestionnaire | null;
  documents?: ApiDocument[];
  recommendation?: {
    id: string;
    recommended_sdlc: string;
    confidence_score: number;
    justification: string;
    risk_factors: string[];
  } | null;
};

export class ApiError extends Error {
  constructor(message: string, readonly status?: number) {
    super(message);
    this.name = "ApiError";
  }
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  if (init.body && !(init.body instanceof FormData)) headers.set("Content-Type", "application/json");

  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, { ...init, headers });
  } catch (error) {
    // React Query aborts obsolete GETs on navigation and stale document refreshes.
    // Preserve cancellation so it is not shown as a backend connectivity error.
    if (error instanceof DOMException && error.name === "AbortError") throw error;
    throw new ApiError(`Cannot reach the backend at ${API_BASE_URL}. Start the FastAPI server and try again.`);
  }

  if (!response.ok) {
    let message = `Request failed (${response.status}).`;
    try {
      const payload = await response.json() as { detail?: string | { msg?: string }[] };
      if (typeof payload.detail === "string") message = payload.detail;
      else if (Array.isArray(payload.detail)) message = payload.detail.map((item) => item.msg).filter(Boolean).join(" ");
    } catch {
      // Keep the status message when the server does not return JSON.
    }
    throw new ApiError(message, response.status);
  }

  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}

function projectFields(values: ProjectForm) {
  return {
    project_name: values.projectName.trim(),
    description: values.description.trim(),
    domain: values.domain,
    organization_type: values.organizationType,
    team_size: values.teamSize,
    stakeholders: values.stakeholders.trim(),
    initial_requirements: values.initialRequirements.trim() || null,
  };
}

function questionnaireFields(values: ProjectForm): ApiQuestionnaire {
  return {
    requirement_stability: values.requirementStability,
    risk_level: values.riskLevel,
    security_criticality: values.securityCriticality,
    compliance_criticality: values.complianceCriticality,
    expected_changes: values.expectedChanges,
    continuous_delivery: values.continuousDelivery,
    legacy_integration: values.legacyIntegration,
    formal_verification: values.formalVerification,
    stakeholder_availability: values.stakeholderAvailability,
    complexity: values.complexity,
    project_size: values.projectSize,
    failure_impact: values.failureImpact,
    testing_requirement: values.testingRequirement,
    budget_constraint: values.budgetConstraint,
    timeline_constraint: values.timelineConstraint,
  };
}

export const api = {
  getDashboardAnalytics() {
    return request<DashboardAnalytics>("/api/analytics/summary");
  },

  listProjects() {
    return request<ApiProject[]>("/api/projects?limit=100&offset=0");
  },

  getProject(projectId: string, signal?: AbortSignal) {
    return request<ApiProject>(`/api/projects/${encodeURIComponent(projectId)}`, { signal });
  },

  createProject(values: ProjectForm) {
    return request<ApiProject>("/api/projects", {
      method: "POST",
      body: JSON.stringify(projectFields(values)),
    });
  },

  updateProject(projectId: string, values: ProjectForm) {
    return request<ApiProject>(`/api/projects/${encodeURIComponent(projectId)}`, {
      method: "PUT",
      body: JSON.stringify(projectFields(values)),
    });
  },

  saveQuestionnaire(projectId: string, values: ProjectForm) {
    return request<ApiQuestionnaire>(`/api/projects/${encodeURIComponent(projectId)}/questionnaire`, {
      method: "POST",
      body: JSON.stringify(questionnaireFields(values)),
    });
  },

  uploadDocument(projectId: string, file: File) {
    const formData = new FormData();
    formData.append("file", file, file.name);
    return request<{ document_id: string; filename: string; status: string; chunk_count: number }>(
      `/api/projects/${encodeURIComponent(projectId)}/documents`,
      { method: "POST", body: formData },
    );
  },

  listDocuments(projectId: string, signal?: AbortSignal) {
    return request<ApiDocument[]>(`/api/projects/${encodeURIComponent(projectId)}/documents`, { signal });
  },

  deleteDocument(projectId: string, documentId: string) {
    return request<void>(`/api/projects/${encodeURIComponent(projectId)}/documents/${encodeURIComponent(documentId)}`, {
      method: "DELETE",
    });
  },

  generateEmbeddings(projectId: string, documentId: string) {
    return request<{ document_id: string; chunks_processed: number; vectors_created: number }>(
      `/api/projects/${encodeURIComponent(projectId)}/documents/${encodeURIComponent(documentId)}/embed`,
      { method: "POST" },
    );
  },

  getEmbeddingStatus(projectId: string, documentId: string, signal?: AbortSignal) {
    return request<EmbeddingStatus>(
      `/api/projects/${encodeURIComponent(projectId)}/documents/${encodeURIComponent(documentId)}/embedding-status`,
      { signal },
    );
  },

  searchDocuments(projectId: string, query: string, topK = 5) {
    return request<ApiSearchResult[]>("/api/search", {
      method: "POST",
      body: JSON.stringify({ project_id: projectId, query, top_k: topK }),
    });
  },

  askQuestion(projectId: string, question: string, conversationId?: string) {
    return request<ApiRAGAnswer>(`/api/projects/${encodeURIComponent(projectId)}/ask`, {
      method: "POST",
      body: JSON.stringify({ question, conversation_id: conversationId, top_k: 5, score_threshold: 0.2 }),
    });
  },

  evaluateRAG(projectId: string, question: string) {
    return request<Record<string, unknown>>(`/api/projects/${encodeURIComponent(projectId)}/evaluate-rag`, {
      method: "POST",
      body: JSON.stringify({ question, top_k: 5, score_threshold: 0.2 }),
    });
  },

  listConversations(projectId: string, limit = 5, signal?: AbortSignal) {
    return request<ApiConversation[]>(
      `/api/projects/${encodeURIComponent(projectId)}/conversations?limit=${limit}`,
      { signal },
    );
  },

  getConversation(projectId: string, conversationId: string, signal?: AbortSignal) {
    return request<ApiConversation>(
      `/api/projects/${encodeURIComponent(projectId)}/conversations/${encodeURIComponent(conversationId)}`,
      { signal },
    );
  },

  generateRecommendation(projectId: string, topK = 5) {
    return request<ApiRecommendation>(`/api/projects/${encodeURIComponent(projectId)}/recommend-sdlc`, {
      method: "POST",
      body: JSON.stringify({ top_k: topK }),
    });
  },

  recommendationHistory(projectId: string, limit = 20) {
    return request<ApiRecommendation[]>(
      `/api/projects/${encodeURIComponent(projectId)}/recommendation-history?limit=${limit}&offset=0`,
    );
  },

  compareSDLC(projectId: string, modelA: string, modelB: string) {
    return request<Record<string, unknown>>(`/api/projects/${encodeURIComponent(projectId)}/compare-sdlc`, {
      method: "POST",
      body: JSON.stringify({ model_a: modelA, model_b: modelB, top_k: 5 }),
    });
  },
};
