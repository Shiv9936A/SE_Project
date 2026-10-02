"""Request and response contracts for adaptive interviews."""
from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field, model_validator
from typing import Literal


class InterviewStartRequest(BaseModel):
    project_idea: str = Field(min_length=8, max_length=10000)
    business_objective: str = Field(min_length=3, max_length=10000)
    users_roles: str = Field(min_length=2, max_length=10000)


class InterviewAnswerRequest(BaseModel):
    question_id: str = Field(min_length=1, max_length=100)
    answer: str = Field(default="", max_length=10000)
    skipped: bool = False

    @model_validator(mode="after")
    def require_answer_or_skip(self):
        if not self.skipped and not self.answer.strip():
            raise ValueError("Provide an answer or mark the question as skipped.")
        return self


class InterviewQuestion(BaseModel):
    id: str
    topic: str
    prompt: str
    explanation: str
    priority: Literal["high", "medium", "low"] | None = None


class InterviewAnswer(BaseModel):
    question_id: str
    topic: str
    answer: str
    skipped: bool = False


class InterviewState(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    project_id: str
    project_idea: str
    business_objective: str
    users_roles: str
    detected_domain: str
    asked_questions: list[InterviewQuestion]
    answers: list[InterviewAnswer]
    covered_topics: list[str]
    uncovered_topics: list[str]
    current_question: InterviewQuestion | None
    question_number: int
    maximum_questions: int
    status: str
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None
