from fastapi import APIRouter, Depends

from app.core.security import get_current_user
from app.models.schemas import ContextIn, SummarizeOut
from app.services.summarize_service import SummarizeService

router = APIRouter()


@router.post("", response_model=SummarizeOut)
def summarize(body: ContextIn, uid: str = Depends(get_current_user)):
    return SummarizeService.summarize(body.context or "", uid)
