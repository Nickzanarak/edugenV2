import json
from datetime import datetime
from fastapi import APIRouter, HTTPException, Path, Depends
from pydantic import BaseModel
from typing import Optional
from app.core.security import get_current_user
from app.db.firebase import get_firestore_db

router = APIRouter()

class SimpleNoteIn(BaseModel):
    content: str

class SimpleNoteOut(BaseModel):
    file_id: str
    content: str
    updated_at: Optional[str] = None

@router.get("/{file_id}", response_model=SimpleNoteOut)
def get_note(file_id: str = Path(...), uid: str = Depends(get_current_user)):
    db = get_firestore_db()
    if not db:
        raise HTTPException(500, "Database not connected")
    try:
        doc = db.collection("users").document(uid).collection("notes").document(file_id).get()
        if doc.exists:
            data = doc.to_dict()
            return {
                "file_id": file_id,
                "content": str(data.get("content", "")),
                "updated_at": data.get("updated_at"),
            }
        return {"file_id": file_id, "content": "", "updated_at": None}
    except Exception:
        return {"file_id": file_id, "content": "", "updated_at": None}

@router.put("/{file_id}", response_model=SimpleNoteOut)
def put_note(file_id: str = Path(...), body: SimpleNoteIn = None, uid: str = Depends(get_current_user)):
    if body is None or not isinstance(body.content, str):
        raise HTTPException(400, "content ว่างหรือรูปแบบไม่ถูกต้อง")
    db = get_firestore_db()
    if not db:
        raise HTTPException(500, "Database not connected")
    content = body.content.strip()
    updated_at = datetime.utcnow().isoformat() + "Z"
    payload = {"content": content, "updated_at": updated_at}
    db.collection("users").document(uid).collection("notes").document(file_id).set(payload)
    return {"file_id": file_id, **payload}
