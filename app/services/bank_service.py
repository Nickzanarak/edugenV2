from typing import List, Dict, Any
from datetime import datetime
from fastapi import HTTPException
from app.core.config import settings
from app.db.firebase import get_firestore_db
from app.utils.nlp import similar
from app.models.bank import QuestionIn, QuizCreateIn


CHOICE_LETTERS = ["ก", "ข", "ค", "ง", "จ", "ฉ"]


def _normalize_mcq_choices(raw: List[str]) -> List[str]:
    """เก็บตัวเลือกตามจำนวนจริง (4-6 ตัว) ไม่ตัดเหลือ 4"""
    ch = [str(c).strip() for c in (raw or []) if str(c).strip()]
    ch = ch[:6]                       # กันเกิน 6
    if len(ch) < 4:                   # กันน้อยกว่า 4
        ch = (ch + [""] * 4)[:4]
    return ch

def _get_bank_ref(uid: str):
    """Return Firestore reference: users/{uid}/bank (single doc with questions & quizzes arrays)."""
    db = get_firestore_db()
    if not db:
        raise HTTPException(500, "Database not connected")
    return db.collection("users").document(uid).collection("bank")


def _read_list(uid: str, kind: str) -> List[Dict[str, Any]]:
    """Read 'questions' or 'quizzes' array from Firestore."""
    ref = _get_bank_ref(uid)
    doc = ref.document(kind).get()
    if doc.exists:
        return doc.to_dict().get("items", [])
    return []


def _write_list(uid: str, kind: str, items: List[Dict[str, Any]]):
    """Write 'questions' or 'quizzes' array to Firestore."""
    ref = _get_bank_ref(uid)
    ref.document(kind).set({"items": items})


def _next_id(items: List[Dict[str, Any]]) -> int:
    mx = 0
    for it in items:
        try:
            mx = max(mx, int(it.get("id", 0)))
        except (ValueError, TypeError):
            pass
    return mx + 1


