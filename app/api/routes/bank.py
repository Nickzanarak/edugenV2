from fastapi import APIRouter, Depends
from typing import List
from app.core.security import get_current_user
from app.models.bank import QuestionIn, QuestionOut, QuizCreateIn, QuizOut
from app.services.bank_service import BankService

router = APIRouter()

@router.get("/questions", response_model=List[QuestionOut])
def bank_list_questions(uid: str = Depends(get_current_user)):
    return BankService.list_questions(uid)

@router.post("/questions", response_model=QuestionOut)
def bank_create_question(body: QuestionIn, uid: str = Depends(get_current_user)):
    return BankService.create_question(uid, body)

@router.patch("/questions/{qid}", response_model=QuestionOut)
def bank_update_question(qid: int, body: QuestionIn, uid: str = Depends(get_current_user)):
    return BankService.update_question(uid, qid, body)

@router.get("/quizzes", response_model=List[QuizOut])
def bank_list_quizzes(uid: str = Depends(get_current_user)):
    return BankService.list_quizzes(uid)

@router.post("/quizzes", response_model=QuizOut)
def bank_create_quiz(body: QuizCreateIn, uid: str = Depends(get_current_user)):
    return BankService.create_quiz(uid, body)

@router.patch("/quizzes/{quiz_id}", response_model=QuizOut)
def bank_update_quiz(quiz_id: int, body: QuizCreateIn, uid: str = Depends(get_current_user)):
    return BankService.update_quiz(uid, quiz_id, body)

@router.post("/quizzes/{quiz_id}/questions", response_model=QuestionOut)
def bank_add_question_to_set(quiz_id: int, body: QuestionIn, uid: str = Depends(get_current_user)):
    return BankService.add_question_to_set(uid, quiz_id, body)

@router.delete("/quizzes/{quiz_id}")
def bank_delete_quiz(quiz_id: int, uid: str = Depends(get_current_user)):
    return BankService.delete_quiz(uid, quiz_id)
