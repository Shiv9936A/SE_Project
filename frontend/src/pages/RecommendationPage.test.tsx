import { describe, expect, it, vi } from "vitest";
import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import RecommendationPage from "@/pages/RecommendationPage";
import { api, type ApiProject, type ApiRecommendation } from "@/services/api";
import { renderAtRoute } from "@/test/render";

const project: ApiProject = {
  id: "project-1", project_name: "Lending modernization", description: "Modernize loan decisions and servicing.",
  domain: "Loan processing", organization_type: "Retail bank", team_size: 8, stakeholders: "Operations",
  initial_requirements: null, created_at: "2026-01-01", updated_at: "2026-01-02",
  questionnaire: { requirement_stability: "Frequently Changing", risk_level: "High", security_criticality: "High", compliance_criticality: "High", expected_changes: "Frequent", continuous_delivery: "Yes", legacy_integration: "No", formal_verification: "Yes", stakeholder_availability: "High", complexity: "High", project_size: "Large", failure_impact: "High", testing_requirement: "Extensive", budget_constraint: "Medium", timeline_constraint: "Strict" },
};

const recommendation: ApiRecommendation = {
  id: "rec-1", project_id: "project-1", recommended_model: "V-Model", confidence: 78,
  reasoning: "Formal verification and high assurance are important for this project.",
  alternative_models: [{ model: "Incremental", score: 76, rationale: "Strong phased delivery fit." }],
  strengths: ["Clear verification gates."], risks: ["Frequent changes need close stakeholder review."],
  implementation_notes: ["Automate regression and security checks."],
  model_scores: [{ model: "V-Model", score: 89 }, { model: "Incremental", score: 76 }], sources: [], created_at: "2026-01-03",
};

describe("recommendation page", () => {
  it("renders the generated recommendation and can request a new run", async () => {
    vi.spyOn(api, "getProject").mockResolvedValue(project);
    vi.spyOn(api, "recommendationHistory").mockResolvedValue([recommendation]);
    vi.spyOn(api, "generateRecommendation").mockResolvedValue({ ...recommendation, id: "rec-2" });

    renderAtRoute(<RecommendationPage />, "/projects/project-1/recommendation", "/projects/:projectId/recommendation");

    expect(await screen.findByRole("heading", { name: "V-Model" })).toBeInTheDocument();
    expect(screen.getByText("Formal verification and high assurance are important for this project.")).toBeInTheDocument();
    expect(screen.getByText("Automate regression and security checks.")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: /Regenerate recommendation/i }));
    expect(api.generateRecommendation).toHaveBeenCalledWith("project-1");
  });
});
