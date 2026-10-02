"""LLM provider selection tests with a stubbed Google SDK and OpenAI client."""
import sys
from types import ModuleType, SimpleNamespace

from app.core.config import settings
from app.core.exceptions import AppError
from app.services import llm_service as llm_module
from app.services.llm_service import GeminiChatProvider, LLMService, create_chat_model
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage


def install_fake_google_sdk(monkeypatch):
    calls = {}

    class GenerateContentConfig:
        def __init__(self, **kwargs):
            self.values = kwargs

    class Models:
        def generate_content(self, **kwargs):
            calls["generation"] = kwargs
            return SimpleNamespace(text="Gemini grounded answer")

    class Client:
        def __init__(self, api_key):
            calls["api_key"] = api_key
            self.models = Models()

    genai_module = ModuleType("google.genai")
    genai_module.Client = Client
    types_module = ModuleType("google.genai.types")
    types_module.GenerateContentConfig = GenerateContentConfig
    genai_module.types = types_module
    google_module = ModuleType("google")
    google_module.genai = genai_module
    monkeypatch.setitem(sys.modules, "google", google_module)
    monkeypatch.setitem(sys.modules, "google.genai", genai_module)
    monkeypatch.setitem(sys.modules, "google.genai.types", types_module)
    return calls


def test_gemini_provider_uses_official_sdk_and_prompt_messages(monkeypatch):
    calls = install_fake_google_sdk(monkeypatch)
    monkeypatch.setattr(settings, "llm_provider", "gemini")
    monkeypatch.setattr(settings, "gemini_api_key", "gemini-test-key")
    monkeypatch.setattr(settings, "gemini_model", "gemini-3.8-flash")

    provider = create_chat_model()
    answer = LLMService(model=provider).generate(
        "Use the retrieved context only.", "What does the document require?"
    )

    assert isinstance(provider, GeminiChatProvider)
    assert calls["api_key"] == "gemini-test-key"
    request = calls["generation"]
    assert request["model"] == "gemini-3.8-flash"
    assert request["contents"] == "What does the document require?"
    assert request["config"].values == {
        "system_instruction": "Use the retrieved context only.",
        "temperature": 0,
    }
    assert answer == "Gemini grounded answer"


def test_gemini_provider_maps_system_and_user_messages(monkeypatch):
    calls = install_fake_google_sdk(monkeypatch)
    provider = GeminiChatProvider(api_key="test-key", model="gemini-2.5-flash")

    response = provider.invoke([
        SystemMessage(content="System instructions"),
        HumanMessage(content="Question and retrieved context"),
    ])

    assert isinstance(response, AIMessage)
    assert response.content == "Gemini grounded answer"
    assert calls["generation"]["contents"] == "Question and retrieved context"
    assert calls["generation"]["config"].values["system_instruction"] == "System instructions"


def test_gemini_provider_falls_back_to_candidate_parts(monkeypatch):
    class Models:
        def generate_content(self, **kwargs):
            class Response:
                candidates = [SimpleNamespace(content=SimpleNamespace(parts=[
                    SimpleNamespace(text="Candidate response"),
                ]))]

                @property
                def text(self):
                    raise ValueError("Text unavailable when candidate parts are used")

            return Response()

    provider = GeminiChatProvider(api_key="test-key", model="gemini-2.5-flash",
                                  client=SimpleNamespace(models=Models()))
    result = provider.invoke([HumanMessage(content="hello")])
    assert result.content == "Candidate response"


def test_gemini_provider_fails_over_on_temporary_overload(monkeypatch):
    monkeypatch.setattr(llm_module.time, "sleep", lambda _seconds: None)
    attempted = []

    class Overloaded(Exception):
        code = 503
        status = "UNAVAILABLE"

    class Models:
        def generate_content(self, **kwargs):
            attempted.append(kwargs["model"])
            if kwargs["model"] != "gemini-3.7-flash":
                raise Overloaded("This model is currently experiencing high demand")
            return SimpleNamespace(text="Fallback answer")

    provider = GeminiChatProvider(
        api_key="test-key", model="gemini-3.8-flash",
        fallback_model="gemini-3.6-flash, gemini-3.7-flash",
        client=SimpleNamespace(models=Models()),
    )
    result = provider.invoke([HumanMessage(content="hello")])

    assert result.content == "Fallback answer"
    assert attempted == [
        "gemini-3.8-flash", "gemini-3.8-flash",
        "gemini-3.6-flash", "gemini-3.6-flash", "gemini-3.7-flash",
    ]


