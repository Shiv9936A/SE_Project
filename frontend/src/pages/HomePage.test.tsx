import { describe, expect, it, vi } from "vitest";
import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import HomePage from "@/pages/HomePage";
import { api } from "@/services/api";
import { renderWithProviders } from "@/test/render";

describe("home dashboard", () => {
  it("shows real backend analytics and opens the existing projects list", async () => {
    vi.spyOn(api, "getDashboardAnalytics").mockResolvedValue({
      project_count: 4, document_count: 9, embedded_document_count: 7,
      recommendation_count: 3, conversation_count: 12,
    });
    vi.spyOn(api, "listProjects").mockResolvedValue([{
      id: "project-1", project_name: "Lending modernization", description: "Upgrade loan decisions for customers.",
      domain: "Loan processing", organization_type: "Retail bank", team_size: 8, stakeholders: "Operations",
      initial_requirements: null, created_at: "2026-01-01", updated_at: "2026-01-02",
    }]);

    renderWithProviders(<HomePage />);

    expect(await screen.findByText("4")).toBeInTheDocument();
    expect(screen.queryByText("Lending modernization")).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: /Existing project/i }));
    expect(await screen.findByText("Lending modernization")).toBeInTheDocument();
    expect(api.listProjects).toHaveBeenCalledOnce();
  });
});
