import { describe, expect, it, vi } from "vitest";
import { cleanup, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import MultiAgentAnalysisPage from "@/pages/MultiAgentAnalysisPage";
import { ApiError, api, type ApiProject, type GovernanceAnalysis, type InterviewState, type OrchestrationResult } from "@/services/api";
import { renderAtRoute } from "@/test/render";

const project: ApiProject = {
  id: "project-1", project_name: "Digital loan approval", description: "Assess and approve loan applications.",
  domain: "Lending", organization_type: "Bank", team_size: 8, stakeholders: "Applicants and reviewers",
  initial_requirements: null, created_at: "2026-09-01", updated_at: "2026-09-02",
};

const interview: InterviewState = {
  id: "interview-1", project_id: project.id, project_idea: "Loan approval", business_objective: "Reduce manual work",
  users_roles: "Applicants and reviewers", detected_domain: "Finance", asked_questions: [],
  answers: [{ question_id: "q-1", topic: "workflow", answer: "Applicants submit information for review." }],
  covered_topics: ["workflow"], uncovered_topics: [], current_question: null, question_number: 1,
  maximum_questions: 1, status: "completed", created_at: "2026-09-01", updated_at: "2026-09-02", completed_at: "2026-09-02",
};

const governance: GovernanceAnalysis = {
  id: "gov-1", project_id: project.id, requirements_analysis_id: "req-1", version: 1,
  status: "needs_review", provider: "mock", model: "mock", created_at: "2026-09-02", updated_at: "2026-09-02",
  result: {
    project_id: project.id, requirements_analysis_id: "req-1",
    methodology: { name: "V-Model", confidence: 0.82, reasoning: [{ factor: "Assurance", observation: "Verification is required.", impact: "Pair each delivery stage with testing.", source_references: ["questionnaire:formal_verification"] }] },
    project_assessment: { complexity: "high", risk_level: "high", requirements_stability: "moderate", integration_complexity: "medium", security_sensitivity: "high", compliance_impact: "high" },
    baseline_scores: [],
    development_lifecycle: [{ phase: "Requirements", activities: ["Review needs"], deliverables: ["SRS"], exit_criteria: ["Stakeholder review recorded"], requirement_references: ["REQ-F-001"] }],
    testing_strategy: { unit_testing: [{ recommendation: "Test decision rules.", requirement_references: ["REQ-F-001"] }], integration_testing: [], system_testing: [], acceptance_testing: [], security_testing: [], performance_testing: [] },
    security_governance: [], documentation_requirements: [],
    governance_checkpoints: [{ checkpoint: "Requirements Review", purpose: "Confirm scope.", entry_conditions: ["Draft ready"], exit_conditions: ["Scope agreed"], required_artifacts: ["SRS"] }],
    risks: [{ risk_id: "RISK-001", title: "Unclear decision rules", description: "Loan eligibility rules require review.", severity: "high", likelihood: "medium", mitigation: "Assign a business owner to confirm policy.", source_references: ["REQ-F-001"], basis: "potential" }],
    quality_gates: [{ gate: "Traceability gate", checks: ["Map requirements to test cases."], requirement_references: ["REQ-F-001"] }],
    prerequisites: [], evidence: [], unresolved_questions: [], fallback_reason: null,
  },
};

const completeResult: OrchestrationResult = {
  orchestration_id: "orch-1", analysis_run_id: "run-1", analysis_run_version: 1, project_id: project.id, status: "completed", requirements_analysis_id: "req-1", governance_analysis_id: "gov-1",
  agents: [{ name: "requirements", status: "completed" }, { name: "governance", status: "completed" }],
  requirements_analysis: {
    analysis_id: "req-1", project_id: project.id, version: 1, status: "needs_review", provider: "mock", model: "mock", created_at: "2026-09-02",
    summary: "Applicants can submit a loan application for a reviewer to assess.",
    requirements: [{ requirement_id: "REQ-F-001", category: "functional", title: "Submit application", description: "The system shall accept a loan application from an applicant.", priority: "high", confidence: 0.9, source_type: "interview", source_reference: "interview:q-1", evidence: "Applicants submit information for review.", acceptance_criteria: ["A reviewer can see submitted applications."], ambiguities: ["Eligibility limits are not defined."], dependencies: ["REQ-DATA-001"], tags: ["loan"], testability: "medium", missing_information: ["Define application retention period."] }],
    ambiguities: [{ description: "Eligibility limits are not defined.", related_requirement_id: "REQ-F-001", severity: "high", clarification_question: "Which eligibility rules should be applied?", source_reference: "interview:q-1" }],
    conflicts: [{ description: "The project summary and interview describe different review ownership.", severity: "medium", sources: [{ source_type: "project_profile", source_reference: "project:description", evidence: "Review by operations" }, { source_type: "interview", source_reference: "interview:q-1", evidence: "Review by lending staff" }], clarification_question: "Who owns final review?" }],
    completeness: [{ area: "security and privacy", status: "partial", note: "Confirm access rules." }], clarification_questions: ["Who owns final review?", "Which eligibility rules should be applied?"], quality_assessment: { traceability: "high" }, evidence_sources: [],
  },
  governance_analysis: governance, warnings: [], errors: [], created_at: "2026-09-02T12:00:00Z",
};

function setup({ completed = true, history = [] }: { completed?: boolean; history?: Awaited<ReturnType<typeof api.listAnalysisRuns>> } = {}) {
  vi.spyOn(api, "getProject").mockResolvedValue(project);
  vi.spyOn(api, "getInterviewState").mockResolvedValue({ ...interview, status: completed ? "completed" : "in_progress" });
  vi.spyOn(api, "listAnalysisRuns").mockResolvedValue(history);
  return renderAtRoute(<MultiAgentAnalysisPage />, "/projects/project-1/analysis", "/projects/:projectId/analysis");
}

describe("multi-agent analysis page", () => {
  it("renders the AI Analysis section, project name, and run action", async () => {
    setup();
    expect(await screen.findByRole("heading", { name: "AI Analysis" })).toBeInTheDocument();
    expect(screen.getByText("Digital loan approval")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Run AI Analysis" })).toBeEnabled();
  });

  it("shows saved versions and loads a selected historical agent result", async () => {
    const history: Awaited<ReturnType<typeof api.listAnalysisRuns>> = [
      { id: "run-2", project_id: project.id, version: 2, status: "completed", orchestration_version: "langgraph-v1", started_at: "2026-09-03", completed_at: "2026-09-03", created_at: "2026-09-03", requirements_analysis_id: "req-2", governance_analysis_id: "gov-2", requirement_count: 0, ambiguity_count: 0, conflict_count: 0, risk_count: 0, methodology: "V-Model", warnings: [], errors: [] },
      { id: "run-1", project_id: project.id, version: 1, status: "completed", orchestration_version: "langgraph-v1", started_at: "2026-09-02", completed_at: "2026-09-02", created_at: "2026-09-02", requirements_analysis_id: "req-1", governance_analysis_id: "gov-1", requirement_count: 1, ambiguity_count: 1, conflict_count: 1, risk_count: 1, methodology: "V-Model", warnings: [], errors: [] },
    ];
    const list = vi.spyOn(api, "listAnalysisRuns");
    const detail = { ...completeResult, analysis_run_id: "run-1", analysis_run_version: 1 };
    vi.spyOn(api, "getAnalysisRun").mockResolvedValue({
      id: "run-1", project_id: project.id, version: 1, status: "completed", orchestration_version: "langgraph-v1", started_at: "2026-09-02", completed_at: "2026-09-02", created_at: "2026-09-02", requirements_analysis_id: "req-1", governance_analysis_id: "gov-1", requirement_count: 1, ambiguity_count: 1, conflict_count: 1, risk_count: 1, methodology: "V-Model", warnings: [], errors: [],
      agents: detail.agents, requirements_analysis: detail.requirements_analysis, governance_analysis: detail.governance_analysis,
    });
    setup({ history });
    expect(await screen.findByRole("heading", { name: "Analysis history" })).toBeInTheDocument();
    expect(await screen.findByRole("button", { name: /Analysis v1/ })).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: /Analysis v1/ }));
    expect(await screen.findByText("Viewing historical analysis v1")).toBeInTheDocument();
    expect(await screen.findByRole("button", { name: "Return to latest" })).toBeInTheDocument();
    expect(list).toHaveBeenCalledWith(project.id, 50, 0, expect.anything());
  });

  it("disables duplicate submissions and reports honest in-flight state", async () => {
    setup();
    let finish!: (value: OrchestrationResult) => void;
    vi.spyOn(api, "orchestrateProject").mockReturnValue(new Promise((resolve) => { finish = resolve; }));
    const button = await screen.findByRole("button", { name: "Run AI Analysis" });
    await userEvent.click(button);
    expect(screen.getByRole("button", { name: "Analysis running" })).toBeDisabled();
    expect(screen.getByText(/AI analysis is running. Agent statuses will be shown/)).toBeInTheDocument();
    expect(screen.getAllByText("Waiting for the orchestration result")).toHaveLength(2);
    finish(completeResult);
    expect(await screen.findByText(/Both agents completed successfully/)).toBeInTheDocument();
  });

  it("renders validated requirements, traceability, criteria, and grouping", async () => {
    setup();
    vi.spyOn(api, "orchestrateProject").mockResolvedValue(completeResult);
    await userEvent.click(await screen.findByRole("button", { name: "Run AI Analysis" }));
    expect(await screen.findByText("Applicants can submit a loan application for a reviewer to assess.")).toBeInTheDocument();
    expect(screen.getByRole("region", { name: "Functional requirements" })).toBeInTheDocument();
    await userEvent.click(screen.getByText("Submit application"));
    expect(screen.getAllByText("interview:q-1").length).toBeGreaterThan(0);
    expect(screen.getByText("Applicants submit information for review.")).toBeInTheDocument();
    expect(screen.getByText("A reviewer can see submitted applications.")).toBeInTheDocument();
  });

  it("renders governance methodology, assessment, lifecycle, testing, risks, checkpoints, and gates", async () => {
    setup();
    vi.spyOn(api, "orchestrateProject").mockResolvedValue(completeResult);
    await userEvent.click(await screen.findByRole("button", { name: "Run AI Analysis" }));
    expect(await screen.findByRole("heading", { name: "V-Model" })).toBeInTheDocument();
    expect(screen.getByText("Verification is required.")).toBeInTheDocument();
    expect(screen.getByText("Project assessment")).toBeInTheDocument();
    expect(screen.getByText("Stakeholder review recorded")).toBeInTheDocument();
    expect(screen.getByText("Test decision rules.")).toBeInTheDocument();
    expect(screen.getByText("Unclear decision rules")).toBeInTheDocument();
    expect(screen.getByText("Requirements Review")).toBeInTheDocument();
    expect(screen.getByText("Traceability gate")).toBeInTheDocument();
    expect(screen.getByText("Map requirements to test cases.")).toBeInTheDocument();
  });

  it("uses backend agent statuses rather than assuming success from HTTP 200", async () => {
    setup();
    vi.spyOn(api, "orchestrateProject").mockResolvedValue({ ...completeResult, status: "partial", agents: [{ name: "requirements", status: "completed" }, { name: "governance", status: "partial" }] });
    await userEvent.click(await screen.findByRole("button", { name: "Run AI Analysis" }));
    expect(await screen.findByText("Analysis completed with fallback data.")).toBeInTheDocument();
    expect(screen.getByText("Completed with fallback")).toBeInTheDocument();
    expect(screen.getByText(/one or more agents used deterministic fallback results/i)).toBeInTheDocument();
  });

  it("shows ambiguities, conflicts, missing information, and clarification questions", async () => {
    setup();
    vi.spyOn(api, "orchestrateProject").mockResolvedValue(completeResult);
    await userEvent.click(await screen.findByRole("button", { name: "Run AI Analysis" }));
    expect(await screen.findAllByText("Which eligibility rules should be applied?")).toHaveLength(2);
    expect(screen.getByText("Conflicts")).toBeInTheDocument();
    expect(screen.getAllByText("Who owns final review?").length).toBeGreaterThan(0);
    expect(screen.getByText("Define application retention period.")).toBeInTheDocument();
    expect(screen.getByText(/security and privacy · partial/i)).toBeInTheDocument();
  });

  it("shows only populated testing strategy categories and does not fabricate other rows", async () => {
    setup();
    vi.spyOn(api, "orchestrateProject").mockResolvedValue(completeResult);
    await userEvent.click(await screen.findByRole("button", { name: "Run AI Analysis" }));
    expect(await screen.findByText("Unit testing")).toBeInTheDocument();
    expect(screen.queryByText("Performance testing")).not.toBeInTheDocument();
  });

  it("does not mark quality gates or checkpoints complete without backend state", async () => {
    setup();
    vi.spyOn(api, "orchestrateProject").mockResolvedValue(completeResult);
    await userEvent.click(await screen.findByRole("button", { name: "Run AI Analysis" }));
    expect(await screen.findByText(/does not report completion state/i)).toBeInTheDocument();
    expect(screen.getByText(/no checkpoint is marked complete automatically/i)).toBeInTheDocument();
    expect(screen.queryByRole("checkbox")).not.toBeInTheDocument();
  });

  it("explains that a completed interview is required and blocks the run", async () => {
    setup({ completed: false });
    expect(await screen.findByText("Complete the adaptive interview first")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Open interview" })).toHaveAttribute("href", "/projects/project-1/questionnaire");
    expect(screen.getByRole("button", { name: "Run AI Analysis" })).toBeDisabled();
  });

  it("shows a safe friendly message for backend errors and allows retry", async () => {
    setup();
    const run = vi.spyOn(api, "orchestrateProject").mockRejectedValueOnce(new ApiError("raw traceback and provider internals", 500)).mockResolvedValueOnce(completeResult);
    await userEvent.click(await screen.findByRole("button", { name: "Run AI Analysis" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("AI analysis could not be completed right now.");
    expect(screen.queryByText(/raw traceback|provider internals/i)).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Retry analysis" }));
    expect(await screen.findByText(/Both agents completed successfully/)).toBeInTheDocument();
    expect(run).toHaveBeenCalledTimes(2);
  });

  it("explains a missing interview conflict returned by the API", async () => {
    setup();
    vi.spyOn(api, "orchestrateProject").mockRejectedValue(new ApiError("backend detail", 409));
    await userEvent.click(await screen.findByRole("button", { name: "Run AI Analysis" }));
    expect(await screen.findByText("No completed interview was found. Complete the adaptive interview before running AI analysis.")).toBeInTheDocument();
    expect(screen.queryByText("backend detail")).not.toBeInTheDocument();
  });

  it("handles not found, validation, rate limit, timeout, and network failures safely", async () => {
    const cases: [ApiError, string][] = [
      [new ApiError("raw", 404), "This project could not be found."],
      [new ApiError("raw", 422), "The project inputs could not be processed."],
      [new ApiError("raw", 429), "The analysis service is temporarily busy."],
      [new ApiError("raw", 504), "The analysis took too long to finish."],
      [new ApiError("raw"), "Could not connect to the analysis service."],
    ];
    for (const [error, message] of cases) {
      cleanup();
      setup();
      vi.spyOn(api, "orchestrateProject").mockRejectedValue(error);
      await userEvent.click(await screen.findByRole("button", { name: "Run AI Analysis" }));
      expect(await screen.findByRole("alert")).toHaveTextContent(message);
    }
  });

  it("renders a requirements-only partial result when governance is skipped", async () => {
    setup();
    const partial: OrchestrationResult = { ...completeResult, status: "partial", governance_analysis_id: null, governance_analysis: null,
      agents: [{ name: "requirements", status: "completed" }, { name: "governance", status: "skipped" }],
      warnings: ["Governance skipped after validation."], errors: [{ code: "GOVERNANCE_AGENT_FAILED", message: "Governance analysis could not be completed.", recoverable: true }] };
    vi.spyOn(api, "orchestrateProject").mockResolvedValue(partial);
    await userEvent.click(await screen.findByRole("button", { name: "Run AI Analysis" }));
    expect(await screen.findByText("Analysis completed with fallback data.")).toBeInTheDocument();
    expect(screen.getByText("Requirements Analysis")).toBeInTheDocument();
    expect(screen.queryByText("V-Model")).not.toBeInTheDocument();
    expect(screen.getByText("Skipped")).toBeInTheDocument();
  });

  it("shows inferred evidence status without inventing a source", async () => {
    setup();
    const inferred = structuredClone(completeResult);
    inferred.requirements_analysis!.requirements[0] = { ...inferred.requirements_analysis!.requirements[0], source_type: "inferred", source_reference: null, evidence: "" };
    vi.spyOn(api, "orchestrateProject").mockResolvedValue(inferred);
    await userEvent.click(await screen.findByRole("button", { name: "Run AI Analysis" }));
    await userEvent.click(await screen.findByText("Submit application"));
    expect(screen.getByText("Source: Inference (not directly sourced)")).toBeInTheDocument();
    expect(screen.getByText("No source reference was returned.")).toBeInTheDocument();
    expect(screen.getByText("No direct evidence was provided for this item.")).toBeInTheDocument();
  });

  it("refreshes interview readiness when project navigation returns to this route", async () => {
    setup();
    await screen.findByRole("button", { name: "Run AI Analysis" });
    expect(screen.getByRole("navigation", { name: "Project navigation" })).toHaveTextContent("AI Analysis");
    expect(screen.getByRole("link", { name: "Questionnaire" })).toHaveAttribute("href", "/projects/project-1/questionnaire");
  });
});
