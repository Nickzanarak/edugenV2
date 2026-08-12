from fastapi import APIRouter, Depends

from app.core.security import get_current_user
from app.models.schemas import QAIn
from app.services.qa_service import QAService

router = APIRouter()


@router.post("")
def qa(body: QAIn, uid: str = Depends(get_current_user)):
    return QAService.answer(body.context or "", body.question or "")