def test_gemini_retries_transient_error_before_failing_over(monkeypatch):
    monkeypatch.setattr(llm_module.time, "sleep", lambda _seconds: None)
    attempted = []

    class Overloaded(Exception):
        code = 503
        status = "UNAVAILABLE"

    class Models:
        def generate_content(self, **kwargs):
            attempted.append(kwargs["model"])
            if len(attempted) == 1:
                raise Overloaded("temporary overload")
            return SimpleNamespace(text="Recovered on retry")

    provider = GeminiChatProvider(
        api_key="test-key", model="gemini-3.8-flash",
        client=SimpleNamespace(models=Models()),
    )
    result = provider.invoke([HumanMessage(content="hello")])

    assert result.content == "Recovered on retry"
    assert attempted == ["gemini-3.8-flash", "gemini-3.8-flash"]


def test_gemini_rate_limit_uses_configured_fallback(monkeypatch):
    monkeypatch.setattr(llm_module.time, "sleep", lambda _seconds: None)

    class RateLimited(Exception):
        code = 429
        status = "RESOURCE_EXHAUSTED"

    class Models:
        def generate_content(self, **kwargs):
            if kwargs["model"] == "primary":
                raise RateLimited("temporary quota limit")
            return SimpleNamespace(text="Fallback after rate limit")

    provider = GeminiChatProvider(
        api_key="test-key", model="primary", fallback_model="secondary",
        client=SimpleNamespace(models=Models()),
    )
    assert provider.invoke([HumanMessage(content="hello")]).content == "Fallback after rate limit"


def test_gemini_provider_does_not_fail_over_for_permanent_errors():
    attempted = []

    class InvalidKey(Exception):
        code = 401
        status = "UNAUTHENTICATED"

    class Models:
        def generate_content(self, **kwargs):
            attempted.append(kwargs["model"])
            raise InvalidKey("invalid API key")

    provider = GeminiChatProvider(
        api_key="test-key", model="gemini-3.8-flash", fallback_model="gemini-3.6-flash",
        client=SimpleNamespace(models=Models()),
    )
    try:
        provider.invoke([HumanMessage(content="hello")])
        assert False, "Expected authentication exception"
    except InvalidKey:
        assert attempted == ["gemini-3.8-flash"]


def test_generation_logs_traceback_and_returns_detail_in_development(monkeypatch, caplog):
    class FailingModel:
        def invoke(self, messages):
            raise RuntimeError("Gemini service unavailable")

    monkeypatch.setattr(settings, "app_environment", "development")
    monkeypatch.setattr(settings, "llm_provider", "gemini")
    with caplog.at_level("ERROR"):
        try:
            LLMService(model=FailingModel()).generate("system", "hello")
            assert False, "Expected provider exception"
        except AppError as error:
            assert error.status_code == 502
            assert "RuntimeError: Gemini service unavailable" in error.message
    assert "Language model generation failed" in caplog.text
    assert "Traceback (most recent call last)" in caplog.text


def test_generation_rejects_empty_response(monkeypatch):
    class EmptyModel:
        def invoke(self, messages):
            return AIMessage(content=" ")

    monkeypatch.setattr(settings, "llm_provider", "gemini")
    try:
        LLMService(model=EmptyModel()).generate("system", "hello")
        assert False, "Expected empty response exception"
    except AppError as error:
        assert error.status_code == 502
        assert "empty answer" in error.message


def test_openai_provider_remains_selectable(monkeypatch):
    constructed = {}

    class FakeChatOpenAI:
        def __init__(self, **kwargs):
            constructed.update(kwargs)

    monkeypatch.setattr(settings, "llm_provider", "openai")
    monkeypatch.setattr(settings, "llm_model", "gpt-4o-mini")
    monkeypatch.setattr(settings, "openai_api_key", "openai-test-key")
    monkeypatch.setattr(llm_module, "ChatOpenAI", FakeChatOpenAI)

    model = create_chat_model()

    assert isinstance(model, FakeChatOpenAI)
    assert constructed == {
        "model": "gpt-4o-mini", "api_key": "openai-test-key", "temperature": 0,
    }
