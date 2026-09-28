from io import BytesIO

from docx import Document
from reportlab.pdfgen import canvas

from app.core.config import settings
from app.parsers.docx_parser import DOCXParser
from app.parsers.pdf_parser import PDFParser
from app.parsers.txt_parser import TXTParser
from app.models import DocumentChunk
from app.services.chunking_service import ChunkingService


def make_pdf(text: str = "Loan applicants need a clear decision status.") -> bytes:
    buffer = BytesIO()
    pdf = canvas.Canvas(buffer)
    pdf.drawString(72, 720, text)
    pdf.save()
    return buffer.getvalue()


def make_docx(text: str = "The system must record each approval decision.") -> bytes:
    document = Document()
    document.add_paragraph(text)
    buffer = BytesIO()
    document.save(buffer)
    return buffer.getvalue()


def make_project(client, project_payload):
    return client.post("/api/projects", json=project_payload).json()


def test_txt_upload_persists_file_document_and_chunks(client, project_payload):
    project = make_project(client, project_payload)
    content = b"The platform shall retain application decisions for seven years."
    response = client.post(f"/api/projects/{project['id']}/documents", files={"file": ("policy.txt", content, "text/plain")})
    assert response.status_code == 201, response.text
    result = response.json()
    assert result["filename"] == "policy.txt"
    assert result["status"] == "processed"
    assert result["chunk_count"] == 1

    listed = client.get(f"/api/projects/{project['id']}/documents").json()
    assert len(listed) == 1
    assert listed[0]["original_filename"] == "policy.txt"
    assert listed[0]["chunk_count"] == 1
    stored = list((settings.upload_directory / project["id"]).iterdir())
    assert len(stored) == 1 and stored[0].name != "policy.txt"

    preview = client.get(f"/api/projects/{project['id']}/documents/{result['document_id']}/preview").json()
    assert preview == {"filename": "policy.txt", "extracted_text": content.decode(), "page_count": None, "chunk_count": 1}
    chunks = client.get(f"/api/projects/{project['id']}/documents/{result['document_id']}/chunks").json()
    assert chunks["total"] == 1
    assert chunks["items"][0]["chunk_text"] == content.decode()
    assert chunks["items"][0]["chunk_size"] == len(content.decode())
    assert all(chunks["items"][0][field] is None for field in
               ("embedding_model", "embedding_status", "chunk_hash", "token_count"))


def test_vector_search_metadata_is_nullable_and_requested_indexes_exist():
    table = DocumentChunk.__table__
    for field in ("embedding_model", "embedding_status", "chunk_hash", "token_count"):
        assert table.c[field].nullable
    index_columns = {tuple(column.name for column in index.columns) for index in table.indexes}
    assert ("document_id",) in index_columns
    assert ("chunk_index",) in index_columns
    assert ("chunk_hash",) in index_columns


def test_pdf_upload_parses_pages_and_creates_chunks(client, project_payload):
    project = make_project(client, project_payload)
    response = client.post(f"/api/projects/{project['id']}/documents", files={"file": ("spec.pdf", make_pdf(), "application/pdf")})
    assert response.status_code == 201, response.text
    preview = client.get(f"/api/projects/{project['id']}/documents/{response.json()['document_id']}/preview").json()
    assert preview["page_count"] == 1
    assert "clear decision status" in preview["extracted_text"]
    assert preview["chunk_count"] >= 1


def test_docx_upload_extracts_paragraph_and_table_text(client, project_payload):
    project = make_project(client, project_payload)
    response = client.post(f"/api/projects/{project['id']}/documents", files={"file": ("spec.docx", make_docx(), "application/vnd.openxmlformats-officedocument.wordprocessingml.document")})
    assert response.status_code == 201, response.text
    preview = client.get(f"/api/projects/{project['id']}/documents/{response.json()['document_id']}/preview").json()
    assert "record each approval decision" in preview["extracted_text"]
    assert preview["page_count"] is None


def test_individual_parsers_return_text_pages_and_metadata(tmp_path):
    txt = tmp_path / "notes.txt"
    txt.write_text("Stakeholders need an audit trail.", encoding="utf-8")
    assert TXTParser().parse(txt)["metadata"]["format"] == "txt"
    pdf = tmp_path / "notes.pdf"
    pdf.write_bytes(make_pdf())
    assert PDFParser().parse(pdf)["pages"][0]["page_number"] == 1
    docx = tmp_path / "notes.docx"
    docx.write_bytes(make_docx())
    parsed = DOCXParser().parse(docx)
    assert parsed["text"] and "pages" in parsed and parsed["metadata"]["format"] == "docx"


def test_chunking_respects_config_and_preserves_page_metadata(monkeypatch):
    monkeypatch.setattr(settings, "chunk_size", 100)
    monkeypatch.setattr(settings, "chunk_overlap", 20)
    parsed = {
        "text": "x" * 260,
        "pages": [{"page_number": 2, "text": "x" * 260}],
        "metadata": {"format": "pdf"},
    }
    chunks = ChunkingService().split(parsed, "spec.pdf")
    assert len(chunks) >= 3
    assert [chunk["chunk_index"] for chunk in chunks] == list(range(len(chunks)))
    assert all(chunk["chunk_size"] <= 100 for chunk in chunks)
    assert all(chunk["page_number"] == 2 and chunk["metadata_json"]["source_filename"] == "spec.pdf" for chunk in chunks)


def test_invalid_extension_is_rejected(client, project_payload):
    project = make_project(client, project_payload)
    response = client.post(f"/api/projects/{project['id']}/documents", files={"file": ("payload.exe", b"no", "application/octet-stream")})
    assert response.status_code == 415
    assert "PDF, DOCX, or TXT" in response.json()["detail"]


def test_empty_upload_is_rejected(client, project_payload):
    project = make_project(client, project_payload)
    response = client.post(f"/api/projects/{project['id']}/documents", files={"file": ("empty.txt", b"  \n", "text/plain")})
    assert response.status_code == 422
    assert "empty" in response.json()["detail"]


def test_oversized_upload_is_rejected(client, project_payload):
    project = make_project(client, project_payload)
    size = settings.max_upload_size_mb * 1024 * 1024 + 1
    response = client.post(f"/api/projects/{project['id']}/documents", files={"file": ("large.txt", b"x" * size, "text/plain")})
    assert response.status_code == 413
    assert "20 MB" in response.json()["detail"]


def test_corrupt_document_is_rejected_and_not_persisted(client, project_payload):
    project = make_project(client, project_payload)
    response = client.post(f"/api/projects/{project['id']}/documents", files={"file": ("broken.pdf", b"not a pdf", "application/pdf")})
    assert response.status_code == 422
    assert client.get(f"/api/projects/{project['id']}/documents").json() == []
    assert list((settings.upload_directory / project["id"]).iterdir()) == []


def test_document_not_found_for_another_project(client, project_payload):
    first = make_project(client, project_payload)
    second_payload = {**project_payload, "project_name": "Different project"}
    second = make_project(client, second_payload)
    uploaded = client.post(f"/api/projects/{first['id']}/documents", files={"file": ("a.txt", b"some text", "text/plain")}).json()
    response = client.get(f"/api/projects/{second['id']}/documents/{uploaded['document_id']}")
    assert response.status_code == 404
