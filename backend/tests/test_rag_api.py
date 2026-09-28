import re
from pathlib import Path

from langchain_core.embeddings import Embeddings
from langchain_core.messages import AIMessage

from app.core.exceptions import AppError
from app.services.embedding_service import embedding_service
from app.services.llm_service import LLMService
from app.services.prompt_service import PromptService, SYSTEM_INSTRUCTIONS
from app.services.rag_service import rag_service
from app.services.retrieval_service import retrieval_service
from app.services.vector_store_service import ChromaVectorStore


class FakeEmbeddings(Embeddings):
    @staticmethod
    def _vector(text):
        words = text.lower().split()
        return [float(sum("loan" in word or "application" in word for word in words)),
                float(sum("audit" in word for word in words)),
                float(sum("security" in word for word in words)),
                float(sum(not any(term in word for term in ("loan", "application", "audit", "security"))
                          for word in words))]

    def embed_documents(self, texts):
        return [self._vector(text) for text in texts]

    def embed_query(self, text):
        return self._vector(text)


class FakeLLM:
    def __init__(self):
        self.calls = []

    def invoke(self, messages):
        self.calls.append(messages)
        user_prompt = messages[-1].content
        match = re.search(r"\[chunk_id=(\d+);", user_prompt)
        if match:
            return AIMessage(content=f"The project evidence covers loan applications [chunk_id={match.group(1)}].")
        return AIMessage(content=("There is insufficient information in the available project context "
                                  "to answer this reliably. Please provide relevant requirements.")
                         )


def configure_rag(monkeypatch, tmp_path: Path):
    embeddings = FakeEmbeddings()
    store = ChromaVectorStore(tmp_path / "rag-chroma")
    llm = FakeLLM()
    monkeypatch.setattr(embedding_service, "embeddings", embeddings)
    monkeypatch.setattr(embedding_service, "vector_store", store)
    monkeypatch.setattr(retrieval_service, "embeddings", embeddings)
    monkeypatch.setattr(retrieval_service, "vector_store", store)
    monkeypatch.setattr(rag_service, "llm", LLMService(llm))
    return llm


def create_project(client, payload):
    response = client.post("/api/projects", json=payload)
    assert response.status_code == 201, response.text
    return response.json()


def upload_and_embed(client, project_id, filename, text):
    response = client.post(f"/api/projects/{project_id}/documents",
                           files={"file": (filename, text.encode(), "text/plain")})
    assert response.status_code == 201, response.text
    document_id = response.json()["document_id"]
    embedded = client.post(f"/api/projects/{project_id}/documents/{document_id}/embed")
    assert embedded.status_code == 200, embedded.text
    return document_id


def test_prompt_assembly_includes_all_named_context_sections_and_citation():
    system, prompt = PromptService().build(
        {"project_name": "Loan portal"}, {"risk_level": "High"},
        [{"chunk_id": "42", "document_id": "doc-1", "score": 0.91,
          "filename": "notes.txt", "page_number": -1, "text": "Keep an audit trail."}],
        "What evidence supports the approach?",
    )
    assert system == SYSTEM_INSTRUCTIONS
    assert prompt.index("PROJECT INFORMATION") < prompt.index("QUESTIONNAIRE RESPONSES")
    assert prompt.index("QUESTIONNAIRE RESPONSES") < prompt.index("RETRIEVED DOCUMENT CONTEXT")
    assert prompt.index("RETRIEVED DOCUMENT CONTEXT") < prompt.index("USER QUESTION")
    assert "[chunk_id=42; document_id=doc-1" in prompt
    assert "Keep an audit trail." in prompt
    assert "What evidence supports the approach?" in prompt
    assert "insufficient information" in system


