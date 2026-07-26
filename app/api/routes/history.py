from fastapi import APIRouter, Depends
from app.core.security import get_current_user
from app.models.history import QuizHistoryIn, RenameHistoryIn
from app.services.history_service import HistoryService

router = APIRouter()

@router.post("/save")
def save_history_item(body: QuizHistoryIn, uid: str = Depends(get_current_user)):
    return HistoryService.save_history_item(uid, body)

@router.get("/list")
def get_history_list(uid: str = Depends(get_current_user)):
    return HistoryService.get_history_list(uid)

@router.delete("/{item_id}")
def delete_history_item(item_id: str, uid: str = Depends(get_current_user)):
    return HistoryService.delete_history_item(uid, item_id)

@router.patch("/{item_id}")
def rename_history_item(item_id: str, body: RenameHistoryIn, uid: str = Depends(get_current_user)):
    return HistoryService.rename_history_item(uid, item_id, body)

@router.patch("/update/{item_id}")
def update_history_item(item_id: str, body: QuizHistoryIn, uid: str = Depends(get_current_user)):
    return HistoryService.update_history_item(uid, item_id, body)
