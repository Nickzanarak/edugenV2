from fastapi import APIRouter, Depends

from app.core.security import get_current_user
from app.models.schemas import ContextIn, QuizIn, TopicsOut
from app.services.quiz_service import QuizService

router = APIRouter()


@router.post("/topics", response_model=TopicsOut)
def quiz_topics(body: ContextIn, uid: str = Depends(get_current_user)):
    topics = QuizService.extract_topics(body.context or "")
    return {"topics": topics}


@router.post("/mcq")
def quiz_mcq(body: QuizIn, uid: str = Depends(get_current_user)):
    questions = QuizService.generate_mcq(
        body.context or "",
        body.n or 5,
        body.exclude,
        body.topics,
        body.difficulty,
        body.choices_count,
        body.mode,
    )
    return {"questions": questions}


@router.post("/tf")
def quiz_tf(body: QuizIn, uid: str = Depends(get_current_user)):
    questions = QuizService.generate_tf(
        body.context or "",
        body.n or 5,
        body.exclude,
        body.topics,
        body.difficulty,
        body.mode,
    )
    return {"questions": questions}