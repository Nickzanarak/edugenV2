from typing import List, Dict
from datetime import datetime
from fastapi import HTTPException
from app.db.firebase import get_firestore_db, firestore
from app.models.history import QuizHistoryIn, RenameHistoryIn

class HistoryService:
    @staticmethod
    def save_history_item(uid: str, body: QuizHistoryIn) -> Dict:
        db = get_firestore_db()
        if not db:
            raise HTTPException(500, "Database not connected")
        try:
            data = {
                "fileName": body.file_name,
                "overview": body.overview,
                "keyPoints": body.key_points,
                "sections": body.sections,
                "dataPoints": body.data_points,
                "questions": body.questions,
                "answers": body.answers,
                "score": body.score,
                "content": body.content,
                "totalQuestions": len(body.questions),
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "qa_history": [q.model_dump() if hasattr(q, 'model_dump') else q.dict() for q in body.qa_history],
            }
            update_time, ref = db.collection("users").document(uid).collection("histories").add(data)
            return {"ok": True, "message": "History saved", "id": ref.id}
        except Exception as e:
            raise HTTPException(500, f"Save history failed: {e}")

    @staticmethod
    def get_history_list(uid: str) -> List[Dict]:
        db = get_firestore_db()
        if not db or not firestore:
            return []
        try:
            docs = db.collection("users").document(uid).collection("histories")\
                     .order_by("timestamp", direction=firestore.Query.DESCENDING)\
                     .limit(30).stream()
            results = []
            for d in docs:
                item = d.to_dict()
                item["id"] = d.id
                results.append(item)
            return results
        except Exception as e:
            print(f"[History] Get list error: {e}")
            return []

    @staticmethod
    def delete_history_item(uid: str, item_id: str) -> Dict:
        db = get_firestore_db()
        if not db:
            raise HTTPException(500, "Database not connected")
        try:
            db.collection("users").document(uid).collection("histories").document(item_id).delete()
            return {"ok": True}
        except Exception as e:
            raise HTTPException(500, f"Delete failed: {e}")

    @staticmethod
    def rename_history_item(uid: str, item_id: str, body: RenameHistoryIn) -> Dict:
        db = get_firestore_db()
        if not db:
            raise HTTPException(500, "Database not connected")
        try:
            ref = db.collection("users").document(uid).collection("histories").document(item_id)
            ref.update({"fileName": body.new_name})
            return {"ok": True}
        except Exception as e:
            raise HTTPException(500, f"Rename failed: {e}")

    @staticmethod
    def update_history_item(uid: str, item_id: str, body: QuizHistoryIn) -> Dict:
        db = get_firestore_db()
        if not db:
            raise HTTPException(500, "Database not connected")
        try:
            data = {
                "questions": body.questions,
                "answers": body.answers,
                "score": body.score,
                "totalQuestions": len(body.questions),
                "timestamp": datetime.utcnow().isoformat() + "Z"
            }
            if body.content:
                data["content"] = body.content
            if body.overview:
                data["overview"] = body.overview
            if body.key_points:
                data["keyPoints"] = body.key_points
            if body.sections:
                data["sections"] = body.sections
            if body.data_points:
                data["dataPoints"] = body.data_points
            
            if body.qa_history is not None:
                 data["qa_history"] = [q.model_dump() if hasattr(q, 'model_dump') else q.dict() for q in body.qa_history]

            db.collection("users").document(uid).collection("histories").document(item_id).update(data)
            return {"ok": True, "message": "History updated"}
        except Exception as e:
            raise HTTPException(500, f"Update history failed: {e}")
