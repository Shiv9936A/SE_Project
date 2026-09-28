import { describe, expect, it } from "vitest";
import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import ProjectFlowPage from "@/pages/ProjectFlowPage";
import { ToastProvider } from "@/components/toast-provider";
import { render } from "@testing-library/react";

describe("questionnaire form", () => {
  it("shows required field validation before advancing", async () => {
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(<QueryClientProvider client={queryClient}><ToastProvider><MemoryRouter initialEntries={["/projects/new"]}><Routes><Route path="/projects/new" element={<ProjectFlowPage />} /></Routes></MemoryRouter></ToastProvider></QueryClientProvider>);

    await userEvent.click(screen.getByRole("button", { name: /^Continue$/ }));
    expect(await screen.findByText("Enter a project name.")).toBeInTheDocument();
    expect(screen.getByText("Choose a financial domain.")).toBeInTheDocument();
  });
});