def test_ask_retrieves_grounded_chunks_and_persists_conversation(client, project_payload, questionnaire_payload,
                                                                  monkeypatch, tmp_path):
    llm = configure_rag(monkeypatch, tmp_path)
    project = create_project(client, project_payload)
    saved = client.post(f"/api/projects/{project['id']}/questionnaire", json=questionnaire_payload)
    assert saved.status_code == 200
    document_id = upload_and_embed(client, project["id"], "loan-policy.txt",
                                   "Loan applications require a documented review and an audit trail.")

    response = client.post(f"/api/projects/{project['id']}/ask", json={
        "question": "What documentation applies to loan applications?", "top_k": 5,
    })
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["answer"].startswith("The project evidence")
    assert len(result["sources"]) == 1
    assert result["sources"][0]["document_id"] == document_id
    assert result["sources"][0]["chunk_id"] in result["answer"]
    prompt = llm.calls[0][-1].content
    assert "QUESTIONNAIRE RESPONSES" in prompt and '"risk_level": "High"' in prompt
    assert "PROJECT INFORMATION" in prompt and project["project_name"] in prompt
    assert "RETRIEVED DOCUMENT CONTEXT" in prompt and "Loan applications require" in prompt

    continued = client.post(f"/api/projects/{project['id']}/ask", json={
        "question": "What about audit records?", "conversation_id": result["conversation_id"],
    })
    assert continued.status_code == 200, continued.text
    history = client.get(f"/api/projects/{project['id']}/conversations/{result['conversation_id']}")
    assert history.status_code == 200
    messages = history.json()["messages"]
    assert [message["role"] for message in messages] == ["user", "assistant", "user", "assistant"]
    assert messages[0]["content"] == "What documentation applies to loan applications?"
    assert messages[-1]["content"] == continued.json()["answer"]


def test_insufficient_context_is_explicit_and_has_no_sources(client, project_payload, monkeypatch, tmp_path):
    llm = configure_rag(monkeypatch, tmp_path)
    project = create_project(client, project_payload)
    response = client.post(f"/api/projects/{project['id']}/ask", json={
        "question": "Which compliance rule applies?", "score_threshold": 0.95,
    })
    assert response.status_code == 200, response.text
    result = response.json()
    assert "insufficient information" in result["answer"].lower()
    assert result["sources"] == []
    assert "No relevant document chunks were retrieved." in llm.calls[0][-1].content


def test_chat_returns_cited_retrieval_only_answer_when_llm_is_unavailable(
    client, project_payload, monkeypatch, tmp_path,
):
    configure_rag(monkeypatch, tmp_path)

    class UnavailableLLM:
        def generate(self, *_args):
            raise AppError("Gemini is temporarily overloaded.", 502)

    monkeypatch.setattr(rag_service, "llm", UnavailableLLM())
    project = create_project(client, project_payload)
    document_id = upload_and_embed(
        client, project["id"], "delivery-notes.txt",
        "The project requires an auditable review before loan approval.",
    )

    response = client.post(f"/api/projects/{project['id']}/ask", json={
        "question": "What review is required?", "top_k": 5,
    })

    assert response.status_code == 200, response.text
    result = response.json()
    assert result["degraded"] is True
    assert "could not synthesize an answer" in result["answer"]
    assert "auditable review before loan approval" in result["answer"]
    assert f"[chunk_id={result['sources'][0]['chunk_id']}]" in result["answer"]
    assert result["sources"][0]["document_id"] == document_id

    history = client.get(
        f"/api/projects/{project['id']}/conversations/{result['conversation_id']}"
    ).json()
    assert history["messages"][-1]["content"] == result["answer"]


def test_rag_respects_score_threshold_and_metadata_filter(client, project_payload, monkeypatch, tmp_path):
    configure_rag(monkeypatch, tmp_path)
    project = create_project(client, project_payload)
    target_id = upload_and_embed(client, project["id"], "target.txt", "Loan application review and records.")
    upload_and_embed(client, project["id"], "unrelated.txt", "Network security perimeter monitoring.")

    high_match = client.post(f"/api/projects/{project['id']}/ask", json={
        "question": "Loan application records", "score_threshold": 0.2,
        "filters": {"filename": "target.txt"},
    })
    assert high_match.status_code == 200, high_match.text
    assert [source["document_id"] for source in high_match.json()["sources"]] == [target_id]

    no_match = client.post(f"/api/projects/{project['id']}/ask", json={
        "question": "Loan application records", "score_threshold": 0.99,
        "filters": {"filename": "target.txt"},
    })
    assert no_match.status_code == 200
    assert no_match.json()["sources"] == []


