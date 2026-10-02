from pathlib import Path

from langchain_core.embeddings import Embeddings

from app.core.config import settings
from app.services.embedding_service import embedding_service
from app.services.retrieval_service import retrieval_service
from app.services.vector_store_service import ChromaVectorStore


class FakeEmbeddings(Embeddings):
    """Small deterministic provider for tests; it never calls an external API."""

    @staticmethod
    def _vector(text: str) -> list[float]:
        words = text.lower().split()
        return [float(sum(word.startswith("loan") or word.startswith("application") for word in words)),
                float(sum("audit" in word for word in words)),
                float(sum("security" in word for word in words)),
                float(sum(not any(term in word for term in ("loan", "application", "audit", "security"))
                          for word in words))]

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._vector(text) for text in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._vector(text)


def create_project(client, payload, name="Vector search test"):
    return client.post("/api/projects", json={**payload, "project_name": name}).json()


def upload_text(client, project_id: str, filename: str, text: str) -> str:
    response = client.post(f"/api/projects/{project_id}/documents",
                           files={"file": (filename, text.encode(), "text/plain")})
    assert response.status_code == 201, response.text
    return response.json()["document_id"]


def configure_vector_services(monkeypatch, tmp_path: Path):
    fake = FakeEmbeddings()
    store = ChromaVectorStore(tmp_path / "chroma-test")
    monkeypatch.setattr(settings, "embedding_model", "fake-test-embedding")
    monkeypatch.setattr(embedding_service, "embeddings", fake)
    monkeypatch.setattr(embedding_service, "vector_store", store)
    monkeypatch.setattr(retrieval_service, "embeddings", fake)
    monkeypatch.setattr(retrieval_service, "vector_store", store)
    return store


def test_embeddings_persist_to_chroma_and_duplicate_call_skips(client, project_payload, monkeypatch, tmp_path):
    store = configure_vector_services(monkeypatch, tmp_path)
    project = create_project(client, project_payload)
    document_id = upload_text(client, project["id"], "loan-policy.txt",
                              "Loan application decisions require an audit trail.")

    before = client.get(f"/api/projects/{project['id']}/documents/{document_id}/embedding-status").json()
    assert before == {"total_chunks": 1, "completed_chunks": 0, "failed_chunks": 0, "status": "pending"}

    response = client.post(f"/api/projects/{project['id']}/documents/{document_id}/embed")
    assert response.status_code == 200, response.text
    assert response.json() == {"document_id": document_id, "chunks_processed": 1, "vectors_created": 1}
    collection = store.collection()
    assert collection.name == "requirements_documents"
    assert collection.count() == 1
    record = collection.get(include=["metadatas"])
    assert record["metadatas"][0]["project_id"] == project["id"]
    assert record["metadatas"][0]["document_id"] == document_id
    assert record["metadatas"][0]["filename"] == "loan-policy.txt"
    assert "chunk_id" in record["metadatas"][0]
    assert record["metadatas"][0]["page_number"] == -1
    assert record["metadatas"][0]["embedding_model"] == "fake-test-embedding"
    assert record["metadatas"][0]["embedding_provider"] == settings.embedding_provider
    assert record["metadatas"][0]["embedding_dimension"] == 4
    chunk = client.get(f"/api/projects/{project['id']}/documents/{document_id}/chunks").json()["items"][0]
    assert chunk["embedding_model"] == "fake-test-embedding"
    assert chunk["embedding_status"] == "completed"
    assert len(chunk["chunk_hash"]) == 64
    assert chunk["token_count"] > 0

    after = client.get(f"/api/projects/{project['id']}/documents/{document_id}/embedding-status").json()
    assert after == {"total_chunks": 1, "completed_chunks": 1, "failed_chunks": 0, "status": "completed"}
    again = client.post(f"/api/projects/{project['id']}/documents/{document_id}/embed")
    assert again.json()["chunks_processed"] == 0
    assert collection.count() == 1


def test_legacy_untagged_vector_is_reembedded_with_model_metadata(client, project_payload, monkeypatch, tmp_path):
    store = configure_vector_services(monkeypatch, tmp_path)
    project = create_project(client, project_payload)
    text = "Loan application decisions require an audit trail."
    document_id = upload_text(client, project["id"], "legacy.txt", text)
    first = client.post(f"/api/projects/{project['id']}/documents/{document_id}/embed")
    assert first.status_code == 200
    chunk = client.get(f"/api/projects/{project['id']}/documents/{document_id}/chunks").json()["items"][0]
    store.delete([str(chunk["id"])])
    store.upsert(
        ids=[str(chunk["id"])], texts=[text], vectors=[FakeEmbeddings._vector(text)],
        metadata=[{"project_id": project["id"], "document_id": document_id,
                   "chunk_id": chunk["id"], "filename": "legacy.txt", "page_number": -1}],
    )
    retried = client.post(f"/api/projects/{project['id']}/documents/{document_id}/embed")
    assert retried.status_code == 200
    assert retried.json()["vectors_created"] == 1
    metadata = store.collection().get(include=["metadatas"])["metadatas"][0]
    assert metadata["embedding_model"] == settings.embedding_model
    assert metadata["embedding_provider"] == settings.embedding_provider


