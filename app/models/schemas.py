from pydantic import BaseModel
from typing import List, Dict, Optional

class ContextIn(BaseModel):
    context: str

class QuizIn(BaseModel):
    context: str
    n: int = 5
    exclude: Optional[List[str]] = None
    topics: Optional[List[str]] = None
    difficulty: Optional[str] = "medium"
    choices_count: Optional[int] = 4

class QAIn(BaseModel):
    context: str
    question: str

class SummarizeOut(BaseModel):
    overview: str
    key_points: List[str]
    sections: List[Dict[str, str]]
    data_points: List[Dict[str, str]]

class TopicsOut(BaseModel):
    topics: List[str]
