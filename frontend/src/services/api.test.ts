import { afterEach, describe, expect, it, vi } from "vitest";
import { api } from "@/services/api";

function jsonResponse(payload: unknown, status = 200) {
  return { ok: status >= 200 && status < 300, status, json: async () => payload } as Response;
}

describe("backend API service", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("sends an SDLC recommendation request to the FastAPI endpoint", async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse({ recommended_model: "V-Model" }));
    vi.stubGlobal("fetch", fetchMock);

    await api.generateRecommendation("project 1", 4);

    expect(fetchMock).toHaveBeenCalledWith("http://127.0.0.1:8000/api/projects/project%201/recommend-sdlc", expect.objectContaining({
      method: "POST", body: JSON.stringify({ top_k: 4 }),
    }));
  });

  it("uses multipart form data for document uploads", async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse({ document_id: "doc-1" }, 201));
    vi.stubGlobal("fetch", fetchMock);
    const file = new File(["project notes"], "notes.txt", { type: "text/plain" });

    await api.uploadDocument("project-1", file);

    const init = fetchMock.mock.calls[0][1] as RequestInit;
    expect(init.body).toBeInstanceOf(FormData);
    expect((init.body as FormData).get("file")).toBeInstanceOf(File);
  });

  it("surfaces backend validation messages with the HTTP status", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse({ detail: "Questionnaire required." }, 409)));

    await expect(api.generateRecommendation("project-1")).rejects.toMatchObject({
      message: "Questionnaire required.", status: 409,
    });
  });

  it("preserves query cancellation instead of reporting a backend connection error", async () => {
    const controller = new AbortController();
    const abortError = new DOMException("The operation was aborted.", "AbortError");
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(abortError));

    await expect(api.getEmbeddingStatus("project-1", "doc-1", controller.signal))
      .rejects.toBe(abortError);
  });
});