def test_large_document_embeddings_are_batched(client, project_payload, monkeypatch, tmp_path):
    class RecordingEmbeddings(FakeEmbeddings):
        def __init__(self):
            self.batch_sizes = []

        def embed_documents(self, texts):
            self.batch_sizes.append(len(texts))
            return super().embed_documents(texts)

    configure_vector_services(monkeypatch, tmp_path)
    recorder = RecordingEmbeddings()
    monkeypatch.setattr(embedding_service, "embeddings", recorder)
    monkeypatch.setattr(settings, "chunk_size", 32)
    monkeypatch.setattr(settings, "chunk_overlap", 0)
    monkeypatch.setattr(settings, "embedding_batch_size", 3)
    project = create_project(client, project_payload)
    document_id = upload_text(client, project["id"], "large-notes.txt", "Loan application audit. " * 20)
    response = client.post(f"/api/projects/{project['id']}/documents/{document_id}/embed")
    assert response.status_code == 200
    assert response.json()["chunks_processed"] > 3
    assert max(recorder.batch_sizes) <= 3
    assert len(recorder.batch_sizes) > 1


def test_search_is_similarity_ranked_and_filtered_by_project_and_metadata(
    client, project_payload, monkeypatch, tmp_path
):
    configure_vector_services(monkeypatch, tmp_path)
    project_a = create_project(client, project_payload, "Project A")
    loan_doc = upload_text(client, project_a["id"], "loan.txt", "Loan application decision workflow.")
    audit_doc = upload_text(client, project_a["id"], "audit.txt", "Audit and security evidence retention.")
    project_b = create_project(client, project_payload, "Project B")
    other_doc = upload_text(client, project_b["id"], "other-loan.txt", "Loan application from another project.")

    for project, document_id in ((project_a, loan_doc), (project_a, audit_doc), (project_b, other_doc)):
        assert client.post(f"/api/projects/{project['id']}/documents/{document_id}/embed").status_code == 200

    response = client.post("/api/search", json={"project_id": project_a["id"], "query": "loan application", "top_k": 5})
    assert response.status_code == 200, response.text
    results = response.json()
    assert results[0]["document_id"] == loan_doc
    assert all(row["document_id"] != other_doc for row in results)
    assert results[0]["score"] > 0

    filtered = client.post("/api/search", json={"project_id": project_a["id"], "query": "loan application",
                           "top_k": 5, "filters": {"filename": "audit.txt"}})
    assert filtered.status_code == 200, filtered.text
    assert [row["document_id"] for row in filtered.json()] == [audit_doc]


def test_embedding_failure_updates_status(client, project_payload, monkeypatch, tmp_path):
    class BrokenEmbeddings(FakeEmbeddings):
        def embed_documents(self, texts):
            raise RuntimeError("simulated provider failure")

    configure_vector_services(monkeypatch, tmp_path)
    monkeypatch.setattr(embedding_service, "embeddings", BrokenEmbeddings())
    project = create_project(client, project_payload)
    document_id = upload_text(client, project["id"], "failure.txt", "Security controls must be audited.")
    response = client.post(f"/api/projects/{project['id']}/documents/{document_id}/embed")
    assert response.status_code == 502
    status = client.get(f"/api/projects/{project['id']}/documents/{document_id}/embedding-status").json()
    assert status == {"total_chunks": 1, "completed_chunks": 0, "failed_chunks": 1, "status": "failed"}


def test_vector_store_failure_returns_safe_service_error(client, project_payload, monkeypatch, tmp_path, caplog):
    configure_vector_services(monkeypatch, tmp_path)
    project = create_project(client, project_payload)

    def unavailable(*_args, **_kwargs):
        raise RuntimeError("private storage path or provider detail")

    monkeypatch.setattr(retrieval_service.vector_store, "search", unavailable)
    caplog.set_level("ERROR", logger="app.services.retrieval_service")
    response = client.post("/api/search", json={
        "project_id": project["id"], "query": "loan application status",
    })
    assert response.status_code == 503
    assert response.json() == {"detail": "Project document search is temporarily unavailable."}
    assert "private storage path" not in response.text
    assert any(record.exc_info for record in caplog.records)
