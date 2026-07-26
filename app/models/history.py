from pydantic import BaseModel
from typing import List, Dict, Any

class QAPair(BaseModel):
    question: str
    answer: str

class QuizHistoryIn(BaseModel):
    file_name: str
    overview: str = ""
    key_points: List[str] = []
    sections: List[Dict[str, str]] = [] 
    data_points: List[Dict[str, str]] = []
    questions: List[Dict[str, Any]]
    answers: Dict[str, str]
    score: int
    content: str = ""
    qa_history: List[QAPair] = [] 

class RenameHistoryIn(BaseModel):
    new_name: str
