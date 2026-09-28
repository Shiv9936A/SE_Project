from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import QuestionnaireResponse


def upsert(db: Session, project_id: str, values: dict) -> QuestionnaireResponse:
    answer = db.scalar(select(QuestionnaireResponse).where(QuestionnaireResponse.project_id == project_id))
    if answer is None:
        answer = QuestionnaireResponse(project_id=project_id, **values)
        db.add(answer)
    else:
        for key, value in values.items():
            setattr(answer, key, value)
    db.commit()
    db.refresh(answer)
    return answer
