import { describe, expect, it, vi } from "vitest";
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import ChatPage from "@/pages/ChatPage";
import { api, type ApiProject, type ApiRAGAnswer } from "@/services/api";
import { renderAtRoute } from "@/test/render";

const project: ApiProject = {
  id: "project-1", project_name: "Lending modernization", description: "Modernize loan decisions and servicing.",
  domain: "Loan processing", organization_type: "Retail bank", team_size: 8, stakeholders: "Operations",
  initial_requirements: null, created_at: "2026-01-01", updated_at: "2026-01-02",
};

describe("chat assistant page", () => {
  it("keeps the submitted question visible in a stable loading state", async () => {
    vi.spyOn(api, "getProject").mockResolvedValue(project);
    vi.spyOn(api, "listConversations").mockResolvedValue([]);
    vi.spyOn(api, "getConversation").mockResolvedValue({
      id: "conversation-2", project_id: "project-1", created_at: "2026-01-03", messages: [
        { id: 2, conversation_id: "conversation-2", role: "assistant", content: "Review the scorecard.", created_at: "2026-01-03" },
      ],
    });
    let finishAsk!: (answer: ApiRAGAnswer) => void;
    vi.spyOn(api, "askQuestion").mockReturnValue(new Promise((resolve) => { finishAsk = resolve; }));

    renderAtRoute(<ChatPage />, "/projects/project-1/chat", "/projects/:projectId/chat");
    await userEvent.type(await screen.findByRole("textbox", { name: "Ask a question" }), "Which delivery approach fits?");
    await userEvent.click(screen.getByRole("button", { name: "Send question" }));

    expect(await screen.findByRole("status")).toHaveTextContent("Searching project context and preparing a grounded answer");
    expect(screen.getByLabelText("Your question")).toHaveTextContent("Which delivery approach fits?");
    expect(screen.queryByText("What would you like to understand?")).not.toBeInTheDocument();

    finishAsk({ answer: "Review the scorecard.", sources: [], conversation_id: "conversation-2" });
    expect(await screen.findByText("Review the scorecard.")).toBeInTheDocument();
  });

  it("submits questions and shows the response citation", async () => {
    vi.spyOn(api, "getProject").mockResolvedValue(project);
    vi.spyOn(api, "listConversations").mockResolvedValue([]);
    vi.spyOn(api, "askQuestion").mockResolvedValue({
      answer: "Use review gates for high impact loan decisions [chunk_id=12].",
      sources: [{ chunk_id: "12", document_id: "doc-1", score: 0.91, filename: "requirements.txt" }],
      conversation_id: "conversation-1",
    });
    vi.spyOn(api, "getConversation").mockResolvedValue({
      id: "conversation-1", project_id: "project-1", created_at: "2026-01-03",
      messages: [
        { id: 1, conversation_id: "conversation-1", role: "user", content: "What controls are needed?", created_at: "2026-01-03" },
        { id: 2, conversation_id: "conversation-1", role: "assistant", content: "Use review gates for high impact loan decisions [chunk_id=12].", created_at: "2026-01-03" },
      ],
    });

    const { queryClient } = renderAtRoute(<ChatPage />, "/projects/project-1/chat", "/projects/:projectId/chat");
    vi.spyOn(queryClient, "invalidateQueries").mockReturnValue(new Promise<void>(() => {}));

    await userEvent.type(await screen.findByRole("textbox", { name: "Ask a question" }), "What controls are needed?");
    await userEvent.click(screen.getByRole("button", { name: "Send question" }));
    expect(await screen.findByText(/Use review gates for high impact loan decisions/)).toBeInTheDocument();
    await waitFor(() => expect(screen.queryByRole("status")).not.toBeInTheDocument());
    expect(await screen.findByText(/requirements.txt · chunk 12/)).toBeInTheDocument();
    expect(api.askQuestion).toHaveBeenCalledWith("project-1", "What controls are needed?", undefined);
  });
});