class BankService:
    @staticmethod
    def list_questions(uid: str) -> List[Dict]:
        return _read_list(uid, "questions")

    @staticmethod
    def create_question(uid: str, body: QuestionIn) -> Dict:
        qs = _read_list(uid, "questions")
        qtype = (body.type or "").lower()
        if qtype == "mcq":
            ch = _normalize_mcq_choices(body.choices or [])
            valid = CHOICE_LETTERS[:len(ch)]
            if body.answer not in valid:
                raise HTTPException(400, f"answer ต้องเป็น {'/'.join(valid)} สำหรับ MCQ")
            payload = {
                "id": _next_id(qs),
                "type": "mcq",
                "question": body.question.strip(),
                "choices": ch,
                "answer": body.answer.strip(),
                "explain": (body.explain or "").strip(),
                "topic": (body.topic or "").strip(),
            }
        else:
            ans = (body.answer or "").strip().lower()
            if ans not in ["true", "false", "จริง", "เท็จ"]:
                raise HTTPException(400, "answer ต้องเป็น true/false สำหรับ TF")
            payload = {
                "id": _next_id(qs),
                "type": "tf",
                "question": body.question.strip(),
                "choices": None,
                "answer": "true" if ans in ["true", "จริง"] else "false",
                "explain": (body.explain or "").strip(),
                "topic": (body.topic or "").strip(),
            }
        qs.append(payload)
        _write_list(uid, "questions", qs)
        return payload

    @staticmethod
    def update_question(uid: str, qid: int, body: QuestionIn) -> Dict:
        qs = _read_list(uid, "questions")
        for i, it in enumerate(qs):
            if int(it.get("id", -1)) == qid:
                qtype = (body.type or it.get("type", "mcq")).lower()
                if qtype == "mcq":
                    ch = _normalize_mcq_choices(body.choices or it.get("choices") or [])
                    ans = (body.answer or it.get("answer", "ก")).strip()
                    valid = CHOICE_LETTERS[:len(ch)]
                    if ans not in valid:
                        raise HTTPException(400, f"answer ต้องเป็น {'/'.join(valid)} สำหรับ MCQ")
                    qs[i] = {
                        "id": qid,
                        "type": "mcq",
                        "question": body.question.strip(),
                        "choices": ch,
                        "answer": ans,
                        "explain": (body.explain or "").strip(),
                        "topic": (body.topic or "").strip(),
                    }
                else:
                    ans = (body.answer or it.get("answer", "true")).strip().lower()
                    if ans not in ["true", "false", "จริง", "เท็จ"]:
                        raise HTTPException(400, "answer ต้องเป็น true/false สำหรับ TF")
                    qs[i] = {
                        "id": qid,
                        "type": "tf",
                        "question": body.question.strip(),
                        "choices": None,
                        "answer": "true" if ans in ["true", "จริง"] else "false",
                        "explain": (body.explain or "").strip(),
                        "topic": (body.topic or "").strip(),
                    }
                _write_list(uid, "questions", qs)
                return qs[i]
        raise HTTPException(404, "Question not found")

    @staticmethod
    def list_quizzes(uid: str) -> List[Dict]:
        return _read_list(uid, "quizzes")

    @staticmethod
    def create_quiz(uid: str, body: QuizCreateIn) -> Dict:
        quizzes = _read_list(uid, "quizzes")
        questions = _read_list(uid, "questions")
        valid_ids = set(int(q.get("id", -1)) for q in questions)
        ids_src = body.question_ids if body.question_ids is not None else []
        keep = [int(i) for i in ids_src if int(i) in valid_ids]
        now = datetime.utcnow().isoformat() + "Z"
        payload = {
            "id": _next_id(quizzes),
            "title": (body.title or "แบบทดสอบ").strip(),
            "question_ids": keep,
            "created_at": now,
            "updated_at": now,
        }
        quizzes.append(payload)
        _write_list(uid, "quizzes", quizzes)
        return payload

    @staticmethod
    def update_quiz(uid: str, quiz_id: int, body: QuizCreateIn) -> Dict:
        quizzes = _read_list(uid, "quizzes")
        questions = _read_list(uid, "questions")
        valid_ids = set(int(q.get("id", -1)) for q in questions)
        for i, qz in enumerate(quizzes):
            if int(qz.get("id", -1)) == quiz_id:
                title_src = body.title if body.title is not None else qz.get("title", "แบบทดสอบ")
                ids_src = body.question_ids if body.question_ids is not None else qz.get("question_ids", [])
                title = (title_src or "แบบทดสอบ").strip()
                ids = [int(x) for x in ids_src if int(x) in valid_ids]
                quizzes[i] = {
                    **qz,
                    "title": title,
                    "question_ids": ids,
                    "updated_at": datetime.utcnow().isoformat() + "Z",
                }
                _write_list(uid, "quizzes", quizzes)
                return quizzes[i]
        raise HTTPException(404, "Quiz not found")

    @staticmethod
    def delete_quiz(uid: str, quiz_id: int) -> Dict:
        quizzes = _read_list(uid, "quizzes")
        new_qz = [x for x in quizzes if int(x.get("id", -1)) != quiz_id]
        if len(new_qz) == len(quizzes):
            raise HTTPException(404, "Quiz not found")
        _write_list(uid, "quizzes", new_qz)
        return {"ok": True}

    @staticmethod
    def _question_texts_in_set(quiz: Dict, questions: List[Dict]) -> List[str]:
        q_by_id = {int(q.get("id", -1)): q for q in questions}
        texts: List[str] = []
        for qid in quiz.get("question_ids", []):
            q = q_by_id.get(int(qid))
            if q:
                text = str(q.get("question") or "").strip()
                if text:
                    texts.append(text)
        return texts

    @staticmethod
    def is_duplicate_in_set(uid: str, quiz_id: int, question_text: str) -> bool:
        quizzes = _read_list(uid, "quizzes")
        questions = _read_list(uid, "questions")
        quiz = next((q for q in quizzes if int(q.get("id", -1)) == quiz_id), None)
        if not quiz:
            raise HTTPException(404, "Quiz not found")
        new_text = (question_text or "").strip()
        if not new_text:
            return False
        for existing in BankService._question_texts_in_set(quiz, questions):
            if similar(new_text, existing) >= settings.NEAR_DUP_THRESHOLD:
                return True
        return False

    @staticmethod
    def add_question_to_set(uid: str, quiz_id: int, body: QuestionIn) -> Dict:
        if BankService.is_duplicate_in_set(uid, quiz_id, body.question):
            raise HTTPException(409, "ข้อนี้มีอยู่ในชุดนี้แล้ว")

        # ตรวจว่าชุดยังอยู่จริงก่อนสร้างข้อสอบ
        # (ถ้าสร้างก่อนแล้วหาชุดไม่เจอ จะได้ข้อสอบลอยค้างในคลังโดยไม่มีชุด)
        quizzes = _read_list(uid, "quizzes")
        if not any(int(qz.get("id", -1)) == quiz_id for qz in quizzes):
            raise HTTPException(404, "Quiz not found")

        created = BankService.create_question(uid, body)
        quizzes = _read_list(uid, "quizzes")

        for i, qz in enumerate(quizzes):
            if int(qz.get("id", -1)) == quiz_id:
                ids = [int(x) for x in qz.get("question_ids", [])]
                if int(created["id"]) not in ids:
                    ids.append(int(created["id"]))
                quizzes[i] = {
                    **qz,
                    "question_ids": ids,
                    "updated_at": datetime.utcnow().isoformat() + "Z",
                }
                _write_list(uid, "quizzes", quizzes)
                return created

        raise HTTPException(404, "Quiz not found")