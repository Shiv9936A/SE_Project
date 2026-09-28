"""Provider-swappable chat model adapter for RAG and SDLC recommendations."""
import logging
import time

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from app.core.config import settings
from app.core.exceptions import AppError

logger = logging.getLogger(__name__)


class GeminiChatProvider:
    """Adapt Google's official Gemini SDK to the chat message interface used by RAG."""

    def __init__(self, api_key: str, model: str, fallback_model: str = "", client=None):
        from google import genai
        from google.genai import types

        self.client = client or genai.Client(api_key=api_key)
        self.model = model
        # Accept a comma-separated failover chain while remaining compatible
        # with the original single fallback setting.
        self.fallback_models = list(dict.fromkeys(
            candidate.strip()
            for candidate in fallback_model.split(",")
            if candidate.strip() and candidate.strip() != model
        ))
        self._config_type = types.GenerateContentConfig

    def invoke(self, messages: list) -> AIMessage:
        system_prompt = "\n\n".join(
            message.content for message in messages if isinstance(message, SystemMessage)
        )
        user_prompt = "\n\n".join(
            message.content for message in messages if isinstance(message, HumanMessage)
        )
        config = self._config_type(system_instruction=system_prompt, temperature=0)
        models_to_try = [self.model, *self.fallback_models]
        previous_error = None
        response = None
        for index, model in enumerate(models_to_try):
            for attempt in range(2):
                try:
                    response = self.client.models.generate_content(
                        model=model, contents=user_prompt, config=config,
                    )
                    break
                except Exception as error:
                    if not self._is_temporary_capacity_error(error):
                        if previous_error is not None:
                            raise error from previous_error
                        raise
                    prior_error = previous_error
                    previous_error = error
                    if attempt == 0:
                        logger.warning(
                            "Gemini model returned a temporary capacity error; retrying once",
                            extra={"provider": "gemini", "model": model,
                                   "failure_type": type(error).__name__},
                        )
                        time.sleep(0.5)
                        continue
                    if index == len(models_to_try) - 1:
                        if prior_error is not None:
                            raise error from prior_error
                        raise
                    logger.warning(
                        "Gemini model unavailable after retry; trying next configured model",
                        extra={"provider": "gemini", "model": model,
                               "next_model": models_to_try[index + 1],
                               "failure_type": type(error).__name__},
                    )
                    break
            if response is not None:
                break
        return AIMessage(content=self._response_text(response))

    @staticmethod
    def _is_temporary_capacity_error(error: Exception) -> bool:
        code = getattr(error, "code", None)
        status = str(getattr(error, "status", "")).upper()
        message = str(error).upper()
        return code in {429, 500, 502, 503, 504} or status in {
            "UNAVAILABLE", "RESOURCE_EXHAUSTED", "INTERNAL", "DEADLINE_EXCEEDED",
        } or any(marker in message for marker in (
            "503 UNAVAILABLE", "429 RESOURCE_EXHAUSTED", "HIGH DEMAND",
        ))

    @staticmethod
    def _response_text(response) -> str:
        """Read the SDK convenience text or assemble text from candidate parts.

        google-genai's ``response.text`` can raise when a response has no text
        candidate (for example, a safety block), so inspect candidates as a fallback.
        """
        try:
            text = response.get("text") if isinstance(response, dict) else response.text
        except (AttributeError, ValueError):
            text = None
        if isinstance(text, str) and text.strip():
            return text.strip()

        candidates = response.get("candidates", []) if isinstance(response, dict) else getattr(response, "candidates", [])
        parts_text: list[str] = []
        for candidate in candidates or []:
            content = candidate.get("content") if isinstance(candidate, dict) else getattr(candidate, "content", None)
            parts = content.get("parts", []) if isinstance(content, dict) else getattr(content, "parts", [])
            for part in parts or []:
                part_text = part.get("text") if isinstance(part, dict) else getattr(part, "text", None)
                if isinstance(part_text, str) and part_text.strip():
                    parts_text.append(part_text.strip())
        return "\n".join(parts_text)


def create_chat_model():
    provider = settings.llm_provider.lower()
    if provider == "gemini":
        if not settings.gemini_api_key:
            raise AppError("GEMINI_API_KEY is required to generate an answer.", 503)
        return GeminiChatProvider(
            api_key=settings.gemini_api_key,
            model=settings.gemini_model,
            fallback_model=settings.gemini_fallback_model,
        )
    if provider == "openai":
        if not settings.openai_api_key:
            raise AppError("OPENAI_API_KEY is required to generate an answer.", 503)
        return ChatOpenAI(model=settings.llm_model, api_key=settings.openai_api_key, temperature=0)
    raise AppError(f"Unsupported LLM provider '{settings.llm_provider}'.", 503)


class LLMService:
    def __init__(self, model=None):
        self.model = model

    def generate(self, system_prompt: str, user_prompt: str | None = None) -> str:
        # One-argument form is useful for a direct provider smoke test.
        if user_prompt is None:
            user_prompt = system_prompt
            system_prompt = "You are a helpful assistant."
        try:
            if self.model is None:
                self.model = create_chat_model()
            model = self.model
            response = model.invoke([SystemMessage(content=system_prompt), HumanMessage(content=user_prompt)])
        except Exception as exc:
            logger.exception(
                "Language model generation failed",
                extra={"provider": settings.llm_provider, "model": _configured_model()},
            )
            if isinstance(exc, AppError):
                raise
            message = "The configured language model could not generate an answer."
            if settings.app_environment.lower() in {"development", "dev", "local"}:
                message = f"{message} {type(exc).__name__}: {exc}"
            raise AppError(message, 502) from exc
        content = response.content
        if isinstance(content, str):
            answer = content.strip()
        else:
            answer = "\n".join(
                part["text"] for part in content
                if isinstance(part, dict) and isinstance(part.get("text"), str)
            ).strip()
        if not answer:
            logger.error(
                "Language model returned an empty response",
                extra={"provider": settings.llm_provider, "model": _configured_model()},
            )
            raise AppError("The language model returned an empty answer.", 502)
        return answer


def _configured_model() -> str:
    return settings.gemini_model if settings.llm_provider.lower() == "gemini" else settings.llm_model


llm_service = LLMService()


def get_llm_service() -> LLMService:
    """Return the shared provider-configured generation service."""
    return llm_service
