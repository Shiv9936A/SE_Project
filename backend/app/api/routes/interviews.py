"""Adaptive requirements interview endpoints."""
from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.schemas.interviews import InterviewAnswerRequest, InterviewStartRequest, InterviewState
from app.services.interview import interview_service

router = APIRouter(prefix="/projects/{project_id}/interview", tags=["adaptive interview"])

@router.post("/start", response_model=InterviewState, status_code=status.HTTP_200_OK, summary="Start or resume project discovery interview")
def start_interview(project_id: str, payload: InterviewStartRequest, db: Session = Depends(get_db)):
    return interview_service.start(db, project_id, payload.project_idea.strip(), payload.business_objective.strip(), payload.users_roles.strip())

@router.post("/answer", response_model=InterviewState, summary="Save an answer and select the next adaptive question")
def answer_interview(project_id: str, payload: InterviewAnswerRequest, db: Session = Depends(get_db)):
    return interview_service.answer(db, project_id, payload.question_id, payload.answer, skipped=payload.skipped)

@router.get("/state", response_model=InterviewState, summary="Get persisted interview state")
def interview_state(project_id: str, db: Session = Depends(get_db)):
    return interview_service.get_state(db, project_id)

@router.post("/complete", response_model=InterviewState, summary="Complete the requirements interview")
def complete_interview(project_id: str, db: Session = Depends(get_db)):
    return interview_service.complete(db, project_id)