def test_evaluate_rag_exposes_retrieval_context_prompt_answer_and_metrics(
    client, project_payload, monkeypatch, tmp_path, caplog
):
    llm = configure_rag(monkeypatch, tmp_path)
    project = create_project(client, project_payload)
    document_id = upload_and_embed(client, project["id"], "evaluation.txt",
                                   "Loan applications require an auditable review.")
    caplog.set_level("INFO", logger="app.services.rag_service")

    response = client.post(f"/api/projects/{project['id']}/evaluate-rag", json={
        "question": "How are loan applications reviewed?", "top_k": 5,
        "score_threshold": 0.2,
    })
    assert response.status_code == 200, response.text
    evaluation = response.json()
    assert evaluation["project_id"] == project["id"]
    assert evaluation["retrieved_chunks"][0]["rank"] == 1
    assert evaluation["retrieved_chunks"][0]["document_id"] == document_id
    assert evaluation["retrieved_chunks"][0]["score"] > 0
    assert evaluation["retrieved_chunks"][0]["metadata"]["filename"] == "evaluation.txt"
    assert "Loan applications require" in evaluation["selected_context"]
    assert "[chunk_id=" in evaluation["final_prompt"]["user"]
    assert evaluation["retrieved_chunks"][0]["chunk_id"] in evaluation["answer"]
    assert evaluation["metrics"]["prompt_size_chars"] > 0
    assert evaluation["metrics"]["prompt_token_estimate"] > 0
    assert evaluation["metrics"]["answer_generation_time_ms"] >= 0
    assert any(getattr(record, "retrieval_time_ms", None) is not None
               and getattr(record, "prompt_size_chars", None) > 0
               and getattr(record, "prompt_token_estimate", None) > 0
               and getattr(record, "answer_generation_time_ms", None) is not None
               and getattr(record, "answer_token_estimate", None) > 0
               for record in caplog.records)


def test_retrieval_debug_returns_ranked_metadata_and_precision(client, project_payload, monkeypatch, tmp_path):
    llm = configure_rag(monkeypatch, tmp_path)
    project = create_project(client, project_payload)
    relevant_id = upload_and_embed(client, project["id"], "relevant.txt",
                                   "Loan application approvals need documented review.")
    upload_and_embed(client, project["id"], "irrelevant.txt",
                     "Network security monitoring protects infrastructure.")

    response = client.get(f"/api/projects/{project['id']}/retrieval-debug", params={
        "question": "loan application review", "top_k": 2, "score_threshold": -1,
    })
    assert response.status_code == 200, response.text
    results = response.json()["retrieved_chunks"]
    assert results
    assert [item["rank"] for item in results] == list(range(1, len(results) + 1))
    assert results[0]["document_id"] == relevant_id
    assert results[0]["metadata"]["project_id"] == project["id"]
    assert results[0]["metadata"]["filename"] == "relevant.txt"
    relevant_ids = {relevant_id}
    precision_at_1 = sum(item["document_id"] in relevant_ids for item in results[:1]) / min(1, len(results))
    assert precision_at_1 == 1.0

    filtered = client.get(f"/api/projects/{project['id']}/retrieval-debug", params={
        "question": "loan application review", "top_k": 5, "score_threshold": -1,
        "filters": '{"filename":"irrelevant.txt"}',
    })
    assert filtered.status_code == 200
    assert all(item["metadata"]["filename"] == "irrelevant.txt"
               for item in filtered.json()["retrieved_chunks"])
    assert llm.calls == []
