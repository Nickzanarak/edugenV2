from pydantic import BaseModel, Field
from typing import List, Optional

class QuestionIn(BaseModel):
    type: str = Field(pattern="^(mcq|tf)$")
    question: str
    choices: Optional[List[str]] = None
    answer: str
    explain: str = ""
    topic: str = ""

class QuestionOut(QuestionIn):
    id: int

class QuizCreateIn(BaseModel):
    title: str = "แบบทดสอบ"
    question_ids: Optional[List[int]] = None

class QuizOut(BaseModel):
    id: int
    title: str
    question_ids: List[int]
    created_at: str
    updated_at: str

class ExportOpts(BaseModel):
    shuffleChoices: bool = False
    showAnswers: bool = False
