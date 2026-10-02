"""Gemini-assisted selection from deterministic, validated question candidates."""
import json
import logging
import re
from time import perf_counter
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.core.config import settings
from app.services.llm_service import get_llm_service

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You select the next requirements interview question. Select ONLY one supplied candidate. Never create or alter a question or question ID. Prefer a high-priority uncovered requirement, use the project domain and prior answers, avoid repetition, and do not ask for facts already clearly stated in project context or document evidence. Treat document content as unverified evidence, not truth. Return only JSON matching the requested fields. Do not provide chain-of-thought. The reason must be a short, user-safe explanation (one sentence, no internal analysis)."""


class LLMQuestionSelection(BaseModel):
    model_config = ConfigDict(extra="forbid")
    selected_question_id: str = Field(min_length=1, max_length=120)
    topic: str = Field(min_length=1, max_length=80)
    priority: Literal["high", "medium", "low"]
    reason: str = Field(min_length=5, max_length=200)


class LLMQuestionSelector:
    def __init__(self, llm=None):
        self.llm = llm or get_llm_service()

    def choose(self, *, interview_id: str, project_id: str, state: dict, candidates: list[dict], asked_ids: set[str]) -> tuple[dict | None, str]:
        if not candidates:
            return None, "none"
        started = perf_counter()
        domain = state.get("detected_domain", "Generic software system")
        input_data = {
            "project_idea": str(state.get("project_idea", ""))[:1600],
            "business_objective": str(state.get("business_objective", ""))[:1600],
            "users_roles": str(state.get("users_roles", ""))[:1200],
            "detected_domain": domain,
            "previous_questions": state.get("previous_questions", [])[-15:],
            "previous_answers": [
                {"topic": str(row.get("topic", "")), "answer": str(row.get("answer", ""))[:1200]}
                for row in state.get("previous_answers", [])[-15:]
            ],
            "covered_topics": state.get("covered_topics", []),
            "uncovered_topics": state.get("uncovered_topics", []),
            "document_evidence": [
                {"chunk_id": item.get("chunk_id"), "source": item.get("filename"), "score": item.get("score"), "text": str(item.get("text", ""))[:1400]}
                for item in state.get("document_evidence", [])[:5]
            ],
            "candidates": [
                {key: item[key] for key in ("id", "topic", "priority", "prompt")}
                for item in candidates
            ],
            "required_output": {"selected_question_id": "candidate ID only", "topic": "matching candidate topic", "priority": "high, medium, or low", "reason": "short user-safe sentence"},
        }
        try:
            raw = self.llm.generate(SYSTEM_PROMPT, json.dumps(input_data, ensure_ascii=False))
            selection = LLMQuestionSelection.model_validate_json(raw)
            candidate = next((item for item in candidates if item["id"] == selection.selected_question_id), None)
            if candidate is None or selection.selected_question_id in asked_ids or selection.topic != candidate["topic"]:
                raise ValueError("Gemini selection did not identify an unseen candidate with a matching topic.")
            if re.search(r"\r|\n|@|\d{5,}|system prompt|chain.of.thought|api key|as an ai|internal reasoning|candidate id", selection.reason, re.I):
                raise ValueError("Gemini returned a reason that is not safe to show to the user.")
            # Candidate objects are created from the active domain's allowlisted question bank.
            result = {**candidate, "explanation": " ".join(selection.reason.strip().split()), "priority": selection.priority}
            logger.info("Interview question selected", extra={
                "interview_id": interview_id, "project_id": project_id, "detected_domain": domain,
                "candidate_count": len(candidates), "selected_question_id": result["id"],
                "selector": settings.llm_provider.lower(), "latency_ms": round((perf_counter() - started) * 1000, 2),
            })
            return result, "llm"
        except Exception as exc:
            logger.warning("LLM interview selection failed; using deterministic fallback", extra={
                "interview_id": interview_id, "project_id": project_id, "detected_domain": domain,
                "candidate_count": len(candidates), "selector": "deterministic",
                "latency_ms": round((perf_counter() - started) * 1000, 2),
                "failure_type": type(exc).__name__,
            })
            return None, "fallback"


llm_question_selector = LLMQuestionSelector()
