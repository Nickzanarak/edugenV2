from fastapi import APIRouter

from app.models.schemas import QAIn
from app.services.qa_service import QAService

router = APIRouter()


@router.post("")
def qa(body: QAIn):
    return QAService.answer(body.context or "", body.question or "")
