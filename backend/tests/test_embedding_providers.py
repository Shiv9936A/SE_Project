"""Provider selection tests without downloading models or calling external APIs."""
import sys
from types import ModuleType

from app.core.config import settings
from app.services import embedding_service as embedding_module
from app.services.embedding_service import SentenceTransformerEmbeddings, create_embeddings


def test_local_provider_wraps_sentence_transformer_and_embeds_text(monkeypatch):
    calls = {"models": [], "encodes": []}

    class FakeSentenceTransformer:
        def __init__(self, model_name):
            calls["models"].append(model_name)

        def encode(self, texts, **kwargs):
            calls["encodes"].append((texts, kwargs))
            return [[0.25, 0.75] for _ in texts]

    fake_module = ModuleType("sentence_transformers")
    fake_module.SentenceTransformer = FakeSentenceTransformer
    monkeypatch.setitem(sys.modules, "sentence_transformers", fake_module)
    monkeypatch.setattr(settings, "embedding_provider", "local")
    monkeypatch.setattr(settings, "embedding_model", "all-MiniLM-L6-v2")

    embeddings = create_embeddings()

    assert isinstance(embeddings, SentenceTransformerEmbeddings)
    assert calls["models"] == ["all-MiniLM-L6-v2"]
    assert embeddings.embed_documents(["Loan requirements", "Audit trail"]) == [
        [0.25, 0.75], [0.25, 0.75],
    ]
    assert embeddings.embed_query("Loan requirements") == [0.25, 0.75]
    assert all(kwargs == {"convert_to_numpy": True, "normalize_embeddings": True}
               for _, kwargs in calls["encodes"])


def test_openai_provider_remains_selectable(monkeypatch):
    constructed = {}

    class FakeOpenAIEmbeddings:
        def __init__(self, **kwargs):
            constructed.update(kwargs)

    monkeypatch.setattr(settings, "embedding_provider", "openai")
    monkeypatch.setattr(settings, "embedding_model", "text-embedding-3-small")
    monkeypatch.setattr(settings, "openai_api_key", "test-key")
    monkeypatch.setattr(embedding_module, "OpenAIEmbeddings", FakeOpenAIEmbeddings)

    embeddings = create_embeddings()

    assert isinstance(embeddings, FakeOpenAIEmbeddings)
    assert constructed == {"model": "text-embedding-3-small", "api_key": "test-key"}
